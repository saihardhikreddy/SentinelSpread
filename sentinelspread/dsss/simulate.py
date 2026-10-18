"""
Numpy model of the GNU Radio burst and channel, for testing receivers without GNU Radio.

Mirrors crypto_dsss_tx (training tones + preamble + spread payload + trail), the flowgraph's RRC
filters (GNU Radio firdes.root_raised_cosine, gain sqrt(sps), 41 taps) and channel_model
(carrier offset in cycles/sample, complex AWGN with total std `noise_voltage`).
"""

from typing import Optional

import numpy as np

from sentinelspread.crypto.encryptor import encrypt_payload
from sentinelspread.crypto.key_mgmt import derive_pn_seed, generate_rsa_keypair
from sentinelspread.dsss.acquisition import header_chips
from sentinelspread.dsss.spreader import DSSSSpreader
from sentinelspread.input.input_handler import InputHandler
from sentinelspread.modem.mapper import ConstellationMapper

DEFAULT_SDR_AES_KEY = b"SentinelSpread_SDR_SessionKey_26"   # same as gnuradio.blocks
TRAIL_FLUSH_LEN = 512


def rrc_taps(sps: int = 4, alpha: float = 0.35, ntaps: int = 41) -> np.ndarray:
    """GNU Radio's firdes.root_raised_cosine(gain=sqrt(sps), fs=sps, rs=1, alpha, ntaps)."""
    t = (np.arange(ntaps) - (ntaps - 1) / 2) / sps
    taps = np.empty(ntaps)
    for i, ti in enumerate(t):
        if abs(ti) < 1e-12:
            taps[i] = 1 - alpha + 4 * alpha / np.pi
        elif abs(abs(4 * alpha * ti) - 1) < 1e-9:
            taps[i] = alpha / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * alpha))
                                           + (1 - 2 / np.pi) * np.cos(np.pi / (4 * alpha)))
        else:
            taps[i] = (np.sin(np.pi * ti * (1 - alpha)) + 4 * alpha * ti * np.cos(np.pi * ti * (1 + alpha))) / (
                np.pi * ti * (1 - (4 * alpha * ti) ** 2))
    return taps * (np.sqrt(sps) / taps.sum())


def build_burst(message: str, spreading_factor: int, aes_key: bytes = DEFAULT_SDR_AES_KEY, rsa_keys=None):
    """Chip stream of one burst, plus what the receiver needs (keys, symbol count, bits)."""
    priv, pub = rsa_keys if rsa_keys is not None else generate_rsa_keypair(key_bits=2048)
    bundle = encrypt_payload(InputHandler.prepare_text_payload(message), pub, aes_key=aes_key)
    bits = ConstellationMapper.bytes_to_bits(bundle.serialize())
    symbols = ConstellationMapper.bits_to_bpsk(bits)
    data, _ = DSSSSpreader(spreading_factor=spreading_factor, seed=derive_pn_seed(aes_key)).spread(symbols)
    chips = np.concatenate([header_chips(), np.real(data), np.ones(TRAIL_FLUSH_LEN)])
    return {"chips": chips, "num_symbols": len(symbols), "bits": np.asarray(bits), "private_key": priv,
            "pn_seed": derive_pn_seed(aes_key)}


def channel(chips: np.ndarray, noise_voltage: float, freq_offset: float = 0.0005, sps: int = 4,
            lead_samples: int = 0, seed: Optional[int] = 42) -> np.ndarray:
    """TX RRC -> carrier offset + AWGN -> RX RRC. Returns matched-filtered samples."""
    taps = rrc_taps(sps)
    up = np.zeros(len(chips) * sps, dtype=np.complex128)
    up[::sps] = chips
    tx = np.convolve(up, taps)
    if lead_samples:
        tx = np.concatenate([np.zeros(lead_samples), tx])
    n = np.arange(len(tx))
    rng = np.random.default_rng(seed)
    noise = (rng.standard_normal(len(tx)) + 1j * rng.standard_normal(len(tx))) * (noise_voltage / np.sqrt(2))
    rx = tx * np.exp(2j * np.pi * freq_offset * n) + noise
    return np.convolve(rx, taps)
