"""
EffectPattern: how the game writes one effect, and everything to do with regular expressions for it.
No other file builds or reads a regex for effects.
"""

from __future__ import annotations

import re

import regex  # like re, but can also match with typos ("fuzzy")


class EffectPattern:
    """
    A pattern from effects.json, like "(?P<stat>Vigor|Mind) \\+(1|2|3)". It has fixed words, and groups in brackets that
    can be one of several options (or, for ([^\\d]+), any text).

    To know which option a line used, even when OCR made a typo, each option gets its own little named group.
    The result is called the selector:
        "(Vigor|Mind) \\+(1|2)"  ->  "(?:(?P<g1_0>Vigor)|(?P<g1_1>Mind))\\s*\\+(?:(?P<g2_0>1)|(?P<g2_1>2))"
    After a match, whichever g1_... group caught something says which option it was (g1_0 = Vigor).
    Spaces become \\s* (any number of spaces, or none), because OCR often adds or drops a space.
    """
    # Finds each group in a pattern: (a|b|c), ([^\d]+), or a named one, (?P<status>a|b|c).
    # Skips (?:...) and escaped brackets \( \), which are part of the text, not groups.
    GROUP = re.compile(r"(?<!\\)\((?:\?P<(\w+)>)?(?!\?)([^()]*)\)")

    @staticmethod
    def _unescape(text: str) -> str:
        """Remove the regex backslashes: "Vigor \\+2" -> "Vigor +2"."""
        return re.sub(r"\\(.)", r"\1", text)

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.options: list[list[str] | None] = []  # each group's options, in order; None for a group that takes any text
        self.names: dict[str, int] = {}  # the groups that have a name, for descriptions: {"stat": 0} means @stat is group 0

        def to_selector(group: re.Match[str]) -> str:
            n = len(self.options) + 1
            name, body = group.group(1), group.group(2)
            if name:
                self.names[name] = n - 1
            if "|" not in body:  # any text, like ([^\d]+)
                self.options.append(None)
                return f"(?P<g{n}>{body})"
            options = body.split("|")
            self.options.append(options)
            return "(?:" + "|".join(f"(?P<g{n}_{i}>{option})" for i, option in enumerate(options)) + ")"

        self.selector = re.compile(self.GROUP.sub(to_selector, pattern).replace(" ", r"\s*"), re.IGNORECASE)
        # Just the words that never change, for a quick "does this line look anything like it" check:
        # "Improve (Daggers|...) attack power" -> "Improve attack power"
        self.fixed_text = " ".join(self._unescape(self.GROUP.sub(" ", pattern)).split())
        self._fuzzy: dict[int, regex.Pattern[str]] = {}  # the selector allowing N typos, made the first time it's needed (making one is slow)

    def exact(self, text: str) -> re.Match[str] | None:
        """The match if the whole line is exactly this effect (ignoring case and spaces), else None."""
        return self.selector.fullmatch(text)

    def fuzzy(self, text: str, max_errors: int) -> regex.Match[str] | None:
        """
        The match if the whole line is this effect with at most max_errors typos, else None.
        A typo is one letter added, removed or changed; digits never count as typos, so "+2" can't be read as "+3".
        It finds the match with the fewest typos, and m.fuzzy_counts says how many there were.
        """
        if max_errors not in self._fuzzy:
            self._fuzzy[max_errors] = regex.compile(
                f"(?:{self.selector.pattern}){{e<={max_errors}:[^\\d]}}", regex.IGNORECASE | regex.BESTMATCH)
        return self._fuzzy[max_errors].fullmatch(text)

    def read(self, m: re.Match[str] | regex.Match[str]) -> tuple[list[str], list[int | None]]:
        """
        What each group read, from a match. Returns the values and the option numbers:
            "Vigcr +2" -> values ["Vigor", "2"], indices [0, 1]
        Values are the options as written in the pattern, so typos are gone ("Vigcr" -> "Vigor").
        A group that takes any text keeps what was read, and has no option number (None).
        """
        values: list[str] = []
        indices: list[int | None] = []
        for n, options in enumerate(self.options, 1):
            if options is None:
                values.append(m.group(f"g{n}").strip())  # ([^\d]+) also catches the spaces around it
                indices.append(None)
            else:
                i = next(i for i in range(len(options)) if m.group(f"g{n}_{i}") is not None)
                values.append(options[i])
                indices.append(i)
        return values, indices

    def official_text(self, values: list[str]) -> str:
        """
        The effect exactly as the game writes it: the pattern with each group replaced by what it read.
            "(Vigor|Mind) \\+(1|2|3)" with ["Vigor", "2"] -> "Vigor +2"
        """
        remaining = iter(values)
        return self._unescape(self.GROUP.sub(lambda group: next(remaining), self.pattern))

    def level_group(self) -> int | None:
        """
        Which group is the effect's level, like the (1|2|3) in "Vigor \\+(1|2|3)": the last group whose options are all
        numbers. None if the effect has no levels.
        """
        for n in reversed(range(len(self.options))):
            options = self.options[n]
            if options and all(o.isdigit() for o in options):
                return n
        return None
