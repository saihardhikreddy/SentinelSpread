"""
Evaluation, metrics, BER, detection rate, and plotting module for SentinelSpread.
"""

from sentinelspread.eval.metrics import compute_ber, compute_ser
from sentinelspread.eval.plot_ber import run_ber_simulation, theoretical_ber
from sentinelspread.eval.processing_gain import measure_processing_gain, run_processing_gain_benchmark
from sentinelspread.eval.plot_psd import compute_and_plot_psd

__all__ = [
    "compute_ber",
    "compute_ser",
    "run_ber_simulation",
    "theoretical_ber",
    "measure_processing_gain",
    "run_processing_gain_benchmark",
    "compute_and_plot_psd",
]
