"""Remember which tile showed which score, so scores stay on tiles as you move around.

When a relic is selected and scored, Ranni remembers that tile by
  - what it looks like (a tiny thumbnail of its artwork), and
  - what its neighbours look like (the tiles just before and after it, in reading order).

On later scans, a tile gets the remembered score if it looks the same AND at least one of
its neighbours matches too. Neighbours make it work for identical-looking relics: scrolling
keeps neighbours together, and selling a relic only disturbs the tiles right next to it.
If two memories with different scores fit the same tile, it shows nothing rather than guess.

Memory lasts for this session only.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ranni.screen import Box

THUMB = 12  # thumbnail size (px)
MAX_DIFF = 10.0  # mean brightness difference (0-255) for two thumbnails to count as the same


@dataclass
class _Memory:
    thumb: np.ndarray
    before: np.ndarray | None
    after: np.ndarray | None
    label: str


class TileMemory:
    def __init__(self) -> None:
        self.memories: list[_Memory] = []

    def thumbnails(self, image: np.ndarray, tiles: list[Box]) -> list[np.ndarray]:
        """A small brightness-normalized picture of the middle of each tile (skips the border glow)."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        out = []
        for x, y, w, h in tiles:
            m = w // 4
            inner = gray[y + m : y + h - m, x + m : x + w - m]
            t = cv2.resize(inner, (THUMB, THUMB), interpolation=cv2.INTER_AREA).astype(np.float32)
            out.append(t - t.mean())
        return out

    def remember(self, thumbs: list[np.ndarray], index: int, label: str) -> None:
        new = _Memory(thumbs[index], _at(thumbs, index - 1), _at(thumbs, index + 1), label)
        # Same tile seen again (same look, same neighbours): update instead of adding.
        self.memories = [m for m in self.memories
                         if not (_same(m.thumb, new.thumb) and _same(m.before, new.before) and _same(m.after, new.after))]
        self.memories.append(new)

    def recall(self, thumbs: list[np.ndarray]) -> dict[int, str]:
        """tile index -> remembered label, for tiles that confidently match a memory."""
        labels = {}
        for i, thumb in enumerate(thumbs):
            before, after = _at(thumbs, i - 1), _at(thumbs, i + 1)
            fits = [(_same(m.before, before) + _same(m.after, after), m.label)
                    for m in self.memories if _same(m.thumb, thumb)]
            fits = [(n, label) for n, label in fits if n >= 1]
            if not fits:
                continue
            best = max(n for n, _ in fits)
            candidates = {label for n, label in fits if n == best}
            if len(candidates) == 1:
                labels[i] = candidates.pop()
        return labels


def _at(items: list[np.ndarray], i: int) -> np.ndarray | None:
    return items[i] if 0 <= i < len(items) else None


def _same(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return float(np.abs(a - b).mean()) <= MAX_DIFF
