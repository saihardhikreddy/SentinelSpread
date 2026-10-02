"""
Unit tests for LSB Image Steganography and Digital Watermarking module.
"""

from pathlib import Path
import numpy as np

import pytest
from PIL import Image
from sentinelspread.input.stego import DigitalWatermark, LSBSteganography


def create_synthetic_cover_image(path: Path, width: int = 100, height: int = 100) -> Path:
    """Create a synthetic RGB cover image for testing."""
    np.random.seed(42)
    img_array = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(img_array, mode="RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


def test_lsb_steganography_roundtrip(tmp_path: Path):
    cover_path = tmp_path / "cover.png"
    stego_path = tmp_path / "stego.png"

    create_synthetic_cover_image(cover_path, width=80, height=80)

    secret_payload = b"Top Secret Payload embedded inside Image LSB for SentinelSpread!"
    LSBSteganography.embed_payload_in_image(cover_path, secret_payload, stego_path)

    assert stego_path.is_file()

    extracted_payload = LSBSteganography.extract_payload_from_image(stego_path)
    assert extracted_payload == secret_payload


def test_stego_capacity_overflow(tmp_path: Path):
    cover_path = tmp_path / "small_cover.png"
    stego_path = tmp_path / "overflow_stego.png"

    create_synthetic_cover_image(cover_path, width=5, height=5)  # 25 pixels * 3 = 75 bits capacity

    huge_payload = b"A" * 100  # 100 bytes = 800 bits > 75 bits
    with pytest.raises(ValueError, match="exceeds cover image capacity"):
        LSBSteganography.embed_payload_in_image(cover_path, huge_payload, stego_path)


def test_digital_watermarking(tmp_path: Path):
    cover_path = tmp_path / "image.png"
    watermarked_path = tmp_path / "watermarked.png"

    create_synthetic_cover_image(cover_path, width=200, height=200)
    DigitalWatermark.apply_watermark(cover_path, "SentinelSpread Verified", watermarked_path)

    assert watermarked_path.is_file()
    img = Image.open(watermarked_path)
    assert img.size == (200, 200)
