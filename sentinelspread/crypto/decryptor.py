"""
AES-256 payload decryption with RSA key unwrapping (PKCS1_OAEP).
"""

from typing import Union
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA

from sentinelspread.crypto.encryptor import CryptoBundle


def decrypt_payload(bundle_or_bytes: Union[CryptoBundle, bytes], rsa_private_key: RSA.RsaKey) -> bytes:
    """
    Unwraps AES session key using RSA private key, then decrypts payload with AES-256-GCM.
    Verifies GCM authentication tag for tamper detection.
    Returns decrypted payload bytes.
    """
    if isinstance(bundle_or_bytes, bytes):
        bundle = CryptoBundle.deserialize(bundle_or_bytes)
    else:
        bundle = bundle_or_bytes

    rsa_cipher = PKCS1_OAEP.new(rsa_private_key)
    try:
        aes_key_bytes = rsa_cipher.decrypt(bundle.wrapped_key)
    except ValueError as e:
        raise ValueError(f"RSA key unwrapping failed: {e}")

    aes_cipher = AES.new(aes_key_bytes, AES.MODE_GCM, nonce=bundle.nonce)
    try:
        payload_bytes = aes_cipher.decrypt_and_verify(bundle.ciphertext, bundle.tag)
    except ValueError as e:
        raise ValueError(f"AES-GCM decryption/verification failed: {e}")

    return payload_bytes
