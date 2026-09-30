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


def embed_invisible_dct_watermark(
    image_bytes: bytes,
    watermark_text: str,
    strength: float = 20.0
) -> dict:
    """
    Embed invisible watermark string into 8x8 DCT mid-frequency coefficients of Y channel.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('YCbCr')
    y_chan, cb_chan, cr_chan = img.split()
    y_arr = np.array(y_chan, dtype=np.float32)
    
    h, w = y_arr.shape
    h_8 = (h // 8) * 8
    w_8 = (w // 8) * 8
    y_arr = y_arr[:h_8, :w_8]
    
    bits = []
    for char in watermark_text.encode('utf-8'):
        for i in range(7, -1, -1):
            bits.append((char >> i) & 1)
            
    total_bits = len(bits)
    max_blocks = (h_8 // 8) * (w_8 // 8)
    
    if total_bits > max_blocks:
        raise ValueError(f"Watermark text too long for DCT capacity! Bits: {total_bits}, Max blocks: {max_blocks}")
        
    block_idx = 0
    for i in range(0, h_8, 8):
        for j in range(0, w_8, 8):
            if block_idx >= total_bits:
                break
            
            block = y_arr[i:i+8, j:j+8]
            dct_block = scipy.fftpack.dct(scipy.fftpack.dct(block.T, norm='ortho').T, norm='ortho')
            
            bit = bits[block_idx]
            # Embed into mid-frequency coefficient (4, 3) vs (3, 4)
            if bit == 1:
                if dct_block[4, 3] <= dct_block[3, 4]:
                    dct_block[4, 3] = dct_block[3, 4] + strength
            else:
                if dct_block[4, 3] >= dct_block[3, 4]:
                    dct_block[3, 4] = dct_block[4, 3] + strength
                    
            idct_block = scipy.fftpack.idct(scipy.fftpack.idct(dct_block.T, norm='ortho').T, norm='ortho')
            y_arr[i:i+8, j:j+8] = idct_block
            block_idx += 1
            
    y_arr = np.clip(y_arr, 0, 255).astype(np.uint8)
    y_img = Image.fromarray(y_arr, 'L')
    
    if (w, h) != (w_8, h_8):
        y_img = y_img.resize((w, h))
        
    stego_img = Image.merge('YCbCr', (y_img, cb_chan, cr_chan)).convert('RGB')
    
    out_io = io.BytesIO()
    stego_img.save(out_io, format='PNG')
    
    return {
        "watermarked_bytes": out_io.getvalue(),
        "bits_embedded": total_bits,
        "max_capacity_bits": max_blocks
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
