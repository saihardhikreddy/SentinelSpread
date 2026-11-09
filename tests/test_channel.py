"""Calibration tests for the AWGN channel models."""

import numpy as np
import pytest

from sentinelspread.channel.awgn import add_awgn_ebn0, add_awgn_snr

N = 200_000


def noise_power(clean, noisy):
    return float(np.mean(np.abs(noisy - clean) ** 2))


@pytest.mark.parametrize("snr_db", [-10.0, 0.0, 12.0])
def test_snr_mode_hits_requested_snr(snr_db):
    clean = 2.0 * np.exp(1j * np.linspace(0, 50, N))  # power 4
    noisy = add_awgn_snr(clean, snr_db, seed=1)
    measured = 10 * np.log10(4.0 / noise_power(clean, noisy))
    assert measured == pytest.approx(snr_db, abs=0.05)


def test_ebn0_mode_scales_with_bits_and_oversampling():
    clean = np.ones(N, dtype=complex)
    # N0 = (Es/k) / 10^(EbN0/10); per-sample noise power = N0 * sps.
    for k, sps, ebn0_db in [(1, 4, 3.0), (2, 8, 6.0), (2, 1, 0.0)]:
        noisy = add_awgn_ebn0(clean, ebn0_db, bits_per_symbol=k, sps=sps, seed=2)
        expected = (1.0 / k) / 10 ** (ebn0_db / 10) * sps
        assert noise_power(clean, noisy) == pytest.approx(expected, rel=0.02)


def test_noise_is_circular_and_zero_mean():
    clean = np.zeros(N, dtype=complex)
    noise = add_awgn_ebn0(clean, 0.0, sps=1, seed=3)
    assert np.var(noise.real) == pytest.approx(np.var(noise.imag), rel=0.03)
    assert abs(np.mean(noise)) < 0.01
    assert abs(np.mean(noise.real * noise.imag)) < 0.01


def test_seed_is_reproducible_and_empty_input_is_empty():
    x = np.ones(64, dtype=complex)
    np.testing.assert_array_equal(add_awgn_snr(x, 5, seed=9), add_awgn_snr(x, 5, seed=9))
    assert not np.array_equal(add_awgn_snr(x, 5, seed=9), add_awgn_snr(x, 5, seed=10))
    assert add_awgn_snr(np.array([]), 5).size == 0
    assert add_awgn_ebn0(np.array([]), 5).size == 0
