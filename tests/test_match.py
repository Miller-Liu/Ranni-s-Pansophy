from ranni.ocr.engine import OcrLine
from ranni.scoring.match import match_effects, snap

KNOWN = ["Faith +1", "Improved Critical Hits",
         "Changes compatible armament's incantation to Beast Claw at start of expedition"]


def test_snap_absorbs_ocr_mistakes():
    assert snap("lmproved Critical Hlts", KNOWN) == "Improved Critical Hits"


def test_snap_ignores_a_stray_icon_character():
    assert snap("@ Improved Critical Hits", KNOWN) == "Improved Critical Hits"


def test_numbers_must_match_exactly():
    assert snap("Faith +1", KNOWN) == "Faith +1"
    assert snap("Faith +2", KNOWN) is None


def test_unrelated_text_is_ignored():
    assert match_effects([OcrLine("Small Jar Bazaar", 10, (0, 0, 100, 20))], KNOWN) == []


def test_wrapped_effect_is_joined_with_the_line_below():
    lines = [OcrLine("Changes compatible armament's incantation to", 1040, (846, 1015, 457, 30)),
             OcrLine("Beast Claw at start of expedition", 1075, (846, 1050, 311, 30))]
    [found] = match_effects(lines, KNOWN)
    assert found.name == KNOWN[2]
    assert found.box == (846, 1015, 457, 65)
