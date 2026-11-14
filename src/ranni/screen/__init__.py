"""SEEING: what's on the screen. Screenshot -> relic tiles and the text on it. Knows nothing about relic effects.

    capture.py      take a screenshot (dxcam / mss)                    Windows
    tiles.py        find the relic tiles, and which one is selected
    ocr.py          read every line of text in an image
    windows_ocr.py  the Windows OCR engine                             Windows
    layout.py       where text lines sit (for effects that wrap onto two lines)
    tracking.py     remember which tile showed which score
"""

Box = tuple[int, int, int, int]  # x, y, w, h in image pixels
