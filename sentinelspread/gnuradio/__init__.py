"""
GNU Radio Software SDR integration module for SentinelSpread.
"""

from sentinelspread.gnuradio.blocks import crypto_dsss_tx, dsss_crypto_rx


def run_software_loopback(*args, **kwargs):
    from sentinelspread.gnuradio.runner import run_software_loopback as _run
    return _run(*args, **kwargs)


__all__ = [
    "crypto_dsss_tx",
    "dsss_crypto_rx",
    "run_software_loopback",
]
