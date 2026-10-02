"""
Unit tests for RSA key management, AES-256-GCM encryption/decryption, and CryptoBundle serialization.
"""

from pathlib import Path
import pytest
from sentinelspread.crypto.key_mgmt import generate_rsa_keypair, export_key, import_key, derive_pn_seed
from sentinelspread.crypto.encryptor import encrypt_payload, CryptoBundle
from sentinelspread.crypto.decryptor import decrypt_payload


def test_rsa_key_generation_and_export_import(tmp_path: Path):
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)

    priv_path = tmp_path / "private.pem"
    pub_path = tmp_path / "public.pem"

    export_key(priv_key, priv_path)
    export_key(pub_key, pub_path)

    imp_priv = import_key(priv_path)
    imp_pub = import_key(pub_path)

    assert imp_priv.export_key() == priv_key.export_key()
    assert imp_pub.export_key() == pub_key.export_key()


def test_aes_rsa_encryption_decryption_roundtrip():
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
    plaintext = b"Top Secret Payload Data for SentinelSpread DSSS Transmission"

    bundle = encrypt_payload(plaintext, pub_key)
    decrypted = decrypt_payload(bundle, priv_key)

    assert decrypted == plaintext


def test_crypto_bundle_serialization():
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
    plaintext = b"Payload to test binary serialization of CryptoBundle"

    bundle = encrypt_payload(plaintext, pub_key)
    serialized_bytes = bundle.serialize()

    deserialized_bundle = CryptoBundle.deserialize(serialized_bytes)
    decrypted = decrypt_payload(deserialized_bundle, priv_key)

    assert decrypted == plaintext


def test_tamper_detection():
    priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
    plaintext = b"Sensitive covert communication data"

    bundle = encrypt_payload(plaintext, pub_key)

    # Modify ciphertext bit to simulate channel corruption or tampering
    corrupted_ciphertext = bytearray(bundle.ciphertext)
    corrupted_ciphertext[0] ^= 0xFF
    corrupted_bundle = CryptoBundle(
        wrapped_key=bundle.wrapped_key,
        nonce=bundle.nonce,
        tag=bundle.tag,
        ciphertext=bytes(corrupted_ciphertext),
    )

    with pytest.raises(ValueError, match="AES-GCM decryption/verification failed"):
        decrypt_payload(corrupted_bundle, priv_key)


def test_derive_pn_seed():
    key1 = b"\x01" * 32
    key2 = b"\x02" * 32

    seed1_a = derive_pn_seed(key1)
    seed1_b = derive_pn_seed(key1)
    seed2 = derive_pn_seed(key2)

    assert isinstance(seed1_a, int)
    assert seed1_a > 0
    # Deterministic with same key
    assert seed1_a == seed1_b
    # Divergent with different keys
    assert seed1_a != seed2
