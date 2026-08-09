"""
Channel simulation and hardware SDR abstraction module for SentinelSpread.
"""

from sentinelspread.channel.awgn import AWGNChannel, add_awgn, add_awgn_ebn0

__all__ = ["AWGNChannel", "add_awgn", "add_awgn_ebn0"]
