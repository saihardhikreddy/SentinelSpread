"""
Features an independent observer can compute from a capture, without any key.

Each returns one number, larger = more "there is a signal here". They are deliberately of
different kinds, because they do not all work against a spread-spectrum burst:

  energy_db         total power against a noise reference. The textbook radiometer.
  spectral_flatness how tone-like the spectrum is. Catches narrowband carriers.
  kurtosis_excess   how non-Gaussian the samples are.
  squaring_peak_db  peak of the spectrum of x**2 over its own mean. Squaring a BPSK signal
                    cancels the +-1 modulation and leaves a tone at twice the carrier offset,
                    so this sees through the spreading.
  chip_autocorr     strongest non-zero-lag peak of |autocorrelation|, normalised. Picks up the
                    repeating structure a fixed PN period leaves behind.
"""

import numpy as np

FEATURE_NAMES = ("energy_db", "spectral_flatness", "kurtosis_excess", "squaring_peak_db", "chip_autocorr")


def energy_db(x: np.ndarray, noise_reference: float = 1.0) -> float:
    """Mean power in dB relative to `noise_reference` (the power the observer expects of an
    empty channel). Needs a calibrated noise floor, which is this detector's weakness."""
    return float(10 * np.log10(np.mean(np.abs(x) ** 2) / max(noise_reference, 1e-30) + 1e-30))


def _welch_psd(x: np.ndarray, nfft: int = 256) -> np.ndarray:
    """Average periodogram over non-overlapping blocks (plain Welch, no window overlap)."""
    n = (len(x) // nfft) * nfft
    if n == 0:
        return np.abs(np.fft.fft(x, nfft)) ** 2
    blocks = x[:n].reshape(-1, nfft) * np.hanning(nfft)
    return np.mean(np.abs(np.fft.fft(blocks, axis=1)) ** 2, axis=0)


def spectral_flatness(x: np.ndarray, nfft: int = 256) -> float:
    """1 - (geometric mean / arithmetic mean) of the PSD. Flat (noise-like) -> near 0,
    one strong tone -> near 1."""
    psd = _welch_psd(x, nfft) + 1e-30
    gm = np.exp(np.mean(np.log(psd)))
    return float(1.0 - gm / np.mean(psd))


def kurtosis_excess(x: np.ndarray) -> float:
    """|excess kurtosis| of the real part. Gaussian noise -> 0."""
    r = np.real(x)
    r = r - np.mean(r)
    var = np.mean(r ** 2)
    if var < 1e-30:
        return 0.0
    return float(abs(np.mean(r ** 4) / var ** 2 - 3.0))


def squaring_peak_db(x: np.ndarray, nfft: int = 4096) -> float:
    """Peak-to-mean of the spectrum of x**2, in dB. Squaring strips BPSK's sign flips, so a
    buried BPSK carrier shows up as a tone even when the signal itself is under the noise."""
    y = np.asarray(x) ** 2
    y = y - np.mean(y)
    n = min(len(y), nfft)
    spec = np.abs(np.fft.fft(y[:n], nfft)) ** 2
    return float(10 * np.log10(np.max(spec) / (np.mean(spec) + 1e-30) + 1e-30))


def chip_autocorr(x: np.ndarray, min_lag: int = 8, max_lag: int = 2048) -> float:
    """Largest |autocorrelation| at a non-trivial lag, normalised by lag 0."""
    y = np.asarray(x) - np.mean(x)
    n = len(y)
    hi = min(max_lag, n - 1)
    if hi <= min_lag:
        return 0.0
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    spec = np.fft.fft(y, nfft)
    ac = np.fft.ifft(spec * np.conj(spec))[:hi + 1]
    zero = np.abs(ac[0])
    if zero < 1e-30:
        return 0.0
    return float(np.max(np.abs(ac[min_lag:hi + 1])) / zero)


def feature_vector(x: np.ndarray, noise_reference: float = 1.0) -> np.ndarray:
    """All features, in FEATURE_NAMES order."""
    return np.array([
        energy_db(x, noise_reference),
        spectral_flatness(x),
        kurtosis_excess(x),
        squaring_peak_db(x),
        chip_autocorr(x),
    ], dtype=float)
