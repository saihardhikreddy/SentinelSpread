"""
RSA Key Management: generation, export, and import of RSA keypairs.
"""

from pathlib import Path
from typing import Tuple, Union
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF


def derive_pn_seed(aes_key: bytes) -> int:
    """Derive a session-unique DSSS PN seed from the ephemeral AES session key
    via HKDF-SHA256, so the spreading sequence changes every session instead
    of reusing a static seed from config.yaml."""
    derived_bytes = HKDF(
        master=aes_key,
        key_len=4,
        salt=b"",
        hashmod=SHA256,
        context=b"sentinelspread-dsss-pn-seed",
    )
    seed = int.from_bytes(derived_bytes, byteorder="big")
    return seed if seed != 0 else 1


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
