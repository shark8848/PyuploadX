#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import cairosvg


@dataclass(frozen=True)
class RenderConfig:
    source_dir: Path
    output_dir: Path
    output_width: int
    force: bool
    check: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def render_svg(
    source: Path,
    destination: Path,
    output_width: int,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_suffix(".png.tmp")

    cairosvg.svg2png(
        url=str(source),
        write_to=str(temporary),
        output_width=output_width,
    )

    temporary.replace(destination)


def png_is_stale(source: Path, destination: Path) -> bool:
    if not destination.exists():
        return True

    return source.stat().st_mtime_ns > destination.stat().st_mtime_ns


def render_all(config: RenderConfig) -> int:
    svg_files = sorted(config.source_dir.glob("*.svg"))

    if not svg_files:
        print(
            f"No SVG files found in {config.source_dir}",
            file=sys.stderr,
        )
        return 1

    stale_files: list[tuple[Path, Path]] = []

    for source in svg_files:
        destination = config.output_dir / f"{source.stem}.png"

        if config.force or png_is_stale(source, destination):
            stale_files.append((source, destination))

    if config.check:
        if stale_files:
            print("Generated PNG diagrams are missing or stale:")

            for source, destination in stale_files:
                print(f"- {source} -> {destination}")

            return 1

        print("All generated diagrams are up to date.")
        return 0

    for source, destination in stale_files:
        print(f"Rendering {source} -> {destination}")

        render_svg(
            source=source,
            destination=destination,
            output_width=config.output_width,
        )

        print(
            "  source_sha256="
            f"{sha256_file(source)}"
        )

    print(
        f"Rendered {len(stale_files)} diagram(s); "
        f"{len(svg_files) - len(stale_files)} unchanged."
    )

    return 0


def parse_args() -> RenderConfig:
    parser = argparse.ArgumentParser(
        description="Render documentation SVG diagrams to PNG.",
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("docs/assets/svg"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/assets/png"),
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1800,
    )
    parser.add_argument(
        "--force",
        action="store_true",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if any PNG is missing or older than its SVG.",
    )

    args = parser.parse_args()

    if args.width <= 0:
        parser.error("--width must be greater than zero")

    return RenderConfig(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        output_width=args.width,
        force=args.force,
        check=args.check,
    )


def main() -> int:
    return render_all(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())