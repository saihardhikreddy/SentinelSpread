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


@pytest.mark.parametrize("name", ["sawtooth", "saturated-noise", "checkerboard"])
def test_dct_mark_survives_saturated_images(name):
    """Blocks of pure 0/255 lose the coefficient gap to RGB clipping; the embedder must read the
    mark back and reinforce those blocks rather than return a damaged mark."""
    h, w = 180, 240
    if name == "sawtooth":
        i = np.arange(h * w).reshape(h, w) * 4
        arr = np.stack([(i * 7) % 256, ((i + 1) * 13) % 256, ((i + 2) * 3) % 256], -1).astype("uint8")
    elif name == "saturated-noise":
        arr = (np.random.default_rng(7).integers(0, 2, (h, w, 3)) * 255).astype("uint8")
    else:
        arr = ((np.indices((h, w)).sum(0) % 2) * 255).astype("uint8")[..., None].repeat(3, -1)

    text = "Copyright SentinelSpread 2026"
    res = W.embed_invisible_dct_watermark(_png(arr), text, 20.0)
    got = W.extract_invisible_dct_watermark(res["watermarked_bytes"], res["bits_embedded"], 20.0)
    assert got["extracted_text"] == text
