"""A transparent, click-through, always-on-top window over the whole screen. Windows only.

UNTESTED: written on macOS.

tkinter (built into Python) draws on a full-screen canvas whose background color is made
transparent. Win32 window styles make it click-through and keep it out of the taskbar,
and SetWindowDisplayAffinity hides it from screen capture, so Ranni never sees (and
re-detects) its own boxes. Tk is not thread-safe: only call Overlay from the thread that
created it.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from ranni.scan import Scene, score_text, summary

TRANSPARENT = "#010101"  # this exact color becomes see-through
GREEN, YELLOW, WHITE, BLUE = "#50dc50", "#ffdc00", "#ffffff", "#3cb4ff"
GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x11
GA_ROOT = 2


class Overlay:
    def __init__(self, show_text_boxes: bool = True) -> None:
        import tkinter as tk

        self.show_text_boxes = show_text_boxes
        user32 = ctypes.windll.user32
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)  # primary monitor

        self.root = tk.Tk()
        self.root.overrideredirect(True)  # no title bar or border
        self.root.geometry(f"{width}x{height}+0+0")
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.root.update()

        user32.GetAncestor.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        # Needs Windows 10 2004+. Without it, captures include our own drawings.
        self.hidden_from_capture = bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))

    def clear(self) -> None:
        self.canvas.delete("all")

    def status(self, text: str) -> None:
        """A small line of text in the bottom-left corner."""
        self.canvas.delete("status")
        height = self.root.winfo_height()
        self._badge(text, 12, height - 40, 11, WHITE, tag="status")

    def show(self, scene: Scene) -> None:
        self.clear()
        s = scene.size[1] / 1080
        thin, thick = max(1, round(2 * s)), max(2, round(4 * s))
        font = round(16 * s)

        for i, (x, y, w, h) in enumerate(scene.tiles):
            selected = i == scene.selected
            color = YELLOW if selected else GREEN
            self.canvas.create_rectangle(x, y, x + w, y + h, outline=color, width=thick if selected else thin)
            label = scene.tile_labels.get(i)
            if selected and scene.score is not None:
                label = score_text(scene.score)
            if label is not None:
                self._badge(label, x + 4, y + 4, font, color)

        if self.show_text_boxes:
            for line in scene.lines:
                if line.box is not None:
                    x, y, w, h = line.box
                    self.canvas.create_rectangle(x, y, x + w, y + h, outline=BLUE, width=1)

        if scene.score is not None:
            for e in scene.effects:
                if e.box is None:
                    continue
                x, y, w, h = e.box
                pts = scene.score.points.get(e.match.official_text)
                text = f"{pts:+g}" if pts is not None else "ruled out"
                self._badge(text, x + w + round(10 * s), y, round(13 * s), GREEN if pts else WHITE)
            anchor = scene.details_icon or (scene.effects[0].box if scene.effects else None)
            if anchor is not None:
                x, y, w, h = anchor
                self._badge(summary(scene.score), x, max(0, y - round(40 * s)), round(14 * s), YELLOW)

        t = scene.timings
        self.status("Ranni live  |  " + "  ".join(f"{k} {v:.0f}ms" for k, v in t.items())
                    + "  |  Ctrl+Alt+Space: off   Ctrl+Alt+End: quit")

    def _badge(self, text: str, x: int, y: int, size: int, color: str, tag: str = "") -> None:
        item = self.canvas.create_text(x + 6, y + 4, text=text, anchor="nw", fill=color,
                                       font=("Segoe UI", max(8, size), "bold"), tags=tag)
        x0, y0, x1, y1 = self.canvas.bbox(item)
        box = self.canvas.create_rectangle(x0 - 6, y0 - 4, x1 + 6, y1 + 4, fill="#141414", outline="", tags=tag)
        self.canvas.tag_lower(box, item)
