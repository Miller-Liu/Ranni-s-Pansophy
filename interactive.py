# Type lines over and over and see every step: uv run python interactive.py  (empty line or Ctrl+C to quit)
import logging
import sys

from ranni.effects import EffectManager
from ranni.scoring import Scorer

logging.basicConfig(format="%(message)s", stream=sys.stdout)
logging.getLogger("ranni.effects").setLevel(logging.DEBUG)  # EffectManager prints each step

manager = EffectManager("settings/effects.json")
scorer = Scorer.load("settings/builds.json")
print(f"{len(manager.effects)} effects loaded. Type what OCR read; empty line to quit.")

while True:
    try:
        line = input("\n> ")
    except (EOFError, KeyboardInterrupt):
        break
    if not line.strip():
        break

    match = manager.match(line)  # steps 3 and 4, logged
    if match is None:
        print("  -> no effect")
        continue

    score = scorer.score([match.text])  # step 5, this effect alone
    print(f"  score:         {score.total} ({score.build})   points per character: "
          + ", ".join(f"{t.name} {t.points(match.text):g}" for t in scorer.tier_lists))
