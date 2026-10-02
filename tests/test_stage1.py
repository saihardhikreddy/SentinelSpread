"""
Integration unit tests for Stage 1: Input + Header + Crypto Pipeline.
"""

from pathlib import Path
from sentinelspread.input.header import PayloadType
from sentinelspread.input.input_handler import InputHandler
from sentinelspread.crypto.key_mgmt import generate_rsa_keypair
from sentinelspread.crypto.encryptor import encrypt_payload, CryptoBundle
from sentinelspread.crypto.decryptor import decrypt_payload


def test_stage1_text_roundtrip():
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
    original_text = "SentinelSpread Stage 1 Test: Secure covert communication text message."

    # 1. Prepare tagged payload
    tagged_payload = InputHandler.prepare_text_payload(original_text)

    # 2. Encrypt
    crypto_bundle = encrypt_payload(tagged_payload, pub_key)

    # 3. Serialize over channel
    channel_bytes = crypto_bundle.serialize()

    # 4. Receive & Deserialize
    received_bundle = CryptoBundle.deserialize(channel_bytes)

    # 5. Decrypt
    decrypted_tagged_payload = decrypt_payload(received_bundle, priv_key)

    # 6. Extract header and verify payload
    header, recovered_payload = InputHandler.extract_payload(decrypted_tagged_payload)

    assert header.payload_type == PayloadType.TEXT
    assert recovered_payload.decode("utf-8") == original_text
    assert decrypted_tagged_payload == tagged_payload


def test_stage1_audio_roundtrip(tmp_path: Path):
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
    wav_file = tmp_path / "test_input.wav"
    InputHandler.generate_sample_wav(wav_file, duration_sec=0.2, sample_rate=8000)
    original_audio_bytes = wav_file.read_bytes()

    # 1. Prepare tagged audio payload
    tagged_payload = InputHandler.prepare_audio_payload(wav_file)

    # 2. Encrypt
    crypto_bundle = encrypt_payload(tagged_payload, pub_key)

    # 3. Serialize over channel
    channel_bytes = crypto_bundle.serialize()

    # 4. Receive & Deserialize
    received_bundle = CryptoBundle.deserialize(channel_bytes)

    # 5. Decrypt
    decrypted_tagged_payload = decrypt_payload(received_bundle, priv_key)

    # 6. Extract header and verify payload
    header, recovered_payload = InputHandler.extract_payload(decrypted_tagged_payload)

    assert header.payload_type == PayloadType.AUDIO
    assert recovered_payload == original_audio_bytes
    assert decrypted_tagged_payload == tagged_payload
