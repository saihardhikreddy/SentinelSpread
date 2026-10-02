"""
Evaluation metrics: Bit Error Rate (BER) and Symbol Error Rate (SER).
"""

import numpy as np


def compute_ber(tx_bits: np.ndarray, rx_bits: np.ndarray) -> float:
    """
    Compute Bit Error Rate (BER) between transmitted and received bit arrays.
    """
    tx = np.asarray(tx_bits, dtype=int)
    rx = np.asarray(rx_bits, dtype=int)
    min_len = min(len(tx), len(rx))
    if min_len == 0:
        return 0.0

    errors = np.count_nonzero(tx[:min_len] != rx[:min_len])
    return float(errors / min_len)


def compute_ser(tx_symbols: np.ndarray, rx_symbols: np.ndarray) -> float:
    """
    Compute Symbol Error Rate (SER) between transmitted and received symbol arrays.
    """
    tx = np.asarray(tx_symbols)
    rx = np.asarray(rx_symbols)
    min_len = min(len(tx), len(rx))
    if min_len == 0:
        return 0.0

    errors = np.count_nonzero(tx[:min_len] != rx[:min_len])
    return float(errors / min_len)
