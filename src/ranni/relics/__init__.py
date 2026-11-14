"""
The relic side of Ranni: which effect a line of text is, and how good a relic is for your builds.
It only works with plain text, never the screen, so it all runs on the Mac (try it with interactive.py).

    manager.py  EffectManager: loads effects.json and works out which effect a line of text is
    effect.py   Effect: one effect and its descriptions. Match: an effect recognized in a line
    pattern.py  EffectPattern: how the game writes an effect, and all the regex work for it
    builds.py   Scorer: loads your tier lists from builds.json and scores a relic's effects
"""
