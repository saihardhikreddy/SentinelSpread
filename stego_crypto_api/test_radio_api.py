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
    # sigma 5.0 is -20 dB per sample: beyond what even the despread-first receiver can find.
    tx = client.post("/api/radio/transmit", json={"message": MESSAGE, "spreading_factor": 16, "noise_voltage": 5.0}).json()
    rx = client.post("/api/radio/receive", json={"transmission_id": tx["transmission_id"]})
    assert rx.status_code == 400
    detail = rx.json()["detail"]
    assert "Could not decode" in detail["message"] and detail["total_bits"] > 0 and detail["ber"] > 0.1
    assert "raise the spreading factor" in detail["message"]


@needs_gnuradio
def test_decodes_below_the_noise_floor():
    # sigma 1.4 is -8.9 dB SNR per sample: the noise is stronger than the signal. The default
    # despread-first receiver recovers the exact text at SF 64 (measured to sigma 2.0 there).
    tx = client.post("/api/radio/transmit", json={"message": MESSAGE, "spreading_factor": 64, "noise_voltage": 1.4}).json()
    assert tx["snr_db"] < 0
    rx = client.post("/api/radio/receive", json={"transmission_id": tx["transmission_id"]})
    assert rx.status_code == 200, rx.text
    body = rx.json()
    assert body["recovered_text"] == MESSAGE and body["bit_errors"] == 0 and body["receiver"] == "despread"


@needs_gnuradio
def test_classic_receiver_cannot_use_spreading_gain():
    # The same -8.9 dB channel defeats the classic chain at any SF: it locks on the raw chips.
    tx = client.post("/api/radio/transmit", json={"message": MESSAGE, "spreading_factor": 64, "noise_voltage": 1.4,
                                                 "receiver": "classic"}).json()
    rx = client.post("/api/radio/receive", json={"transmission_id": tx["transmission_id"]})
    assert rx.status_code == 400
    assert "a higher spreading factor will not help" in rx.json()["detail"]["message"]


# Pluto channel: only the refusal paths are tested here. None of them transmit, so the suite is
# safe to run with a Pluto plugged in (and antennas on); real-RF runs are done by hand.

def test_rejects_unknown_channel_and_bad_uri():
    assert client.post("/api/radio/transmit", json={"message": "x", "channel": "bogus"}).status_code == 422
    assert client.post("/api/radio/transmit", json={"message": "x", "channel": "pluto", "pluto_uri": "file:/etc"}).status_code == 422


def test_pluto_refuses_without_cabling_confirmation():
    r = client.post("/api/radio/transmit", json={"message": "x", "channel": "pluto"})
    assert r.status_code == 400 and "Refusing to transmit" in r.json()["detail"]


def test_pluto_bare_cable_enforces_attenuation_floor():
    r = client.post("/api/radio/transmit", json={"message": "x", "channel": "pluto", "direct_cable": True, "tx_atten_db": 30})
    assert r.status_code == 400 and "at least 60 dB" in r.json()["detail"]


@needs_gnuradio
def test_pluto_missing_board_is_a_400():
    r = client.post("/api/radio/transmit", json={"message": "x", "channel": "pluto", "direct_cable": True, "pluto_uri": "usb:9.9.9"})
    assert r.status_code == 400 and "ADALM-Pluto not detected at usb:9.9.9" in r.json()["detail"]


@needs_gnuradio
def test_status_reports_pluto_detection():
    body = client.get("/api/radio/status").json()
    assert body["channels"] == ["sim", "pluto"]
    assert isinstance(body["pluto"]["detected"], bool)
