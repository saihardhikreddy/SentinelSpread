"""Visible text watermark: placement and size."""
import io

import numpy as np
from PIL import Image

from stego_crypto_api.watermark_engine import add_visible_text_watermark


def _ink(position, font_size=28, size=(400, 200)):
    buf = io.BytesIO()
    Image.new("RGB", size, "black").save(buf, "PNG")
    out = add_visible_text_watermark(buf.getvalue(), "SENTINEL WATERMARK", font_size=font_size,
                                     opacity=1.0, position=position)
    ys, xs = np.nonzero(np.asarray(Image.open(io.BytesIO(out)).convert("L")) > 0)
    w, h = size
    return xs.min(), w - 1 - xs.max(), ys.min(), h - 1 - ys.max()


def test_corner_text_sits_20_px_from_both_edges():
    _, right, _, bottom = _ink("bottom-right")
    assert 19 <= right <= 21 and 19 <= bottom <= 21   # was 18 and 18: width used right - top
    left, _, top, _ = _ink("top-left")
    assert 19 <= left <= 22 and 19 <= top <= 21


def test_font_size_is_honoured_without_arial():
    small = _ink("top-left", font_size=14)
    big = _ink("top-left", font_size=28)
    small_width = 400 - small[0] - small[1]
    big_width = 400 - big[0] - big[1]
    assert big_width > 1.6 * small_width   # the bitmap fallback drew both the same size
