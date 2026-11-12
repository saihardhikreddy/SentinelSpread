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


def test_power_policy_counts_the_processing_gain_of_a_chip_level_measurement():
    p = PowerPolicy(target_symbol_snr_db=9.0, step_db=3.0)
    pg = 10 * np.log10(16)  # spreading factor 16, as DSSSSpreader.processing_gain_db gives
    # 0 dB per chip with a 16x spreader is about 12 dB per symbol: 3 dB above target, so back off.
    backed_off = p.required_amplitude(0.0, current_amplitude=0.5, processing_gain_db=pg)
    assert backed_off == pytest.approx(0.5 * 10 ** (-3.0 / 20), rel=0.01)
    # Without the gain the same reading looks 9 dB short and power goes up.
    assert p.required_amplitude(0.0, current_amplitude=0.5) > 0.5


def test_fec_ignores_extra_trailing_bits():
    # The receiver may hand back a few bits more than were sent (noise after the frame).
    rng = np.random.default_rng(4)
    bits = rng.integers(0, 2, 400).astype(np.uint8)
    enc = fec_encode(bits)
    for extra in (1, 7, 30):
        padded = np.concatenate([enc, rng.integers(0, 2, extra).astype(np.uint8)])
        msg, corrected = fec_decode(padded, len(bits))
        assert np.array_equal(msg, bits), extra
        assert corrected == 0


def test_fec_survives_a_few_missing_trailing_bits():
    # The last interleaved bits are the third parity bit of the last codewords, so losing
    # them costs no message bits: the code corrects the zero-filled gap.
    rng = np.random.default_rng(5)
    bits = rng.integers(0, 2, 400).astype(np.uint8)
    enc = fec_encode(bits)
    for missing in (1, 3, 20):
        msg, _ = fec_decode(enc[:-missing], len(bits))
        assert np.array_equal(msg, bits), missing


def test_fec_rejects_a_negative_length():
    import pytest

    with pytest.raises(ValueError):
        fec_decode(np.zeros(7, dtype=np.uint8), -1)


def test_hop_schedule_is_independent_of_the_pn_seed():
    from sentinelspread.crypto.key_mgmt import derive_hop_seed, derive_pn_seed
    from sentinelspread.harden.fhss import _hop_offsets

    key = bytes(range(16))
    assert derive_hop_seed(key) != derive_pn_seed(key)
    # Knowing the PN seed no longer reproduces the hop pattern.
    from_pn = _hop_offsets(4096, 64, 8, 0.05, derive_pn_seed(key))
    actual = _hop_offsets(4096, 64, 8, 0.05, derive_hop_seed(key))
    assert not np.array_equal(from_pn, actual)


def test_fhss_rejects_a_zero_dwell():
    import pytest

    with pytest.raises(ValueError):
        apply_fhss(np.ones(10), bytes(16), chips_per_hop=0)
