"""
EffectManager: holds every effect from effects.json (normal relics) and deep_effects.json (deep relics and their curses),
and works out which one a line of text is.

It decides the order of things (try an exact match first, then allow typos; which effects are worth trying).
The regex work is in EffectPattern, and filling in descriptions is in Effect.
It only ever sees plain strings: scan.py hands it the lines OCR read.
To watch it work step by step, run interactive.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rapidfuzz import fuzz, process, utils

from ranni.relics.effect import Effect, EffectsError, Match
from ranni.relics.pattern import EffectPattern

log = logging.getLogger(__name__)

# How many typos to allow: 10% of the line's length, but at least 1 so short lines like "Vigcr +2" still match.
MAX_ERROR_RATE = 0.10
MIN_ERRORS = 1
# Checking for typos is slow on long lines (30+ characters, 3+ typos allowed). For those, only the effects whose fixed
# words look most like the line are checked: the top 5, if they're at least 50% similar. The right effect scores 60+
# even with typos.
PREFILTER_FROM = 3
PREFILTER_TOP = 5
PREFILTER_MIN_SIMILARITY = 50


class EffectManager:
    def __init__(self, effects_path: str | Path, deep_effects_path: str | Path):
        self.normal = self.load(effects_path, deep=False)
        self.deep = self.load(deep_effects_path, deep=True)
        # the fixed words of every effect, for the quick similarity check; same order as the lists above
        self._fixed_texts = {False: [e.pattern.fixed_text for e in self.normal], True: [e.pattern.fixed_text for e in self.deep]}

    def effects(self, deep: bool) -> list[Effect]:
        return self.deep if deep else self.normal

    def load(self, effects_path: str | Path, deep: bool) -> list[Effect]:
        """
        Every effect in the json file. Stops with an EffectsError naming the effect if one has a mistake.
        A description can be one text, or a dict that picks a text by what the named group read; one text is stored as
        {"default": text}, so it's always a dict.
        In deep_effects.json, the effects in the "Curse" section are curses.
        """
        sections = json.loads(Path(effects_path).read_text(encoding="utf-8"))
        effects: list[Effect] = []
        for category, entries in sections.items():
            for entry in entries:
                try:
                    pattern = EffectPattern(entry["pattern"])
                except Exception as error:
                    raise EffectsError(f"{effects_path}, {entry.get('name')!r}: bad pattern ({error})") from error
                description = entry["description"]
                descriptions = description if isinstance(description, dict) else {"default": description}
                kind = ("curse" if category == "Curse" else "deep") if deep else "normal"
                effects.append(Effect(entry["name"], category, kind, pattern, descriptions, entry["stackable"], entry.get("note")))
        return effects

    def match(self, text: str, deep: bool | None = None) -> Match | None:
        """
        The effect this line of text is, or None if it isn't one (a menu, a price, the relic's name...).
        deep=False looks only in effects.json, deep=True only in deep_effects.json, and None (the default) tries
        effects.json first, then deep_effects.json.
        """
        log.debug("%r", text)
        for in_deep in ([False, True] if deep is None else [deep]):
            log.debug("  in %s", "deep_effects.json" if in_deep else "effects.json")
            for candidate in self._variants(text.strip()):
                if candidate != text.strip():
                    log.debug("  without icon:  %s", candidate)
                found = self._match_one(candidate, in_deep)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _variants(text: str) -> list[str]:
        """
        The ways to try a line: as it is, and without its first word if that's only 1-2 characters.
        Each effect has a small icon in front of it, and OCR sometimes reads the icon as a stray letter or two.
        """
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and len(parts[0]) <= 2 and not parts[0].isdigit():
            return [text, parts[1]]
        return [text]

    def _match_one(self, text: str, deep: bool) -> Match | None:
        effects = self.effects(deep)

        # 1. An exact match.
        found = next(((e, m) for e in effects if (m := e.pattern.exact(text)) is not None), None)
        log.debug("  exact:         %s", found[0].name if found else "no match")

        # 2. If there isn't one, the effect that matches with the fewest typos.
        if found is None:
            max_errors = max(MIN_ERRORS, int(len(text) * MAX_ERROR_RATE))
            candidates = effects
            if max_errors >= PREFILTER_FROM:
                similar = process.extract(text, self._fixed_texts[deep], scorer=fuzz.ratio, processor=utils.default_process,
                                          limit=PREFILTER_TOP, score_cutoff=PREFILTER_MIN_SIMILARITY)
                candidates = [effects[i] for _, _, i in similar]
                log.debug("  most similar:  %s", [e.name for e in candidates])
            best = None  # (effect, match, typos) with the fewest typos so far
            for effect in candidates:
                m = effect.pattern.fuzzy(text, max_errors)
                if m is None:
                    continue
                typos = sum(m.fuzzy_counts)
                if best is None or typos < best[2]:
                    best = (effect, m, typos)
                    if typos == 1:  # can't do better than 1 (0 would have been an exact match)
                        break
            log.debug("  fuzzy (≤%d):    %s", max_errors, f"{best[0].name} ({best[2]} typos)" if best else "no match")
            if best is not None:
                found = (best[0], best[1])

        # 3. Nothing close enough: not an effect.
        if found is None:
            return None

        # 4. Read what each group matched, and turn it into the official text and the description.
        effect, m = found
        values, indices = effect.pattern.read(m)
        result = Match(effect, effect.pattern.official_text(values), values, effect.description(values, indices))
        log.debug("  values:        %s", result.values)
        log.debug("  official text: %s", result.official_text)
        log.debug("  description:   %s", result.description)
        return result
