"""Live mode: hotkey -> capture -> scan -> overlay. Windows only.

UNTESTED: written on macOS.

Threads:
  main      the overlay (Tk must stay on one thread); checks for new results every 50 ms
  hotkeys   waits for Ctrl+Alt+Space (live on/off) and Ctrl+Alt+End (quit); no CPU while waiting
  scanner   while live: capture -> scan -> hand the result to the overlay, a few times a second;
            while not live it just waits, so Ranni sits at ~0% CPU
"""

from __future__ import annotations

import ctypes
import queue
import signal
import threading
import time
import traceback
from pathlib import Path

from ranni.capture import open_capture
from ranni.hotkey import MOD_ALT, MOD_CONTROL, VK_END, VK_SPACE, Hotkeys
from ranni.ocr import default_engine
from ranni.overlay import Overlay
from ranni.scan import scan
from ranni.scoring import Build
from ranni.tracking import TileMemory


def run(builds: list[Build], capture_kind: str = "auto", interval: float = 0.25, show_text_boxes: bool = True) -> None:
    _make_dpi_aware()  # before any window or capture, so all coordinates are real pixels
    overlay = Overlay(show_text_boxes)
    if not overlay.hidden_from_capture:
        print("warning: this Windows version can't hide the overlay from capture; "
              "Ranni may detect its own boxes")

    events: queue.Queue[str] = queue.Queue()
    results: queue.Queue = queue.Queue()
    live, stop = threading.Event(), threading.Event()

    hotkeys = Hotkeys([
        (MOD_CONTROL | MOD_ALT, VK_SPACE, lambda: events.put("toggle")),
        (MOD_CONTROL | MOD_ALT, VK_END, lambda: events.put("quit")),
    ])
    hotkeys.start()
    for error in hotkeys.errors:
        print("warning:", error)
    scanner = threading.Thread(target=_scan_loop, args=(builds, capture_kind, interval, live, stop, results),
                               daemon=True, name="scanner")
    scanner.start()
    signal.signal(signal.SIGINT, lambda *_: events.put("quit"))  # Ctrl+C in the console

    def tick() -> None:
        while not events.empty():
            event = events.get()
            if event == "quit":
                overlay.root.quit()
                return
            if live.is_set():
                live.clear()
                overlay.clear()
                print("live: off")
            else:
                live.set()
                overlay.status("Ranni live  |  starting...")
                print("live: on")
        latest = None
        while not results.empty():
            latest = results.get()
        if latest is not None and live.is_set():
            if isinstance(latest, str):
                overlay.status(latest)
            else:
                overlay.show(latest)
        overlay.root.after(50 if live.is_set() else 200, tick)

    print("Ranni is running.  Ctrl+Alt+Space: live overlay on/off   Ctrl+Alt+End (or Ctrl+C): quit")
    overlay.root.after(50, tick)
    try:
        overlay.root.mainloop()
    finally:
        stop.set()
        live.set()  # wake the scanner so it can exit
        hotkeys.stop()
        scanner.join(timeout=3)
        overlay.root.destroy()


def _scan_loop(builds, capture_kind, interval, live, stop, results) -> None:
    capture = engine = None
    memory = TileMemory()
    try:
        while not stop.is_set():
            if not live.wait(timeout=0.5) or stop.is_set():
                continue
            started = time.perf_counter()
            try:
                if capture is None:
                    capture = open_capture(capture_kind)
                    print(f"capture: {capture.name}")
                    try:
                        engine = default_engine()
                    except Exception as error:
                        print(f"OCR unavailable ({error}); showing tiles only")
                frame = capture.grab()
                grabbed = time.perf_counter()
                scene = scan(frame, engine, builds, memory)
                scene.timings = {"capture": (grabbed - started) * 1000, **scene.timings}
                results.put(scene)
            except Exception as error:
                traceback.print_exc()
                results.put(f"Ranni error: {error}  (details in the console)")
                time.sleep(1)
            time.sleep(max(0.0, interval - (time.perf_counter() - started)))
    finally:
        if capture is not None:
            capture.close()


def _make_dpi_aware() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2
    except Exception:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
