"""
Root-Raised Cosine (RRC) pulse shaping and matched filtering.
"""

import numpy as np


def generate_rrc_taps(rrc_alpha: float = 0.35, sps: int = 4, span: int = 10) -> np.ndarray:
    """
    Generate Root-Raised Cosine (RRC) filter impulse response taps.

    Parameters:
        rrc_alpha: Roll-off factor (0.0 < alpha <= 1.0).
        sps: Samples per symbol (oversampling factor).
        span: Filter span in symbols (length is span * sps + 1).

    Returns:
        Energy-normalized filter taps (sum(h[n]^2) == 1.0).
    """
    num_taps = span * sps + 1
    t = np.arange(-span / 2.0, span / 2.0 + 1e-9, 1.0 / sps)[:num_taps]
    h = np.zeros(num_taps, dtype=float)

    for i, ti in enumerate(t):
        if np.isclose(ti, 0.0):
            h[i] = 1.0 - rrc_alpha + 4.0 * rrc_alpha / np.pi
        elif np.isclose(abs(ti), 1.0 / (4.0 * rrc_alpha)):
            h[i] = (rrc_alpha / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * rrc_alpha))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * rrc_alpha))
            )
        else:
            denom = np.pi * ti * (1.0 - (4.0 * rrc_alpha * ti) ** 2)
            num = np.sin(np.pi * ti * (1.0 - rrc_alpha)) + 4.0 * rrc_alpha * ti * np.cos(
                np.pi * ti * (1.0 + rrc_alpha)
            )
            h[i] = num / denom

    # Normalize to unit energy: sum(h[n]^2) = 1.0
    energy = np.sum(h ** 2)
    h = h / np.sqrt(energy)
    return h


class RRCFilter:
    """RRC Pulse Shaper (TX) and Matched Filter (RX)."""

    def __init__(self, rrc_alpha: float = 0.35, sps: int = 4, span: int = 10):
        self.rrc_alpha = rrc_alpha
        self.sps = sps
        self.span = span
        self.taps = generate_rrc_taps(rrc_alpha=rrc_alpha, sps=sps, span=span)
        self.filter_delay = (len(self.taps) - 1) // 2

    def shape_pulses(self, symbols: np.ndarray) -> np.ndarray:
        """
        Transmit pulse shaping:
        Upsamples symbols by sps and filters with RRC taps.
        Scaled by sqrt(sps) to preserve unitary symbol energy in continuous-to-discrete representation.
        """
        symbols = np.asarray(symbols, dtype=complex)
        upsampled = np.zeros(len(symbols) * self.sps, dtype=complex)
        upsampled[:: self.sps] = symbols

        tx_iq = np.convolve(upsampled, self.taps, mode="full") * np.sqrt(self.sps)
        return tx_iq

    def matched_filter(self, iq_samples: np.ndarray) -> np.ndarray:
        """
        Receive matched filtering:
        Convolves received IQ samples with conjugate time-reversed RRC filter.
        (Since RRC taps are real and symmetric, h*[-n] == h[n]).
        """
        iq_samples = np.asarray(iq_samples, dtype=complex)
        mf_output = np.convolve(iq_samples, self.taps, mode="full")
        return mf_output
