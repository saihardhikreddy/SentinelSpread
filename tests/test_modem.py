"""
Unit tests for Stage 2: BPSK/QPSK Modem, RRC filter, AWGN channel, and BER vs Eb/N0 trends.
"""

import numpy as np
import pytest
from sentinelspread.channel.awgn import add_awgn_ebn0
from sentinelspread.eval.metrics import compute_ber
from sentinelspread.modem.mapper import ConstellationMapper
from sentinelspread.modem.modem import Modem
from sentinelspread.modem.rrc import generate_rrc_taps


def test_constellation_mapper_bpsk():
    bits = np.array([0, 1, 1, 0, 1])
    symbols = ConstellationMapper.bits_to_bpsk(bits)
    assert np.allclose(np.real(symbols), [-1.0, 1.0, 1.0, -1.0, 1.0])

    recovered_bits = ConstellationMapper.bpsk_to_bits(symbols)
    assert np.array_equal(bits, recovered_bits)


def test_constellation_mapper_qpsk_gray():
    bits = np.array([0, 0, 0, 1, 1, 1, 1, 0])
    symbols = ConstellationMapper.bits_to_qpsk(bits)
    assert len(symbols) == 4

    recovered_bits = ConstellationMapper.qpsk_to_bits(symbols)
    assert np.array_equal(bits, recovered_bits)


def test_rrc_filter_taps():
    taps = generate_rrc_taps(rrc_alpha=0.35, sps=4, span=10)
    assert len(taps) == 41  # 10 * 4 + 1
    assert np.isclose(np.sum(taps**2), 1.0)


@pytest.mark.parametrize("scheme", ["BPSK", "QPSK"])
def test_modem_clean_loopback(scheme):
    np.random.seed(123)
    num_bits = 1000
    tx_bits = np.random.randint(0, 2, size=num_bits)
    if scheme == "QPSK" and len(tx_bits) % 2 != 0:
        tx_bits = tx_bits[:-1]

    modem = Modem(scheme=scheme, sps=4, span=10)
    tx_iq = modem.modulate(tx_bits)

    rx_bits = modem.demodulate(tx_iq, expected_num_bits=len(tx_bits), ref_bits=tx_bits[:32])
    ber = compute_ber(tx_bits, rx_bits)

    assert ber == 0.0, f"Clean loopback BER for {scheme} was {ber}, expected 0.0"


@pytest.mark.parametrize("scheme", ["BPSK", "QPSK"])
def test_modem_ber_vs_snr_progression(scheme):
    """
    Sanity check: Transmit random bits through AWGN channel simulator at 0, 4, 8 dB Eb/N0.
    Assert BER decreases as Eb/N0 increases.
    """
    np.random.seed(42)
    num_bits = 50000
    tx_bits = np.random.randint(0, 2, size=num_bits)
    if scheme == "QPSK" and len(tx_bits) % 2 != 0:
        tx_bits = tx_bits[:-1]

    bits_per_symbol = 1 if scheme == "BPSK" else 2
    modem = Modem(scheme=scheme, sps=4, span=10)
    tx_iq = modem.modulate(tx_bits)

    ebn0_levels = [0.0, 4.0, 8.0]
    bers = []

    for ebn0_db in ebn0_levels:
        rx_iq = add_awgn_ebn0(
            tx_iq,
            ebn0_db=ebn0_db,
            bits_per_symbol=bits_per_symbol,
            sps=4,
            seed=42,
        )
        rx_bits = modem.demodulate(rx_iq, expected_num_bits=len(tx_bits), ref_bits=tx_bits[:32])
        ber = compute_ber(tx_bits, rx_bits)
        bers.append(ber)

    assert bers[1] < bers[0], f"BER at 4 dB ({bers[1]}) >= BER at 0 dB ({bers[0]}) for {scheme}"
    assert bers[2] < bers[1], f"BER at 8 dB ({bers[2]}) >= BER at 4 dB ({bers[1]}) for {scheme}"
    assert bers[2] < 0.001, f"High Eb/N0 (8 dB) BER ({bers[2]}) should be < 0.001 for {scheme}"
