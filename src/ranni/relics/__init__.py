"""image -> boxes around every relic icon tile.

Relic tiles are squares with a thin straight border. No settings needed: sizes are
relative to the image height, so it works on any screen and resolution.

How it works (on a copy shrunk to WORK_HEIGHT):
1. Edges, then keep only straight horizontal / vertical runs (tile borders; relic art isn't straight).
2. For each tile size, score every position by how much of a square's border is covered
   by those lines, minus how much the lines run on past its corners (a box straddling two
   neighbouring tiles has borders running past its corners; a real tile's stop).
3. Keep the best non-overlapping squares that have no line through their middle (rejects
   blocks of several tiles) and have artwork inside (rejects empty frames).
"""

from __future__ import annotations

import cv2
import numpy as np

from ranni.types import Box

WORK_HEIGHT = 540  # detection runs at this height, whatever the screenshot size
MIN_SIZE, MAX_SIZE = 0.06, 0.30  # tile size as a fraction of image height
SIZE_STEP = 1.04  # try sizes 4% apart
MIN_SCORE = 0.45  # border coverage minus overshoot, 0..1
MAX_INNER_LINE = 0.4  # reject if a straight line crosses this much of the middle
MIN_ART = 0.04  # fraction of edge pixels needed inside a tile


def find_relics(image: np.ndarray) -> list[Box]:
    """Boxes (x, y, w, h) in the image's pixels, top-to-bottom then left-to-right."""
    f = WORK_HEIGHT / image.shape[0]
    small = cv2.resize(image, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 20, 60)
    horizontal, vertical = _straight_lines(edges)

    h, w = edges.shape
    sums = _RunningSums(horizontal, vertical, pad=int(0.1 * MAX_SIZE * h) + 2)

    candidates = []
    size = int(MIN_SIZE * h)
    while size <= MAX_SIZE * h:
        ys, xs, scores = _square_scores(sums, size, h - size, w - size)
        candidates += zip(scores.tolist(), xs.tolist(), ys.tolist(), [size] * len(xs))
        size = max(size + 1, int(size * SIZE_STEP))

    kept: list[tuple[int, int, int]] = []
    for _, x, y, s in sorted(candidates, reverse=True):
        if any(_overlaps((x, y, s), k) for k in kept):
            continue
        if _line_through_middle(horizontal, vertical, x, y, s) or not _has_art(edges, x, y, s):
            continue
        kept.append((x, y, s))

    boxes = [(round(x / f), round(y / f), round(s / f), round(s / f)) for x, y, s in kept]
    boxes.sort(key=lambda b: (b[1] // max(1, b[3] // 2), b[0]))
    return boxes


def _straight_lines(edges: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Float masks (0/1) of horizontal and vertical edge runs at least 3% of the height long."""
    length = max(3, int(0.03 * edges.shape[0]))
    thicken = np.ones((3, 3), np.uint8)
    horizontal = cv2.morphologyEx(edges, cv2.MORPH_OPEN, np.ones((1, length), np.uint8))
    vertical = cv2.morphologyEx(edges, cv2.MORPH_OPEN, np.ones((length, 1), np.uint8))
    return (cv2.dilate(horizontal, thicken).astype(np.float32) / 255,
            cv2.dilate(vertical, thicken).astype(np.float32) / 255)


class _RunningSums:
    """Line coverage of any horizontal/vertical run in O(1): running sums over zero-padded masks."""

    def __init__(self, horizontal: np.ndarray, vertical: np.ndarray, pad: int):
        self.pad = pad
        self.h = np.pad(np.pad(horizontal, pad).cumsum(axis=1, dtype=np.float32), ((0, 0), (1, 0)))
        self.v = np.pad(np.pad(vertical, pad).cumsum(axis=0, dtype=np.float32), ((1, 0), (0, 0)))

    def h_run(self, dy: int, dx: int, length: int, n: int, m: int) -> np.ndarray:
        """[y, x] = fraction of [x+dx, x+dx+length) on row y+dy covered by horizontal lines."""
        r, c = self.pad + dy, self.pad + dx
        return (self.h[r : r + n, c + length : c + length + m] - self.h[r : r + n, c : c + m]) / length

    def v_run(self, dy: int, dx: int, length: int, n: int, m: int) -> np.ndarray:
        """[y, x] = fraction of [y+dy, y+dy+length) on column x+dx covered by vertical lines."""
        r, c = self.pad + dy, self.pad + dx
        return (self.v[r + length : r + length + n, c : c + m] - self.v[r : r + n, c : c + m]) / length


def _square_scores(sums: _RunningSums, s: int, n: int, m: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Top-left corners (ys, xs) of squares of side s scoring >= MIN_SCORE, and their scores.

    score = border coverage - lines running on past the corners. Overshoot can only lower the
    score, so it's computed only where coverage alone passes.
    """
    H, V = sums.h_run, sums.v_run
    coverage = (H(0, 0, s, n, m) + H(s, 0, s, n, m) + V(0, 0, s, n, m) + V(0, s, s, n, m)) / 4
    ys, xs = np.nonzero(coverage >= MIN_SCORE)
    e = max(2, int(0.1 * s))  # how far past each corner to look for lines running on
    p = sums.pad

    def h_at(dy, dx):
        r, c = ys + p + dy, xs + p + dx
        return (sums.h[r, c + e] - sums.h[r, c]) / e

    def v_at(dy, dx):
        r, c = ys + p + dy, xs + p + dx
        return (sums.v[r + e, c] - sums.v[r, c]) / e

    overshoot = (h_at(0, -e) + h_at(0, s) + h_at(s, -e) + h_at(s, s)
                 + v_at(-e, 0) + v_at(s, 0) + v_at(-e, s) + v_at(s, s)) / 8
    scores = coverage[ys, xs] - overshoot
    ok = scores >= MIN_SCORE
    return ys[ok], xs[ok], scores[ok]


def _overlaps(a: tuple[int, int, int], b: tuple[int, int, int]) -> bool:
    (ax, ay, a_s), (bx, by, b_s) = a, b
    return abs(ax + a_s / 2 - bx - b_s / 2) < b_s / 2 and abs(ay + a_s / 2 - by - b_s / 2) < b_s / 2


def _line_through_middle(horizontal: np.ndarray, vertical: np.ndarray, x: int, y: int, s: int) -> bool:
    lo, hi, q1, q3 = int(0.1 * s), int(0.9 * s), s // 4, 3 * s // 4
    rows = horizontal[y + lo : y + hi, x + q1 : x + q3].mean(axis=1).max()
    cols = vertical[y + q1 : y + q3, x + lo : x + hi].mean(axis=0).max()
    return bool(max(rows, cols) > MAX_INNER_LINE)


def _has_art(edges: np.ndarray, x: int, y: int, s: int) -> bool:
    m = s // 5
    return bool((edges[y + m : y + s - m, x + m : x + s - m] > 0).mean() >= MIN_ART)


def find_selected(image: np.ndarray, boxes: list[Box]) -> int | None:
    """Index of the selected tile (the one with a glowing border), or None if none stands out.

    The selected tile's border band is much brighter than every other tile's (~2x on the samples).
    """
    if not boxes:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = [_border_brightness(gray, box) for box in boxes]
    order = sorted(range(len(boxes)), key=lambda i: brightness[i], reverse=True)
    best = order[0]
    runner_up = brightness[order[1]] if len(order) > 1 else 0.0
    if brightness[best] >= 40 and brightness[best] >= 1.6 * runner_up:
        return best
    return None


def _border_brightness(gray: np.ndarray, box: Box) -> float:
    x, y, w, h = box
    t = max(2, w // 25)
    region = gray[max(0, y - t) : y + h + t, max(0, x - t) : x + w + t].astype(np.float32)
    inner = gray[y + t : y + h - t, x + t : x + w - t].astype(np.float32)
    return float((region.sum() - inner.sum()) / max(1, region.size - inner.size))
