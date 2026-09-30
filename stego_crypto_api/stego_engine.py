"""
Image LSB Steganography Engine Module
------------------------------------
Embeds and extracts binary text data into/from PNG/JPEG images via 1-bit LSB replacement across RGBA channels.
"""

import io
import struct
from typing import Tuple, Dict, Any
from PIL import Image
import numpy as np

MAGIC_HEADER = b"IMGSTG"

def calculate_capacity_bytes(width: int, height: int, channels: int = 4) -> int:
    """Calculate total maximum embedding payload capacity in bytes."""
    total_pixels = width * height * channels
    # Subtract 10 bytes for header (6 bytes magic + 4 bytes length)
    header_bits = 10 * 8
    capacity_bits = total_pixels - header_bits
    return max(0, capacity_bits // 8)

def embed_data(image_bytes: bytes, payload_text: str) -> Dict[str, Any]:
    """
    Embed string payload into image byte stream using LSB steganography.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = img.size
    img_array = np.array(img, dtype=np.uint8)
    
    payload_raw = payload_text.encode('utf-8')
    header = MAGIC_HEADER + struct.pack(">I", len(payload_raw))
    full_data = header + payload_raw
    
    # Convert bytes to bit array
    bits = []
    for b in full_data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
            
    total_bits = len(bits)
    total_samples = img_array.size
    
    if total_bits > total_samples:
        raise ValueError(f"Payload exceeds image capacity! Required bits: {total_bits}, Available: {total_samples}")
        
    flat_array = img_array.flatten().copy()
    for i in range(total_bits):
        flat_array[i] = (flat_array[i] & ~1) | bits[i]
        
    stego_array = flat_array.reshape(img_array.shape)
    stego_img = Image.fromarray(stego_array, 'RGBA')
    
    out_io = io.BytesIO()
    stego_img.save(out_io, format='PNG')
    stego_bytes = out_io.getvalue()
    
    return {
        "stego_image_bytes": stego_bytes,
        "bits_used": total_bits,
        "capacity_bytes": total_samples // 8,
        "width": width,
        "height": height
    }

def extract_data(image_bytes: bytes) -> Tuple[bytes, str]:
    """
    Extract embedded payload from stego image bytes.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    flat_array = np.array(img, dtype=np.uint8).flatten()
    
    # Read first 80 LSB bits (10 bytes: 6 magic + 4 len)
    header_bits = [int(flat_array[i] & 1) for i in range(80)]
    header_bytes = []
    for i in range(0, 80, 8):
        byte_val = 0
        for bit in header_bits[i:i+8]:
            byte_val = (byte_val << 1) | bit
        header_bytes.append(byte_val)
    header = bytes(header_bytes)
    
    magic = header[:6]
    if magic != MAGIC_HEADER:
        raise ValueError("Invalid stego header! Magic signature 'IMGSTG' not found.")
        
    payload_len = struct.unpack(">I", header[6:10])[0]
    total_bits_needed = payload_len * 8
    
    start_idx = 80
    end_idx = start_idx + total_bits_needed
    
    if end_idx > len(flat_array):
        raise ValueError("Corrupted stego file: payload length exceeds image pixel data.")
        
    payload_bits = [int(flat_array[i] & 1) for i in range(start_idx, end_idx)]
    out_bytes = []
    for i in range(0, len(payload_bits), 8):
        byte_val = 0
        for bit in payload_bits[i:i+8]:
            byte_val = (byte_val << 1) | bit
        out_bytes.append(byte_val)
        
    raw_payload = bytes(out_bytes)
    return raw_payload, raw_payload.decode('utf-8', errors='replace')
