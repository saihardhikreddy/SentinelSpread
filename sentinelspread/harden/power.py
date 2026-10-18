"""
Adaptive power (gain) control.

Given a link-quality estimate, pick the smallest transmit amplitude that keeps the symbol SNR at
a target margin above what the receiver needs. Lower transmit amplitude for the same link means
less energy radiated than a fixed-power link would use, so the extra margin is not wasted.

This is a scalar policy (amplitude and the predicted margin); the loop that measures link quality
and feeds it back lives in the SDR runner, not here.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class PowerPolicy:
    target_symbol_snr_db: float = 9.0     # SNR the receiver wants after despreading
    min_amplitude: float = 0.05
    max_amplitude: float = 1.0
    step_db: float = 1.0                  # max change per update (a real loop moves gradually)

    def required_amplitude(self, measured_symbol_snr_db: float, current_amplitude: float,
                           processing_gain_db: float = 0.0) -> float:
        """Amplitude for the next burst from the last measured symbol SNR.

        The margin above target tells us how much we are overshooting; we scale amplitude down by
        that margin (and up when short), limited to `step_db` per update and the amplitude bounds.
        """
        headroom_db = measured_symbol_snr_db - self.target_symbol_snr_db
        change_db = float(np.clip(-headroom_db, -self.step_db, self.step_db))
        amp = current_amplitude * 10 ** (change_db / 20)
        return float(np.clip(amp, self.min_amplitude, self.max_amplitude))

    def predicted_margin_db(self, symbol_snr_db: float) -> float:
        return float(symbol_snr_db - self.target_symbol_snr_db)
