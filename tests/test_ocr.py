import numpy as np

from ranni.ocr import read_text
from ranni.ocr.engine import OcrLine


def test_read_text_shrinks_for_the_engine_and_maps_boxes_back():
    class FakeOcr:
        max_height = 500  # smaller than the image: read_text must shrink it 2x

        def recognize(self, image):
            assert max(image.shape) <= 500
            return [OcrLine("Faith +1", 50.0, (10, 40, 100, 20))]

    lines = read_text(np.zeros((600, 1000, 3), np.uint8), FakeOcr())
    assert [l.text for l in lines] == ["Faith +1"]
    assert lines[0].box == (20, 80, 200, 40)
    assert lines[0].y == 100
