"""One full scan of a screenshot: everything the overlay needs to draw.

    find relic tiles -> read text -> pick out the selected relic's effects -> score it
    -> remember the score on its tile -> recall scores for other tiles

Works on any image (file or live capture). Without an OCR engine it only finds tiles.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ranni.relics.builds import Score, Scorer
from ranni.relics.effect import Match
from ranni.relics.manager import EffectManager
from ranni.screen import Box
from ranni.screen.layout import line_below, union
from ranni.screen.ocr import OcrEngine, OcrLine, read_text
from ranni.screen.tiles import find_relics, find_selected
from ranni.screen.tracking import TileMemory


@dataclass
class FoundEffect:
    match: Match  # which effect, its official text, description
    box: Box | None  # where it is on screen (both lines for a wrapped effect)


@dataclass
class Scene:
    size: tuple[int, int]  # image width, height
    tiles: list[Box]  # relic tiles (the big icon in the details panel is not a tile)
    selected: int | None = None  # index into tiles of the glowing (selected) tile
    details_icon: Box | None = None  # the big relic icon in the details panel
    effects: list[FoundEffect] = field(default_factory=list)  # the selected relic's effects
    score: Score | None = None  # None: no details panel seen (or no OCR)
    tile_labels: dict[int, str] = field(default_factory=dict)  # tile index -> remembered score text
    lines: list[OcrLine] = field(default_factory=list)  # everything OCR read
    timings: dict[str, float] = field(default_factory=dict)  # step -> ms


def scan(image: np.ndarray, engine: OcrEngine | None, manager: EffectManager, scorer: Scorer | None,
         memory: TileMemory | None = None) -> Scene:
    timings = {}
    t = time.perf_counter()

    def lap(step: str) -> None:
        nonlocal t
        now = time.perf_counter()
        timings[step] = (now - t) * 1000
        t = now

    boxes = find_relics(image)
    lap("find tiles")

    lines = read_text(image, engine) if engine is not None else []
    lap("read text")

    effects = find_effects(lines, manager)
    icon = _details_icon(boxes, lines)
    tiles = [b for b in boxes if b != icon]
    selected = find_selected(image, tiles)
    score = scorer.score([e.match for e in effects]) if scorer and (icon or effects) else None
    lap("score")

    labels = {}
    if memory is not None:
        thumbs = memory.thumbnails(image, tiles)
        if selected is not None and score is not None:
            memory.remember(thumbs, selected, score_text(score))
        labels = memory.recall(thumbs)
    lap("track")

    timings["total"] = sum(timings.values())
    h, w = image.shape[:2]
    return Scene((w, h), tiles, selected, icon, effects, score, labels, lines, timings)


def find_effects(lines: list[OcrLine], manager: EffectManager) -> list[FoundEffect]:
    """
    Every effect in the OCR lines, with its box.
    First each line is looked up in effects.json, then deep_effects.json. If anything was only in deep_effects.json
    (a curse, or a deep-only effect), the relic is a deep relic, so all lines are read again in deep_effects.json only:
    some texts, like "Increased Maximum FP", are in both files and mean something different on a deep relic.
    """
    found = _find_effects(lines, manager, deep=None)
    if any(f.match.kind != "normal" for f in found):
        found = _find_effects(lines, manager, deep=True)
    return found


def _find_effects(lines: list[OcrLine], manager: EffectManager, deep: bool | None) -> list[FoundEffect]:
    """Every effect in the lines. A line that matches nothing is tried joined with the line below it (a wrapped effect)."""
    found: list[FoundEffect] = []
    used: set[int] = set()
    for i, line in enumerate(lines):
        if i in used:
            continue
        match = manager.match(line.text, deep)
        if match is not None:
            found.append(FoundEffect(match, line.box))
            continue
        j = line_below(lines, i)
        if j is not None and j not in used:
            match = manager.match(f"{line.text} {lines[j].text}", deep)
            if match is not None:
                found.append(FoundEffect(match, union(line.box, lines[j].box)))
                used.add(j)
    return found


def score_text(score: Score) -> str:
    """Short label for a tile: the score, or an X if every build forbids the relic."""
    if score.total is None:
        return "X"
    return f"{score.total:g}"


def summary(score: Score) -> str:
    """One line for the details panel, e.g. 'Score 12 (Ironeye bleed)'."""
    if score.total is None:
        return "Ruled out by every build" if score.ruled_out_by else "No builds"
    text = f"Score {score.total:g} ({score.build})"
    if score.ruled_out_by:
        text += f"  - ruled out: {', '.join(score.ruled_out_by)}"
    return text


def _details_icon(boxes: list[Box], lines: list[OcrLine]) -> Box | None:
    """The box with lines of text right next to it (the relic name and effects): the big
    icon in the details panel. Tiles in a grid don't have text beside them."""
    best, best_count = None, 1  # need at least 2 lines
    for box in boxes:
        x, y, w, h = box
        count = sum(1 for line in lines if line.box is not None
                    and x + w <= line.box[0] <= x + w + 0.6 * w
                    and y <= line.box[1] + line.box[3] / 2 <= y + 2.2 * h)
        if count > best_count:
            best, best_count = box, count
    return best
