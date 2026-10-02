"""
Unit tests for input handling and header type-tagging.
"""

from pathlib import Path
import pytest
from sentinelspread.input.header import Header, PayloadType, MAGIC_BYTES, HEADER_VERSION
from sentinelspread.input.input_handler import InputHandler


def test_header_pack_unpack():
    orig_len = 1024
    header = Header(payload_type=PayloadType.TEXT, original_length=orig_len)
    packed = header.pack()

    unpacked_hdr, payload_rem = Header.unpack(packed)
    assert unpacked_hdr.magic == MAGIC_BYTES
    assert unpacked_hdr.version == HEADER_VERSION
    assert unpacked_hdr.payload_type == PayloadType.TEXT
    assert unpacked_hdr.original_length == orig_len
    assert len(payload_rem) == 0


def test_header_invalid_magic():
    bad_data = b"BADM" + b"\x01\x01\x00\x00\x00\x10\x00\x00\x00\x00"
    with pytest.raises(ValueError, match="Invalid magic bytes"):
        Header.unpack(bad_data)


def test_text_input_preparation(tmp_path: Path):
    text_data = "SentinelSpread Secret Message 12345! @#$%^&*()"
    tagged_payload = InputHandler.prepare_text_payload(text_data)

    header, payload = InputHandler.extract_payload(tagged_payload)
    assert header.payload_type == PayloadType.TEXT
    assert header.original_length == len(text_data.encode("utf-8"))
    assert payload.decode("utf-8") == text_data

    # Test file path input
    txt_file = tmp_path / "input.txt"
    txt_file.write_text(text_data, encoding="utf-8")
    file_tagged = InputHandler.prepare_text_payload(txt_file)
    hdr, body = InputHandler.extract_payload(file_tagged)
    assert body.decode("utf-8") == text_data


def test_audio_input_preparation(tmp_path: Path):
    wav_file = tmp_path / "sample.wav"
    InputHandler.generate_sample_wav(wav_file, duration_sec=0.1, sample_rate=8000)

    assert wav_file.is_file()
    orig_audio_bytes = wav_file.read_bytes()

    tagged_payload = InputHandler.prepare_audio_payload(wav_file)
    header, payload = InputHandler.extract_payload(tagged_payload)

    assert header.payload_type == PayloadType.AUDIO
    assert header.original_length == len(orig_audio_bytes)
    assert payload == orig_audio_bytes
