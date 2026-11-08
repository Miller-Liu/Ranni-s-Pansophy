"""OCR lines -> the known effects they show.

Each line is snapped to the closest known effect name (fuzzy, to absorb OCR mistakes).
Numbers must match exactly, so "Faith +2" is never taken for "Faith +1". A line that
doesn't match on its own is tried joined with the line below it (a wrapped effect).
Lines that match nothing (menus, prices, the relic's name) are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process, utils

from ranni.ocr.engine import OcrLine
from ranni.types import Box

MIN_SIMILARITY = 85  # 0-100


@dataclass
class FoundEffect:
    name: str  # known effect name
    text: str  # what OCR read
    box: Box | None  # where it is on screen (both lines for a wrapped effect)


def match_effects(lines: list[OcrLine], known: list[str]) -> list[FoundEffect]:
    found = []
    used: set[int] = set()
    for i, line in enumerate(lines):
        if i in used:
            continue
        name = snap(line.text, known)
        if name is not None:
            found.append(FoundEffect(name, line.text, line.box))
            continue
        j = _line_below(lines, i)
        if j is not None and j not in used:
            joined = f"{line.text} {lines[j].text}"
            name = snap(joined, known)
            if name is not None:
                found.append(FoundEffect(name, joined, _union(line.box, lines[j].box)))
                used.add(j)
    return found


def snap(text: str, known: list[str]) -> str | None:
    """The known effect closest to `text`, or None if nothing is similar enough."""
    if not text or not known:
        return None
    for candidate in _variants(text):
        match = process.extractOne(candidate, known, scorer=fuzz.ratio, processor=utils.default_process,
                                   score_cutoff=MIN_SIMILARITY)
        if match is not None and _numbers(match[0]) == _numbers(candidate):
            return match[0]
    return None


def _variants(text: str) -> list[str]:
    """The text, and the text without a short leading token (OCR often reads the effect's
    little icon as a stray character or two)."""
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 2 and not parts[0].isdigit():
        return [text, parts[1]]
    return [text]


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+", text)


def _line_below(lines: list[OcrLine], i: int) -> int | None:
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


def _union(a: Box | None, b: Box | None) -> Box | None:
    if a is None or b is None:
        return a or b
    x, y = min(a[0], b[0]), min(a[1], b[1])
    return (x, y, max(a[0] + a[2], b[0] + b[2]) - x, max(a[1] + a[3], b[1] + b[3]) - y)
