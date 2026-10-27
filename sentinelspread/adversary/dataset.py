"""
Labelled I/Q captures for training and testing the CNN adversary.

Each capture is one fixed-length complex segment, turned into a real array of shape (2, length):
row 0 is the in-phase part, row 1 the quadrature. Every capture is scaled by its own RMS before
it is handed to the network. That is deliberate: without it the CNN could separate the classes on
absolute power alone and would be nothing but the radiometer the project already has. Normalising
each capture removes the power cue and forces the network to decide on structure, which is the
only thing that survives a signal buried below the noise floor.

Signal and noise captures come from `sentinelspread.detector.evaluate`, so the adversary is
trained and scored on exactly the observer model the Stage 5 detectors use: chip-rate sampling,
payload region only, and per-capture noise drawn from a +-0.5 dB uncertainty band. A `transform`
(a chips->chips callable such as `harden.fhss.fhss_transform`) rewrites the chip stream before the
channel, which is how the adversary is trained or tested against a hardening measure.
"""

from typing import Callable, Optional, Sequence

import numpy as np

from sentinelspread.detector.evaluate import (DEFAULT_LENGTH, NOISE_UNCERTAINTY_DB,
                                              noise_segments, signal_segments)


def iq_to_array(capture: np.ndarray) -> np.ndarray:
    """One complex capture -> (2, len) float32, scaled by its own RMS (power cue removed)."""
    x = np.asarray(capture, dtype=np.complex128)
    rms = np.sqrt(np.mean(np.abs(x) ** 2))
    x = x / (rms if rms > 1e-12 else 1.0)
    return np.stack([x.real, x.imag]).astype(np.float32)


def segments_to_array(segments: Sequence[np.ndarray], length: int) -> np.ndarray:
    """A list of complex captures -> (n, 2, length) float32, each trimmed/padded to `length`."""
    out = np.zeros((len(segments), 2, length), dtype=np.float32)
    for i, seg in enumerate(segments):
        a = iq_to_array(seg)
        m = min(length, a.shape[1])
        out[i, :, :m] = a[:, :m]
    return out


def build_dataset(sigmas: Sequence[float], per_class: int = 200, length: int = DEFAULT_LENGTH,
                  spreading_factor: int = 16, transform: Optional[Callable[[np.ndarray], np.ndarray]] = None,
                  seed: int = 0, uncertainty_db: float = NOISE_UNCERTAINTY_DB, rsa_keys=None):
    """Balanced signal/noise captures pooled over every noise level in `sigmas`.

    Returns (x, y, snr): x is (N, 2, length) float32, y is 0 (noise) / 1 (signal), and snr is the
    nominal per-sample SNR in dB of each capture (noise captures get their level's reference SNR,
    taken as the matching signal level's, for bookkeeping only). One RSA keypair is shared across
    all signal captures (it does not change what a key-free observer sees) so bulk generation for
    training is fast.
    """
    if rsa_keys is None:
        from sentinelspread.crypto.key_mgmt import generate_rsa_keypair
        rsa_keys = generate_rsa_keypair(key_bits=2048)
    xs, ys, snrs = [], [], []
    for si, sigma in enumerate(sigmas):
        n_per = max(1, per_class // len(sigmas) + 1)
        noise = noise_segments(n_per, length, sigma, seed=seed + 7 * si, uncertainty_db=uncertainty_db)
        sig = signal_segments(n_per, length, sigma, spreading_factor, seed=seed + 101 * (si + 1),
                              transform=transform, uncertainty_db=uncertainty_db, rsa_keys=rsa_keys)
        snr = float(10 * np.log10(0.25 / sigma ** 2))
        xs.append(segments_to_array(noise, length)); ys.append(np.zeros(len(noise)))
        xs.append(segments_to_array(sig, length));   ys.append(np.ones(len(sig)))
        snrs.extend([snr] * (len(noise) + len(sig)))
    x = np.concatenate(xs).astype(np.float32)
    y = np.concatenate(ys).astype(np.int64)
    return x, y, np.asarray(snrs, dtype=float)
