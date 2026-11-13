import json
from pathlib import Path

import pytest

from ranni.effects import EffectManager, EffectsError, Match
from ranni.ocr.engine import OcrLine

ROOT = Path(__file__).parent.parent
REGULAR = EffectManager(ROOT / "settings" / "effects.json")
DEEP = EffectManager(ROOT / "settings" / "deep_effects.json")


def _match(manager: EffectManager, line: str) -> Match:
    """The match, failing the test if there is none."""
    m = manager.match(line)
    assert m is not None, line
    return m


def _lines(name):
    return [l.strip() for l in (ROOT / "tests" / name).read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.mark.parametrize("matcher, name", [(REGULAR, "relic_effects.txt"), (DEEP, "deep_relic_effects.txt")])
def test_every_listed_effect_matches_and_reads_back(matcher, name):
    for line in _lines(name):
        m = matcher.match(line)
        assert m is not None, line
        assert m.text.lower() == line.lower(), line


def test_ocr_mistakes_snap_to_the_options_as_written():
    m = _match(REGULAR, "VIGCR  +2")
    assert (m.text, m.values) == ("Vigor +2", ["Vigor", "2"])
    m = _match(REGULAR, "Attack power permanentiy increased for each evergaol prisoner defeated")
    assert m.text == "Attack power permanently increased for each evergaol prisoner defeated"


def test_spaces_dont_matter():
    assert _match(REGULAR, "Vigor+2").text == "Vigor +2"
    assert _match(REGULAR, "Improved BloodLoss Resistance").text == "Improved Blood Loss Resistance"


def test_numbers_must_match_exactly():
    assert _match(REGULAR, "Faith +1").text == "Faith +1"
    assert REGULAR.match("Faith +4") is None


def test_a_stray_icon_character_is_ignored():
    assert _match(REGULAR, "@ Faith +1").text == "Faith +1"


def test_unrelated_text_is_ignored():
    for line in ["Sell", "Small Jar Bazaar", "Polished Burning Scene", "Sort by acquisition order"]:
        assert REGULAR.match(line) is None, line


def test_description_is_filled_in():
    assert _match(REGULAR, "Vigor +2").description == "Increase Maximum HP by 40"  # dict by the first group, level 2
    assert _match(REGULAR, "Strength +3").description == "Increase Strength by 3"  # default, @1
    assert _match(DEEP, "Physical Attack Up +4").description == "Increases physical damage by 1.12x"  # (3|4): 4 is index 1
    assert "[MaxHP * 0.005]" in _match(REGULAR, "Slowly restore HP for self and nearby allies when HP is low").description


def test_free_text_keeps_what_was_read():
    m = _match(REGULAR, "Crimson Crystal Tear in possession at start of expedition")
    assert m.values == ["Crimson Crystal Tear"]


def test_wrapped_effect_is_joined_with_the_line_below():
    lines = [OcrLine("Polished Burning Scene", 990, (846, 975, 300, 30)),
             OcrLine("Attack power permanently increased for each", 1040, (846, 1025, 457, 30)),
             OcrLine("evergaol prisoner defeated", 1075, (846, 1060, 311, 30)),
             OcrLine("Faith +1", 1110, (846, 1095, 120, 30))]
    found = REGULAR.match_lines(lines)
    assert [m.text for m in found] == ["Attack power permanently increased for each evergaol prisoner defeated", "Faith +1"]
    assert found[0].box == (846, 1025, 457, 65)


def _load(tmp_path, entry):
    path = tmp_path / "effects.json"
    path.write_text(json.dumps({"Test": [{"name": "Test effect", "stackable": True, **entry}]}))
    return EffectManager(path)


def test_mistakes_in_effects_json_are_reported(tmp_path):
    bad = [
        {"pattern": "Improved (Poison|Frostbite) Resistance", "effect": {"frost": "..."}},  # key is not an option
        {"pattern": "Improved (Poison|Frostbite) Resistance", "effect": "@2 resistance"},  # only 1 group
        {"pattern": "Faith \\+(1|2|3)", "effect": "Increase by [1, 2]"},  # 3 levels, 2 values
        {"pattern": "Physical Attack Up", "effect": "by [1.04x, 1.05x]"},  # no level group
        {"pattern": "Improved (Poison", "effect": ""},  # not a valid regex
    ]
    for entry in bad:
        with pytest.raises(EffectsError):
            _load(tmp_path, entry)
    _load(tmp_path, {"pattern": "Faith \\+(1|2|3)", "effect": "Restores [MaxHP * 0.005] by [1, 2, 3]"})  # fine
