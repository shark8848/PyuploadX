# Repository Guidelines

PyUploadX is an early-stage file and directory upload service: a FastAPI backend, a Python client SDK, and a React portal, backed by PostgreSQL, Redis, and Local/S3/MinIO storage. The authoritative product and architecture specification is `docs/docs_product-design.md` (in Chinese); read it before writing code.

## Project Structure & Module Organization

- `docs/docs_product-design.md` — product, API, deployment, and testing spec; planned module layout in §31.
- `docs/docs_assets_svg_*.svg` — architecture diagram sources, rendered to PNGs.
- `scripts/render_diagrams.py` — deterministic SVG→PNG renderer with freshness checking.
- `pyproject.toml` — Python metadata; currently only the `docs` extra (`CairoSVG`).
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

- No automated tests exist yet; follow the test plan in spec §29 (pytest expected for backend and SDK) when adding the first suites.
- Keep generated artifacts verifiable: `--check` must pass before committing diagram changes.

## Commit & Pull Request Guidelines

- No commit history exists yet; use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- One logical change per commit, imperative summary under 72 characters, body only to explain why.
- Pull requests: describe behavior changes, link the relevant spec section or task, add screenshots for UI changes, and keep PNGs in sync with edited SVGs.

## Security & Configuration

- Runtime configuration is YAML-driven (spec §19); keep secrets in environment variables, never in config files or commits.
- Storage backends are pluggable via the storage adapter layer (spec §15); keep credentials out of source control.
