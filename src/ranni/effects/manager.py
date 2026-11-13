"""EffectManager: the effects from effects.json, and which one a line of text shows.

It makes the decisions (exact first, then the closest; which effects to try) and leaves the regex details to
EffectPattern and the descriptions to Effect. Turn on logging at DEBUG to see every step (see interactive.py).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rapidfuzz import fuzz, process, utils

from ranni.effects.effect import Effect, EffectsError, Match
from ranni.effects.pattern import EffectPattern
from ranni.ocr.engine import OcrLine
from ranni.ocr.layout import line_below, union

log = logging.getLogger(__name__)

MAX_ERROR_RATE = 0.10  # closest match: allow edits up to 10% of the line's length...
MIN_ERRORS = 1  # ...but at least 1, so short lines like "Vigcr +2" still match
PREFILTER_FROM = 3  # from this many allowed edits (lines of ~30+ characters), only try the most similar effects (fuzzy is slow there)
PREFILTER_TOP = 5
PREFILTER_MIN_SIMILARITY = 50  # 0-100, against the effect's fixed words (the right one scores ~60+ even with typos)

def _variants(text: str) -> list[str]:
    """
    The text, and the text without a short leading token (OCR often reads the effect's little icon as a stray character or two).
    """
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 2 and not parts[0].isdigit():
        return [text, parts[1]]
    return [text]

class EffectManager:
    def __init__(self, effects_path: str | Path):
        self.effects = self.load(effects_path)
        self.fixed_texts = [e.pattern.fixed_text for e in self.effects]  # same order as self.effects

    def load(self, effects_path: str | Path) -> list[Effect]:
        """Every effect in the json, checked (EffectsError names the entry with a mistake)."""
        all_effects = json.loads(Path(effects_path).read_text(encoding="utf-8"))
        effects = []
        for effect_type, entries in all_effects.items():
            for entry in entries:
                try:
                    pattern = EffectPattern(entry["pattern"])
                except Exception as error:
                    raise EffectsError(f"{effects_path}, {entry.get('name')!r}: bad pattern ({error})") from error
                effects.append(Effect(entry["name"], effect_type, pattern, entry["effect"], entry["stackable"], entry.get("note")))
        return effects

    def match(self, text: str) -> Match | None:
        """
        The effect this line shows, or None (menus, prices, the relic's name).
        """
        log.debug("%r", text)
        for candidate in _variants(text.strip()):
            if candidate != text.strip():
                log.debug("  without icon:  %s", candidate)
            found = self._match_one(candidate)
            if found is not None:
                return found
        return None

    def _match_one(self, text: str) -> Match | None:
        # Exact match
        found = next(((e, m) for e in self.effects if (m := e.pattern.exact(text)) is not None), None)
        log.debug("  exact:         %s", found[0].name if found else "no match")

        # Closest match
        if found is None:
            max_errors = max(MIN_ERRORS, int(len(text) * MAX_ERROR_RATE))
            candidates = self.effects
            if max_errors >= PREFILTER_FROM:
                similar = process.extract(text, self.fixed_texts, scorer=fuzz.ratio, processor=utils.default_process,
                                          limit=PREFILTER_TOP, score_cutoff=PREFILTER_MIN_SIMILARITY)
                candidates = [self.effects[i] for _, _, i in similar]
                log.debug("  most similar:  %s", [e.name for e in candidates])
            best = None  # (effect, match, edits) with the fewest edits so far
            for effect in candidates:
                m = effect.pattern.fuzzy(text, max_errors)
                if m is None:
                    continue
                errors = sum(m.fuzzy_counts)
                if best is None or errors < best[2]:
                    best = (effect, m, errors)
                    if errors == 1:
                        break
            log.debug("  fuzzy (≤%d):    %s", max_errors, f"{best[0].name} ({best[2]} edits)" if best else "no match")
            if best is not None:
                found = (best[0], best[1])

        # Nothing close enough
        if found is None:
            return None

        # What it means
        effect, m = found
        values, indices = effect.pattern.read(m)
        result = Match(effect.name, effect.effect_type, effect.pattern.official_text(values), values,
                       effect.describe(values, indices), effect.stackable)
        log.debug("  values:        %s", result.values)
        log.debug("  official text: %s", result.text)
        log.debug("  description:   %s", result.description)
        return result

    def match_lines(self, lines: list[OcrLine]) -> list[Match]:
        """
        Every effect in the OCR lines, with its box. A line that matches nothing is tried joined with the line below it (a wrapped effect).
        """
        found = []
        used: set[int] = set()
        for i, line in enumerate(lines):
            if i in used:
                continue
            result = self.match(line.text)
            if result is not None:
                result.box = line.box
                found.append(result)
                continue
            j = line_below(lines, i)
            if j is not None and j not in used:
                result = self.match(f"{line.text} {lines[j].text}")
                if result is not None:
                    result.box = union(line.box, lines[j].box)
                    found.append(result)
                    used.add(j)
        return found
