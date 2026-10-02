"""
Bits-to-Symbols and Symbols-to-Bits mapping for BPSK and Gray-coded QPSK.
"""

import numpy as np


class ConstellationMapper:
    """Handles bit-to-symbol mapping and symbol slicing (demapping)."""

    # QPSK Gray constellation map: 00, 01, 11, 10
    QPSK_MAP = {
        (0, 0): (1.0 + 1.0j) / np.sqrt(2.0),
        (0, 1): (-1.0 + 1.0j) / np.sqrt(2.0),
        (1, 1): (-1.0 - 1.0j) / np.sqrt(2.0),
        (1, 0): (1.0 - 1.0j) / np.sqrt(2.0),
    }

    @staticmethod
    def bits_to_bpsk(bits: np.ndarray) -> np.ndarray:
        """Map bits (0 or 1) to BPSK complex symbols (-1 or +1)."""
        bits = np.asarray(bits, dtype=int)
        # 0 -> -1.0 + 0j, 1 -> +1.0 + 0j
        return (2.0 * bits - 1.0) + 0.0j

    @staticmethod
    def bpsk_to_bits(symbols: np.ndarray) -> np.ndarray:
        """Slice BPSK complex symbols back into bits (0 or 1)."""
        symbols = np.asarray(symbols, dtype=complex)
        return (np.real(symbols) >= 0.0).astype(int)

    @staticmethod
    def bits_to_qpsk(bits: np.ndarray) -> np.ndarray:
        """Map bit array to Gray-coded QPSK complex symbols."""
        bits = np.asarray(bits, dtype=int)
        if len(bits) % 2 != 0:
            raise ValueError(f"QPSK requires an even number of bits (got {len(bits)})")

        bit_pairs = bits.reshape(-1, 2)
        symbols = np.zeros(len(bit_pairs), dtype=complex)

        for i, pair in enumerate(bit_pairs):
            symbols[i] = ConstellationMapper.QPSK_MAP[(pair[0], pair[1])]

        return symbols

    @staticmethod
    def qpsk_to_bits(symbols: np.ndarray) -> np.ndarray:
        """Slice Gray-coded QPSK complex symbols into bits."""
        symbols = np.asarray(symbols, dtype=complex)
        bits = np.zeros(len(symbols) * 2, dtype=int)

        re = np.real(symbols)
        im = np.imag(symbols)

        for i in range(len(symbols)):
            r, m = re[i], im[i]
            if r >= 0 and m >= 0:
                b0, b1 = 0, 0
            elif r < 0 and m >= 0:
                b0, b1 = 0, 1
            elif r < 0 and m < 0:
                b0, b1 = 1, 1
            else:  # r >= 0 and m < 0
                b0, b1 = 1, 0

            bits[2 * i] = b0
            bits[2 * i + 1] = b1

        return bits
