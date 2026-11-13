"""Where OCR lines sit on screen: for effects that wrap onto a second line."""

from __future__ import annotations

from ranni.ocr.engine import OcrLine
from ranni.types import Box


def line_below(lines: list[OcrLine], i: int) -> int | None:
    """Index of the line directly below line i (a wrapped continuation), if any."""
    a = lines[i].box
    if a is None:
        return None
    best, best_gap = None, None
    for j, other in enumerate(lines):
        b = other.box
        if j == i or b is None:
            continue
        gap = b[1] - (a[1] + a[3])
        overlaps = b[0] < a[0] + a[2] and a[0] < b[0] + b[2]
        if overlaps and -a[3] / 2 < gap < a[3] and (best_gap is None or gap < best_gap):
            best, best_gap = j, gap
    return best


def union(a: Box | None, b: Box | None) -> Box | None:
    """The box around both."""
    if a is None or b is None:
        return a or b
    x, y = min(a[0], b[0]), min(a[1], b[1])
    return (x, y, max(a[0] + a[2], b[0] + b[2]) - x, max(a[1] + a[3], b[1] + b[3]) - y)
