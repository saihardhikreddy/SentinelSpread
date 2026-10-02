"""
Synchronization module: Symbol timing recovery, Costas loop carrier phase recovery,
and Preamble-assisted Phase Ambiguity Resolution.
"""

import numpy as np
from sentinelspread.modem.mapper import ConstellationMapper


class CostasLoop:
    """
    Second-order Costas Loop for carrier frequency and phase tracking.
    Supports BPSK and QPSK constellations.
    """

    def __init__(self, scheme: str = "BPSK", loop_bw: float = 0.005, damping: float = 0.707, enabled: bool = True):
        self.scheme = scheme.upper()
        self.enabled = enabled
        denom = 1.0 + 2.0 * damping * loop_bw + loop_bw**2
        self.alpha = (4.0 * damping * loop_bw) / denom
        self.beta = (4.0 * loop_bw**2) / denom

    def process(self, iq_samples: np.ndarray) -> np.ndarray:
        """
        Processes complex IQ samples through Costas loop to remove residual carrier phase/frequency offset.
        """
        if not self.enabled:
            return iq_samples

        N = len(iq_samples)
        corrected_samples = np.zeros(N, dtype=complex)

        phase = 0.0
        freq = 0.0

        for i in range(N):
            sample = iq_samples[i] * np.exp(-1j * phase)
            corrected_samples[i] = sample

            if self.scheme == "BPSK":
                error = np.sign(np.real(sample)) * np.imag(sample)
            else:  # QPSK
                error = np.sign(np.real(sample)) * np.imag(sample) - np.sign(np.imag(sample)) * np.real(sample)

            freq += self.beta * error
            phase += freq + self.alpha * error
            phase = (phase + np.pi) % (2.0 * np.pi) - np.pi

        return corrected_samples


def resolve_phase_ambiguity(
    symbols: np.ndarray, scheme: str = "BPSK", ref_bits: np.ndarray = None
) -> np.ndarray:
    """
    Resolves 180-degree (BPSK) or 90-degree (QPSK) phase ambiguity using preamble reference bits
    or constellation decision metric.
    """
    symbols = np.asarray(symbols, dtype=complex)
    scheme_upper = scheme.upper()
    rotations = [0.0, np.pi / 2.0, np.pi, 3.0 * np.pi / 2.0] if scheme_upper == "QPSK" else [0.0, np.pi]

    best_symbols = symbols
    min_errors = float("inf")

    if ref_bits is not None and len(ref_bits) > 0:
        ref_bits = np.asarray(ref_bits, dtype=int)
        num_ref_symbols = len(ref_bits) if scheme_upper == "BPSK" else len(ref_bits) // 2
        num_ref_symbols = min(num_ref_symbols, len(symbols))
        test_syms = symbols[:num_ref_symbols]

        for rot in rotations:
            rotated = test_syms * np.exp(-1j * rot)
            if scheme_upper == "BPSK":
                demapped = ConstellationMapper.bpsk_to_bits(rotated)
            else:
                demapped = ConstellationMapper.qpsk_to_bits(rotated)

            errors = np.sum(ref_bits[: len(demapped)] != demapped)
            if errors < min_errors:
                min_errors = errors
                best_symbols = symbols * np.exp(-1j * rot)
    else:
        min_dist = float("inf")
        for rot in rotations:
            rotated = symbols * np.exp(-1j * rot)
            if scheme_upper == "BPSK":
                sliced = np.sign(np.real(rotated)) + 0.0j
                sliced[sliced == 0] = -1.0
            else:
                r_slice = np.sign(np.real(rotated))
                i_slice = np.sign(np.imag(rotated))
                r_slice[r_slice == 0] = 1.0
                i_slice[i_slice == 0] = 1.0
                sliced = (r_slice + 1j * i_slice) / np.sqrt(2.0)

            dist = np.sum(np.abs(rotated - sliced) ** 2)
            if dist < min_dist:
                min_dist = dist
                best_symbols = rotated

    return best_symbols


class SymbolTimingRecovery:
    """
    Symbol timing recovery based on max-energy optimum sampling phase search.
    """

    def __init__(self, sps: int = 4, filter_delay: int = 0):
        self.sps = sps
        self.filter_delay = filter_delay

    def recover_symbols(self, matched_filtered_signal: np.ndarray, expected_num_symbols: int = None) -> np.ndarray:
        """
        Finds the optimal sampling phase and downsamples matched filter output to 1 sample/symbol.
        """
        signal = np.asarray(matched_filtered_signal, dtype=complex)

        best_phase = 0
        max_energy = -1.0
        start_offset = 2 * self.filter_delay

        for phase in range(self.sps):
            test_indices = np.arange(start_offset + phase, len(signal), self.sps)
            if len(test_indices) == 0:
                continue
            energy = np.sum(np.abs(signal[test_indices]) ** 2)
            if energy > max_energy:
                max_energy = energy
                best_phase = phase

        sample_indices = np.arange(start_offset + best_phase, len(signal), self.sps)

        if expected_num_symbols is not None and len(sample_indices) > expected_num_symbols:
            sample_indices = sample_indices[:expected_num_symbols]

        return signal[sample_indices]
