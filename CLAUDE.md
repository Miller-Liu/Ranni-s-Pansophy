# Ranni — Project Context

## What this is

**Ranni** is a lightweight background helper for the game *Elden Ring Nightreign* (Windows, Steam). The goal: when the user presses a hotkey on a relic screen, it captures one frame, reads the selected relic's effects, applies the user's keep/sell rules, and shows the verdict as a click-through overlay.

It is a **passive reader**: it never reads or writes game memory and never sends inputs to the game. The user does the actual selling by hand. Keep it that way. The game runs Easy Anti-Cheat, and screen capture plus a hotkey is in the same category as OBS or Discord overlays, while automated input is not.

How the game shows relics: relic **tiles** show icons only; the effects appear only in one **details panel** (relic name + up to 3 effects, each with a small icon in front; wrapped effects are indented; an empty slot shows `-`) for the selected relic. Screens seen so far: Relic Rites (inventory grid), Small Jar Bazaar (purchase popup), End Screen (expedition rewards).

## Hard constraints and priorities

- **Runtime efficiency is the top priority.** Idle at ~0% CPU; work only while live mode is on (toggled by hotkey).
- **No ML for finding relics.** The UI is fixed, so classical CV finds the tiles.
- **Windows is the only target.** The only OCR engine is Windows OCR. No Tesseract, no Mac support. On the Mac everything except OCR runs, for development and tests.
- Target: hotkey press → overlay visible in **< 300 ms**. Measure, don't assume.

## Goal (simplified)

Recognize a relic → score it. Scores come from `settings/builds.json`: per build, points per effect plus a `forbid` list; a relic's score is the best total over builds that don't forbid any of its effects. Scores are drawn by a full-screen overlay on the tiles themselves.

## How it works

`scan(image, engine, builds, memory) -> Scene` (`src/ranni/scan.py`) is the whole pipeline, platform-independent:

1. **Find tiles** (`relics/find_relics`): no settings; straight-line square scoring at 540 px height. ~100 ms.
2. **Read text** (`ocr/read_text`): Windows OCR of the whole screen (lines + boxes).
3. **Match effects** (`scoring/match.py`): snap each line to a known effect (every name in builds.json) with rapidfuzz (`fuzz.ratio` ≥ 85, numbers must match exactly, a stray leading icon character is tolerated); unmatched lines are tried joined with the line below (wrapped effects). Everything else is ignored.
4. **Details icon**: the box with ≥ 2 text lines just to its right; it's not a tile.
5. **Selected tile** (`relics/find_selected`): its border band is ≥ 1.6× brighter than any other tile's.
6. **Score** (`scoring/score_relic`).
7. **Track** (`tracking/TileMemory`, session only): remember the selected tile's score by a 12×12 thumbnail of its art plus its neighbours' thumbnails (reading order); recall it on tiles that look the same and have ≥ 1 matching neighbour. Conflicting memories → no label. Handles scrolling, selling and identical-looking relics.

Live mode (`ranni run`, `src/ranni/app.py`, Windows): hotkey thread (Ctrl+Alt+Space live on/off, Ctrl+Alt+End quit; `GetMessageW`, no CPU) → scanner thread (while live: capture → scan, every 0.25 s; while off it waits) → overlay on the main thread (Tk polls a queue). Capture is dxcam (DXGI Desktop Duplication), falling back to mss. The overlay is click-through and excluded from capture (`SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`) so Ranni never detects its own drawings.

**All Windows code (capture/, hotkey/, overlay/, app.py, ocr/windows.py) was written on macOS and is UNTESTED.** Library APIs were checked against the installed versions' sources/stubs (dxcam 0.3.0, mss 10.2, pywinrt 3.2.1). See TESTING.md.

Samples: `End Screen #1` and `Small Jar #1/#3` are good. `Small Jar #2/#4` are low-res web images; `Relic Rites #1.avif` can't be read by OpenCV. Real in-game PNGs of Relic Rites are needed.

## Code organization: one folder per concern

```
settings/builds.json     builds: effect points + forbid list (example data; user will replace)
settings/effects.json    effect patterns (regex + details); see effects/__init__.py
src/ranni/
  types.py               Box
  relics/                find_relics (tiles), find_selected (glowing tile)
  ocr/                   read_text, default_engine; engine.py (OcrLine, OcrEngine); windows.py
  effects/               OCR line -> effect: effects.json loading (__init__), match_effect (match.py)
  scoring/               builds.json, score_relic; match.py (old OCR matcher, to be replaced by effects/)
  tracking/              TileMemory: keep scores attached to tiles
  scan.py                the pipeline -> Scene
  draw.py                draw a Scene on an image (debug)
  capture/               screen -> image (dxcam / mss)            Windows
  hotkey/                global hotkeys thread                    Windows
  overlay/               transparent click-through Tk overlay     Windows
  app.py                 live mode wiring                         Windows
  cli.py                 `ranni scan <image> [--debug]`, `ranni run`
tests/                   pytest; real samples + fake OCR engines; Windows parts only import-checked
```

Windows-only packages load lazily (inside functions) so everything imports and tests run on macOS; `tests/test_imports.py` enforces it.

## Tech stack

`numpy`, `opencv-python-headless`, `rapidfuzz`, `pytest`; Python's built-in `tkinter` for the overlay; on Windows `dxcam` + `mss` (capture) and the `winrt-*` packages (OCR) (platform markers in `pyproject.toml`). Managed with `uv`, Python 3.12: `uv sync` installs the project editable into `.venv/` and provides the `ranni` command.

Prefer small, boring dependencies. Ask before adding anything heavy (ML frameworks, GUI toolkits).

## Open questions

- Does the untested Windows code run? (first Windows test pending)
- Which screens matter most (Relic Rites, Small Jar Bazaar, End Screen)?
- The user's resolution / aspect ratio (Small Jar #3 is 2560x1600 with the game letterboxed).
- Exact game process name on Windows.

## Working conventions for Claude Code

- **Propose before building, and ask about uncertain design decisions.** Wait for agreement before creating code or files.
- **Keep code small and intuitive.** Don't pre-build options or fallbacks that aren't needed yet.
- Each stage is inspectable via `ranni scan --debug`. Performance claims are measured, not assumed.

---

## Windows notes

- **Capture:** `dxcam` (DXGI) or `windows-capture` (WGC, can target the game window). Create the capture object when the game is detected, not on hotkey. Avoid `PIL.ImageGrab`, `pyautogui.screenshot`, GDI BitBlt.
- **Hotkey:** one thread owns a Win32 message loop (`GetMessageW`, sleeps at 0% CPU). Hotkey registered with `hWnd=None` belongs to that thread; register/unregister/`WM_HOTKEY` all on it. `SetTimer(None, 0, 2000, None)` → on `WM_TIMER` check `psutil` for the game process; `RegisterHotKey` (with `MOD_NOREPEAT`) when it appears, `UnregisterHotKey` when gone. Optional stricter mode: `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` (keep a reference to the ctypes callback). On `WM_HOTKEY` push to a `queue.Queue`; scan on another thread. Don't use the `keyboard` library (global low-level hook).
- **Overlay:** tkinter window, layered + click-through + topmost via `ctypes` (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST`), created hidden at arm time; Tk isn't thread-safe, so the scan thread signals it. Fallback: native layered window via ctypes. Avoid PyQt (idle RAM).
- **DPI:** `user32.SetProcessDpiAwarenessContext(-4)` at startup.
- **Borderless windowed** mode required.
- **Launching:** tray app that starts with Windows and arms itself when the game appears; alternative Steam launch option `"C:\path\launch.bat" %command%`.
- **Packaging:** Nuitka (faster startup) or PyInstaller.
