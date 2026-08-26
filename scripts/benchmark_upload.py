#!/usr/bin/env python3
"""PyUploadX performance smoke tests (docs 29.7).

Scenarios:
  1. N concurrent small-file proxy uploads (default 100 files at 64 KiB).
  2. Optional large multipart file through the Python SDK (--large-mb).

Requires a running API instance (e.g. `make dev` or `docker compose up`).

Usage:
  python scripts/benchmark_upload.py --base-url http://localhost:8000 \
      --api-key dev-key --files 100 --concurrency 16
  python scripts/benchmark_upload.py --large-mb 64 --concurrency 8
"""

from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
import time
import uuid
from pathlib import Path

import httpx

API = "v1/files/upload"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("UPLOAD_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("UPLOAD_API_KEY", "dev-key"))
    parser.add_argument("--bucket", default="app-default")
    parser.add_argument("--files", type=int, default=100, help="small-file count (scenario 1)")
    parser.add_argument("--size", type=int, default=64 * 1024, help="small-file size in bytes")
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--large-mb", type=int, default=0, help="large multipart file size in MiB (scenario 2)")
    parser.add_argument("--part-size", type=int, default=8 * 1024 * 1024)
    return parser.parse_args()


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, round(len(ordered) * pct / 100) - 1))
    return ordered[index]


async def _upload_small(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    bucket: str,
    size: int,
) -> tuple[float, int]:
    payload = os.urandom(size)
    started = time.perf_counter()
    response = await client.post(
        f"{base_url}/{API}",
        headers={"X-API-Key": api_key},
        data={"bucket": bucket, "object_key": f"bench/{uuid.uuid4().hex}.bin"},
        files={"file": (f"f-{uuid.uuid4().hex}.bin", payload, "application/octet-stream")},
    )
    elapsed = time.perf_counter() - started
    return elapsed, response.status_code


async def _benchmark_small(args: argparse.Namespace) -> list[float]:
    semaphore = asyncio.Semaphore(args.concurrency)

    async def worker() -> float:
        async with semaphore:
            async with httpx.AsyncClient(timeout=120) as client:
                elapsed, status = await _upload_small(
                    client, args.base_url, args.api_key, args.bucket, args.size
                )
        if status != 200:
            raise SystemExit(f"FAILED: upload returned HTTP {status}")
        return elapsed

    started = time.perf_counter()
    samples = await asyncio.gather(*(worker() for _ in range(args.files)))
    total = time.perf_counter() - started
    _report("small proxy uploads", args.files, args.size, samples, total)
    return samples


def _benchmark_large(args: argparse.Namespace) -> None:
    from pyuploadx import UploadClient

    client = UploadClient(base_url=args.base_url, api_key=args.api_key, state_dir="/tmp/pyuploadx-bench")
    with tempfile.TemporaryDirectory(prefix="pyuploadx-bench-") as tmp:
        path = Path(tmp) / "large.bin"
        with path.open("wb") as handle:
            remaining = args.large_mb * 1024 * 1024
            while remaining > 0:
                chunk = os.urandom(min(4 * 1024 * 1024, remaining))
                handle.write(chunk)
                remaining -= len(chunk)
        started = time.perf_counter()
        result = client.upload_large_file(
            str(path),
            bucket=args.bucket,
            object_key=f"bench/{uuid.uuid4().hex}.bin",
            part_size=args.part_size,
            concurrency=args.concurrency,
            resume=False,
        )
        total = time.perf_counter() - started
    _report("multipart upload", 1, args.large_mb * 1024 * 1024, [total], total)
    print(f"  object_key={result.object_key}")


def _report(label: str, count: int, size: int, samples: list[float], total: float) -> None:
    total_bytes = count * size
    print(f"\n[{label}] files={count} size={size} bytes")
    print(f"  wall time      : {total:.2f}s")
    print(f"  throughput     : {count / total:.1f} files/s, {total_bytes / total / 1024 / 1024:.2f} MiB/s")
    print(f"  p50 / p95 / max: {_percentile(samples, 50) * 1000:.0f} / "
          f"{_percentile(samples, 95) * 1000:.0f} / {max(samples) * 1000:.0f} ms")


def main() -> None:
    args = _parse_args()
    asyncio.run(_benchmark_small(args))
    if args.large_mb > 0:
        _benchmark_large(args)
    print("\nBENCHMARK DONE")


if __name__ == "__main__":
    main()
