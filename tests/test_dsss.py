"""
Unit and integration tests for Stage 3: DSSS Spreading, PN Sequences, Correlator,
Processing Gain, and Negative SNR decoding vs Unspread Control.
"""

import numpy as np
import pytest

from sentinelspread.crypto.key_mgmt import generate_rsa_keypair, derive_pn_seed
from sentinelspread.crypto.encryptor import encrypt_payload, CryptoBundle
from sentinelspread.crypto.decryptor import decrypt_payload
from sentinelspread.input.input_handler import InputHandler
from sentinelspread.dsss.pn_gen import PNGenerator, PRIMITIVE_POLYNOMIALS
from sentinelspread.dsss.spreader import DSSSSpreader
from sentinelspread.dsss.correlator import DSSSCorrelator
from sentinelspread.eval.processing_gain import measure_processing_gain
from sentinelspread.eval.metrics import compute_ber
from sentinelspread.modem.mapper import ConstellationMapper


def test_pn_generator_degree7_and_10_properties():
    # Degree 7: Period 2^7 - 1 = 127
    gen7 = PNGenerator(degree=7, seed=1)
    chips7 = gen7.generate_msequence(bipolar=True)
    assert len(chips7) == 127
    # Autocorrelation peak at lag 0 is 127, at non-zero lag is -1
    assert np.isclose(np.sum(chips7 * chips7), 127.0)
    assert np.isclose(np.sum(chips7 * np.roll(chips7, 1)), -1.0)

    # Degree 10: Period 2^10 - 1 = 1023
    gen10 = PNGenerator(degree=10, seed=1)
    chips10 = gen10.generate_msequence(bipolar=True)
    assert len(chips10) == 1023
    assert np.isclose(np.sum(chips10 * chips10), 1023.0)
    assert np.isclose(np.sum(chips10 * np.roll(chips10, 1)), -1.0)


def test_pn_generator_seed_derivation_from_aes_key():
    key_a = b"\x11" * 32
    key_b = b"\x22" * 32

    gen_a1 = PNGenerator(degree=7, aes_key=key_a)
    gen_a2 = PNGenerator(degree=7, aes_key=key_a)
    gen_b = PNGenerator(degree=7, aes_key=key_b)

    seq_a1 = gen_a1.generate_chips(100)
    seq_a2 = gen_a2.generate_chips(100)
    seq_b = gen_b.generate_chips(100)

    # Deterministic with same AES key
    assert np.array_equal(seq_a1, seq_a2)
    # Divergent with different AES keys
    assert not np.array_equal(seq_a1, seq_b)


@pytest.mark.parametrize("sf", [16, 32, 64, 128])
def test_dsss_spreader_dimensions_and_gain(sf):
    symbols = np.array([1.0, -1.0, 1.0, 1.0, -1.0])
    spreader = DSSSSpreader(spreading_factor=sf, seed=42)
    chips, pn = spreader.spread(symbols)

    assert len(chips) == len(symbols) * sf
    assert len(pn) == len(symbols) * sf
    assert np.isclose(spreader.processing_gain_db, 10.0 * np.log10(sf))


def test_sliding_correlator_acquisition_and_early_late():
    spreader = DSSSSpreader(spreading_factor=32, seed=99)
    symbols = np.array([1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0])
    frame_chips, data_pn, preamble_chips = spreader.spread_frame(symbols, preamble_length=127)

    # Inject channel delay of 25 chips
    delay = 25
    rx_signal = np.concatenate([np.zeros(delay), frame_chips, np.zeros(20)])

    # Sliding correlator
    correlator = DSSSCorrelator(spreading_factor=32)
    detected_offset, peak_corr = correlator.find_lock_offset(rx_signal, preamble_chips, search_window=64)
    assert detected_offset == delay
    assert peak_corr > 0.95

    # Early-Late gate at prompt alignment
    timing_err = correlator.early_late_gate(rx_signal, detected_offset, preamble_chips, delta=1)
    assert abs(timing_err) < 0.1


def test_processing_gain_empirical_vs_theoretical():
    for sf in [16, 32, 64]:
        res = measure_processing_gain(sf=sf, num_symbols=5000, input_snr_db=0.0, seed=123)
        # Measured processing gain within ~1.0 dB of theoretical
        assert res["delta_db"] < 1.0, f"Gp discrepancy too high for SF={sf}: {res}"


def test_dsss_negative_snr_decode_success_vs_unspread_control():
    """
    CRITICAL INTEGRATION TEST:
    1. Transmit DSSS-spread signal at negative SNR (-10 dB). Demonstrate successful decode (BER <= 0.01).
    2. Control test: Transmit unspread signal at the exact same negative SNR (-10 dB).
       Show it fails completely (BER > 0.30), proving spreading is strictly necessary.
    """
    rng = np.random.default_rng(2026)
    num_symbols = 2000
    tx_symbols = rng.choice([-1.0, 1.0], size=num_symbols)

    sf = 64
    snr_db = -10.0
    # Channel noise power for signal power = 1.0
    noise_power = 10.0 ** (-snr_db / 10.0)  # 10.0
    sigma = np.sqrt(noise_power)

    # -------------------------------------------------------------
    # 1. DSSS Transmission
    # -------------------------------------------------------------
    spreader = DSSSSpreader(spreading_factor=sf, seed=777)
    tx_chips, pn = spreader.spread(tx_symbols)

    # Add AWGN
    noise_dsss = rng.normal(0.0, sigma, len(tx_chips))
    rx_chips = tx_chips + noise_dsss

    # Despread
    correlator = DSSSCorrelator(spreading_factor=sf)
    despread_symbols = correlator.despread(rx_chips, pn)
    rx_dsss_decisions = np.sign(despread_symbols)

    ber_dsss = compute_ber(tx_symbols, rx_dsss_decisions)

    # -------------------------------------------------------------
    # 2. Control Test: Unspread Transmission (Exact same channel noise)
    # -------------------------------------------------------------
    noise_unspread = rng.normal(0.0, sigma, num_symbols)
    rx_unspread = tx_symbols + noise_unspread
    rx_unspread_decisions = np.sign(rx_unspread)

    ber_unspread = compute_ber(tx_symbols, rx_unspread_decisions)

    print(f"\n[Negative SNR Test @ {snr_db} dB with SF={sf}]")
    print(f"  DSSS Spread BER:    {ber_dsss:.4f} (passed)")
    print(f"  Unspread Control:   {ber_unspread:.4f} (failed as expected)")

    # Assert DSSS decodes reliably
    assert ber_dsss <= 0.01, f"DSSS BER ({ber_dsss}) exceeded 0.01 at -10 dB SNR"

    # Assert unspread signal fails completely (proving spreading is necessary)
    assert ber_unspread > 0.30, f"Unspread control unexpectedly decoded with low BER ({ber_unspread})"


def test_end_to_end_crypto_dsss_pipeline():
    """
    End-to-end integration test:
    Input Payload -> RSA Keypair -> AES-256-GCM Encryption ->
    Session Seed Derivation -> DSSS Spreading (SF=64) ->
    Channel with Negative SNR (-6 dB) -> Despreading ->
    AES-256-GCM Decryption & Authenticated Tag Verification ->
    Bit-exact payload recovery.
    """
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
    message = "SentinelSpread DSSS Covert Comms: Operating Below the Noise Floor."
    tagged_payload = InputHandler.prepare_text_payload(message)

    # Encrypt
    crypto_bundle = encrypt_payload(tagged_payload, pub_key)
    serialized_bytes = crypto_bundle.serialize()

    # Convert bytes to bits and BPSK symbols
    tx_bits = ConstellationMapper.bytes_to_bits(serialized_bytes)
    tx_symbols = ConstellationMapper.bits_to_bpsk(tx_bits)

    # Unwrap session key for DSSS PN derivation
    # In symmetric/pre-shared or session-negotiated DSSS:
    from Crypto.Cipher import PKCS1_OAEP
    session_key = PKCS1_OAEP.new(priv_key).decrypt(crypto_bundle.wrapped_key)

    # Spread with session-derived PN seed (SF=128 ensures 0-error recovery below noise floor)
    sf = 128
    spreader = DSSSSpreader(spreading_factor=sf, aes_key=session_key)
    tx_chips, pn = spreader.spread(tx_symbols)

    # Negative SNR channel (-6 dB)
    snr_db = -6.0
    noise_power = 10.0 ** (-snr_db / 10.0)
    sigma = np.sqrt(noise_power)
    noise = np.random.default_rng(42).normal(0.0, sigma, len(tx_chips))
    rx_chips = tx_chips + noise

    # Receiver: despread
    correlator = DSSSCorrelator(spreading_factor=sf, aes_key=session_key)
    rx_symbols = correlator.despread(rx_chips, pn)
    rx_bits = ConstellationMapper.bpsk_to_bits(rx_symbols)

    assert compute_ber(tx_bits, rx_bits) == 0.0

    # Deserialize & Decrypt
    recovered_bytes = ConstellationMapper.bits_to_bytes(rx_bits[:len(tx_bits)])
    recovered_bundle = CryptoBundle.deserialize(recovered_bytes)
    decrypted_tagged = decrypt_payload(recovered_bundle, priv_key)
    header, recovered_msg = InputHandler.extract_payload(decrypted_tagged)

    assert recovered_msg.decode("utf-8") == message
