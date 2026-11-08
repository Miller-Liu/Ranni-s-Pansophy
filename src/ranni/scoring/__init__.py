"""Effect names -> a score, from settings/builds.json.

builds.json:
    {
      "Ironeye bleed": {
        "scores": {"Improved Critical Hits": 5, "Faith +1": 2},
        "forbid": ["Improved Dragon Cult Incantations"]
      },
      "Another build": {...}
    }

A relic's score for one build is the sum of its effects' points (unlisted effects are 0).
A build is ruled out if the relic has any of its forbidden effects.
The relic's score is the best score over the builds that aren't ruled out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Build:
    name: str
    scores: dict[str, float]
    forbid: frozenset[str] = frozenset()


@dataclass
class Score:
    total: float | None  # None: every build forbids this relic (or there are no builds)
    build: str | None  # the build that gave the best total
    points: dict[str, float] = field(default_factory=dict)  # effect -> points in that build
    forbidden_by: list[str] = field(default_factory=list)  # builds ruled out


def load_builds(path: str | Path) -> list[Build]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Build(name, dict(b.get("scores", {})), frozenset(b.get("forbid", []))) for name, b in raw.items()]


def known_effects(builds: list[Build]) -> list[str]:
    """Every effect name mentioned in any build: what Ranni tries to recognize on screen."""
    names = {e for b in builds for e in b.scores} | {e for b in builds for e in b.forbid}
    return sorted(names)


def score_relic(effects: list[str], builds: list[Build]) -> Score:
    best = Score(total=None, build=None)
    for build in builds:
        if any(e in build.forbid for e in effects):
            best.forbidden_by.append(build.name)
            continue
        total = sum(build.scores.get(e, 0) for e in effects)
        if best.total is None or total > best.total:
            best.total, best.build = total, build.name
            best.points = {e: build.scores.get(e, 0) for e in effects}
    return best
