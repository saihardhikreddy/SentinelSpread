"""
Production Cryptography Engine Module
-------------------------------------
Implements hybrid RSA-OAEP + AES-256-GCM encryption, RSA-PSS signatures,
and key management using PyCA Cryptography primitives.
"""

import os
import json
import base64
import hashlib
from typing import Tuple, Dict, Any

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


def generate_rsa_keypair(key_size: int = 2048) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate RSA private and public key pair."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    return private_key, private_key.public_key()


def export_public_key_pem(public_key: rsa.RSAPublicKey) -> str:
    """Export RSA public key to PEM format string."""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode('utf-8')


def export_private_key_pem(private_key: rsa.RSAPrivateKey) -> str:
    """Export RSA private key to PKCS8 PEM format string without password."""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    return pem.decode('utf-8')


def import_public_key_pem(pem_str: str) -> rsa.RSAPublicKey:
    """Import RSA public key from PEM string."""
    return serialization.load_pem_public_key(pem_str.encode('utf-8'), backend=default_backend())


def import_private_key_pem(pem_str: str) -> rsa.RSAPrivateKey:
    """Import RSA private key from PEM string."""
    return serialization.load_pem_private_key(pem_str.encode('utf-8'), password=None, backend=default_backend())


def hybrid_encrypt(plaintext: str, public_key: rsa.RSAPublicKey) -> Dict[str, Any]:
    """
    Encrypt plaintext message using Hybrid RSA-OAEP + AES-256-GCM.
    Returns dictionary with base64 encoded fields.
    """
    aes_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)
    
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    
    enc_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return {
        "mode": "webcrypto-hybrid",
        "enc_key_b64": base64.b64encode(enc_aes_key).decode('utf-8'),
        "nonce_b64": base64.b64encode(nonce).decode('utf-8'),
        "ciphertext_b64": base64.b64encode(ciphertext).decode('utf-8')
    }


def hybrid_decrypt(payload: Dict[str, Any], private_key: rsa.RSAPrivateKey) -> str:
    """
    Decrypt hybrid payload JSON object using RSA private key.
    """
    enc_aes_key = base64.b64decode(payload["enc_key_b64"])
    nonce = base64.b64decode(payload["nonce_b64"])
    ciphertext = base64.b64decode(payload["ciphertext_b64"])
    
    aes_key = private_key.decrypt(
        enc_aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    aesgcm = AESGCM(aes_key)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode('utf-8')


def sign_message(message: str, private_key: rsa.RSAPrivateKey) -> str:
    """Sign message using RSA-PSS signature."""
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')


def verify_signature(message: str, signature_b64: str, public_key: rsa.RSAPublicKey) -> bool:
    """Verify RSA-PSS signature."""
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def sha256_text(text: str) -> str:
    """Compute SHA-256 hex digest of string."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sha256_bytes(raw_bytes: bytes) -> str:
    """Compute SHA-256 hex digest of bytes."""
    return hashlib.sha256(raw_bytes).hexdigest()


def aes_encrypt_with_password(plaintext: str, password: str) -> Dict[str, Any]:
    """Encrypt plaintext using AES-256-GCM with PBKDF2 derived key."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=32)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    
    payload = {
        "enc": "aes-256-gcm",
        "salt_b64": base64.b64encode(salt).decode('utf-8'),
        "nonce_b64": base64.b64encode(nonce).decode('utf-8'),
        "ciphertext_b64": base64.b64encode(ciphertext).decode('utf-8')
    }
    return {"ciphertext_payload": json.dumps(payload)}


def aes_decrypt_with_password(payload_str: str, password: str) -> str:
    """Decrypt AES-256-GCM JSON payload string with password."""
    payload = json.loads(payload_str)
    salt = base64.b64decode(payload["salt_b64"])
    nonce = base64.b64decode(payload["nonce_b64"])
    ciphertext = base64.b64decode(payload["ciphertext_b64"])
    
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=32)
    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode('utf-8')


def encrypt_file_bytes(file_bytes: bytes, public_key: rsa.RSAPublicKey) -> bytes:
    """Encrypt binary file bytes using hybrid RSA-OAEP + AES-256-GCM package format."""
    aes_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, file_bytes, None)
    
    enc_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    pkg = {
        "magic": "STGENC",
        "enc_key_b64": base64.b64encode(enc_key).decode('utf-8'),
        "nonce_b64": base64.b64encode(nonce).decode('utf-8'),
        "ciphertext_b64": base64.b64encode(ciphertext).decode('utf-8')
    }
    return json.dumps(pkg).encode('utf-8')


def decrypt_file_bytes(pkg_bytes: bytes, private_key: rsa.RSAPrivateKey) -> bytes:
    """Decrypt hybrid file package bytes."""
    pkg = json.loads(pkg_bytes.decode('utf-8'))
    enc_key = base64.b64decode(pkg["enc_key_b64"])
    nonce = base64.b64decode(pkg["nonce_b64"])
    ciphertext = base64.b64decode(pkg["ciphertext_b64"])
    
    aes_key = private_key.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ciphertext, None)
