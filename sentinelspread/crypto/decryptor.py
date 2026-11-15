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

    # 1. Unwrap AES session key using RSA private key. Given the public key by mistake (the
    # two PEM files sit side by side), PyCryptodome raised a bare TypeError from deep inside
    # OAEP; say what is wrong instead.
    if not rsa_private_key.has_private():
        raise ValueError("RSA key unwrapping failed: this is a public key; decrypting needs the private key")
    rsa_cipher = PKCS1_OAEP.new(rsa_private_key)
    try:
        aes_key_bytes = rsa_cipher.decrypt(bundle.wrapped_key)
    except ValueError as e:
        raise ValueError(f"RSA key unwrapping failed: {e}")

    # 2. Decrypt ciphertext with AES-GCM and verify integrity tag
    try:
        # inside the try: an empty nonce from a damaged bundle makes AES.new raise too
        aes_cipher = AES.new(aes_key_bytes, AES.MODE_GCM, nonce=bundle.nonce)
        payload_bytes = aes_cipher.decrypt_and_verify(bundle.ciphertext, bundle.tag)
    except ValueError as e:
        raise ValueError(f"AES-GCM decryption/verification failed: {e}")

    return payload_bytes
