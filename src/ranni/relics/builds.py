"""
Scorer: how good a relic is for your builds in settings/builds.json.

builds.json lists, for each character and each of their builds, how many points each effect is worth. Effects are
written exactly as the game writes them (their official text), in one of three sections:
    {
      "Duchess": {
        "Favorite Build": {
          "normal effect": {"Improve Daggers Attack Power": 9, "Magic Attack Up +2": 9},
          "deep effect":   {"Dormant Power Helps Discover @weapon": -1},
          "deep curse":    {"Reduced Vigor and Arcane": 0, "Reduced Rune Acquisition": -2}
        }
      }
    }
"normal effect" is for effects.json; "deep effect" and "deep curse" are for deep_effects.json (curses are its
"Curse" section). @name leaves a named group open: "@weapon" means any weapon. A specific entry wins over it.

How a relic is scored:
  - For each build, add up the points of the relic's effects and curses. An effect that isn't listed is worth 0.
  - A curse that isn't listed is one the build can't live with: the relic is ruled out for that build.
  - The relic's score is the best total among the builds that aren't ruled out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

from ranni.relics.effect import Kind, Match
from ranni.relics.manager import EffectManager

SECTIONS: dict[str, Kind] = {"normal effect": "normal", "deep effect": "deep", "deep curse": "curse"}


class BuildsError(ValueError):
    """A mistake in builds.json."""


@dataclass
class Score:
    total: float | None  # the best build's total; None if every build is ruled out (or there are no builds)
    build: str | None  # that build, e.g. "Duchess: Favorite Build"
    points: dict[str, float] = field(default_factory=dict)  # each effect's (official text's) points in that build
    ruled_out_by: list[str] = field(default_factory=list)  # the builds with a curse they don't list


class Build:
    """One build of one character: how many points each effect and curse is worth."""

    def __init__(self, character: str, name: str, sections: dict[str, dict[str, float]], manager: EffectManager):
        self.character = character
        self.name = name
        self.points: dict[tuple[Kind, str], float] = {}  # (kind, official text, see _key) -> points; texts with @name are wildcards
        for section, effects in sections.items():
            if section not in SECTIONS:
                self._fail(f"{section!r} isn't a section; use one of {list(SECTIONS)}")
            kind = SECTIONS[section]
            for text, points in effects.items():
                if not isinstance(points, (int, float)):
                    self._fail(f"{text!r}: points must be a number, not {points!r}")
                self._check(text, kind, manager)
                self.points[(kind, self._key(text))] = float(points)

    def __str__(self) -> str:
        return f"{self.character}: {self.name}"

    @staticmethod
    def _key(official_text: str) -> str:
        """Ignore case and extra spaces when looking an effect up, so "vigor  +2" still finds "Vigor +2"."""
        return " ".join(official_text.lower().split())

    def effect_points(self, effect: Match) -> float | None:
        """
        What the effect is worth in this build: its own entry, or else a wildcard entry that fits it.
        Not listed: 0 for an effect, None for a curse (the build can't take it).
        """
        for text in [effect.official_text, *effect.wildcard_texts()]:
            points = self.points.get((effect.kind, self._key(text)))
            if points is not None:
                return points
        return None if effect.kind == "curse" else 0

    def _check(self, text: str, kind: Kind, manager: EffectManager) -> None:
        """
        Stop with a BuildsError if an entry isn't an effect of its section, written the way the game writes it.
        Otherwise a typo would never match anything and quietly be worth 0 forever.
        """
        deep = kind != "normal"
        file = "deep_effects.json" if deep else "effects.json"
        if "@" in text:
            self._check_wildcard(text, kind, manager)
            return
        match = manager.match(text, deep=deep)
        if match is None:
            self._fail(f"{text!r} isn't an effect in {file}")
        if self._key(match.official_text) != self._key(text):
            self._fail(f"{text!r} isn't written the way the game writes it; did you mean {match.official_text!r}?")
        if match.kind != kind:
            section_of = {k: s for s, k in SECTIONS.items()}
            self._fail(f"{text!r} is a {section_of[match.kind]!r}, but it's under {section_of[kind]!r}")

    def _check_wildcard(self, text: str, kind: Kind, manager: EffectManager) -> None:
        """A wildcard fits if putting one of the group's options in place of @name gives an effect of this kind."""
        for effect in manager.effects(kind != "normal"):
            if effect.kind != kind:
                continue
            for name, group in effect.pattern.names.items():
                options = effect.pattern.options[group]
                if f"@{name}" not in text or options is None:
                    continue
                match = manager.match(text.replace(f"@{name}", options[0]), deep=kind != "normal")
                if match is not None and match.effect is effect and self._key(text) in map(self._key, match.wildcard_texts()):
                    return
        self._fail(f"{text!r} doesn't fit any effect: @name must be the name of one of its groups, like @weapon in "
                   f"\"Dormant Power Helps Discover (?P<weapon>...)\"")

    def _fail(self, problem: str) -> NoReturn:
        raise BuildsError(f"builds.json, {self}: {problem}")


class Scorer:
    """Every build in builds.json, checked against the effects EffectManager knows."""

    def __init__(self, builds_path: str | Path, manager: EffectManager):
        characters = json.loads(Path(builds_path).read_text(encoding="utf-8"))
        self.builds = [Build(character, name, sections, manager)
                       for character, builds in characters.items() for name, sections in builds.items()]

    def score(self, effects: list[Match]) -> Score:
        """The score of a relic with these effects and curses: the best build's total."""
        best = Score(total=None, build=None)
        for build in self.builds:
            points = {e.official_text: build.effect_points(e) for e in effects}
            if any(p is None for p in points.values()):
                best.ruled_out_by.append(str(build))
                continue
            listed = {text: p for text, p in points.items() if p is not None}
            total = sum(listed.values())
            if best.total is None or total > best.total:
                best.total, best.build, best.points = total, str(build), listed
        return best
