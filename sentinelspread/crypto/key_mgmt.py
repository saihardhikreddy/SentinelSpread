"""
RSA Key Management & Key Derivation: generation, export, import of RSA keypairs,
and per-session PN seed derivation using HKDF.
"""

from pathlib import Path
import struct
from typing import Tuple, Union
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from Crypto.PublicKey import RSA


def generate_rsa_keypair(key_bits: int = 2048) -> Tuple[RSA.RsaKey, RSA.RsaKey]:
    """Generate an RSA keypair (private_key, public_key)."""
    private_key = RSA.generate(key_bits)
    public_key = private_key.publickey()
    return private_key, public_key


def export_key(key: RSA.RsaKey, output_path: Union[str, Path]) -> Path:
    """Export RSA key to PEM file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pem_data = key.export_key(format="PEM")
    path.write_bytes(pem_data)
    return path


def import_key(key_path: Union[str, Path]) -> RSA.RsaKey:
    """Import RSA key from PEM file or bytes."""
    path = Path(key_path)
    key_bytes = path.read_bytes()
    return RSA.import_key(key_bytes)


def derive_pn_seed(aes_key: bytes, context_salt: bytes = b"SentinelSpreadPNSeed") -> int:
    """
    Derive a 32-bit PN sequence seed per-session from the negotiated AES session key
    using HKDF-SHA256.
    """
    derived_bytes = HKDF(
        master=aes_key,
        key_len=4,
        salt=context_salt,
        hashmod=SHA256,
        num_keys=1,
    )
    seed = struct.unpack(">I", derived_bytes)[0]
    return seed
