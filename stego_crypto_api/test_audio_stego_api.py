"""
Test Audio/Video Steganography Endpoints in FastAPI
"""

import io
import wave
import numpy as np
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def generate_test_wav_bytes():
    out_io = io.BytesIO()
    with wave.open(out_io, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        t = np.linspace(0, 2.0, 44100 * 2)
        samples = (np.sin(2 * np.pi * 440 * t) * 30000).astype(np.int16)
        wf.writeframes(samples.tobytes())
    return out_io.getvalue()

def test_audio_stego_api():
    print("Testing Audio/Video Steganography Web API Endpoints...")
    wav_bytes = generate_test_wav_bytes()
    secret_text = "TOP SECRET SENTINEL-SPREAD COMMUNICATE: 0x9F42"
    password = "MySecureAudioPassword2026"

    # 1. Test Embed Endpoint
    response = client.post(
        "/api/stego/audio/embed",
        data={"text": secret_text, "password": password},
        files={"file": ("test_input.wav", wav_bytes, "audio/wav")}
    )
    assert response.status_code == 200, f"Embed endpoint failed: {response.text}"
    stego_wav_bytes = response.content
    assert len(stego_wav_bytes) > 0, "Stego WAV output empty!"

    # 2. Test Extract Endpoint
    ext_response = client.post(
        "/api/stego/audio/extract",
        data={"password": password},
        files={"file": ("stego_output.wav", stego_wav_bytes, "audio/wav")}
    )
    assert ext_response.status_code == 200, f"Extract endpoint failed: {ext_response.text}"
    ext_data = ext_response.json()
    assert ext_data["status"] == "success"
    assert ext_data["extracted_text"] == secret_text

    # 3. Test Audio Quality Metrics Endpoint
    metrics_response = client.post(
        "/api/metrics/compare-audio",
        files={
            "original_file": ("orig.wav", wav_bytes, "audio/wav"),
            "modified_file": ("stego.wav", stego_wav_bytes, "audio/wav")
        }
    )
    assert metrics_response.status_code == 200, f"Compare audio endpoint failed: {metrics_response.text}"
    met_data = metrics_response.json()
    assert met_data["status"] == "success"
    assert "psnr_db" in met_data["metrics"]
    assert "snr_db" in met_data["metrics"]
    assert "mse" in met_data["metrics"]

if __name__ == "__main__":
    test_audio_stego_api()
