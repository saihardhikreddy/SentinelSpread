"""
Direct Sequence Spread Spectrum (DSSS) Despreading and Correlation.
Includes coherent sliding correlator for chip acquisition and early-late gate tracking.
"""

from typing import Optional, Tuple
import numpy as np

from sentinelspread.dsss.pn_gen import PNGenerator
from sentinelspread.dsss.spreader import VALID_SPREADING_FACTORS


class DSSSCorrelator:
    """
    DSSS Receive Correlator and Despreader.
    Performs sliding correlation sync, early-late error detection, and chip despreading.
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

    def find_lock_offset(
        self,
        rx_chips: np.ndarray,
        sync_pattern: np.ndarray,
        search_window: int = 256,
    ) -> Tuple[int, float]:
        """
        Sliding Correlator:
        Searches over PN phase offsets within search_window to find the lock index.

        Returns:
            (best_offset, peak_correlation_magnitude)
        """
        rx = np.asarray(rx_chips)
        sync = np.asarray(sync_pattern)
        sync_len = len(sync)

        max_search = min(search_window, len(rx) - sync_len)
        if max_search <= 0:
            return 0, 0.0

        corrs = np.empty(max_search, dtype=float)
        for tau in range(max_search):
            segment = rx[tau : tau + sync_len]
            # Coherent cross-correlation with reference pattern
            corrs[tau] = np.abs(np.mean(segment * sync))

        best_offset = int(np.argmax(corrs))
        peak_val = float(corrs[best_offset])
        return best_offset, peak_val

    def early_late_gate(
        self,
        rx_chips: np.ndarray,
        lock_idx: int,
        sync_pattern: np.ndarray,
        delta: int = 1,
    ) -> float:
        """
        Early-Late Gate Timing Error Detector (Delay-Locked Loop).
        Computes timing error e = |R_early| - |R_late|.

        Returns:
            timing_error: > 0 means peak is early, < 0 means peak is late.
        """
        rx = np.asarray(rx_chips)
        sync = np.asarray(sync_pattern)
        sync_len = len(sync)

        early_idx = lock_idx - delta
        late_idx = lock_idx + delta

        if early_idx < 0 or late_idx + sync_len > len(rx):
            return 0.0

        r_early = np.abs(np.mean(rx[early_idx : early_idx + sync_len] * sync))
        r_late = np.abs(np.mean(rx[late_idx : late_idx + sync_len] * sync))

        return float(r_early - r_late)

    def despread(
        self,
        rx_chips: np.ndarray,
        pn_sequence: np.ndarray,
        offset: int = 0,
        num_symbols: Optional[int] = None,
    ) -> np.ndarray:
        """
        Coherently despreads chips into data symbols.

        Parameters:
            rx_chips: Received chip array (complex or float).
            pn_sequence: Reference bipolar PN chips matching transmission.
            offset: Aligned start chip offset.
            num_symbols: Number of symbols to despread. If None, derived from lengths.

        Returns:
            Despread symbols array with processing gain applied.
        """
        rx = np.asarray(rx_chips)
        pn = np.asarray(pn_sequence)

        available_chips = len(rx) - offset
        if num_symbols is None:
            num_symbols = min(available_chips // self.sf, len(pn) // self.sf)

        total_chips = num_symbols * self.sf
        if total_chips <= 0:
            return np.array([])

        aligned_rx = rx[offset : offset + total_chips]
        matched_pn = pn[:total_chips]

        # Elementwise multiplication followed by SF-chip block averaging
        product = aligned_rx * matched_pn
        reshaped = product.reshape((num_symbols, self.sf))
        despread_symbols = np.mean(reshaped, axis=1)

        return despread_symbols

    def despread_frame(
        self,
        rx_frame: np.ndarray,
        data_pn_sequence: np.ndarray,
        preamble_length: int = 127,
        num_symbols: Optional[int] = None,
        search_window: int = 256,
    ) -> Tuple[np.ndarray, int]:
        """
        Full frame synchronization and despreading:
        1. Acquire frame lock via preamble sliding correlator.
        2. Despread data symbols following the preamble.

        Returns:
            (despread_symbols, lock_offset)
        """
        preamble_gen = PNGenerator(degree=7, seed=0x5A)
        preamble_chips = preamble_gen.generate_chips(preamble_length, bipolar=True)

        lock_offset, _ = self.find_lock_offset(rx_frame, preamble_chips, search_window=search_window)
        data_start = lock_offset + preamble_length

        symbols = self.despread(
            rx_frame,
            pn_sequence=data_pn_sequence,
            offset=data_start,
            num_symbols=num_symbols,
        )
        return symbols, lock_offset
