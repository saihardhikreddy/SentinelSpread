"""
Digital Watermarking Engine Module
----------------------------------
Supports visible text/logo watermarking and invisible 8x8 block Discrete Cosine Transform (DCT)
frequency domain embedding and extraction.
"""

import io
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import scipy.fftpack

def add_visible_text_watermark(
    image_bytes: bytes,
    text: str,
    font_size: int = 28,
    opacity: float = 0.4,
    position: str = "bottom-right",
    color_hex: str = "#ffffff"
) -> bytes:
    """Add a visible text overlay watermark to an image."""
    base = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    txt_layer = Image.new('RGBA', base.size, (255, 255, 255, 0))
    
    draw = ImageDraw.Draw(txt_layer)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
        
    bbox = draw.textbbox((0, 0), text, font=font)
    t_width = bbox[2] - bbox[1]
    t_height = bbox[3] - bbox[1]
    
    w, h = base.size
    margin = 20
    
    if position == "bottom-right":
        x = w - t_width - margin
        y = h - t_height - margin
    elif position == "bottom-left":
        x = margin
        y = h - t_height - margin
    elif position == "top-right":
        x = w - t_width - margin
        y = margin
    elif position == "top-left":
        x = margin
        y = margin
    else:  # center
        x = (w - t_width) // 2
        y = (h - t_height) // 2
        
    rgb_color = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    alpha_val = int(255 * opacity)
    
    draw.text((x, y), text, fill=(*rgb_color, alpha_val), font=font)
    watermarked = Image.alpha_composite(base, txt_layer)
    
    out_io = io.BytesIO()
    watermarked.save(out_io, format='PNG')
    return out_io.getvalue()


def add_visible_logo_watermark(
    base_image_bytes: bytes,
    logo_image_bytes: bytes,
    opacity: float = 0.4,
    scale: float = 0.2,
    position: str = "bottom-right"
) -> bytes:
    """Add a visible logo image overlay watermark to a base image."""
    base = Image.open(io.BytesIO(base_image_bytes)).convert('RGBA')
    logo = Image.open(io.BytesIO(logo_image_bytes)).convert('RGBA')
    
    bw, bh = base.size
    target_logo_width = int(bw * scale)
    aspect = logo.height / logo.width
    target_logo_height = int(target_logo_width * aspect)
    
    logo = logo.resize((target_logo_width, target_logo_height), Image.Resampling.LANCZOS)
    
    if opacity < 1.0:
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * opacity))
        logo.putalpha(a)
        
    margin = 20
    if position == "bottom-right":
        pos = (bw - target_logo_width - margin, bh - target_logo_height - margin)
    elif position == "bottom-left":
        pos = (margin, bh - target_logo_height - margin)
    elif position == "top-right":
        pos = (bw - target_logo_width - margin, margin)
    elif position == "top-left":
        pos = (margin, margin)
    else:
        pos = ((bw - target_logo_width) // 2, (bh - target_logo_height) // 2)
        
    watermarked = base.copy()
    watermarked.paste(logo, pos, mask=logo)
    
    out_io = io.BytesIO()
    watermarked.save(out_io, format='PNG')
    return out_io.getvalue()


def _dct2(block):
    return scipy.fftpack.dct(scipy.fftpack.dct(block.T, norm='ortho').T, norm='ortho')


def _idct2(block):
    return scipy.fftpack.idct(scipy.fftpack.idct(block.T, norm='ortho').T, norm='ortho')


def _block_origins(h_8, w_8, n):
    """Top-left corners of the first n 8x8 blocks, row by row (the order the extractor reads)."""
    return [(i, j) for i in range(0, h_8, 8) for j in range(0, w_8, 8)][:n]


def _embed_bit(y, i, j, bit, strength):
    # Mid-frequency pair (4, 3) vs (3, 4). Always force a gap of `strength` around their midpoint:
    # a pair that is already ordered but only barely apart would otherwise flip after rounding.
    d = _dct2(y[i:i+8, j:j+8])
    mid = (d[4, 3] + d[3, 4]) / 2
    sign = 1 if bit == 1 else -1
    d[4, 3] = mid + sign * strength / 2
    d[3, 4] = mid - sign * strength / 2
    y[i:i+8, j:j+8] = _idct2(d)


def _compose(y_full, cb_chan, cr_chan):
    y_img = Image.fromarray(np.clip(np.round(y_full), 0, 255).astype(np.uint8), 'L')
    return Image.merge('YCbCr', (y_img, cb_chan, cr_chan)).convert('RGB')


def embed_invisible_dct_watermark(
    image_bytes: bytes,
    watermark_text: str,
    strength: float = 20.0
) -> dict:
    """
    Embed invisible watermark string into 8x8 DCT mid-frequency coefficients of Y channel.

    Only whole 8x8 blocks are marked; the right/bottom remainder is left untouched (the image is
    never resized, which would shift the blocks off the grid the extractor reads). After embedding,
    the mark is read back from the final RGB image: blocks whose bit did not survive rounding and
    RGB clipping (saturated, high-contrast blocks) are re-marked with more strength.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('YCbCr')
    y_chan, cb_chan, cr_chan = img.split()
    y_full = np.array(y_chan, dtype=np.float32)

    h, w = y_full.shape
    h_8 = (h // 8) * 8
    w_8 = (w // 8) * 8

    bits = []
    for char in watermark_text.encode('utf-8'):
        for i in range(7, -1, -1):
            bits.append((char >> i) & 1)

    total_bits = len(bits)
    max_blocks = (h_8 // 8) * (w_8 // 8)

    if total_bits > max_blocks:
        raise ValueError(f"Watermark text too long for DCT capacity! Bits: {total_bits}, Max blocks: {max_blocks}")

    origins = _block_origins(h_8, w_8, total_bits)
    for (i, j), bit in zip(origins, bits):
        _embed_bit(y_full, i, j, bit, strength)
    stego_img = _compose(y_full, cb_chan, cr_chan)

    reinforced = 0
    for attempt in range(1, 7):
        y_rt = np.array(stego_img.convert('YCbCr').split()[0], dtype=np.float32)
        wrong = [(i, j, bit) for (i, j), bit in zip(origins, bits)
                 if (1 if _dct2(y_rt[i:i+8, j:j+8])[4, 3] > _dct2(y_rt[i:i+8, j:j+8])[3, 4] else 0) != bit]
        if not wrong:
            break
        for i, j, bit in wrong:
            _embed_bit(y_full, i, j, bit, strength * (1.6 ** attempt))
        reinforced += len(wrong)
        stego_img = _compose(y_full, cb_chan, cr_chan)

    out_io = io.BytesIO()
    stego_img.save(out_io, format='PNG')

    return {
        "watermarked_bytes": out_io.getvalue(),
        "bits_embedded": total_bits,
        "max_capacity_bits": max_blocks,
        "blocks_reinforced": reinforced,
    }


def extract_invisible_dct_watermark(
    image_bytes: bytes,
    watermark_bit_length: int,
    strength: float = 20.0
) -> dict:
    """
    Extract invisible watermark string from 8x8 DCT mid-frequency coefficients.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('YCbCr')
    y_chan, _, _ = img.split()
    y_arr = np.array(y_chan, dtype=np.float32)
    
    h, w = y_arr.shape
    h_8 = (h // 8) * 8
    w_8 = (w // 8) * 8
    
    extracted_bits = []
    block_idx = 0
    
    for i in range(0, h_8, 8):
        for j in range(0, w_8, 8):
            if block_idx >= watermark_bit_length:
                break
                
            block = y_arr[i:i+8, j:j+8]
            dct_block = scipy.fftpack.dct(scipy.fftpack.dct(block.T, norm='ortho').T, norm='ortho')
            
            bit = 1 if dct_block[4, 3] > dct_block[3, 4] else 0
            extracted_bits.append(bit)
            block_idx += 1
            
    out_bytes = []
    for i in range(0, len(extracted_bits), 8):
        byte_val = 0
        for bit in extracted_bits[i:i+8]:
            byte_val = (byte_val << 1) | bit
        out_bytes.append(byte_val)
        
    extracted_bytes = bytes(out_bytes)
    return {
        "extracted_text": extracted_bytes.decode('utf-8', errors='replace'),
        "bits_extracted": len(extracted_bits)
    }
