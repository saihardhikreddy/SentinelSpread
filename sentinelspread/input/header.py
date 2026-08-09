"""
Header definition and serialization for type-tagging incoming payloads.
"""

from enum import IntEnum
import struct
from typing import Tuple


class PayloadType(IntEnum):
    TEXT = 1
    AUDIO = 2


MAGIC_BYTES = b"SSPD"
HEADER_VERSION = 1
HEADER_FORMAT = ">4sBBII"  # Magic (4s), Version (B), Type (B), Length (I), Reserved (I)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class Header:
    """Header structure containing payload metadata."""

    def __init__(self, payload_type: PayloadType, original_length: int, version: int = HEADER_VERSION):
        self.magic = MAGIC_BYTES
        self.version = version
        self.payload_type = PayloadType(payload_type)
        self.original_length = original_length

    def pack(self) -> bytes:
        """Pack header metadata into binary format."""
        return struct.pack(
            HEADER_FORMAT,
            self.magic,
            self.version,
            int(self.payload_type),
            self.original_length,
            0,  # Reserved field for alignment/future flags
        )

    @classmethod
    def unpack(cls, data: bytes) -> Tuple["Header", bytes]:
        """Unpack binary data into a Header object and remaining payload bytes."""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Data length ({len(data)} B) is smaller than header size ({HEADER_SIZE} B)")

        magic, version, ptype, orig_len, _ = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])

        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic bytes in header: {magic} != {MAGIC_BYTES}")

        if version != HEADER_VERSION:
            raise ValueError(f"Unsupported header version: {version}")

        header = cls(payload_type=PayloadType(ptype), original_length=orig_len, version=version)
        payload = data[HEADER_SIZE:]

        return header, payload

    def __repr__(self) -> str:
        return f"<Header magic={self.magic.decode()} ver={self.version} type={self.payload_type.name} len={self.original_length}>"
