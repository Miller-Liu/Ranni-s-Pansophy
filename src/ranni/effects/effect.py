"""Effect: one entry of effects.json, checked when it's created. Match: one effect found in a line of text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NoReturn

from ranni.effects.pattern import EffectPattern
from ranni.types import Box

LEVELS = re.compile(r"\[([^\[\]]*,[^\[\]]*)\]")  # [a, b, c]; brackets without a comma, like [MaxHP * 0.005], are text
BLANK = re.compile(r"@(\d+)")  # @1: the first group's value

class EffectsError(ValueError):
    """A mistake in effects.json."""

@dataclass
class Effect:
    name: str
    effect_type: str
    pattern: EffectPattern
    template: str | dict | None  # description with blanks (@1, [a, b, c]); a dict picks one by the first group
    stackable: bool | None  # None: depends (see note)
    note: str | None

    def __post_init__(self):
        self.check()

    def describe(self, values: list[str], indices: list[int | None]) -> str:
        """
        The template filled in: a dict picks by the first group, @1 is the first group's value, [a, b, c] picks by the level.
        "Increase @1 by [1, 2, 3]" with ["Strength", "2"] -> "Increase Strength by 2"
        """
        text = self._template_for(values[0] if values else None)
        text = BLANK.sub(lambda g: values[int(g.group(1)) - 1], text)
        level = self.pattern.level_group()
        index = indices[level] if level is not None else None  # which level matched: +2 in (1|2|3) is 1
        if index is not None:
            text = LEVELS.sub(lambda g: [c.strip() for c in g.group(1).split(",")][index], text)
        return text

    def _template_for(self, first: str | None) -> str:
        if isinstance(self.template, dict):
            return self.template.get(first.lower() if first else "", self.template.get("default", ""))
        return self.template or ""

    def check(self) -> None:
        """Raise EffectsError for mistakes that would otherwise only show up as a wrong description."""
        def fail(problem: str) -> NoReturn:
            raise EffectsError(f"effects.json, {self.name!r}: {problem}")
        options = self.pattern.options
        templates = list(self.template.values()) if isinstance(self.template, dict) else [self.template or ""]
        if isinstance(self.template, dict):
            first = options[0] if options else None
            if first is None:
                fail("the effect is a dict, but the first group has no options to pick by")
            allowed = {o.lower() for o in first}
            for key in self.template:
                if key != "default" and key not in allowed:
                    fail(f"{key!r} is not an option of the first group {first}")
        level = self.pattern.level_group()
        level_options = options[level] if level is not None else None
        for template in templates:
            for g in BLANK.finditer(template):
                if not 1 <= int(g.group(1)) <= len(options):
                    fail(f"{g.group(0)} in {template!r}, but the pattern has {len(options)} group(s)")
            for g in LEVELS.finditer(template):
                if level_options is None:
                    fail(f"{g.group(0)} in {template!r}, but the pattern has no level group like (1|2|3)")
                if len(g.group(1).split(",")) != len(level_options):
                    fail(f"{g.group(0)} in {template!r} needs {len(level_options)} values, one per {level_options}")

@dataclass
class Match:
    effect: str
    effect_type: str
    text: str  # the official text, e.g. "Vigor +2"
    values: list[str]  # per group, the option that matched as written, e.g. ["Vigor", "2"]
    description: str  # filled in, e.g. "Increase Maximum HP by 40"
    stackable: bool | None
    box: Box | None = None  # where it is on screen (match_lines only; both lines for a wrapped effect)
