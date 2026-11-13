"""Effects -> a score, from the tier lists in settings/builds.json.

builds.json, one tier list per character, effects by their official text (as EffectManager gives it):
    {
      "Ironeye": {
        "10": ["[Ironeye] Extends duration of weak point"],
        "5": ["Improved Critical Hits"],
        "-1": ["Improved Dragon Cult Incantations"]
      },
      "Revenant": {...}
    }

A relic's score for one character is the sum of its effects' tiers (unlisted effects are 0).
An effect in the -1 tier rules that character out.
The relic's score is the best score over the characters that aren't ruled out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

AVOID = -1  # tier that rules a character out


def _key(effect: str) -> str:
    """Tier lists don't need exact case or spacing: "vigor  +2" is "Vigor +2"."""
    return " ".join(effect.lower().split())


@dataclass
class Score:
    total: float | None  # None: every character rules this relic out (or there are no tier lists)
    build: str | None  # the character that gave the best total
    points: dict[str, float] = field(default_factory=dict)  # effect -> points for that character
    forbidden_by: list[str] = field(default_factory=list)  # characters ruled out


class TierList:
    """One character's tier list."""

    def __init__(self, name: str, tiers: dict[str, list[str]]):
        self.name = name
        self.tiers = {_key(e): float(tier) for tier, effects in tiers.items() for e in effects}  # effect -> tier

    def points(self, effect: str) -> float:
        """The effect's tier, 0 if it isn't listed."""
        return self.tiers.get(_key(effect), 0)

    def rules_out(self, effects: list[str]) -> bool:
        """True if any of the effects is in the -1 tier."""
        return any(self.points(e) == AVOID for e in effects)


class Scorer:
    """Every character's tier list, from builds.json."""

    def __init__(self, tier_lists: list[TierList]):
        self.tier_lists = tier_lists

    @classmethod
    def load(cls, builds_path: str | Path) -> Scorer:
        raw = json.loads(Path(builds_path).read_text(encoding="utf-8"))
        return cls([TierList(name, tiers) for name, tiers in raw.items()])

    def score(self, effects: list[str]) -> Score:
        """The best character's total for a relic with these effects."""
        best = Score(total=None, build=None)
        for tier_list in self.tier_lists:
            if tier_list.rules_out(effects):
                best.forbidden_by.append(tier_list.name)
                continue
            points = {e: tier_list.points(e) for e in effects}
            total = sum(points.values())
            if best.total is None or total > best.total:
                best.total, best.build, best.points = total, tier_list.name, points
        return best
