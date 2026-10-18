"""
Despread-first DSSS receiver (numpy only).

The classic chain (RRC -> Mueller & Muller timing -> Costas -> despread) locks timing and carrier
on the raw chips. Each chip carries 1/SF of a symbol's energy, so once the chip SNR drops to
around 0 dB those loops lose lock, and a higher spreading factor cannot help: they never see
the processing gain.

This receiver uses the processing gain *before* it synchronises:

  1. Acquisition. The known burst header (training tones + preamble, 767 chips) is correlated
     against the matched-filtered samples at every sample phase and lag. Segments are combined
     non-coherently, so a carrier offset cannot smear the peak. The header gives ~29 dB of
     correlation gain, enough to find the burst well below 0 dB chip SNR.
  2. Carrier. The carrier offset comes from an FFT of the header-wiped chips (the header is
     known, so it is a pure tone); the starting phase comes from the header correlation, which
     also fixes the BPSK 180-degree ambiguity.
  3. Despread, then track. Data chips are de-rotated and despread. The residual frequency is
     refined from the squared symbols (FFT over the whole burst), and a decision-directed PLL
     follows what is left. All of this runs on symbols, whose SNR is SF times higher than a chip's.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.signal import fftconvolve

from sentinelspread.dsss.pn_gen import PNGenerator

PREAMBLE_LEN = 255
TRAINING_TONES_LEN = 512
PREAMBLE_SEED = 0xAA
DATA_PN_DEGREE = 7


def header_chips(training_tones_len: int = TRAINING_TONES_LEN, preamble_len: int = PREAMBLE_LEN) -> np.ndarray:
    """The known start of every burst: alternating training tones, then the m-sequence preamble."""
    tones = np.tile([1.0, -1.0], training_tones_len // 2)
    preamble = PNGenerator(degree=8, seed=PREAMBLE_SEED).generate_chips(preamble_len, bipolar=True)
    return np.concatenate([tones, preamble]).astype(np.float64)


@dataclass
class DespreadResult:
    symbols: np.ndarray
    bits: np.ndarray
    sample_phase: int
    header_start_chip: int
    acquisition_db: float          # header correlation peak over the noise floor of the search
    cfo_rad_per_chip: float        # estimated carrier offset (coarse + refined)
    symbol_snr_db: float           # after despreading, from the symbol cluster
    evm_db: float
    diagnostics: dict = field(default_factory=dict)


class DespreadFirstReceiver:
    def __init__(
        self,
        spreading_factor: int,
        pn_seed: int,
        sps: int = 4,
        training_tones_len: int = TRAINING_TONES_LEN,
        preamble_len: int = PREAMBLE_LEN,
        segment_len: int = 64,
        pll_bandwidth: float = 0.02,
    ):
        self.sf = spreading_factor
        self.pn_seed = pn_seed
        self.sps = sps
        self.header = header_chips(training_tones_len, preamble_len)
        self.tones_len = training_tones_len
        self.segment_len = segment_len
        self.pll_bandwidth = pll_bandwidth

    # ── 1. acquisition ───────────────────────────────────────────────────────────────────────
    def _preamble_metric(self, chips: np.ndarray, max_lag: int) -> np.ndarray:
        """Non-coherent sum of |segment correlation|^2 over the preamble, for lags 0..max_lag-1
        (lag = start of the whole header). Only the m-sequence preamble is used for timing:
        the training tones alternate +1/-1, so they correlate almost as well two chips early or
        late and would make the peak ambiguous at low SNR."""
        L = self.segment_len
        pre0 = self.tones_len
        metric = np.zeros(max_lag)
        for s0 in range(pre0, len(self.header) - L + 1, L):
            ref = self.header[s0:s0 + L]
            # y[m] = sum_n chips[m + n] * ref[n]
            y = fftconvolve(chips, ref[::-1], mode="valid")
            metric += np.abs(y[s0:s0 + max_lag]) ** 2
        return metric

    def acquire(self, samples: np.ndarray, data_chips: int):
        """Best (sample phase, header start chip) whose whole burst fits in the capture, and the
        peak's margin over the rest of the search in dB."""
        need = len(self.header) + data_chips
        best = None
        for phase in range(self.sps):
            chips = samples[phase::self.sps]
            max_lag = len(chips) - need + 1
            if max_lag <= 0:
                continue
            metric = self._preamble_metric(chips, max_lag)
            k = int(np.argmax(metric))
            if best is None or metric[k] > best[2]:
                best = (phase, k, float(metric[k]), metric)
        if best is None:
            raise ValueError("Capture is too short to hold a whole burst.")
        phase, start, peak, metric = best
        away = np.ones(len(metric), dtype=bool)
        away[max(0, start - 2):start + 3] = False
        floor = float(np.mean(metric[away])) if away.any() else 0.0
        return phase, start, 10 * np.log10(peak / max(floor, 1e-30))

    # ── 2. carrier from the known header ───────────────────────────────────────────────────────
    def _header_cfo(self, chips: np.ndarray, start: int) -> float:
        z = chips[start:start + len(self.header)] * self.header
        n_fft = 1 << int(np.ceil(np.log2(len(z) * 32)))
        spec = np.abs(np.fft.fft(z, n_fft))
        k = int(np.argmax(spec))
        # parabolic refinement around the peak
        a, b, c = spec[(k - 1) % n_fft], spec[k], spec[(k + 1) % n_fft]
        denom = a - 2 * b + c
        delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
        f = (k + delta) / n_fft
        if f > 0.5:
            f -= 1.0
        return 2 * np.pi * f

    # ── 3. despread + symbol-rate tracking ─────────────────────────────────────────────────────
    def _despread(self, chips: np.ndarray, num_symbols: int) -> np.ndarray:
        pn = PNGenerator(degree=DATA_PN_DEGREE, seed=self.pn_seed).generate_chips(num_symbols * self.sf, bipolar=True)
        return (chips[:num_symbols * self.sf] * pn).reshape(num_symbols, self.sf).mean(axis=1)

    @staticmethod
    def _refine_from_squares(symbols: np.ndarray) -> float:
        """Residual carrier step per symbol from the squared (modulation-free) symbols."""
        sq = symbols ** 2
        n_fft = 1 << int(np.ceil(np.log2(len(sq) * 16)))
        spec = np.abs(np.fft.fft(sq, n_fft))
        k = int(np.argmax(spec))
        a, b, c = spec[(k - 1) % n_fft], spec[k], spec[(k + 1) % n_fft]
        denom = a - 2 * b + c
        delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
        f = (k + delta) / n_fft
        if f > 0.5:
            f -= 1.0
        return np.pi * f          # half the squared tone's frequency, in rad/symbol

    def _pll(self, symbols: np.ndarray) -> np.ndarray:
        """Second-order decision-directed PLL on BPSK symbols, starting at phase 0."""
        bn = self.pll_bandwidth
        zeta = 0.707
        theta = bn / (zeta + 1 / (4 * zeta))
        kp = 4 * zeta * theta / (1 + 2 * zeta * theta + theta ** 2)
        ki = 4 * theta ** 2 / (1 + 2 * zeta * theta + theta ** 2)
        out = np.empty_like(symbols)
        phase = freq = 0.0
        for i, s in enumerate(symbols):
            y = s * np.exp(-1j * phase)
            out[i] = y
            d = 1.0 if y.real >= 0 else -1.0
            err = np.angle(y * d)
            freq += ki * err
            phase += freq + kp * err
        return out

    def demodulate(self, samples: np.ndarray, num_symbols: int) -> DespreadResult:
        samples = np.asarray(samples, dtype=np.complex128)
        data_chips = num_symbols * self.sf
        phase, start, acq_db = self.acquire(samples, data_chips)
        chips = samples[phase::self.sps]

        omega = self._header_cfo(chips, start)
        n = np.arange(len(chips))
        derot = chips * np.exp(-1j * omega * (n - start))
        hdr = derot[start:start + len(self.header)] * self.header
        theta0 = float(np.angle(np.sum(hdr)))
        derot *= np.exp(-1j * theta0)

        data = derot[start + len(self.header):start + len(self.header) + data_chips]
        sym = self._despread(data, num_symbols)

        # The data starts right after the header, where the header's phase estimate is accurate,
        # so remove the residual rotation as k * step (anchored at the first symbol).
        step = self._refine_from_squares(sym)
        k = np.arange(len(sym))
        sym = sym * np.exp(-1j * step * k)
        sym = self._pll(sym)

        bits = (sym.real >= 0).astype(np.uint8)
        amp = np.mean(np.abs(sym.real))
        noise = np.var(np.abs(sym.real) - amp) + np.mean(sym.imag ** 2)
        snr_db = 10 * np.log10(amp ** 2 / max(noise, 1e-30))
        ideal = np.where(bits == 1, amp, -amp)
        evm_db = 10 * np.log10(np.mean(np.abs(sym - ideal) ** 2) / max(amp ** 2, 1e-30))
        cfo = omega + step / self.sf
        return DespreadResult(
            symbols=sym, bits=bits, sample_phase=phase, header_start_chip=start,
            acquisition_db=float(acq_db), cfo_rad_per_chip=float(cfo),
            symbol_snr_db=float(snr_db), evm_db=float(evm_db),
            diagnostics={"header_cfo": float(omega), "symbol_step": float(step), "theta0": theta0},
        )
