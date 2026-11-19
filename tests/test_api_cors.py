"""The web API's CORS policy: other websites may not call it from a browser."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stego_crypto_api"))
from main import app  # noqa: E402

client = TestClient(app)


def test_other_websites_get_no_cors_approval():
    pre = client.options("/api/radio/transmit", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    # Used to answer with the caller's origin and allow-credentials: true, so any page could
    # send JSON to every endpoint, including the one that keys the SDR.
    assert "access-control-allow-origin" not in pre.headers
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_the_bundled_frontend_still_works_same_origin():
    r = client.post("/api/crypto/hash", json={"text": "abc"})
    assert r.status_code == 200
    assert r.json()["hash_sha256"].startswith("ba7816bf")
