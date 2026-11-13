# Ranni

A passive screen-reading helper for *Elden Ring Nightreign* (Windows). Press a hotkey on a relic screen and it reads the selected relic's effects with Windows OCR and shows a score as a click-through overlay. It never reads game memory and never sends input to the game.

Status: early. The Windows parts (capture, OCR, hotkeys, overlay) have not been run yet; see [TESTING.md](TESTING.md).

## Setup (Windows)

Run these in PowerShell.

1. Install [git](https://git-scm.com/download/win) and [uv](https://docs.astral.sh/uv/):
   ```powershell
   winget install --id=Git.Git -e
   winget install --id=astral-sh.uv -e
   ```
   Then open a new terminal so both are on PATH.

2. Get the project and install everything (uv also installs Python 3.12):
   ```powershell
   git clone <repo-url> Ranni
   cd Ranni
   uv sync
   ```

3. Windows OCR needs the English language pack. Check:
   ```powershell
   Get-WindowsCapability -Online | Where-Object { $_.Name -like 'Language.OCR*en-US*' }
   ```
   `State : Installed` is good. If not: Settings > Time & language > Language & region > add English (United States).

4. Check it works:
   ```powershell
   uv run pytest
   ```

To update later: `git pull`, then `uv sync`.

## Usage

```powershell
uv run ranni scan "samples\End Screen #1.jpg" --debug   # one screenshot: tiles, text read, effects, score
uv run ranni run                                        # live overlay
```

`--debug` saves `debug\<image name>\scene.png` with everything drawn on it.

Live mode: set the game to **Borderless Windowed**, start `uv run ranni run`, then:
- **Ctrl+Alt+Space**: live on/off
- **Ctrl+Alt+End**: quit

To test OCR on the real game, take a screenshot on a relic screen (**Win+PrtScn** saves a PNG to `Pictures\Screenshots`) and scan it:
```powershell
uv run ranni scan "$env:USERPROFILE\Pictures\Screenshots\<shot>.png" --debug
```

## Development (macOS)

Everything except OCR, capture, hotkeys and the overlay runs on the Mac:
```bash
uv sync
uv run pytest
uv run ranni scan "samples/End Screen #1.jpg" --debug   # tiles only, no OCR
```

## Files

- `settings/effects.json`, `settings/deep_effects.json`: every relic effect (pattern, description, stackable)
- `settings/builds.json`: per-character tier lists of effects
- `interactive.py`: type lines and see every matching step and the score (`uv run python interactive.py`)
- `src/ranni/`: the code; [CLAUDE.md](CLAUDE.md) describes how it fits together
- [TESTING.md](TESTING.md): step-by-step Windows test plan
