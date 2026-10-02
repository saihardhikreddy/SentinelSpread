"""
Carrier and symbol synchronization:
- 2nd-order Costas Loop for carrier phase/frequency recovery.
- Symbol timing recovery and optimal downsampling.
- Constellation rotational phase ambiguity resolution via preamble correlation.
"""

import numpy as np
from sentinelspread.modem.mapper import ConstellationMapper


class CostasLoop:
    """2nd-order Costas Loop carrier phase and frequency tracking."""

    def __init__(
        self,
        scheme: str = "BPSK",
        alpha: float = 0.05,
        beta: float = 0.001,
        enabled: bool = False,
    ):
        self.scheme = scheme.upper()
        self.alpha = alpha
        self.beta = beta
        self.enabled = enabled
        self.phase = 0.0
        self.freq = 0.0

    def process(self, samples: np.ndarray) -> np.ndarray:
        """
        Process complex samples through Costas loop.
        If disabled, passes samples through transparently.
        """
        if not self.enabled:
            return samples

        samples = np.asarray(samples, dtype=complex)
        out = np.zeros_like(samples)

        for n in range(len(samples)):
            # Rotate input sample by current phase estimate
            z = samples[n] * np.exp(-1j * self.phase)
            out[n] = z

            # Phase error detector
            re_z = np.real(z)
            im_z = np.imag(z)
            sgn_re = 1.0 if re_z >= 0.0 else -1.0
            sgn_im = 1.0 if im_z >= 0.0 else -1.0

            if self.scheme == "BPSK":
                # BPSK phase error detector: Im{z} * sgn(Re{z})
                phi_e = im_z * sgn_re
            else:
                # QPSK phase error detector: Im{z} * sgn(Re{z}) - Re{z} * sgn(Im{z})
                phi_e = im_z * sgn_re - re_z * sgn_im

            # Loop filter updates
            self.freq += self.beta * phi_e
            self.phase += self.freq + self.alpha * phi_e

            # Wrap phase to [-pi, pi)
            self.phase = (self.phase + np.pi) % (2.0 * np.pi) - np.pi

        return out


class SymbolTimingRecovery:
    """Symbol timing recovery and optimal eye-diagram downsampling."""

    def __init__(self, sps: int = 4, filter_delay: int = 20):
        self.sps = sps
        self.filter_delay = filter_delay

    def recover_symbols(
        self, samples: np.ndarray, expected_num_symbols: int = None
    ) -> np.ndarray:
        """
        Downsamples matched-filtered samples at the center opening of the eye diagram.
        Accounts for cascaded TX + RX filter delay (2 * filter_delay).
        Normalizes amplitude by 1/sqrt(sps) to restore unit constellation power.
        """
        samples = np.asarray(samples, dtype=complex)
        start_idx = 2 * self.filter_delay

        if expected_num_symbols is not None:
            end_idx = start_idx + expected_num_symbols * self.sps
            downsampled = samples[start_idx:end_idx:self.sps]
        else:
            downsampled = samples[start_idx::self.sps]

        return downsampled / np.sqrt(self.sps)


def resolve_phase_ambiguity(
    symbols: np.ndarray,
    scheme: str = "BPSK",
    ref_bits: np.ndarray = None,
) -> np.ndarray:
    """
    Resolve 90-degree / 180-degree rotational ambiguity using known reference preamble bits.
    """
    if ref_bits is None or len(ref_bits) == 0 or len(symbols) == 0:
        return symbols

    symbols = np.asarray(symbols, dtype=complex)
    scheme = scheme.upper()

    if scheme == "BPSK":
        candidate_rotations = [0.0, np.pi]
        ref_symbols = ConstellationMapper.bits_to_bpsk(ref_bits)
    else:
        candidate_rotations = [0.0, np.pi / 2.0, np.pi, 3.0 * np.pi / 2.0]
        if len(ref_bits) % 2 != 0:
            ref_bits = ref_bits[:-1]
        ref_symbols = ConstellationMapper.bits_to_qpsk(ref_bits)

    compare_len = min(len(symbols), len(ref_symbols))
    if compare_len == 0:
        return symbols

    best_rot = 0.0
    best_corr = -float("inf")

    for rot in candidate_rotations:
        rot_factor = np.exp(-1j * rot)
        cand_symbols = symbols[:compare_len] * rot_factor
        # Metric is real part of cross-correlation with reference
        corr = np.real(np.sum(cand_symbols * np.conj(ref_symbols[:compare_len])))
        if corr > best_corr:
            best_corr = corr
            best_rot = rot

    return symbols * np.exp(-1j * best_rot)
