"""
Analysis Metrics Module: MSE and PSNR Calculators
Provides quantitative metrics to evaluate image degradation caused by steganography and watermarking.
"""

import io
import math
from typing import Union, Dict, Any
import numpy as np
from PIL import Image

def calculate_mse(image_array1: np.ndarray, image_array2: np.ndarray) -> float:
    """
    Calculate Mean Squared Error (MSE) between two image numpy arrays.
    """
    if image_array1.shape != image_array2.shape:
        raise ValueError(f"Image shapes do not match: {image_array1.shape} vs {image_array2.shape}")

    arr1 = image_array1.astype(np.float64)
    arr2 = image_array2.astype(np.float64)
    err = np.sum((arr1 - arr2) ** 2)
    mse = err / float(image_array1.size)
    return float(mse)

def calculate_psnr(mse: float, max_pixel: float = 255.0) -> float:
    """
    Calculate Peak Signal-to-Noise Ratio (PSNR) in decibels (dB).
    """
    if mse <= 1e-10:
        return 100.0  # Perfect match convention
    psnr = 10.0 * math.log10((max_pixel ** 2) / mse)
    return float(psnr)

def compare_images(
    original_input: Union[bytes, io.BytesIO, Image.Image],
    modified_input: Union[bytes, io.BytesIO, Image.Image]
) -> Dict[str, Any]:
    """
    Compare original image and modified image (stego or watermarked).
    """
    def load_rgba(inp):
        if isinstance(inp, (bytes, io.BytesIO)):
            if isinstance(inp, bytes):
                inp = io.BytesIO(inp)
            img = Image.open(inp)
        elif isinstance(inp, Image.Image):
            img = inp
        else:
            raise ValueError("Invalid image type.")
        return img.convert('RGBA')

    img_orig = load_rgba(original_input)
    img_mod = load_rgba(modified_input)

    if img_orig.size != img_mod.size:
        img_mod = img_mod.resize(img_orig.size, Image.Resampling.LANCZOS)

    arr_orig = np.array(img_orig, dtype=np.uint8)
    arr_mod = np.array(img_mod, dtype=np.uint8)

    mse = calculate_mse(arr_orig, arr_mod)
    psnr = calculate_psnr(mse)

    if psnr >= 50.0:
        verdict = "Imperceptible / Excellent quality"
    elif psnr >= 40.0:
        verdict = "High quality (minor imperceptible changes)"
    elif psnr >= 30.0:
        verdict = "Acceptable quality (slight visible degradation)"
    else:
        verdict = "Low quality (noticeable distortion)"

    width, height = img_orig.size
    return {
        "mse": round(mse, 6),
        "psnr_db": round(psnr, 4),
        "width": width,
        "height": height,
        "channels": arr_orig.shape[2] if len(arr_orig.shape) > 2 else 1,
        "quality_verdict": verdict
    }

def compare_audio_bytes(orig_bytes: bytes, mod_bytes: bytes) -> dict:
    """
    Compare original and modified 16-bit PCM WAV audio using MSE, PSNR, SNR, and sample parameters.
    """
    import wave
    
    with wave.open(io.BytesIO(orig_bytes), 'rb') as wf1, wave.open(io.BytesIO(mod_bytes), 'rb') as wf2:
        framerate = wf1.getframerate()
        channels = wf1.getnchannels()
        sampwidth = wf1.getsampwidth()
        
        s1 = np.frombuffer(wf1.readframes(wf1.getnframes()), dtype=np.int16).astype(np.float64)
        s2 = np.frombuffer(wf2.readframes(wf2.getnframes()), dtype=np.int16).astype(np.float64)
        
    min_len = min(len(s1), len(s2))
    s1 = s1[:min_len]
    s2 = s2[:min_len]
    
    noise = s1 - s2
    mse_val = float(np.mean(noise ** 2))
    max_val = 32767.0
    psnr_val = float(10 * np.log10((max_val ** 2) / mse_val)) if mse_val > 0 else 99.99
    
    signal_power = float(np.mean(s1 ** 2))
    snr_val = float(10 * np.log10(signal_power / mse_val)) if mse_val > 0 and signal_power > 0 else 99.99

    duration_sec = round(min_len / (framerate * channels), 2) if (framerate and channels) else 0.0

    if psnr_val >= 60.0:
        verdict = "Imperceptible / Studio Quality"
        verdict_badge = "success"
    elif psnr_val >= 45.0:
        verdict = "High Fidelity (Imperceptible LSB noise)"
        verdict_badge = "success"
    elif psnr_val >= 35.0:
        verdict = "Acceptable Quality (Slight audio noise)"
        verdict_badge = "warning"
    else:
        verdict = "Audible Distortion"
        verdict_badge = "error"
    
    return {
        "mse": round(mse_val, 6),
        "psnr_db": round(psnr_val, 2),
        "snr_db": round(snr_val, 2),
        "sample_rate": framerate,
        "channels": channels,
        "sample_width": sampwidth * 8,
        "total_samples": min_len,
        "duration_sec": duration_sec,
        "capacity_bytes": min_len // 8,
        "quality_verdict": verdict,
        "verdict_badge": verdict_badge
    }
