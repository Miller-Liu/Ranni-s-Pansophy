from ranni.scoring import Build, known_effects, score_relic

BUILDS = [
    Build("Bleed", {"Improved Critical Hits": 5, "Starting armament inflicts blood loss": 6},
          frozenset({"Improved Dragon Cult Incantations"})),
    Build("Faith", {"Improved Dragon Cult Incantations": 7, "Faith +1": 3}),
]


def test_score_is_the_best_build():
    s = score_relic(["Improved Critical Hits", "Faith +1"], BUILDS)
    assert (s.total, s.build) == (5, "Bleed")
    assert s.points == {"Improved Critical Hits": 5, "Faith +1": 0}


def test_forbidden_effect_rules_a_build_out():
    s = score_relic(["Improved Critical Hits", "Improved Dragon Cult Incantations"], BUILDS)
    assert (s.total, s.build) == (7, "Faith")
    assert s.forbidden_by == ["Bleed"]


def test_forbidden_by_every_build():
    s = score_relic(["X"], [Build("Only", {"X": 9}, frozenset({"X"}))])
    assert s.total is None and s.forbidden_by == ["Only"]


def test_known_effects_include_forbidden_ones():
    assert "Improved Dragon Cult Incantations" in known_effects(BUILDS)
