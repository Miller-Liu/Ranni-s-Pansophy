"""The full scan on real screenshots, with a fake OCR engine returning the text visible in them."""

from pathlib import Path

import cv2
import pytest

from ranni.ocr.engine import OcrLine
from ranni.effects import EffectManager
from ranni.scan import scan
from ranni.scoring import Scorer, TierList
from ranni.tracking import TileMemory

SAMPLES = Path(__file__).parent.parent / "samples"
MANAGER = EffectManager(Path(__file__).parent.parent / "settings" / "effects.json")
SCORER = Scorer([TierList("Revenant", {"7": ["Improved Dragon Cult Incantations"], "3": ["Faith +1"]})])
END_SCREEN_TEXT = [
    OcrLine("Polished Burning Scene", 825, (507, 803, 436, 45)),
    OcrLine("Improved Dragon Cult Incantations", 903, (575, 880, 555, 47)),
    OcrLine("Faith +1", 1030, (577, 1012, 131, 40)),
]


class FakeOcr:
    max_height = 10_000

    def __init__(self, lines):
        self.lines = lines

    def recognize(self, image):
        return [OcrLine(l.text, l.y, l.box) for l in self.lines]


def _load(name):
    img = cv2.imread(str(SAMPLES / name))
    if img is None:
        pytest.skip(f"sample {name} missing")
    return img


def test_end_screen_scores_the_selected_relic_and_labels_its_tile():
    scene = scan(_load("End Screen #1.jpg"), FakeOcr(END_SCREEN_TEXT), MANAGER, SCORER, TileMemory())
    assert len(scene.tiles) == 5  # the big details icon is not counted as a tile
    assert scene.details_icon is not None and abs(scene.details_icon[0] - 211) <= 8
    assert scene.selected == 0
    assert [e.text for e in scene.effects] == ["Improved Dragon Cult Incantations", "Faith +1"]
    assert scene.score is not None and scene.score.total == 10
    assert scene.tile_labels == {0: "10"}


def test_small_jar_finds_the_selected_tile():
    image = _load("Small Jar #1.webp")
    scene = scan(image, None, MANAGER, None)
    assert scene.selected is not None
    x, y, w, h = scene.tiles[scene.selected]
    assert abs(x - 1346) <= 8 and abs(y - 236) <= 8


def test_without_ocr_only_tiles_are_found():
    scene = scan(_load("End Screen #1.jpg"), None, MANAGER, SCORER)
    assert scene.score is None and scene.effects == [] and len(scene.tiles) == 6
