"""Windows OCR engine (Windows.Media.Ocr, via pywinrt 3.x). Windows only.

UNTESTED: written on macOS. Check it with `ranni scan <screenshot>` on Windows.
Uses the English OCR language pack, or else the user's profile languages
(Settings > Time & language > Language & region).
"""

from __future__ import annotations

import asyncio

import cv2
import numpy as np
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter

from ranni.ocr.engine import OcrLine


class WindowsOcr:
    """Create and use it on the same thread."""

    def __init__(self, language: str = "en-US"):
        try:
            from winrt.runtime import ApartmentType, init_apartment

            init_apartment(ApartmentType.MULTI_THREADED)  # needed on threads pywinrt didn't set up
        except Exception:
            pass  # already initialized on this thread
        engine = OcrEngine.try_create_from_language(Language(language))
        if engine is None:
            engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("Windows OCR: no OCR language pack installed")
        self._engine = engine
        self.max_height = int(OcrEngine.max_image_dimension)

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        bgra = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
        h, w = bgra.shape[:2]
        writer = DataWriter()
        writer.write_bytes(bgra.tobytes())
        bitmap = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h)
        operation = self._engine.recognize_async(bitmap)
        try:
            result = operation.get()  # blocks until done (fine on a worker thread)
        except Exception:
            result = asyncio.run(_wait(operation))  # .get() refuses on some UI threads

        lines = []
        for line in result.lines:
            rects = [word.bounding_rect for word in line.words]
            if rects:
                left, top = min(r.x for r in rects), min(r.y for r in rects)
                right = max(r.x + r.width for r in rects)
                bottom = max(r.y + r.height for r in rects)
                box = (round(left), round(top), round(right - left), round(bottom - top))
                lines.append(OcrLine(line.text, (top + bottom) / 2, box))
        return lines


async def _wait(operation):
    return await operation
