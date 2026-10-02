"""
Evaluation metrics: Bit Error Rate (BER) calculation and statistics.
"""

import numpy as np


def compute_ber(tx_bits: np.ndarray, rx_bits: np.ndarray) -> float:
    """
    Computes Bit Error Rate (BER) between transmitted and received bit arrays.
    """
    tx_bits = np.asarray(tx_bits, dtype=int)
    rx_bits = np.asarray(rx_bits, dtype=int)

    min_len = min(len(tx_bits), len(rx_bits))
    if min_len == 0:
        return 1.0

    tx_slice = tx_bits[:min_len]
    rx_slice = rx_bits[:min_len]

    bit_errors = np.sum(tx_slice != rx_slice)
    ber = float(bit_errors) / float(min_len)

    return ber
