# Testing Ranni on Windows

All Windows parts (screen capture, hotkeys, overlay, Windows OCR) were written on a Mac and
have **never been run**. Expect a fix or two. If something fails, copy the **whole console
output** (and the debug image if there is one) back to Claude.

Go in order: each step tests one more piece.

## 0. Setup (once)

1. Copy the project folder to the Windows PC (or push/pull it with git).
2. Install uv (PowerShell):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. In the project folder:
   ```powershell
   uv sync
   ```
   This installs Python 3.12 and everything else, including the Windows-only packages.
4. Windows OCR needs an English language pack with OCR. Check (PowerShell):
   ```powershell
   Get-WindowsCapability -Online | Where-Object { $_.Name -like 'Language.OCR*en-US*' }
   ```
   `State : Installed` is good. If not: Settings > Time & language > Language & region > add English (United States).

## 1. OCR + scoring on a screenshot (no game needed)

```powershell
uv run ranni scan "samples\End Screen #1.jpg" --debug
```
Expected:
- `5 tiles, selected: #0`
- under **text read**: the lines on screen, including `Polished Burning Scene`, `Improved Dragon Cult Incantations`, `Faith +1`
- under **effects recognized**: `Improved Dragon Cult Incantations (normal)`, `Faith +1 (normal)`, each with its points
- a `Score ...` line for the best build in `settings\builds.json`
- open `debug\End Screen #1\scene.png`: tiles boxed, the selected one yellow with its score, points next to the effects

Also try `"samples\Small Jar #1.webp"` and `"samples\Small Jar #3.png"`.

This tests Windows OCR. If it fails, this is the most likely place: send the error.

## 2. Live overlay, without the game

1. Open `samples\Small Jar #1.webp` full screen (e.g. Photos app, then F11).
2. In a terminal:
   ```powershell
   uv run ranni run
   ```
   It prints `Ranni is running...` and which capture it uses (`capture: dxcam`).
3. Press **Ctrl+Alt+Space**. Within a second:
   - green boxes on every relic tile, a yellow box on the selected one
   - thin blue boxes around text OCR read, `+N` next to recognized effects, a score line above the details icon
   - bottom-left status line with timings per step (capture / find tiles / read text / ...)
4. **Ctrl+Alt+Space** again turns it off (boxes disappear). **Ctrl+Alt+End** (or Ctrl+C in the terminal) quits.

Clicks should go through the overlay to whatever is underneath.

## 3. In the game

1. Set the game to **Borderless Windowed** (exclusive fullscreen hides overlays and can give black captures).
2. `uv run ranni run`, open Relic Rites (or the bazaar / end screen), press **Ctrl+Alt+Space**.
3. Move the selection over a few relics. Each selected relic should get a score on its tile, and
   **tiles you already visited should keep their score** (tracking) as you move on and scroll.
4. Take a few screenshots for `samples\` (Win+PrtScn saves PNGs to Pictures\Screenshots),
   especially **Relic Rites**. Real screenshots are the best way to tune detection.

## 4. Your builds

Edit `settings\builds.json`: for each character, each build, how many points each effect is worth.
Effects are written as the game shows them (the official text, e.g. `Vigor +2`; case and spacing don't matter):

```json
{
  "Duchess": {
    "Favorite Build": {
      "normal effect": {"Improve Daggers Attack Power": 9, "Magic Attack Up +2": 9},
      "deep effect":   {"Dormant Power Helps Discover @weapon": -1},
      "deep curse":    {"Reduced Vigor and Arcane": 0, "Reduced Rune Acquisition": -2}
    }
  }
}
```

A relic's score for a build = the sum of its effects' and curses' points (unlisted effects = 0).
A curse that isn't listed rules that build out. The relic shows the best build's score.
`@weapon` stands for any value of the effect's group named `weapon` (see the patterns in the effects files).
Ranni checks every entry when it starts and names any that isn't a real effect of its section.

## If something goes wrong

| Symptom | Try / send |
|---|---|
| `dxcam unavailable (...)`, or black / frozen captures | `uv run ranni run --capture mss` |
| `warning: hotkey #1 is already used by another program` | Another app owns Ctrl+Alt+Space. Tell Claude which key to use instead. |
| `warning: ... can't hide the overlay from capture` | Windows is older than 10 (2004). Ranni may detect its own boxes. |
| `OCR unavailable (...)` / no text read | Check step 0.4 (language pack); send the error |
| Boxes are offset from the tiles | Display scaling issue: tell Claude your resolution and scaling % |
| Overlay too slow | Send the bottom-left status line (it shows ms per step) |
| Anything else | The whole console output, plus `debug\...\scene.png` if it was a `scan` |

Options: `ranni run --interval 0.5` (scan less often), `ranni run --no-text-boxes` (hide the blue text outlines).
