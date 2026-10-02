"""
Channel simulation and hardware SDR abstraction module for SentinelSpread.
"""

from sentinelspread.channel.awgn import add_awgn_ebn0, add_awgn_snr

__all__ = [
    "add_awgn_ebn0",
    "add_awgn_snr",
]
