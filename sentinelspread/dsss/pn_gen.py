"""
Pseudo-Noise (PN) sequence and m-sequence generation via Linear Feedback Shift Registers (LFSR).
Supports session-unique PN seed derivation from AES keys.
"""

from typing import Optional, Union
import numpy as np

from sentinelspread.crypto.key_mgmt import derive_pn_seed


# Known primitive polynomial feedback tap pairs for maximum-length sequences (m-sequences)
# Form: x^degree + x^k + 1
PRIMITIVE_POLYNOMIALS = {
    5: (5, 2),
    6: (6, 1),
    7: (7, 1),
    8: (8, 4),
    9: (9, 4),
    10: (10, 3),
    11: (11, 2),
}


class PNGenerator:
    """
    Maximal-length sequence (m-sequence) generator based on LFSR.
    Supports degrees 5 through 11 (minimum required: degree 7 and degree 10).
    """

    def __init__(
        self,
        degree: int = 7,
        seed: Optional[int] = None,
        aes_key: Optional[bytes] = None,
    ):
        if degree not in PRIMITIVE_POLYNOMIALS:
            raise ValueError(
                f"Unsupported LFSR degree {degree}. Supported degrees: {list(PRIMITIVE_POLYNOMIALS.keys())}"
            )

        self.degree = degree
        self.deg, self.k = PRIMITIVE_POLYNOMIALS[degree]
        self.period = (1 << degree) - 1
        self.mask = self.period

        # Determine initial seed
        if aes_key is not None:
            self.initial_seed = derive_pn_seed(aes_key)
        elif seed is not None:
            self.initial_seed = seed
        else:
            self.initial_seed = 1

        self.reset()

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the LFSR register state."""
        if seed is not None:
            self.initial_seed = seed

        # Ensure register is never all-zero
        state = self.initial_seed & self.mask
        self.state = state if state != 0 else 1

    def step(self) -> int:
        """Advance LFSR by one step and return output bit (0 or 1)."""
        out_bit = (self.state >> (self.deg - 1)) & 1
        feedback = ((self.state >> (self.deg - 1)) ^ (self.state >> (self.k - 1))) & 1
        self.state = ((self.state << 1) & self.mask) | feedback
        return out_bit

    def generate_chips(self, num_chips: int, bipolar: bool = True) -> np.ndarray:
        """
        Generate num_chips pseudo-noise chips.
        If bipolar=True, maps 0 -> -1.0, 1 -> +1.0.
        """
        raw_bits = np.empty(num_chips, dtype=int)
        for i in range(num_chips):
            raw_bits[i] = self.step()

        if bipolar:
            return 2.0 * raw_bits - 1.0
        return raw_bits

    def generate_msequence(self, bipolar: bool = True) -> np.ndarray:
        """Generate one full period (2^degree - 1) of the m-sequence."""
        return self.generate_chips(self.period, bipolar=bipolar)


def generate_gold_code(
    degree: int = 7,
    seed1: int = 1,
    seed2: int = 2,
    length: Optional[int] = None,
    bipolar: bool = True,
) -> np.ndarray:
    """
    Generate Gold sequence from pair of preferred m-sequences.
    """
    if length is None:
        length = (1 << degree) - 1

    gen1 = PNGenerator(degree=degree, seed=seed1)
    gen2 = PNGenerator(degree=degree, seed=seed2)

    bits1 = gen1.generate_chips(length, bipolar=False)
    bits2 = gen2.generate_chips(length, bipolar=False)
    gold_bits = bits1 ^ bits2

    if bipolar:
        return 2.0 * gold_bits - 1.0
    return gold_bits
