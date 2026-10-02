"""
Input handler module: processes text string/file input and audio (WAV) input.
Applies header type-tagging before passing payloads to crypto/spreading layers.
"""

from pathlib import Path
import struct
from typing import Tuple, Union
import wave
import numpy as np

from sentinelspread.input.header import Header, PayloadType


class InputHandler:
    """Handles text and audio payload loading, header tagging, and saving."""

    @staticmethod
    def prepare_text_payload(text_or_path: Union[str, Path]) -> bytes:
        """Read text from string or file path, convert to UTF-8 bytes, and attach Header."""
        path = Path(text_or_path)
        if path.is_file():
            text_bytes = path.read_bytes()
        else:
            text_bytes = str(text_or_path).encode("utf-8")

        header = Header(payload_type=PayloadType.TEXT, original_length=len(text_bytes))
        return header.pack() + text_bytes

    @staticmethod
    def prepare_audio_payload(wav_path: Union[str, Path]) -> bytes:
        """Read WAV file raw content and attach Header."""
        path = Path(wav_path)
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {wav_path}")

        audio_bytes = path.read_bytes()
        header = Header(payload_type=PayloadType.AUDIO, original_length=len(audio_bytes))
        return header.pack() + audio_bytes

    @staticmethod
    def extract_payload(tagged_data: bytes) -> Tuple[Header, bytes]:
        """Extract header metadata and return (header, raw_payload_bytes)."""
        return Header.unpack(tagged_data)

    @staticmethod
    def save_payload(header: Header, payload: bytes, output_path: Union[str, Path]) -> Path:
        """Save extracted payload based on its Header payload_type."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    @staticmethod
    def generate_sample_wav(output_path: Union[str, Path], duration_sec: float = 0.5, freq: float = 440.0, sample_rate: int = 8000) -> Path:
        """Generate a simple sine-wave WAV file for testing purposes."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
        signal = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(signal.tobytes())

        return path
