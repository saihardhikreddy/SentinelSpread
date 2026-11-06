"""
RSA Key Management: generation, export, and import of RSA keypairs.
"""

import os
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
    """Export RSA key to PEM file. Private keys are readable by the owner only."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pem_data = key.export_key(format="PEM")
    if not key.has_private():
        path.write_bytes(pem_data)
        return path
    # Create the file as 0600 rather than chmod-ing it afterwards, so the key is
    # never briefly readable by other users. Windows ignores the mode bits.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem_data)
    if os.name == "posix":
        os.chmod(path, 0o600)  # an existing file keeps its old mode on O_TRUNC
    return path


def import_key(key_path: Union[str, Path]) -> RSA.RsaKey:
    """Import RSA key from PEM file or bytes."""
    path = Path(key_path)
    key_bytes = path.read_bytes()
    return RSA.import_key(key_bytes)
