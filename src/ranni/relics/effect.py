"""
Effect: one effect from effects.json or deep_effects.json, e.g. "Vigor +1/+2/+3", and the text that explains what it does.
Match: what EffectManager gives back when it recognizes an effect in a line of text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, NoReturn

from ranni.relics.pattern import EffectPattern

# The two kinds of blanks a description can have:
NAME_BLANK = re.compile(r"@(\w+)")  # "@status" becomes what the group named status read, e.g. "Rot"
LEVEL_LIST = re.compile(r"\[([^\[\]]*,[^\[\]]*)\]")  # "[20, 40, 60]" becomes the one for the effect's level (+1, +2 or +3)
# (brackets without a comma, like "[MaxHP * 0.005]", are normal text and stay as they are)


Kind = Literal["normal", "deep", "curse"]  # from effects.json; from deep_effects.json; the Curse section of deep_effects.json


class EffectsError(ValueError):
    """A mistake in effects.json."""


@dataclass
class Effect:
    name: str  # our name for it, e.g. "Increase stat"
    category: str  # the section of the json file it's in, e.g. "Stat boost"
    kind: Kind  # a normal relic's effect, a deep relic's effect, or a deep relic's curse
    pattern: EffectPattern  # how the game writes it, e.g. "(?P<stat>Vigor|Mind|...) \+(1|2|3)"
    descriptions: dict[str, str]  # what it does, by the named group's value, e.g. {"vigor": "Increase Maximum HP by [20, 40, 60]", "default": "Increase @stat by [1, 2, 3]"}
    stackable: bool | None  # whether two of it add up; None when it depends (see note)
    note: str | None
    pick_by: int | None = field(init=False, default=None)  # the group whose value picks the description; None if there's only "default"

    def __post_init__(self):
        self.check()
        if any(key != "default" for key in self.descriptions):
            self.pick_by = next(iter(self.pattern.names.values()))  # check() made sure there's exactly one named group

    def description(self, values: list[str], indices: list[int | None]) -> str:
        """
        What the effect does, for what was read. For "Vigor +2" (values ["Vigor", "2"], indices [0, 1]):
          1. Pick the description for what @stat read, "vigor" (or "default")   -> "Increase Maximum HP by [20, 40, 60]"
          2. Fill each @name with what that group read                          -> nothing to fill here
          3. Fill each [a, b, c] with the one for the level: +2 is the 2nd      -> "Increase Maximum HP by 40"
        """
        key = values[self.pick_by].lower() if self.pick_by is not None else "default"
        text = self.descriptions.get(key, self.descriptions.get("default", ""))

        text = NAME_BLANK.sub(lambda blank: values[self.pattern.names[blank.group(1)]], text)

        level = self.pattern.level_group()
        which = indices[level] if level is not None else None  # 0 for +1, 1 for +2, ...
        if which is not None:
            text = LEVEL_LIST.sub(lambda blank: [v.strip() for v in blank.group(1).split(",")][which], text)
        return text

    def check(self) -> None:
        """
        Stop with an EffectsError if a description could never be filled in. That way a typo in effects.json shows up
        as soon as Ranni starts, instead of as a wrong description in the middle of a game.
        """
        def fail(problem: str) -> NoReturn:
            raise EffectsError(f"effects.json, {self.name!r}: {problem}")

        # A dict of descriptions, like {"vigor": "...", "mind": "...", "default": "..."}, is picked from by what the
        # named group read ("Vigor" picks "vigor"). For that to work:
        keys = [key for key in self.descriptions if key != "default"]
        if keys:
            # 1. There's exactly one named group. With none there's nothing to pick by; with two we wouldn't know which.
            if len(self.pattern.names) != 1:
                fail(f"the description is picked by a named group's value, so the pattern needs exactly one named group, "
                     f"like (?P<stat>Vigor|Mind), but it has {len(self.pattern.names)}")
            name, group = next(iter(self.pattern.names.items()))
            options = self.pattern.options[group]
            # 2. That group is a list of options, like (?P<stat>Vigor|Mind), not any text, like (?P<item>[^\d]+).
            if options is None:
                fail(f"the description is picked by @{name}, but that group takes any text, so there's nothing to pick from")
            # 3. Every key is one of those options (catches typos like "frost" for "Frostbite").
            for key in keys:
                if key not in {o.lower() for o in options}:
                    fail(f"{key!r} is not an option of @{name}: {options}")

        # Every blank in every description can be filled in:
        level = self.pattern.level_group()
        levels = self.pattern.options[level] if level is not None else None
        for text in self.descriptions.values():
            # @name: there's a group with that name, (?P<name>...).
            for blank in NAME_BLANK.finditer(text):
                if blank.group(1) not in self.pattern.names:
                    fail(f"{blank.group(0)} in {text!r}, but no group is named {blank.group(1)!r}: write it as (?P<{blank.group(1)}>...)")
            # [a, b, c]: the effect has a level, like \+(1|2|3), and there's one value for each level.
            for blank in LEVEL_LIST.finditer(text):
                if levels is None:
                    fail(f"{blank.group(0)} in {text!r}, but the pattern has no level like \\+(1|2|3)")
                if len(blank.group(1).split(",")) != len(levels):
                    fail(f"{blank.group(0)} in {text!r} needs {len(levels)} values, one for each of {levels}")


@dataclass
class Match:
    effect: Effect = field(repr=False)  # the effect it is
    official_text: str  # exactly how the game writes it, typos fixed, e.g. "Vigor +2" (builds.json uses this)
    values: list[str]  # what each group read, e.g. ["Vigor", "2"]
    description: str  # what it does, filled in, e.g. "Increase Maximum HP by 40"

    @property
    def kind(self) -> Kind:
        return self.effect.kind

    def wildcard_texts(self) -> list[str]:
        """
        The official text with a named group left open, the way builds.json writes "any of these":
            "Dormant Power Helps Discover Daggers" -> ["Dormant Power Helps Discover @weapon"]
        """
        texts: list[str] = []
        for name, group in self.effect.pattern.names.items():
            values = list(self.values)
            values[group] = f"@{name}"
            texts.append(self.effect.pattern.official_text(values))
        return texts
