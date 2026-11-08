from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

# ----- LOADING EFFECTS -----
@dataclass
class Effect:
    name: str 
    effect_type: str
    regex: re.Pattern
    template: str | dict | None  # description with blanks (@group, [a, b, c]); a dict picks one by the first group
    stackable: bool
    spellings: list[dict[str, str]]  # per group: normalized spelling -> the option as written, e.g. {"vigor": "Vigor"}

GROUP = re.compile(r"(?<!\\)\((?:\?P<\w+>)?(?!\?)([^()]*)\)")  # a simple group: (a|b|c) or (?P<name>a|b|c), not (?:...) or \(...\)
def _spellings(pattern: str) -> list[dict[str, str]]:
    """
    For each group in the pattern, in order: normalized spelling -> the option as written.
    "(?P<stat>Vigor|Blood Loss) \\+(1|2)" -> [{"vigor": "Vigor", "bloodloss": "Blood Loss"}, {"1": "1", "2": "2"}]
    """
    return [
        {option.lower().replace(" ", ""): option for option in inner.split("|")} 
        for inner in GROUP.findall(pattern)
    ]

def _split_options(pattern: str) -> str:
    """
    Give each option of a group its own named group, so a match tells which option it was, even a fuzzy one.
    "(?P<stat>Vigor|Mind) \\+(1|2)" -> "(?:(?P<stat_0>Vigor)|(?P<stat_1>Mind)) \\+(?:(?P<g2_0>1)|(?P<g2_1>2))"
    Groups without options, like (?P<item>[^\\d]+), stay as they are.
    """
    position = 0
    def split(g: re.Match) -> str:
        nonlocal position
        position += 1
        if "|" not in g.group(1):
            return g.group(0)
        named = re.match(r"\(\?P<(\w+)>", g.group(0))
        name = named.group(1) if named else f"g{position}"  # unnamed groups are named by their position
        options = [f"(?P<{name}_{i}>{option})" for i, option in enumerate(g.group(1).split("|"))]
        return f"(?:{'|'.join(options)})"
    return GROUP.sub(split, pattern)

def load_effects(effects_path: str | Path) -> list[Effect]:
    """Load list of effects from effects.json file"""
    all_effects = json.loads(Path(effects_path).read_text(encoding="utf-8"))
    effects = []
    for effect_type, entries in all_effects.items():
        for entry in entries:
            pattern = entry["pattern"].replace(" ", r"\s*")  # spaces are optional
            compiled = re.compile(pattern, re.IGNORECASE)
            effects.append(Effect(entry["name"], effect_type, compiled, entry["effect"], entry["stackable"], _spellings(entry["pattern"])))
    return effects

# ----- PRINTING -----
Show = Literal["name", "regex"]
SHOW: dict[str, Callable[[Effect], str]] = {
    "name": lambda e: e.name,
    "regex": lambda e: e.regex.pattern,
}
def print_effects(effects: list[Effect], show: Show = "name") -> None:
    """Print every effect grouped by effect type (its name, regex, ...), for debugging."""
    grouped: dict[str, list[Effect]] = {}
    for e in effects:
        grouped.setdefault(e.effect_type, []).append(e)
    print("-" * 25)
    print(f"Loaded {len(effects)} effects:")
    for effect_type, entries in grouped.items():
        print(f"\n{effect_type} ({len(entries)} items):")
        for e in entries:
            print(f"  {SHOW[show](e)}")
    print("-" * 25)
