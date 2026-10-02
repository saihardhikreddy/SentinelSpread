"""
Evaluation, metrics, BER, detection rate, and plotting module for SentinelSpread.
"""

from sentinelspread.eval.metrics import compute_ber
from sentinelspread.eval.plot_ber import run_ber_simulation

__all__ = ["compute_ber", "run_ber_simulation"]
