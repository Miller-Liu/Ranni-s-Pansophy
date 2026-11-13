"""read_text(image, engine): all text in an image, as lines with positions."""

from __future__ import annotations

import sys

import cv2
import numpy as np

from ranni.ocr.engine import OcrEngine, OcrLine


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
    from ranni.ocr.windows import WindowsOcr

    return WindowsOcr()
