"""Despread-first receiver (sentinelspread.dsss.acquisition), tested on the numpy channel model."""
import numpy as np
import pytest

from sentinelspread.crypto.decryptor import decrypt_payload
from sentinelspread.crypto.encryptor import CryptoBundle
from sentinelspread.crypto.key_mgmt import generate_rsa_keypair
from sentinelspread.dsss.acquisition import DespreadFirstReceiver
from sentinelspread.dsss.pn_gen import PRIMITIVE_POLYNOMIALS, PNGenerator
from sentinelspread.dsss.simulate import build_burst, channel
from sentinelspread.input.input_handler import InputHandler
from sentinelspread.modem.mapper import ConstellationMapper

MESSAGE = "Meet at the north gate, 21:40."
KEYS = generate_rsa_keypair(key_bits=2048)


def _decode(burst, samples, sf):
    r = DespreadFirstReceiver(sf, burst["pn_seed"]).demodulate(samples, burst["num_symbols"])
    try:
        bundle = CryptoBundle.deserialize(ConstellationMapper.bits_to_bytes(r.bits))
        text = InputHandler.extract_payload(decrypt_payload(bundle, burst["private_key"]))[1].decode()
    except Exception:
        text = None
    return r, text, int(np.sum(r.bits != burst["bits"]))


@pytest.mark.parametrize("degree", sorted(PRIMITIVE_POLYNOMIALS))
def test_every_pn_degree_is_maximal_length(degree):
    # Regression: degree 8 used taps (8, 4), which repeat every 12 chips, so the 255-chip
    # "m-sequence" preamble was a 12-chip pattern and the burst position was ambiguous.
    n = (1 << degree) - 1
    seq = PNGenerator(degree=degree, seed=1).generate_chips(2 * n, bipolar=True)
    shifts = [p for p in range(1, n + 1) if np.array_equal(seq[:n], seq[p:p + n])]
    assert shifts[0] == n


def test_finds_the_burst_and_the_carrier_offset():
    burst = build_burst(MESSAGE, 16, rsa_keys=KEYS)
    for lead in (0, 137, 1001):
        y = channel(burst["chips"], 0.3, freq_offset=0.0005, lead_samples=lead, seed=lead)
        r, text, errors = _decode(burst, y, 16)
        assert text == MESSAGE and errors == 0
        # header chip 0 sits at sample lead + 40 (two 41-tap RRC filters, 4 samples per chip)
        assert r.header_start_chip * 4 + r.sample_phase == lead + 40
        assert abs(r.cfo_rad_per_chip - 2 * np.pi * 0.0005 * 4) < 1e-3


def test_decodes_below_the_noise_floor():
    # sigma 2.0 is -12 dB SNR per sample; SF 64 still recovers every bit.
    burst = build_burst(MESSAGE, 64, rsa_keys=KEYS)
    y = channel(burst["chips"], 2.0, freq_offset=0.0005, lead_samples=200, seed=7)
    r, text, errors = _decode(burst, y, 64)
    assert text == MESSAGE and errors == 0
    assert r.symbol_snr_db > 6


def test_more_spreading_buys_more_range():
    # At sigma 2.0, SF 16 leaves bit errors (so AES-GCM rejects it) while SF 64 is clean.
    results = {}
    for sf in (16, 64):
        burst = build_burst(MESSAGE, sf, rsa_keys=KEYS)
        y = channel(burst["chips"], 2.0, freq_offset=0.0005, lead_samples=200, seed=11)
        results[sf] = _decode(burst, y, sf)
    assert results[16][1] is None and results[16][2] > 0
    assert results[64][1] == MESSAGE and results[64][2] == 0


def test_capture_too_short_is_a_clear_error():
    burst = build_burst(MESSAGE, 16, rsa_keys=KEYS)
    y = channel(burst["chips"][:500], 0.02)
    with pytest.raises(ValueError, match="too short"):
        DespreadFirstReceiver(16, burst["pn_seed"]).demodulate(y, burst["num_symbols"])
