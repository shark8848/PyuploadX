#!/usr/bin/env python3
"""End-to-end smoke test for a deployed PyUploadX stack (10.88.155.31)."""

from __future__ import annotations

import hashlib
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sdk"))
from pyuploadx import Client
from pyuploadx.exceptions import UploadClientError

BASE = os.environ.get("PYUPX_BASE", "http://10.88.155.31:8060")
PORTAL = os.environ.get("PYUPX_PORTAL", "http://10.88.155.31:5173")
MINIO = os.environ.get("PYUPX_MINIO", "http://10.88.155.31:19000")
API_KEY = os.environ.get("PYUPX_API_KEY", "1qaz2wsx3edc")

passed: list[str] = []
failed: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}  {detail}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    run_id = str(int(time.time()))
    small_name = f"smoke-{run_id}-small.bin"
    big_name = f"smoke-{run_id}-big.bin"
    dir_prefix = f"smoke-{run_id}-dir"
    print("== 1. HTTP 基础探测 ==")
    with httpx.Client(timeout=20.0, follow_redirects=True) as http:
        r = http.get(f"{BASE}/healthz")
        check("API /healthz -> 200", r.status_code == 200, f"got {r.status_code}")

        r = http.get(f"{PORTAL}/")
        check("Portal / -> 200 HTML", r.status_code == 200 and "text/html" in r.headers.get("content-type", ""),
              f"got {r.status_code} ct={r.headers.get('content-type')}")

        r = http.get(f"{MINIO}/minio/health/live")
        check("MinIO(HAProxy) /minio/health/live -> 200", r.status_code == 200, f"got {r.status_code}")

        r = http.get(f"{PORTAL}/v1/files?limit=1", headers={"X-API-Key": API_KEY})
        ok = r.status_code == 200 and r.json().get("total", -1) >= 0
        check("Portal 代理链路带 key -> 200 JSON", ok, f"got {r.status_code} {r.text[:120]}")

        r = http.get(f"{BASE}/v1/files?limit=1", headers={"X-API-Key": "wrong-key"})
        check("错误 key -> 401", r.status_code == 401, f"got {r.status_code}")

    print("== 2. SDK 配置与鉴权 ==")
    with Client(base_url=BASE, api_key=API_KEY) as client:
        cfg = httpx.get(f"{BASE}/v1/client-config", headers={"X-API-Key": API_KEY}).json()
        bucket = cfg.get("storage", {}).get("default_bucket", "app-default")
        version = cfg.get("service", {}).get("version", "?")
        check(f"client-config 读取成功 (version={version})", bool(version), str(cfg)[:200])
        check(f"默认桶可用: {bucket}", bool(bucket), str(bucket))
        print(f"  INFO  默认桶={bucket} 版本={version}")

        page = client.list_files(limit=5)
        check("list_files 鉴权通过", page.get("total", -1) >= 0, str(page)[:200])

        # 清理历史残留（幂等）
        stale = client.list_files(bucket=bucket, prefix="smoke-", limit=200)
        for item in stale["items"]:
            try:
                client.delete(item["id"])
            except UploadClientError:
                pass

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # --- 小文件直传 ---
            small = td / small_name
            small.write_bytes(bytes(random.Random(42).randrange(256) for _ in range(64 * 1024)))
            small_sha = sha256(small)
            info = client.upload(str(small), bucket=bucket)
            check("小文件 upload_file", info.original_filename == small_name and info.size_bytes == small.stat().st_size,
                  str(info)[:200])
            print(f"  INFO  file_id={info.id} object_key={info.object_key}")

            got = client.get_file(info.id)
            check("get_file 回读", got.id == info.id and got.status == "active", str(got)[:200])

            dl = client.download(info.id, str(td / "dl-small.bin"))
            check("download 内容一致", sha256(dl) == small_sha, f"{sha256(dl)} != {small_sha}")

            url = client.get_download_url(info.id)
            check("presign-download 生成 URL", bool(url), str(url))
            if url:
                dl2 = client.download_from_url(url, str(td / "dl-small-presigned.bin"))
                check("download_from_url 内容一致", sha256(dl2) == small_sha, f"{sha256(dl2)} != {small_sha}")
                name = client.filename_from_url(url)
                check("filename_from_url(预签名URL)", name == small_name, f"got {name!r}")

            api_url = f"{BASE}/v1/files/{info.id}/download"
            name = client.filename_from_url(api_url)
            check("filename_from_url(API下载URL) -> 原始文件名", name == small_name, f"got {name!r}")

            lifecycle = client.get_lifecycle(info.id)
            check("get_lifecycle 返回对象", isinstance(lifecycle, dict), str(lifecycle)[:200])

            # --- 大文件分片上传（>=8MB -> multipart）---
            big = td / big_name
            big.write_bytes(bytes(random.Random(7).randrange(256) for _ in range(25 * 1024 * 1024)))
            big_sha = sha256(big)
            info2 = client.upload(str(big), bucket=bucket)
            check("大文件 upload_large_file(multipart)", info2.size_bytes == big.stat().st_size, str(info2)[:200])
            dlb = client.download(info2.id, str(td / "dl-big.bin"), concurrency=4)
            check("大文件并行 download 内容一致", sha256(dlb) == big_sha, f"{sha256(dlb)} != {big_sha}")

            # --- 目录上传 ---
            src_dir = td / "srcdir"
            (src_dir / "sub").mkdir(parents=True)
            (src_dir / "a.txt").write_text("alpha")
            (src_dir / "sub" / "b.txt").write_text("beta")
            job = client.upload(str(src_dir), bucket=bucket, destination_prefix=dir_prefix)
            job_id = job.id
            for _ in range(60):
                if job.status == "completed":
                    break
                time.sleep(1)
                job = client.get_directory_job(job_id)
            check(f"目录 upload_directory 完成 (status={job.status})",
                  job.status == "completed" and job.uploaded_files >= 2,
                  f"status={job.status} uploaded={job.uploaded_files} failed={job.failed_files}")

            # --- 列表与删除 ---
            listing = client.list_files(bucket=bucket, prefix="smoke-", limit=100)
            keys = {item["object_key"] for item in listing["items"]}
            check("list_files 可见上传对象", info.object_key in keys and info2.object_key in keys, str(listing)[:200])

            client.delete(info.id)
            client.delete(info2.id)
            try:
                client.get_file(info.id)
                check("delete 后 get_file 报错", False, "file still exists")
            except UploadClientError:
                check("delete 后 get_file 404/错误", True)

            # 目录对象清理（尽力而为）
            for item in listing["items"]:
                if item["object_key"].startswith(f"{dir_prefix}/"):
                    try:
                        client.delete(item["id"])
                    except UploadClientError:
                        pass

    print(f"\n== 结果: {len(passed)} 通过, {len(failed)} 失败 ==")
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
