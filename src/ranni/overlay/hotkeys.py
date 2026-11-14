"""Global hotkeys via the Win32 API. Windows only.

UNTESTED: written on macOS.

One background thread registers the hotkeys and waits in GetMessageW, which sleeps until
Windows delivers a message, so it uses no CPU while waiting. Registering, unregistering
and receiving WM_HOTKEY must all happen on that same thread.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
VK_SPACE, VK_END = 0x20, 0x23
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012


class Hotkeys(threading.Thread):
    def __init__(self, bindings: list[tuple[int, int, Callable[[], None]]]):
        """bindings: (modifiers, virtual key, callback). Callbacks run on the hotkey thread."""
        super().__init__(daemon=True, name="hotkeys")
        self.bindings = bindings
        self.errors: list[str] = []
        self._thread_id = 0
        self._ready = threading.Event()

    def start(self) -> None:
        super().start()
        self._ready.wait(2)

    def run(self) -> None:
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered = []
        for i, (mods, vk, _) in enumerate(self.bindings, start=1):
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                registered.append(i)
            else:
                self.errors.append(f"hotkey #{i} is already used by another program")
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and 1 <= msg.wParam <= len(self.bindings):
                    self.bindings[msg.wParam - 1][2]()
        finally:
            for i in registered:
                user32.UnregisterHotKey(None, i)

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
