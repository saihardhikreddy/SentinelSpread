"""
Constellation mapping and demapping for BPSK and Gray-coded QPSK.
"""

import numpy as np


class ConstellationMapper:
    """Provides constellation mapping and demapping routines."""

    @staticmethod
    def bits_to_bpsk(bits: np.ndarray) -> np.ndarray:
        """
        Maps binary bits [0, 1] to BPSK symbols [-1.0, +1.0].
        k = 1 bit/symbol, Es = 1.0.
        """
        bits = np.asarray(bits, dtype=int)
        symbols = 2.0 * bits - 1.0
        return symbols.astype(complex)

    @staticmethod
    def bpsk_to_bits(symbols: np.ndarray) -> np.ndarray:
        """
        Demaps BPSK symbols to binary bits [0, 1] using optimal threshold at 0.
        """
        symbols = np.asarray(symbols)
        return (np.real(symbols) >= 0.0).astype(int)

    @staticmethod
    def bits_to_qpsk(bits: np.ndarray) -> np.ndarray:
        """
        Maps binary bit pairs [b0, b1] to Gray-coded QPSK symbols:
            00 -> (-1 - 1j) / sqrt(2)
            01 -> (-1 + 1j) / sqrt(2)
            11 -> (+1 + 1j) / sqrt(2)
            10 -> (+1 - 1j) / sqrt(2)
        k = 2 bits/symbol, Es = 1.0. Adjacent points differ by exactly 1 bit.
        """
        bits = np.asarray(bits, dtype=int)
        if len(bits) % 2 != 0:
            raise ValueError("QPSK mapping requires an even number of bits")

        b0 = bits[0::2]
        b1 = bits[1::2]
        i = 2.0 * b0 - 1.0
        q = 2.0 * b1 - 1.0
        symbols = (i + 1j * q) / np.sqrt(2.0)
        return symbols

    @staticmethod
    def qpsk_to_bits(symbols: np.ndarray) -> np.ndarray:
        """
        Demaps Gray-coded QPSK symbols to bit stream [b0, b1, ...].
        Decisions are independent on I and Q channels.
        """
        symbols = np.asarray(symbols)
        b0 = (np.real(symbols) >= 0.0).astype(int)
        b1 = (np.imag(symbols) >= 0.0).astype(int)

        bits = np.empty(len(symbols) * 2, dtype=int)
        bits[0::2] = b0
        bits[1::2] = b1
        return bits

    @staticmethod
    def bytes_to_bits(data: bytes) -> np.ndarray:
        """Convert bytes to an array of individual bits (MSB first)."""
        byte_arr = np.frombuffer(data, dtype=np.uint8)
        bits = np.unpackbits(byte_arr)
        return bits

    @staticmethod
    def bits_to_bytes(bits: np.ndarray) -> bytes:
        """Convert an array of individual bits (MSB first) back to bytes."""
        bits = np.asarray(bits, dtype=np.uint8)
        # Pad with zeros to multiple of 8 if needed
        rem = len(bits) % 8
        if rem != 0:
            pad = 8 - rem
            bits = np.pad(bits, (0, pad), mode="constant", constant_values=0)
        packed = np.packbits(bits)
        return packed.tobytes()
