import json

from ranni.scoring import Scorer, TierList

SCORER = Scorer([
    TierList("Ironeye", {"5": ["Improved Critical Hits"], "6": ["Stating armament inflicts Blood Loss status"],
                         "-1": ["Improved Dragon Cult Incantations"]}),
    TierList("Revenant", {"7": ["Improved Dragon Cult Incantations"], "3": ["Faith +1"]}),
])


def test_score_is_the_best_character():
    s = SCORER.score(["Improved Critical Hits", "Faith +1"])
    assert (s.total, s.build) == (5, "Ironeye")
    assert s.points == {"Improved Critical Hits": 5, "Faith +1": 0}


def test_avoid_tier_rules_a_character_out():
    s = SCORER.score(["Improved Critical Hits", "Improved Dragon Cult Incantations"])
    assert (s.total, s.build) == (7, "Revenant")
    assert s.forbidden_by == ["Ironeye"]


def test_ruled_out_by_every_character():
    s = Scorer([TierList("Only", {"-1": ["X"]})]).score(["X"])
    assert s.total is None and s.forbidden_by == ["Only"]


def test_tier_lists_load_with_any_case_and_spacing(tmp_path):
    path = tmp_path / "builds.json"
    path.write_text(json.dumps({"Revenant": {"8": ["Improved  Dragon Cult Incantations"], "-1": ["vigor +2"]}}))
    scorer = Scorer.load(path)
    assert scorer.score(["Improved Dragon Cult Incantations"]).total == 8
    assert scorer.score(["Vigor +2"]).forbidden_by == ["Revenant"]
