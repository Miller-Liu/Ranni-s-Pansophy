"""Screen -> image (BGR numpy array) of the primary monitor.

UNTESTED: written on macOS.

dxcam (DXGI Desktop Duplication) is the fastest: it copies the frame the GPU already
composed, a few ms per grab. mss (GDI) is the fallback: slower (~20-40 ms at 1440p) but
works everywhere. Create the capture on the thread that will use it.
"""

from __future__ import annotations

import time

import numpy as np


class DxcamCapture:
    name = "dxcam"

    def __init__(self) -> None:
        import dxcam  # pyright: ignore[reportMissingImports]  (Windows only: not installed on the Mac)

        self._camera = dxcam.create(output_color="BGR")

    def grab(self) -> np.ndarray:
        # new_frame_only=False: if the screen hasn't changed, return the last frame instead of None.
        for _ in range(50):
            frame = self._camera.grab(new_frame_only=False)
            if frame is not None:
                return frame
            time.sleep(0.01)  # the very first grab can take a moment
        raise RuntimeError("dxcam returned no frame")

    def close(self) -> None:
        self._camera.release()


class MssCapture:
    name = "mss"

    def __init__(self) -> None:
        import mss  # pyright: ignore[reportMissingImports]  (Windows only: not installed on the Mac)

        self._mss = mss.mss()
        self._monitor = self._mss.monitors[1]  # primary monitor

    def grab(self) -> np.ndarray:
        shot = self._mss.grab(self._monitor)
        return np.asarray(shot)[:, :, :3].copy()  # BGRA -> BGR

    def close(self) -> None:
        self._mss.close()


def open_capture(kind: str = "auto"):
    """kind: "auto" (dxcam, falling back to mss), "dxcam" or "mss"."""
    if kind in ("auto", "dxcam"):
        try:
            return DxcamCapture()
        except Exception as error:
            if kind == "dxcam":
                raise
            print(f"dxcam unavailable ({error}); using mss")
    return MssCapture()
