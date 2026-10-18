"""
Frequency hopping (FHSS) applied on top of the DSSS chip stream.

Each hop dwell of `chips_per_hop` chips is multiplied by a complex exponential whose normalised
frequency is chosen from a key-derived pseudo-random schedule. The result spreads the burst's
energy across a wider band over time: a non-coherent power measurement integrating over the
whole dwell set sees the same total energy, but any test that relies on the carrier staying at
one frequency (for example the x**2 carrier-tone statistic) only integrates coherently within a
single dwell, so its peak is reduced by roughly the number of hops.

The schedule is derived from the AES session key via the same HKDF path as the PN seed, so the
receiver reconstructs the identical hop pattern and removes it before despreading.
"""

from typing import Optional

import numpy as np

from sentinelspread.crypto.key_mgmt import derive_pn_seed


def hop_schedule(num_hops: int, num_channels: int, seed: int) -> np.ndarray:
    """Pseudo-random hop frequencies as integer channel indices in [0, num_channels)."""
    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    return rng.integers(0, num_channels, size=num_hops)


def _hop_offsets(num_chips: int, chips_per_hop: int, num_channels: int, channel_spacing: float,
                 seed: int) -> np.ndarray:
    """Per-chip normalised frequency offset (cycles per chip) for the whole burst."""
    num_hops = int(np.ceil(num_chips / chips_per_hop))
    channels = hop_schedule(num_hops, num_channels, seed)
    # center the channel grid on zero so the mean offset is ~0
    freqs = (channels - (num_channels - 1) / 2.0) * channel_spacing
    return np.repeat(freqs, chips_per_hop)[:num_chips]


def apply_fhss(chips: np.ndarray, aes_key: bytes, chips_per_hop: int = 64, num_channels: int = 8,
               channel_spacing: float = 0.05) -> np.ndarray:
    """Multiply the chip stream by the per-chip hop exponential. Phase is accumulated across chip
    boundaries so each dwell is phase-continuous (no artificial edges for an edge detector)."""
    chips = np.asarray(chips, dtype=np.complex128)
    offsets = _hop_offsets(len(chips), chips_per_hop, num_channels, channel_spacing,
                           derive_pn_seed(aes_key))
    phase = 2 * np.pi * np.cumsum(offsets)
    return chips * np.exp(1j * phase)


def remove_fhss(chips: np.ndarray, aes_key: bytes, chips_per_hop: int = 64, num_channels: int = 8,
                channel_spacing: float = 0.05) -> np.ndarray:
    """Inverse of apply_fhss: regenerate the same schedule and conjugate the hop exponential."""
    chips = np.asarray(chips, dtype=np.complex128)
    offsets = _hop_offsets(len(chips), chips_per_hop, num_channels, channel_spacing,
                           derive_pn_seed(aes_key))
    phase = 2 * np.pi * np.cumsum(offsets)
    return chips * np.exp(-1j * phase)


def fhss_transform(aes_key: bytes, chips_per_hop: int = 64, num_channels: int = 8,
                   channel_spacing: float = 0.05):
    """A chips->chips callable for detector.evaluate.sweep(transform=...)."""
    def transform(chips: np.ndarray) -> np.ndarray:
        return apply_fhss(chips, aes_key, chips_per_hop, num_channels, channel_spacing)
    return transform
