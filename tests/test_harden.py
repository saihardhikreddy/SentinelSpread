"""Stage 5 hardening: FEC, FHSS, adaptive power, key rotation."""
import numpy as np
import pytest

from sentinelspread.harden import (
    KeyRatchet,
    PowerPolicy,
    apply_fhss,
    fec_decode,
    fec_encode,
    fhss_transform,
    remove_fhss,
)


# ── FEC: Hamming(7,4) + interleaving ──────────────────────────────────────────────────────────

def test_fec_round_trip_exact():
    rng = np.random.default_rng(1)
    bits = rng.integers(0, 2, 404).astype(np.uint8)
    enc = fec_encode(bits)
    assert len(enc) == 7 * ((len(bits) + 3) // 4)        # rate 4/7 with padding
    msg, corrected = fec_decode(enc, len(bits))
    assert np.array_equal(msg, bits) and corrected == 0


def test_fec_corrects_one_error_per_codeword():
    rng = np.random.default_rng(2)
    bits = rng.integers(0, 2, 400).astype(np.uint8)
    enc = fec_encode(bits)
    n_words = len(enc) // 7
    noisy = enc.copy()
    # one flip per codeword, kept on distinct codewords by the interleave
    for w in range(n_words):
        noisy[w] ^= 1
    msg, corrected = fec_decode(noisy, len(bits))
    assert np.array_equal(msg, bits) and corrected == n_words


def test_fec_detects_but_may_miss_double_errors():
    # Hamming(7,4) corrects one error per word; two errors in a word cannot always be fixed.
    rng = np.random.default_rng(3)
    bits = rng.integers(0, 2, 40).astype(np.uint8)
    enc = fec_encode(bits)
    enc_bad = enc.copy()
    n_words = len(enc) // 7
    enc_bad[0] ^= 1
    enc_bad[0 + n_words] ^= 1            # two flips in codeword 0 (interleaved positions 0 and 1)
    msg, _ = fec_decode(enc_bad, len(bits))
    assert not np.array_equal(msg, bits)  # a double error is not guaranteed correctable


# ── FHSS ──────────────────────────────────────────────────────────────────────────────────────

def test_fhss_is_invertible_with_the_same_key():
    key = b"SentinelSpread_SDR_SessionKey_26"
    rng = np.random.default_rng(4)
    chips = (rng.integers(0, 2, 4096) * 2 - 1).astype(np.complex128)
    hopped = apply_fhss(chips, key, chips_per_hop=32, num_channels=8)
    assert np.allclose(remove_fhss(hopped, key, chips_per_hop=32, num_channels=8), chips, atol=1e-9)
    assert not np.allclose(hopped, chips)          # it actually changed the stream


def test_fhss_wrong_key_does_not_recover():
    rng = np.random.default_rng(5)
    chips = (rng.integers(0, 2, 2048) * 2 - 1).astype(np.complex128)
    hopped = apply_fhss(chips, b"A" * 32)
    assert not np.allclose(remove_fhss(hopped, b"B" * 32), chips, atol=1e-6)


def test_fhss_lowers_the_squaring_statistic_on_a_real_burst():
    # The honest test: against the carrier-tone (x**2) statistic on a buried burst, not toy chips.
    from sentinelspread.detector.evaluate import sweep

    key = b"SentinelSpread_SDR_SessionKey_26"
    base = sweep([1.0], trials=16, length=2048, spreading_factor=16, pfa=0.01,
                 include_ml=False, observer_sps=1, seed=0)
    hard = sweep([1.0], trials=16, length=2048, spreading_factor=16, pfa=0.01, include_ml=False,
                 observer_sps=1, transform=fhss_transform(key, chips_per_hop=32, num_channels=8,
                                                          channel_spacing=0.06), seed=0)
    assert base["rates"]["squaring"][0] >= 0.9
    assert hard["rates"]["squaring"][0] <= 0.5


# ── adaptive power ──────────────────────────────────────────────────────────────────────────────

def test_power_policy_reduces_when_snr_is_high_and_raises_when_low():
    p = PowerPolicy(target_symbol_snr_db=9.0, step_db=1.0)
    # measured well above target -> back off (lower amplitude)
    assert p.required_amplitude(15.0, current_amplitude=1.0) < 1.0
    # measured below target -> push up (but clamped by max_amplitude)
    assert p.required_amplitude(3.0, current_amplitude=0.5) > 0.5
    # change is limited to step_db per update
    amp = p.required_amplitude(40.0, current_amplitude=1.0)
    assert amp >= 1.0 * 10 ** (-1.0 / 20) - 1e-9


# ── key rotation ────────────────────────────────────────────────────────────────────────────────

def test_key_ratchet_is_deterministic_and_distinct_per_epoch():
    a = KeyRatchet(b"root-key-0123456", epoch=0)
    b = KeyRatchet(b"root-key-0123456", epoch=0)
    a_keys = [a.current_key()] + [a.advance() for _ in range(4)]
    b_keys = [b.key_for(e) for e in range(5)]
    assert a_keys == b_keys                 # both ends derive the same chain
    assert len(set(a_keys)) == 5            # every epoch key is different
    assert all(len(k) == 32 for k in a_keys)


def test_key_ratchet_different_roots_diverge():
    assert KeyRatchet(b"root-A" + b"\x00" * 10).current_key() != \
           KeyRatchet(b"root-B" + b"\x00" * 10).current_key()


def test_key_ratchet_rejects_short_root():
    with pytest.raises(ValueError):
        KeyRatchet(b"short")
