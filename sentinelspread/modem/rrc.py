"""
Root-Raised Cosine (RRC) filter generation, upsampling, and matched filtering.
"""

import numpy as np


def generate_rrc_taps(rrc_alpha: float = 0.35, sps: int = 4, span: int = 10) -> np.ndarray:
    """
    Generate Root-Raised Cosine (RRC) filter coefficients.

    Parameters:
        rrc_alpha (float): Roll-off factor (0 < alpha <= 1.0).
        sps (int): Samples per symbol.
        span (int): Filter span in symbol periods.

    Returns:
        np.ndarray: Normalized RRC filter tap coefficients.
    """
    num_taps = span * sps + 1
    t = np.arange(-span / 2, span / 2 + 1 / sps, 1 / sps)
    h = np.zeros(len(t))

    for i in range(len(t)):
        ti = t[i]
        if ti == 0.0:
            h[i] = 1.0 - rrc_alpha + (4.0 * rrc_alpha / np.pi)
        elif rrc_alpha != 0 and abs(abs(ti) - 1.0 / (4.0 * rrc_alpha)) < 1e-6:
            h[i] = (rrc_alpha / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * rrc_alpha))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * rrc_alpha))
            )
        else:
            denom = np.pi * ti * (1.0 - (4.0 * rrc_alpha * ti) ** 2)
            if abs(denom) < 1e-12:
                h[i] = 0.0
            else:
                num = np.sin(np.pi * ti * (1.0 - rrc_alpha)) + 4.0 * rrc_alpha * ti * np.cos(
                    np.pi * ti * (1.0 + rrc_alpha)
                )
                h[i] = num / denom

    # Normalize filter energy to 1
    h = h / np.sqrt(np.sum(h**2))
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
        """Upsample complex symbols and apply RRC transmit filter."""
        symbols = np.asarray(symbols, dtype=complex)
        upsampled = np.zeros(len(symbols) * self.sps, dtype=complex)
        upsampled[:: self.sps] = symbols

        # Convolve with RRC filter
        shaped = np.convolve(upsampled, self.taps, mode="full")
        return shaped

    def matched_filter(self, iq_samples: np.ndarray) -> np.ndarray:
        """Apply RRC matched filter to received IQ samples."""
        iq_samples = np.asarray(iq_samples, dtype=complex)
        filtered = np.convolve(iq_samples, self.taps, mode="full")
        return filtered
