"""
Direct Sequence Spread Spectrum (DSSS) Spreader.
Spreads narrowband data symbols into wideband chip streams.
"""

from typing import Optional, Tuple
import numpy as np

from sentinelspread.dsss.pn_gen import PNGenerator


VALID_SPREADING_FACTORS = (16, 32, 64, 128)


class DSSSSpreader:
    """
    DSSS Transmit Spreader.
    Multiplies each data symbol by SF pseudo-noise chips.
    """

    def __init__(
        self,
        spreading_factor: int = 16,
        pn_gen: Optional[PNGenerator] = None,
        seed: Optional[int] = None,
        aes_key: Optional[bytes] = None,
        degree: int = 7,
    ):
        if spreading_factor not in VALID_SPREADING_FACTORS:
            raise ValueError(
                f"Spreading factor {spreading_factor} not supported. Must be one of {VALID_SPREADING_FACTORS}"
            )

        self.sf = spreading_factor
        self.degree = degree

        if pn_gen is not None:
            self.pn_gen = pn_gen
        else:
            self.pn_gen = PNGenerator(degree=degree, seed=seed, aes_key=aes_key)

    @property
    def processing_gain_db(self) -> float:
        """Theoretical processing gain in dB: Gp = 10 * log10(SF)."""
        return float(10.0 * np.log10(self.sf))

    def spread(
        self,
        symbols: np.ndarray,
        pn_sequence: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Spread data symbols into chips.

        Parameters:
            symbols: Array of complex or real modulation symbols.
            pn_sequence: Optional pre-generated PN chip array. If None, generated from pn_gen.

        Returns:
            (spread_chips, pn_sequence_used)
        """
        symbols = np.asarray(symbols)
        num_symbols = len(symbols)
        total_chips = num_symbols * self.sf

        if pn_sequence is None:
            pn_chips = self.pn_gen.generate_chips(total_chips, bipolar=True)
        else:
            if len(pn_sequence) < total_chips:
                raise ValueError(
                    f"PN sequence length ({len(pn_sequence)}) is shorter than required chips ({total_chips})"
                )
            pn_chips = pn_sequence[:total_chips]

        # Spread each symbol across SF chips
        repeated_symbols = np.repeat(symbols, self.sf)
        spread_chips = repeated_symbols * pn_chips

        return spread_chips, pn_chips

    def spread_frame(
        self,
        symbols: np.ndarray,
        preamble_length: int = 127,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Creates a framed DSSS transmission:
            [Preamble Chips] + [Spread Data Chips]

        Returns:
            (frame_chips, data_pn_chips, preamble_chips)
        """
        # Preamble from a fixed known sync generator
        preamble_gen = PNGenerator(degree=7, seed=0x5A)
        preamble_chips = preamble_gen.generate_chips(preamble_length, bipolar=True)

        data_chips, data_pn = self.spread(symbols)
        frame_chips = np.concatenate([preamble_chips, data_chips])

        return frame_chips, data_pn, preamble_chips
