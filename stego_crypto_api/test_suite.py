"""
Comprehensive Test Suite for FastAPI StegoCrypto Suite
"""

import io
from PIL import Image
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_rsa_keygen_and_hybrid_crypto():
    keys = client.post("/api/crypto/generate-rsa-keys", json={"key_size": 2048}).json()
    assert "public_key_pem" in keys
    assert "private_key_pem" in keys

    plain = "SentinelSpread Test Message"
    enc = client.post("/api/crypto/encrypt-hybrid", json={"plaintext": plain, "public_key_pem": keys["public_key_pem"]}).json()
    dec = client.post("/api/crypto/decrypt-hybrid", json={"payload": enc, "private_key_pem": keys["private_key_pem"]}).json()
    assert dec["plaintext"] == plain

def test_signatures():
    keys = client.post("/api/crypto/generate-rsa-keys", json={"key_size": 2048}).json()
    msg = "Integrity Payload Check"
    sig = client.post("/api/crypto/sign", json={"message": msg, "private_key_pem": keys["private_key_pem"]}).json()
    ver = client.post("/api/crypto/verify", json={"message": msg, "signature_b64": sig["signature_b64"], "public_key_pem": keys["public_key_pem"]}).json()
    assert ver["valid"] is True

def test_aes_password():
    plain = "AES Password Secret"
    pwd = "TopSecretPassword123"
    enc = client.post("/api/crypto/encrypt-aes", json={"plaintext": plain, "password": pwd}).json()
    dec = client.post("/api/crypto/decrypt-aes", json={"ciphertext_payload": enc["ciphertext_payload"], "password": pwd}).json()
    assert dec["plaintext"] == plain
