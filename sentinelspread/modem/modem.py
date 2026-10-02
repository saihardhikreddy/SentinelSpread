"""
BPSK and QPSK Modem implementations combining mapping, pulse shaping, matched filtering, and synchronization.
"""

import numpy as np
from sentinelspread.modem.mapper import ConstellationMapper
from sentinelspread.modem.rrc import RRCFilter
from sentinelspread.modem.sync import CostasLoop, SymbolTimingRecovery, resolve_phase_ambiguity


class Modem:
    """Unified Baseband Modem supporting BPSK and QPSK schemes."""

    def __init__(self, scheme: str = "BPSK", rrc_alpha: float = 0.35, sps: int = 4, span: int = 10, enable_costas: bool = False):
        self.scheme = scheme.upper()
        if self.scheme not in ("BPSK", "QPSK"):
            raise ValueError(f"Unsupported modulation scheme: {scheme}")

        self.rrc_alpha = rrc_alpha
        self.sps = sps
        self.span = span

        self.rrc = RRCFilter(rrc_alpha=rrc_alpha, sps=sps, span=span)
        self.timing_recovery = SymbolTimingRecovery(sps=sps, filter_delay=self.rrc.filter_delay)
        self.costas_loop = CostasLoop(scheme=self.scheme, enabled=enable_costas)

    def modulate(self, bits: np.ndarray) -> np.ndarray:
        """
        Transmit Chain:
            bits -> constellation mapper -> RRC pulse shaping -> complex IQ baseband samples.
        """
        bits = np.asarray(bits, dtype=int)
        if self.scheme == "BPSK":
            symbols = ConstellationMapper.bits_to_bpsk(bits)
        else:
            symbols = ConstellationMapper.bits_to_qpsk(bits)

        iq_samples = self.rrc.shape_pulses(symbols)
        return iq_samples

    def demodulate(self, iq_samples: np.ndarray, expected_num_bits: int = None, ref_bits: np.ndarray = None) -> np.ndarray:
        """
        Receive Chain:
            IQ samples -> matched filter -> Costas loop phase recovery -> timing recovery -> phase ambiguity resolution -> symbol slicing -> bits.
        """
        iq_samples = np.asarray(iq_samples, dtype=complex)

        # 1. Matched Filtering
        mf_output = self.rrc.matched_filter(iq_samples)

        # 2. Costas Loop Phase/Carrier Recovery
        synced_samples = self.costas_loop.process(mf_output)

        # 3. Symbol Timing Recovery & Downsampling
        expected_symbols = (expected_num_bits // 2) if (expected_num_bits and self.scheme == "QPSK") else expected_num_bits
        recovered_symbols = self.timing_recovery.recover_symbols(synced_samples, expected_num_symbols=expected_symbols)

        # 4. Resolve Phase Ambiguity using preamble ref_bits if supplied
        resolved_symbols = resolve_phase_ambiguity(recovered_symbols, scheme=self.scheme, ref_bits=ref_bits)

        # 5. Symbol Slicing to Bits
        if self.scheme == "BPSK":
            demapped_bits = ConstellationMapper.bpsk_to_bits(resolved_symbols)
        else:
            demapped_bits = ConstellationMapper.qpsk_to_bits(resolved_symbols)

        if expected_num_bits is not None:
            demapped_bits = demapped_bits[:expected_num_bits]

        return demapped_bits
