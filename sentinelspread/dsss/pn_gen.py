"""
Pseudo-Noise (PN) sequence and m-sequence generation via Linear Feedback Shift Registers (LFSR).
Supports session-unique PN seed derivation from AES keys.
"""

from typing import Optional
import numpy as np

from sentinelspread.crypto.key_mgmt import derive_pn_seed


# Feedback taps of primitive polynomials, so each LFSR produces a maximum-length sequence
# (period 2^degree - 1). (deg, k) is x^deg + x^k + 1. Degree 8 has no primitive trinomial, so it
# needs four taps: x^8 + x^6 + x^5 + x^4 + 1. (The old pair (8, 4) repeated every 12 chips.)
PRIMITIVE_POLYNOMIALS = {
    5: (5, 2),
    6: (6, 1),
    7: (7, 1),
    8: (8, 6, 5, 4),
    9: (9, 4),
    10: (10, 3),
    11: (11, 2),
}


# Preferred pairs of primitive polynomials, in the same tap notation: the two m-sequences of a
# pair cross-correlate at only three values, which is what makes their XORs a Gold family.
# Degree 8 (a multiple of 4) has no preferred pairs.
GOLD_PREFERRED_PAIRS = {
    5: ((5, 2), (5, 4, 3, 2)),
    6: ((6, 1), (6, 5, 2, 1)),
    7: ((7, 3), (7, 3, 2, 1)),
    9: ((9, 4), (9, 6, 4, 3)),
    10: ((10, 3), (10, 8, 3, 2)),
    11: ((11, 2), (11, 8, 5, 2)),
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
        taps: Optional[tuple] = None,
    ):
        if degree not in PRIMITIVE_POLYNOMIALS:
            raise ValueError(
                f"Unsupported LFSR degree {degree}. Supported degrees: {list(PRIMITIVE_POLYNOMIALS.keys())}"
            )
        if taps is not None and (not taps or taps[0] != degree):
            raise ValueError(f"taps must start with the degree {degree}, got {taps!r}")

        self.degree = degree
        taps = taps or PRIMITIVE_POLYNOMIALS[degree]
        self.deg = taps[0]
        self.taps = taps[1:]
        self.k = self.taps[0]
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
        feedback = self.state >> (self.deg - 1)
        for t in self.taps:
            feedback ^= self.state >> (t - 1)
        feedback &= 1
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
    Generate a Gold sequence: the XOR of the m-sequences of a preferred pair of polynomials.
    Different seeds shift the second sequence against the first and give different members of
    the family.

    Both generators used to share one polynomial. By the shift-and-add property, the XOR of two
    shifts of the same m-sequence is just a third shift of it, so every "Gold code" was the
    plain m-sequence, with its poor cross-correlation between codes.
    """
    if degree not in GOLD_PREFERRED_PAIRS:
        raise ValueError(f"No preferred pair for degree {degree}; Gold codes are available for "
                         f"degrees {sorted(GOLD_PREFERRED_PAIRS)}")
    if length is None:
        length = (1 << degree) - 1

    taps1, taps2 = GOLD_PREFERRED_PAIRS[degree]
    gen1 = PNGenerator(degree=degree, seed=seed1, taps=taps1)
    gen2 = PNGenerator(degree=degree, seed=seed2, taps=taps2)

    bits1 = gen1.generate_chips(length, bipolar=False)
    bits2 = gen2.generate_chips(length, bipolar=False)
    gold_bits = bits1 ^ bits2

    if bipolar:
        return 2.0 * gold_bits - 1.0
    return gold_bits
