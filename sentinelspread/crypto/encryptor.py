"""
AES-256 payload encryption with RSA key wrapping (PKCS1_OAEP).
"""

import struct
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes


class CryptoBundle:
    """Encapsulates encrypted payload components and binary serialization."""

    def __init__(self, wrapped_key: bytes, nonce: bytes, tag: bytes, ciphertext: bytes):
        self.wrapped_key = wrapped_key
        self.nonce = nonce
        self.tag = tag
        self.ciphertext = ciphertext

    def serialize(self) -> bytes:
        """Serialize bundle into flat byte stream for transmission."""
        key_len = len(self.wrapped_key)
        nonce_len = len(self.nonce)
        tag_len = len(self.tag)

        hdr = struct.pack(">HBB", key_len, nonce_len, tag_len)
        return hdr + self.wrapped_key + self.nonce + self.tag + self.ciphertext

    @classmethod
    def deserialize(cls, data: bytes) -> "CryptoBundle":
        """Deserialize flat byte stream back into CryptoBundle."""
        hdr_size = struct.calcsize(">HBB")
        if len(data) < hdr_size:
            raise ValueError("Crypto bundle data too short to read header")

        key_len, nonce_len, tag_len = struct.unpack(">HBB", data[:hdr_size])
        offset = hdr_size

        if len(data) < offset + key_len + nonce_len + tag_len:
            raise ValueError("Crypto bundle data incomplete")

        wrapped_key = data[offset : offset + key_len]
        offset += key_len

        nonce = data[offset : offset + nonce_len]
        offset += nonce_len

        tag = data[offset : offset + tag_len]
        offset += tag_len

        ciphertext = data[offset:]

        return cls(wrapped_key=wrapped_key, nonce=nonce, tag=tag, ciphertext=ciphertext)


def encrypt_payload(payload_bytes: bytes, rsa_public_key: RSA.RsaKey, aes_key_bits: int = 256) -> CryptoBundle:
    """
    Encrypts payload using AES-256-GCM.
    Wraps the random AES session key using RSA-OAEP with the recipient's public key.
    Returns a CryptoBundle.
    """
    aes_key_bytes = get_random_bytes(aes_key_bits // 8)

    rsa_cipher = PKCS1_OAEP.new(rsa_public_key)
    wrapped_key = rsa_cipher.encrypt(aes_key_bytes)

    aes_cipher = AES.new(aes_key_bytes, AES.MODE_GCM)
    ciphertext, tag = aes_cipher.encrypt_and_digest(payload_bytes)

    return CryptoBundle(
        wrapped_key=wrapped_key,
        nonce=aes_cipher.nonce,
        tag=tag,
        ciphertext=ciphertext,
    )
