"""
Energy-calibrated AWGN channel models.
Supports Eb/N0 and SNR noise scaling modes.
"""

from typing import Optional
import numpy as np


def _complex_noise(n: int, sigma_dim: float, seed: Optional[int]) -> np.ndarray:
    """n samples of circular complex Gaussian noise, sigma_dim per I/Q dimension."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, sigma_dim, n) + 1j * rng.normal(0.0, sigma_dim, n)


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
    # sps=0 or es=0 used to return the signal with no noise at all (a perfect BER at any Eb/N0),
    # a negative sps filled it with nan, and bits_per_symbol=0 divided by zero.
    if bits_per_symbol < 1:
        raise ValueError(f"bits_per_symbol must be at least 1, got {bits_per_symbol}")
    if sps < 1:
        raise ValueError(f"sps must be at least 1, got {sps}")
    if not es > 0:
        raise ValueError(f"es must be more than 0, got {es}")
    if len(iq_samples) == 0:
        return np.array([], dtype=complex)

    k = bits_per_symbol
    eb = es / float(k)
    n0 = eb / (10.0 ** (ebn0_db / 10.0))
    sigma_dim = np.sqrt((n0 * sps) / 2.0)

    return iq_samples + _complex_noise(len(iq_samples), sigma_dim, seed)


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
    if len(iq_samples) == 0:
        return np.array([], dtype=complex)

    signal_pwr = np.mean(np.abs(iq_samples) ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    noise_pwr = signal_pwr / snr_lin
    sigma_dim = np.sqrt(noise_pwr / 2.0)

    return iq_samples + _complex_noise(len(iq_samples), sigma_dim, seed)
