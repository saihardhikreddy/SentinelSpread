"""
Input module for SentinelSpread: handles text and audio payload processing and header tagging.
"""

from sentinelspread.input.header import Header, PayloadType
from sentinelspread.input.input_handler import InputHandler

__all__ = ["Header", "PayloadType", "InputHandler"]
