"""Invisible DCT watermark: the mark must survive images whose sides are not multiples of 8.

Regression: the embedder used to crop to the 8x8 grid and then resize back to the full size,
which resampled every pixel and shifted the blocks, so the mark was lost and PSNR fell to ~20 dB.
"""
import io

import numpy as np
import pytest
from PIL import Image

import watermark_engine as W


def _png(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("h,w", [(180, 240), (179, 241), (200, 301), (256, 256), (480, 640)])
@pytest.mark.parametrize("kind", ["photo", "noise"])
def test_dct_mark_round_trip_any_size(h, w, kind):
    rng = np.random.default_rng(h * w)
    if kind == "photo":
        small = (rng.random((h // 8, w // 8, 3)) * 255).astype("uint8")
        arr = np.array(Image.fromarray(small).resize((w, h), Image.BICUBIC))
    else:
        arr = np.clip(128 + rng.normal(0, 25, (h, w, 3)), 0, 255).astype("uint8")

    res = W.embed_invisible_dct_watermark(_png(arr), "SENTINEL", 20.0)
    out = np.array(Image.open(io.BytesIO(res["watermarked_bytes"])).convert("RGB"))
    assert out.shape == arr.shape                       # size is preserved

    mse = ((out.astype(float) - arr.astype(float)) ** 2).mean()
    assert 10 * np.log10(255 ** 2 / mse) > 40           # the mark stays invisible

    got = W.extract_invisible_dct_watermark(res["watermarked_bytes"], res["bits_embedded"], 20.0)
    assert got["extracted_text"] == "SENTINEL"

