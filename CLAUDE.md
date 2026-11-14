# Ranni — Project Context

## What this is

**Ranni** is a lightweight background helper for the game *Elden Ring Nightreign* (Windows, Steam). The goal: when the user presses a hotkey on a relic screen, it captures one frame, reads the selected relic's effects, applies the user's keep/sell rules, and shows the verdict as a click-through overlay.

It is a **passive reader**: it never reads or writes game memory and never sends inputs to the game. The user does the actual selling by hand. Keep it that way. The game runs Easy Anti-Cheat, and screen capture plus a hotkey is in the same category as OBS or Discord overlays, while automated input is not.

How the game shows relics: relic **tiles** show icons only; the effects appear only in one **details panel** (relic name + up to 3 effects, each with a small icon in front; wrapped effects are indented; an empty slot shows `-`) for the selected relic. Screens seen so far: Relic Rites (inventory grid), Small Jar Bazaar (purchase popup), End Screen (expedition rewards).

## Hard constraints and priorities

- **Runtime efficiency is the top priority.** Idle at ~0% CPU; work only while live mode is on (toggled by hotkey).
- **No ML for finding relics.** The UI is fixed, so classical CV finds the tiles.
- **Windows is the only target.** The only OCR engine is Windows OCR. No Tesseract, no Mac support. On the Mac everything except OCR runs, for development.
- Target: hotkey press → overlay visible in **< 300 ms**. Measure, don't assume.

## Goal (simplified)

Recognize a relic → score it. Scores come from `settings/builds.json`: character → build → section (`normal effect` / `deep effect` / `deep curse`) → {official text: points}; `@name` is a wildcard for a named group. A relic's score for a build is the sum of its effects' and curses' points (unlisted effects 0); an unlisted curse rules that build out; the relic shows the best build's score. Scores are drawn by a full-screen overlay on the tiles themselves.

## How it works

`scan(image, engine, manager, scorer, memory) -> Scene` (`src/ranni/scan.py`) is the whole pipeline, platform-independent:

1. **Find tiles** (`screen/tiles.py`, `find_relics`): no settings; straight-line square scoring at 540 px height. ~100 ms.
2. **Read text** (`screen/ocr.py`, `read_text`): Windows OCR of the whole screen (lines + boxes).
3. **Match effects** (`scan.find_effects` → `relics/manager.py`, `EffectManager.match`): each line against every pattern in `settings/effects.json`, then `settings/deep_effects.json`; if anything is only in the deep file (a curse or deep-only effect), the relic is deep and all its lines are re-read in the deep file only. Each group option is its own named group (selector), so a match tells which option it was even with typos. Exact match first, else fuzzy with the `regex` package (≤ 10% of the length in edits, ≥ 1, never on digits; lines of 30+ chars only try the 5 most similar effects by rapidfuzz first). Spaces match any spaces; a stray leading icon character is tolerated; unmatched lines are tried joined with the line below (wrapped effects). Gives the official text (`Vigor +2`, the key builds.json uses), the options and the filled-in description. Deep vs normal is decided from the text only (a deep relic with no curse and only effects that also exist as normal ones is read as normal).
4. **Details icon**: the box with ≥ 2 text lines just to its right; it's not a tile.
5. **Selected tile** (`screen/tiles.py`, `find_selected`): its border band is ≥ 1.6× brighter than any other tile's.
6. **Score** (`relics/builds.py`, `Scorer`): one `Build` per character's build, by official text and kind.
7. **Track** (`screen/tracking.py`, `TileMemory`, session only): remember the selected tile's score by a 12×12 thumbnail of its art plus its neighbours' thumbnails (reading order); recall it on tiles that look the same and have ≥ 1 matching neighbour. Conflicting memories → no label. Handles scrolling, selling and identical-looking relics.

Live mode (`ranni run`, `src/ranni/app.py`, Windows): hotkey thread (Ctrl+Alt+Space live on/off, Ctrl+Alt+End quit; `GetMessageW`, no CPU) → scanner thread (while live: capture → scan, every 0.25 s; while off it waits) → overlay on the main thread (Tk polls a queue). Capture is dxcam (DXGI Desktop Duplication), falling back to mss. The overlay is click-through and excluded from capture (`SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`) so Ranni never detects its own drawings.

**All Windows code (screen/capture.py, screen/windows_ocr.py, overlay/window.py, overlay/hotkeys.py, app.py) was written on macOS and is UNTESTED.** Library APIs were checked against the installed versions' sources/stubs (dxcam 0.3.0, mss 10.2, pywinrt 3.2.1). See TESTING.md.

Samples: `End Screen #1` and `Small Jar #1/#3`. Real in-game PNGs of Relic Rites are needed.

## Code organization: seeing, knowing, showing

```
settings/builds.json     the user's builds: points per effect / deep effect / curse
settings/effects.json    every regular relic effect: pattern (regex; a group named (?P<status>...) fills @status in the description), description, stackable
settings/deep_effects.json  the same for deep relics; its "Curse" section is the curses
src/ranni/
  screen/                SEEING: screenshot -> tiles + text. Knows nothing about effects. Box lives in __init__.py
    capture.py             take a screenshot (dxcam / mss)                       Windows
    tiles.py               find_relics (tiles), find_selected (glowing tile)
    ocr.py                 read_text, default_engine, OcrLine, OcrEngine
    windows_ocr.py         the Windows OCR engine                                Windows
    layout.py              line_below, union (wrapped effects)
    tracking.py            TileMemory: keep scores attached to tiles
  relics/                KNOWING: text -> effect -> score. Pure Python, plain strings only, no screen imports
    manager.py             EffectManager: loads effects.json, decides which effect a line shows
    effect.py              Effect (checks itself on load, fills its description), Match, EffectsError
    pattern.py             EffectPattern: every regex detail
    builds.py              Scorer (loads builds.json, checks every entry against the right file and section), Build (one character's build), Score
  overlay/               SHOWING: what the user sees and presses
    window.py              transparent click-through Tk overlay                  Windows
    draw.py                draw a Scene on a saved image (--debug)
    hotkeys.py             global hotkeys thread                                 Windows
  scan.py                the pipeline -> Scene; joins screen/ and relics/ (find_effects: OCR lines -> FoundEffect with box)
  app.py                 live mode wiring                                      Windows
  cli.py                 `ranni scan <image> [--debug]`, `ranni run`
interactive.py           type lines, see every matching step and the score (logging at DEBUG shows EffectManager's steps)
```

Dependencies go one way: screen/ and relics/ never import each other or overlay/; scan.py joins them; overlay/ draws a Scene. Windows-only packages load lazily (inside functions, or windows_ocr.py only through default_engine) so everything else imports on macOS.

## Tech stack

`numpy`, `opencv-python-headless`, `regex` (fuzzy matching), `rapidfuzz` (quick similarity prefilter); Python's built-in `tkinter` for the overlay; on Windows `dxcam` + `mss` (capture) and the `winrt-*` packages (OCR) (platform markers in `pyproject.toml`). Managed with `uv`, Python 3.12: `uv sync` installs the project editable into `.venv/` and provides the `ranni` command.

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
