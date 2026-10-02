"""
Energy-calibrated AWGN channel models.
Supports Eb/N0 and SNR noise scaling modes.
"""

from typing import Optional
import numpy as np


def add_awgn_ebn0(
    iq_samples: np.ndarray,
    ebn0_db: float,
    bits_per_symbol: int = 1,
    sps: int = 4,
    es: float = 1.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Add Complex Additive White Gaussian Noise (AWGN) calibrated to Eb/N0.

    Mathematical formulation:
        Eb = Es / k
        N0 = Eb / 10^(EbN0_dB / 10)
        sigma_dim = sqrt(N0 * sps / 2)
        w[n] ~ CN(0, 2*sigma_dim^2) = N(0, sigma_dim^2) + j*N(0, sigma_dim^2)

    Parameters:
        iq_samples: Complex baseband samples.
        ebn0_db: Energy per bit to noise spectral density ratio in dB.
        bits_per_symbol: Modulation order (k=1 for BPSK, k=2 for QPSK).
        sps: Samples per symbol (oversampling factor).
        es: Average symbol energy (default 1.0).
        seed: Optional RNG seed for deterministic reproducibility.

    Returns:
        Noisy complex baseband samples.
    """
    if seed is not None:
        rng = np.random.default_rng(seed)
    else:
        rng = np.random.default_rng()

    k = bits_per_symbol
    eb = es / float(k)
    n0 = eb / (10.0 ** (ebn0_db / 10.0))
    sigma_dim = np.sqrt((n0 * sps) / 2.0)

    noise_i = rng.normal(0.0, sigma_dim, len(iq_samples))
    noise_q = rng.normal(0.0, sigma_dim, len(iq_samples))
    noise = noise_i + 1j * noise_q

    return iq_samples + noise


def add_awgn_snr(
    iq_samples: np.ndarray,
    snr_db: float,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Add Complex Additive White Gaussian Noise (AWGN) calibrated to signal SNR in dB.

    Parameters:
        iq_samples: Complex baseband samples.
        snr_db: Signal-to-Noise Ratio in dB.
        seed: Optional RNG seed.

    Returns:
        Noisy complex baseband samples.
    """
    if seed is not None:
        rng = np.random.default_rng(seed)
    else:
        rng = np.random.default_rng()

    signal_pwr = np.mean(np.abs(iq_samples) ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    noise_pwr = signal_pwr / snr_lin
    sigma_dim = np.sqrt(noise_pwr / 2.0)

    noise_i = rng.normal(0.0, sigma_dim, len(iq_samples))
    noise_q = rng.normal(0.0, sigma_dim, len(iq_samples))
    noise = noise_i + 1j * noise_q

    return iq_samples + noise
