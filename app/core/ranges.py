"""HTTP Range header parsing for ranged downloads (RFC 7233, single range)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import ApiError


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_byte_range(header: str | None, size: int) -> ByteRange | None:
    """Parse a single ``bytes=start-end`` Range header against ``size``.

    Returns None when the header is absent (serve the full body). Supports
    open-ended (``bytes=N-``) and suffix (``bytes=-N``) ranges. Raises
    ``RANGE_NOT_SATISFIABLE`` (416) for malformed or unsatisfiable ranges.
    """
    if header is None:
        return None
    if not header.startswith("bytes="):
        raise ApiError("RANGE_NOT_SATISFIABLE", f"Unsupported range spec: {header}", status_code=416)
    spec = header[len("bytes="):].strip()
    if "," in spec:
        raise ApiError("RANGE_NOT_SATISFIABLE", "Multi-range requests are not supported", status_code=416)
    if "-" not in spec:
        raise ApiError("RANGE_NOT_SATISFIABLE", f"Invalid range spec: {header}", status_code=416)
    start_text, end_text = spec.split("-", 1)
    try:
        if start_text == "":
            suffix = int(end_text)
            if suffix <= 0:
                raise ValueError
            start = max(0, size - suffix)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
    except ValueError:
        raise ApiError("RANGE_NOT_SATISFIABLE", f"Invalid range spec: {header}", status_code=416) from None
    if size <= 0 or start >= size or end < start:
        raise ApiError("RANGE_NOT_SATISFIABLE", f"Range not satisfiable: {header}", status_code=416)
    return ByteRange(start=start, end=min(end, size - 1))
