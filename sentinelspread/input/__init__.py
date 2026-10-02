"""
Input module for SentinelSpread: handles text, audio, and steganographic image payload processing.
"""

from sentinelspread.input.header import Header, PayloadType
from sentinelspread.input.input_handler import InputHandler
from sentinelspread.input.stego import LSBSteganography, DigitalWatermark

__all__ = ["Header", "PayloadType", "InputHandler", "LSBSteganography", "DigitalWatermark"]
