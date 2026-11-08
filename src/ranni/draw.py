"""Draw a Scene onto a screenshot (for `ranni scan --debug`). The live overlay draws the same things."""

from __future__ import annotations

import cv2
import numpy as np

from ranni.scan import Scene, score_text, summary

GREEN, YELLOW, WHITE, BLUE, RED = (80, 220, 80), (0, 220, 255), (255, 255, 255), (255, 180, 60), (80, 80, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_scene(image: np.ndarray, scene: Scene) -> np.ndarray:
    out = image.copy()
    s = scene.size[1] / 1080  # scale line widths and text with resolution
    thin, thick = max(1, round(2 * s)), max(2, round(4 * s))

    for i, (x, y, w, h) in enumerate(scene.tiles):
        selected = i == scene.selected
        cv2.rectangle(out, (x, y), (x + w, y + h), YELLOW if selected else GREEN, thick if selected else thin)
        label = scene.tile_labels.get(i)
        if selected and scene.score is not None:
            label = score_text(scene.score)
        if label is not None:
            _badge(out, label, (x + 4, y + 4), 0.9 * s, YELLOW if selected else GREEN)

    for line in scene.lines:
        if line.box is not None:
            x, y, w, h = line.box
            cv2.rectangle(out, (x, y), (x + w, y + h), BLUE, 1)

    if scene.score is not None:
        for e in scene.effects:
            if e.box is None:
                continue
            x, y, w, h = e.box
            pts = scene.score.points.get(e.name)
            text = f"+{pts:g}" if pts is not None else "forbidden"
            _badge(out, text, (x + w + round(10 * s), y), 0.7 * s, GREEN if pts else WHITE)
        anchor = scene.details_icon or (scene.effects[0].box if scene.effects else None)
        if anchor is not None:
            x, y, w, h = anchor
            _badge(out, summary(scene.score), (x, max(0, y - round(40 * s))), 0.8 * s, YELLOW)
    return out


def _badge(img: np.ndarray, text: str, origin: tuple[int, int], scale: float, color) -> None:
    (tw, th), base = cv2.getTextSize(text, FONT, scale, max(1, round(2 * scale)))
    x, y = origin
    cv2.rectangle(img, (x, y), (x + tw + 8, y + th + base + 8), (20, 20, 20), -1)
    cv2.putText(img, text, (x + 4, y + th + 4), FONT, scale, color, max(1, round(2 * scale)), cv2.LINE_AA)
