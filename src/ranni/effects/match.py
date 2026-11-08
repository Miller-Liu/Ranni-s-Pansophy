"""OCR line -> the effect it shows (see __init__.py for the effects.json format).

OCR mistakes: if no pattern matches exactly, the closest one within a few edits is used (match_effect).
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

import regex  # like re, plus fuzzy matching

from ranni.effects import GROUP, Effect

# ----- MATCHING AND FILLING -----

@dataclass
class Match:
    effect: str 
    effect_type: str
    description: str
    stackable: bool


@functools.lru_cache(maxsize=None)
def _fuzzy(pattern: str, max_errors: int) -> regex.Pattern:
    """
    The pattern allowing up to max_errors non-digit edits. BESTMATCH makes it find the fewest edits, not just any match. Cached: compiling is slow.
    """
    return regex.compile(f"(?:{pattern}){{e<={max_errors}:[^\\d]}}", regex.IGNORECASE | regex.BESTMATCH)

def _official_text(effect: Effect, values: list[str | None]) -> str:
    """
    The effect as the game writes it: the pattern with each group replaced by its value.
    "(?P<stat>Vigor|Mind)\\s*\\+(1|2|3)" with ["Vigor", "2"] -> "Vigor +2"
    """
    remaining = iter(values)
    text = GROUP.sub(lambda g: next(remaining) or "", effect.regex.pattern)  # "Vigor\s*\+2"
    text = text.replace(r"\s*", " ")  # "Vigor \+2" (spaces were made optional when loading)
    return re.sub(r"\\(.)", r"\1", text)  # "Vigor +2" (drop the escapes)

def _to_match(effect: Effect, m: re.Match | regex.Match) -> Match:
    """
    Convert a regex match to a Match object: its named groups, its level and its filled-in details.
    """
    print(m.string)

    # Normalize effect formatting
    values = [table.get(caught.lower().replace(" ", "")) if caught else None
              for table, caught in zip(effect.spellings, m.groups())]
    print(values)

    description : str
    template : str | dict = effect.template or ""
    if isinstance(template, dict):
        description = template.get(m.group(1).lower(), template.get("default")) # type: ignore
    else:
        description = template

    ans = Match(effect.name, effect.effect_type, description, effect.stackable)
    print(ans)
    return ans

MAX_ERROR_RATE = 0.10  # closest match: allow edits up to 10% of the line's length...
MIN_ERRORS = 1  # ...but at least 1, so short lines like "Vigcr +2" still match
def match_effect(text: str, effects: list[Effect]) -> Match | None:
    # Exact match 
    text = text.strip()
    for effect in effects:
        m = effect.regex.fullmatch(text)
        if m is not None:
            return _to_match(effect, m)

    # Closest match
    max_errors = max(MIN_ERRORS, int(len(text) * MAX_ERROR_RATE))
    best: tuple[Effect, regex.Match, int] | None = None  # (effect, match, edits) with the fewest edits so far
    for effect in effects:
        m = _fuzzy(effect.regex.pattern, max_errors).fullmatch(text)
        if m is None:
            continue
        errors = sum(m.fuzzy_counts)
        if best is None or errors < best[2]:
            best = (effect, m, errors)
            if errors == 1:
                break

    # Nothing close enough
    if best is None:
        return None 

    return _to_match(best[0], best[1])


if __name__ == "__main__":
    # Quick check: uv run python -m ranni.effects.match (from the project folder)
    from ranni.effects import load_effects, print_effects

    effects = load_effects("settings/effects.json")
    # print_effects(effects)
    for line in ["Vigor +2", "Vigcr +2", "Poise +3", "Strength +1", "Increased Maximum FP",
                 "Improved Blood Loss Resistance", "Sell"]:
        m = match_effect(line, effects)
        # print(f"{line:32} -> " + (f"{m.effect.name} {m.groups} level={m.level}: {m.details}" if m else "no match"))
