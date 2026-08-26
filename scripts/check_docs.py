#!/usr/bin/env python3
"""Docs CI checks per docs_product-design.md section 35.5.

Verifies:
  - every SVG is safe: no external scripts, no local absolute file references
  - every markdown image reference resolves to an existing file under docs/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def check_svg(path: Path) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"<script\b", content, re.IGNORECASE):
        errors.append(f"{path}: SVG contains a <script> element (external scripts forbidden)")
    if re.search(r"xlink:href\s*=\s*\"(https?|file)://", content, re.IGNORECASE):
        errors.append(f"{path}: SVG references an external resource via xlink:href")
    if re.search(r"href\s*=\s*\"/[A-Za-z]:", content):
        errors.append(f"{path}: SVG contains a local absolute path reference")
    return errors


def check_markdown_refs(path: Path) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", content):
        reference = match.group(1).split()[0]
        if reference.startswith(("http://", "https://", "data:")):
            continue
        target = (DOCS / reference).resolve()
        if not target.exists():
            errors.append(f"{path}: image reference missing: {reference}")
    return errors


def main() -> int:
    errors: list[str] = []
    for svg in sorted((DOCS / "assets" / "svg").glob("*.svg")):
        errors.extend(check_svg(svg))
    for markdown in sorted(DOCS.glob("*.md")):
        errors.extend(check_markdown_refs(markdown))
    if errors:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("docs check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
