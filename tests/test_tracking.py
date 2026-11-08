import numpy as np

from ranni.tracking import TileMemory


def _look(seed):
    t = np.random.default_rng(seed).random((12, 12)).astype(np.float32) * 255
    return t - t.mean()


A, B, C, D = (_look(i) for i in range(4))


def test_remembered_tile_is_recalled():
    m = TileMemory()
    m.remember([A, B, C], 1, "7")
    assert m.recall([A, B, C]) == {1: "7"}


def test_label_follows_the_tile_when_the_list_scrolls():
    m = TileMemory()
    m.remember([A, B, C], 1, "7")
    assert m.recall([D, A, B, C]) == {2: "7"}


def test_identical_looking_relics_are_told_apart_by_their_neighbours():
    m = TileMemory()
    m.remember([A, B, A, C], 0, "5")
    m.remember([A, B, A, C], 2, "9")
    assert m.recall([A, B, A, C]) == {0: "5", 2: "9"}
    # Sell B: both A's keep the right score.
    assert m.recall([A, A, C]) == {0: "5", 1: "9"}


def test_no_label_when_nothing_around_it_matches():
    m = TileMemory()
    m.remember([A, B, C], 1, "7")
    assert m.recall([D, B, D]) == {}
