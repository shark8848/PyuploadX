# Repository Guidelines

PyUploadX is an early-stage file and directory upload service: a FastAPI backend, a Python client SDK, and a React portal, backed by PostgreSQL, Redis, and Local/S3/MinIO storage. The authoritative product and architecture specification is `docs/docs_product-design.md` (in Chinese); read it before writing code.

## Project Structure & Module Organization

- `docs/docs_product-design.md` — product, API, deployment, and testing spec; planned module layout in §31.
- `docs/docs_assets_svg_*.svg` — architecture diagram sources, rendered to PNGs.
- `scripts/render_diagrams.py` — deterministic SVG→PNG renderer with freshness checking.
- `pyproject.toml` — 服务端包 `pyuploadx-server` 元数据（含 `docs`/`dev` extras、`upload-service` 命令与 pytest/ruff 配置）。
- `sdk/pyuploadx/pyproject.toml` — SDK 包 `pyuploadx` 元数据（第三方依赖仅 `httpx`）。
- `dist/` — 发布产物（wheel + sdist，全部历史版本保留，随仓库提交并推送两个远程）。
- `scripts/publish-pypi.sh` / `scripts/publish-pypi-server.sh` — SDK / 服务端 PyPI 发布脚本（凭据在 `config/pypi.env`，已 gitignore）。
- Planned modules (spec §31): `app/` (FastAPI service), `sdk/pyuploadx/` (SDK), `portal/` (React UI). Put new code under this layout and keep the spec in sync.

## Build, Test, and Development Commands

- `python -m venv .venv && source .venv/bin/activate` — create and activate the dev environment.
- `pip install -e ".[docs]"` — install documentation tooling (CairoSVG).
- `python scripts/render_diagrams.py --check` — fail if any PNG is missing or stale.
- `python scripts/render_diagrams.py --force` — regenerate all PNGs.
- Add `--source-dir docs --output-dir docs` when working with the current flat `docs/` layout.

## Coding Style & Naming Conventions

- Python: PEP 8, 4-space indentation, `snake_case` functions and variables, `UPPER_CASE` module constants, type hints, and `from __future__ import annotations`.
- Use dataclasses for configuration objects (see `scripts/render_diagrams.py`).
- No formatter or linter is configured; propose one before adding it.
- Design docs stay in Chinese; code identifiers, comments, and commits use English.

## Testing Guidelines

- Automated tests live under `tests/` (pytest; spec §29). SDK tests import `pyuploadx` from source via `tests/conftest.py`, since the SDK is packaged separately.
- Keep generated artifacts verifiable: `--check` must pass before committing diagram changes.

## Commit & Pull Request Guidelines

- No commit history exists yet; use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- One logical change per commit, imperative summary under 72 characters, body only to explain why.
- Pull requests: describe behavior changes, link the relevant spec section or task, add screenshots for UI changes, and keep PNGs in sync with edited SVGs.

## Security & Configuration

- Runtime configuration is YAML-driven (spec §19); keep secrets in environment variables, never in config files or commits.
- Storage backends are pluggable via the storage adapter layer (spec §15); keep credentials out of source control.

## Architecture Contracts

- **Database layer must use ORM mode.** All data access goes through SQLAlchemy 2 ORM models
  (`Mapped`/`mapped_column` in `app/db/models.py`) and the repository layer (`app/db/repositories/`).
  Do not write raw SQL strings for application DML. The only exception is the Postgres
  `ON CONFLICT` upsert, expressed via `sqlalchemy.dialects.postgresql.insert` inside a repository.
  Schema changes are delivered as Alembic migrations; never mutate tables with ad-hoc scripts.
- State machines, error codes, and endpoint shapes must match `docs/docs_product-design.md`
  (§12/§13/§14/§16); do not invent new status values or error codes.

## GitHub Projects Sync (PROJ-PYUPX-0001)

- Target board: https://github.com/users/shark8848/projects/4 (user-level Projects v2).
- Auth: Classic PAT with `project` scope, stored at `/tmp/gh_token` (chmod 600). Never commit
  tokens; fine-grained PATs cannot access user-level Projects v2.
- Run `bash scripts/sync-github-projects.sh <items.tsv>` to upsert tasks (idempotent by title).
- TSV rows: `title<TAB>status<TAB>priority`; status ∈ `未开始|进行中|已完成`,
  priority ∈ `P0|P1|P2` (optional). Update the TSV, sync, then commit both.

## Push / Remote Contract

- `origin` must use the SSH-over-443 endpoint because outbound TCP to github.com:22 is blocked
  in this environment. Canonical remote URL:
  `ssh://git@ssh.github.com:443/shark8848/PyuploadX.git`.
- Do not revert `origin` to `git@github.com:shark8848/PyuploadX.git`; pushes through port 22 hang.
  Verify before pushing with `git remote -v`.
- Push directly to `main` (direct-push workflow, no PR), matching the established workflow in
  `/home/ontolith/AGENTS.md`.
