"""
Steganography & Watermarking Module for SentinelSpread.
Provides LSB image steganography (embedding & extracting binary payloads in cover images)
and digital image watermarking for authentication.
"""

from pathlib import Path
import struct
from typing import Tuple, Union
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class LSBSteganography:
    """Least Significant Bit (LSB) image steganography encoder and decoder."""

    MAGIC_HEADER = b"STEG"

    @classmethod
    def embed_payload_in_image(
        cls, cover_image_path: Union[str, Path], payload_bytes: bytes, output_image_path: Union[str, Path]
    ) -> Path:
        """
        Embeds binary payload into the LSBs of a cover image (PNG format).
        Prepends a magic header and 32-bit length integer.
        """
        cover_path = Path(cover_image_path)
        out_path = Path(output_image_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        img = Image.open(cover_path).convert("RGB")
        img_data = np.array(img, dtype=np.uint8)
        flat_data = img_data.flatten()

        # Build stego header: MAGIC (4 B) + length (4 B) + payload
        stego_data = cls.MAGIC_HEADER + struct.pack(">I", len(payload_bytes)) + payload_bytes

        # Convert stego_data to array of bits (0 or 1)
        bits = np.unpackbits(np.frombuffer(stego_data, dtype=np.uint8))

        if len(bits) > len(flat_data):
            raise ValueError(
                f"Payload size ({len(bits)} bits) exceeds cover image capacity ({len(flat_data)} bits/channels)"
            )

        # Replace LSBs of cover image
        flat_data[: len(bits)] = (flat_data[: len(bits)] & 0xFE) | bits

        stego_img_data = flat_data.reshape(img_data.shape)
        stego_img = Image.fromarray(stego_img_data, mode="RGB")
        stego_img.save(out_path, format="PNG")

        return out_path

    @classmethod
    def extract_payload_from_image(cls, stego_image_path: Union[str, Path]) -> bytes:
        """
        Extracts embedded binary payload from the LSBs of a stego PNG image.
        """
        stego_path = Path(stego_image_path)
        img = Image.open(stego_path).convert("RGB")
        flat_data = np.array(img, dtype=np.uint8).flatten()

        header_bits_needed = (len(cls.MAGIC_HEADER) + 4) * 8
        if len(flat_data) < header_bits_needed:
            raise ValueError("Image data too small to contain valid stego header")

        # Extract header bits
        hdr_bits = flat_data[:header_bits_needed] & 1
        hdr_bytes = np.packbits(hdr_bits).tobytes()

        magic = hdr_bytes[: len(cls.MAGIC_HEADER)]
        if magic != cls.MAGIC_HEADER:
            raise ValueError(f"Invalid stego magic header: {magic} != {cls.MAGIC_HEADER}")

        payload_len = struct.unpack(">I", hdr_bytes[len(cls.MAGIC_HEADER) :])[0]

        total_bits_needed = (len(cls.MAGIC_HEADER) + 4 + payload_len) * 8
        if len(flat_data) < total_bits_needed:
            raise ValueError("Stego image corrupted or incomplete payload bits")

        # Extract payload bits
        payload_bits = flat_data[header_bits_needed:total_bits_needed] & 1
        payload_bytes = np.packbits(payload_bits).tobytes()

        return payload_bytes


class DigitalWatermark:
    """Applies semi-transparent ownership watermarks to image payloads."""

    @staticmethod
    def apply_watermark(
        image_path: Union[str, Path],
        watermark_text: str = "SentinelSpread Secure Output",
        output_path: Union[str, Path] = None,
    ) -> Path:
        """Overlays semi-transparent watermark text onto an image."""
        img_path = Path(image_path)
        out_path = Path(output_path) if output_path else img_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        base_img = Image.open(img_path).convert("RGBA")
        txt_overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))

        draw = ImageDraw.Draw(txt_overlay)
        # Position watermark in bottom-right corner
        margin = 15
        width, height = base_img.size

        # Simple default font size calculation
        font_size = max(14, int(height / 25))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        x = width - text_w - margin
        y = height - text_h - margin

        # Draw semi-transparent background box and text
        draw.rectangle([x - 5, y - 5, x + text_w + 5, y + text_h + 5], fill=(0, 0, 0, 120))
        draw.text((x, y), watermark_text, fill=(255, 255, 255, 200), font=font)

        watermarked = Image.alpha_composite(base_img, txt_overlay).convert("RGB")
        watermarked.save(out_path, format="PNG")

        return out_path
