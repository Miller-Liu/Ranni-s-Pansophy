# Type lines over and over and see every step: uv run python interactive.py  (empty line or Ctrl+C to quit)
import logging
import sys

from ranni.relics.builds import Scorer
from ranni.relics.manager import EffectManager

manager = EffectManager("settings/effects.json", "settings/deep_effects.json")
scorer = Scorer("settings/builds.json", manager)
print(f"{len(manager.normal)} effects and {len(manager.deep)} deep effects loaded, {len(scorer.builds)} builds. "
      "Type what OCR read; empty line to quit.")

logging.basicConfig(format="%(message)s", stream=sys.stdout)
logging.getLogger("ranni.relics").setLevel(logging.DEBUG)  # EffectManager prints each step

while True:
    try:
        line = input("\n> ")
    except (EOFError, KeyboardInterrupt):
        break
    if not line.strip():
        break

    match = manager.match(line)  # effects.json first, then deep_effects.json; every step is logged
    if match is None:
        print("  -> no effect")
        continue

    print(f"  kind:          {match.kind}")
    for build in scorer.builds:  # what this one effect is worth in each build
        points = build.effect_points(match)
        print(f"  {str(build) + ':':<14} {'ruled out' if points is None else f'{points:+g}'}")
