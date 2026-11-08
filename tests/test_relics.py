"""find_relics on real screenshots in samples/. Expected positions were read off the images."""

from pathlib import Path

import cv2
import pytest

from ranni.relics import find_relics

SAMPLES = Path(__file__).parent.parent / "samples"
TOLERANCE = 8  # px


def _load(name):
    img = cv2.imread(str(SAMPLES / name))
    if img is None:
        pytest.skip(f"sample {name} missing")
    return img


def _found(boxes, x, y):
    return any(abs(bx - x) <= TOLERANCE and abs(by - y) <= TOLERANCE for bx, by, _, _ in boxes)


def test_end_screen_finds_every_relic_and_nothing_else():
    boxes = find_relics(_load("End Screen #1.jpg"))
    assert len(boxes) == 6  # 5 rewards + the big icon in the details panel
    for x in (86, 446, 806, 1166, 1526):
        assert _found(boxes, x, 118)
    assert _found(boxes, 211, 713)  # details panel icon


def test_small_jar_finds_the_popup_row_and_details_icon():
    boxes = find_relics(_load("Small Jar #1.webp"))
    for x in (446, 626, 806, 986, 1166, 1346):
        assert _found(boxes, x, 236)
    assert _found(boxes, 508, 532)  # details panel icon


def test_boxes_are_square_and_inside_the_image():
    img = _load("Small Jar #3.png")
    for x, y, w, h in find_relics(img):
        assert w == h
        assert 0 <= x and 0 <= y and x + w <= img.shape[1] and y + h <= img.shape[0]
