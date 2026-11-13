"""EffectPattern: everything about regular expressions. Nothing else in Ranni builds or reads a regex for effects."""

from __future__ import annotations

import re

import regex  # like re, plus fuzzy matching


class EffectPattern:
    """
    A pattern from effects.json, e.g. "(Vigor|Mind) \\+(1|2|3)", turned into a selector: a regex where each option of
    each group is its own named group, so a match tells which option it was, even a fuzzy one.
    "(Vigor|Mind) \\+(1|2)" -> "(?:(?P<g1_0>Vigor)|(?P<g1_1>Mind))\\s*\\+(?:(?P<g2_0>1)|(?P<g2_1>2))"
    Spaces match any number of spaces (or none), so OCR adding or dropping a space doesn't matter.
    """
    GROUP = re.compile(r"(?<!\\)\((?!\?)([^()]*)\)")  # a simple group: (a|b|c) or ([^\d]+), not (?:...) or \(...\)

    @staticmethod
    def _unescape(text: str) -> str:
        return re.sub(r"\\(.)", r"\1", text)  # "Vigor \+2" -> "Vigor +2"

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.options: list[list[str] | None] = []  # per group, its options as written; None for free text like ([^\d]+)
        def split(g: re.Match) -> str:
            n = len(self.options) + 1
            if "|" not in g.group(1):
                self.options.append(None)
                return f"(?P<g{n}>{g.group(1)})"
            options = g.group(1).split("|")
            self.options.append(options)
            return "(?:" + "|".join(f"(?P<g{n}_{i}>{option})" for i, option in enumerate(options)) + ")"
        self.selector = re.compile(self.GROUP.sub(split, pattern).replace(" ", r"\s*"), re.IGNORECASE)
        # the words that never change, for the quick similarity check: "Improve (Daggers|...) attack power" -> "Improve attack power"
        self.fixed_text = " ".join(self._unescape(self.GROUP.sub(" ", pattern)).split())
        self._fuzzy: dict[int, regex.Pattern] = {}  # max_errors -> compiled fuzzy selector, built when first needed

    def exact(self, text: str) -> re.Match | None:
        return self.selector.fullmatch(text)

    def fuzzy(self, text: str, max_errors: int) -> regex.Match | None:
        """
        The closest match within max_errors edits (never on digits); m.fuzzy_counts says how many.
        BESTMATCH makes it find the fewest edits, not just any match. Each compiled version is kept: compiling is slow.
        """
        if max_errors not in self._fuzzy:
            self._fuzzy[max_errors] = regex.compile(
                f"(?:{self.selector.pattern}){{e<={max_errors}:[^\\d]}}", regex.IGNORECASE | regex.BESTMATCH)
        return self._fuzzy[max_errors].fullmatch(text)

    def read(self, m: re.Match | regex.Match) -> tuple[list[str], list[int | None]]:
        """
        Per group, the option whose group matched ("Vigcr" -> "Vigor") and its index; free text keeps what was read (no index).
        """
        values, indices = [], []
        for n, options in enumerate(self.options, 1):
            if options is None:
                values.append(m.group(f"g{n}").strip())  # [^\d]+ also takes the spaces around it
                indices.append(None)
            else:
                i = next(i for i in range(len(options)) if m.group(f"g{n}_{i}") is not None)
                values.append(options[i])
                indices.append(i)
        return values, indices

    def official_text(self, values: list[str]) -> str:
        """
        The effect as the game writes it: the pattern with each group replaced by its value.
        "(Vigor|Mind) \\+(1|2|3)" with ["Vigor", "2"] -> "Vigor +2"
        """
        remaining = iter(values)
        return self._unescape(self.GROUP.sub(lambda g: next(remaining), self.pattern))

    def level_group(self) -> int | None:
        """Index of the group that is the level (the last group of only numbers, like \\+(1|2|3)), if any."""
        for n in reversed(range(len(self.options))):
            options = self.options[n]
            if options and all(o.isdigit() for o in options):
                return n
        return None
