"""
AWGN (Additive White Gaussian Noise) Channel Simulator.
Simulates baseband wireless channel with configurable Signal-to-Noise Ratio (SNR) or Eb/N0.
"""

import numpy as np


def add_awgn_ebn0(
    signal: np.ndarray,
    ebn0_db: float,
    bits_per_symbol: int = 1,
    sps: int = 4,
    seed: int = None,
) -> np.ndarray:
    """
    Adds complex AWGN noise to IQ signal given target Eb/N0 in dB.

    Parameters:
        signal (np.ndarray): Complex baseband IQ signal array (RRC shaped).
        ebn0_db (float): Target Eb/N0 ratio in dB.
        bits_per_symbol (int): Number of bits per symbol (1 for BPSK, 2 for QPSK).
        sps (int): Samples per symbol.
        seed (int, optional): Random seed for reproducible noise generation.

    Returns:
        np.ndarray: Noisy complex baseband IQ signal array.
    """
    if seed is not None:
        np.random.seed(seed)

    ebn0_linear = 10.0 ** (ebn0_db / 10.0)

    # Average energy per bit Eb = Es / bits_per_symbol (assuming constellation Es = 1.0)
    eb = 1.0 / float(bits_per_symbol)
    n0 = eb / ebn0_linear

    # Noise std dev per dimension (real/imag) before matched filtering
    std_dev = np.sqrt(n0 / 2.0)
    noise = std_dev * (np.random.randn(len(signal)) + 1j * np.random.randn(len(signal)))

    return signal + noise


def add_awgn(signal: np.ndarray, snr_db: float, seed: int = None) -> np.ndarray:
    """
    Adds complex AWGN noise to an IQ signal given overall signal power SNR in dB.
    Legacy entry point.
    """
    if seed is not None:
        np.random.seed(seed)

    signal_power = np.mean(np.abs(signal) ** 2)
    if signal_power == 0:
        return signal

    snr_linear = 10.0 ** (snr_db / 10.0)
    noise_power = signal_power / snr_linear

    std_dev = np.sqrt(noise_power / 2.0)
    noise = std_dev * (np.random.randn(len(signal)) + 1j * np.random.randn(len(signal)))

    return signal + noise


class AWGNChannel:
    """Channel simulator wrapper matching common SDR interface."""

    def __init__(self, ebn0_db: float = 10.0, bits_per_symbol: int = 1, sps: int = 4):
        self.ebn0_db = ebn0_db
        self.bits_per_symbol = bits_per_symbol
        self.sps = sps

    def transmit(self, iq_samples: np.ndarray, ebn0_db: float = None) -> np.ndarray:
        target_ebn0 = self.ebn0_db if ebn0_db is None else ebn0_db
        return add_awgn_ebn0(
            iq_samples,
            ebn0_db=target_ebn0,
            bits_per_symbol=self.bits_per_symbol,
            sps=self.sps,
        )
