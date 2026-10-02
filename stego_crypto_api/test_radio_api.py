"""Tests for the live-transmission routes. They need the GNU Radio runtime (radioconda), so the
flowgraph tests skip cleanly on a machine without it; the validation tests always run."""

import pytest
from fastapi.testclient import TestClient

import radio
from main import app

client = TestClient(app)
needs_gnuradio = pytest.mark.skipif(not radio.RADIO_PYTHON.is_file(), reason="radioconda python not found")
MESSAGE = "Meet at the north gate, 21:40."


def test_routes_are_registered():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/radio/transmit", "/api/radio/receive", "/api/radio/wav/{transmission_id}", "/api/radio/status"):
        assert p in paths


def test_rejects_unsupported_spreading_factor():
    r = client.post("/api/radio/transmit", json={"message": "hi", "spreading_factor": 7, "noise_voltage": 0.02})
    assert r.status_code == 400
    assert "Spreading factor" in r.json()["detail"]


def test_rejects_empty_message_and_negative_noise():
    assert client.post("/api/radio/transmit", json={"message": "", "spreading_factor": 16, "noise_voltage": 0.02}).status_code == 422
    assert client.post("/api/radio/transmit", json={"message": "x", "spreading_factor": 16, "noise_voltage": -1}).status_code == 422


def test_receive_rejects_path_traversal_and_unknown_ids():
    assert client.post("/api/radio/receive", json={"transmission_id": "../../etc/passwd"}).status_code == 400
    assert client.post("/api/radio/receive", json={"transmission_id": "000000000000"}).status_code == 404
    assert client.get("/api/radio/wav/..%2f..%2fsecret").status_code in (400, 404)


@needs_gnuradio
@pytest.mark.parametrize("sf", [16, 64])
def test_round_trip_recovers_exact_message(sf):
    tx = client.post("/api/radio/transmit", json={"message": MESSAGE, "spreading_factor": sf, "noise_voltage": 0.02})
    assert tx.status_code == 200, tx.text
    body = tx.json()
    assert body["bundle_bytes"] == 306 + len(MESSAGE.encode())          # the formula the UI's estimate relies on
    assert body["num_chips"] == body["bundle_bytes"] * 8 * sf + 1279
    wav = client.get(body["wav_url"])
    assert wav.status_code == 200 and wav.headers["content-type"] == "audio/wav"
    rx = client.post("/api/radio/receive", json={"transmission_id": body["transmission_id"]})
    assert rx.status_code == 200, rx.text
    assert rx.json()["recovered_text"] == MESSAGE and rx.json()["bit_errors"] == 0


@needs_gnuradio
def test_heavy_noise_is_a_readable_400_not_a_500():
    tx = client.post("/api/radio/transmit", json={"message": MESSAGE, "spreading_factor": 16, "noise_voltage": 0.6}).json()
    rx = client.post("/api/radio/receive", json={"transmission_id": tx["transmission_id"]})
    assert rx.status_code == 400
    detail = rx.json()["detail"]
    assert "Could not decode" in detail["message"] and detail["total_bits"] > 0 and detail["ber"] > 0.1
