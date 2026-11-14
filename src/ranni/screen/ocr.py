"""read_text(image, engine): all text in an image, as lines with positions. OcrEngine: what an engine looks like."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

from ranni.screen import Box


@dataclass
class OcrLine:
    text: str
    y: float  # vertical center of the line in the image the engine was given
    box: Box | None = None  # x, y, w, h of the line in that image


class OcrEngine(Protocol):
    max_height: int  # largest width or height the engine accepts

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        """Read a grayscale image. One OcrLine per line of text, top to bottom."""
        ...


def read_text(image: np.ndarray, engine: OcrEngine) -> list[OcrLine]:
    """Every line of text in a BGR image, top to bottom, with boxes in the image's pixels."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    f = min(1.0, engine.max_height / max(gray.shape))  # shrink only if the engine requires it
    if f < 1.0:
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    lines = engine.recognize(gray)
    if f < 1.0:
        for line in lines:
            line.y /= f
            if line.box is not None:
                x, y, w, h = line.box
                line.box = (round(x / f), round(y / f), round(w / f), round(h / f))
    return lines


def default_engine() -> OcrEngine | None:
    """Windows OCR on Windows; no engine elsewhere."""
    if sys.platform != "win32":
        return None
    from ranni.screen.windows_ocr import WindowsOcr

    return WindowsOcr()
