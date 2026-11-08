"""
Evaluation metrics: Bit Error Rate (BER) and Symbol Error Rate (SER).
"""

import numpy as np


def _error_rate(tx: np.ndarray, rx: np.ndarray) -> float:
    """Fraction of transmitted items that were not received correctly.

    Items the receiver never produced count as errors: a receiver that lost sync and
    returned nothing used to score a perfect 0.0. Extra received items (e.g. padding) are ignored.
    """
    if len(tx) == 0:
        return 0.0
    min_len = min(len(tx), len(rx))
    errors = np.count_nonzero(tx[:min_len] != rx[:min_len]) + (len(tx) - min_len)
    return float(errors / len(tx))


def compute_ber(tx_bits: np.ndarray, rx_bits: np.ndarray) -> float:
    """
    Compute Bit Error Rate (BER) between transmitted and received bit arrays.
    """
    return _error_rate(np.asarray(tx_bits, dtype=int).ravel(), np.asarray(rx_bits, dtype=int).ravel())


def compute_ser(tx_symbols: np.ndarray, rx_symbols: np.ndarray) -> float:
    """
    Compute Symbol Error Rate (SER) between transmitted and received symbol arrays.
    """
    return _error_rate(np.asarray(tx_symbols).ravel(), np.asarray(rx_symbols).ravel())
