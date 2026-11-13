"""OCR text -> the relic effects it shows.

    manager.py  EffectManager: loads effects.json, decides which effect a line shows
    effect.py   Effect (one json entry: checks itself, fills in its description), Match (one result)
    pattern.py  EffectPattern: every regular-expression detail
"""

from ranni.effects.effect import Effect, EffectsError, Match
from ranni.effects.manager import EffectManager
from ranni.effects.pattern import EffectPattern

__all__ = ["Effect", "EffectManager", "EffectPattern", "EffectsError", "Match"]
