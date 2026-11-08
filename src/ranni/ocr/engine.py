"""What an OCR engine looks like to the rest of Ranni."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ranni.types import Box


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
