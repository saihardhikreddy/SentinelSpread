"""
Single-feature threshold detectors, calibrated on noise.

The observer never sees a labelled signal: it watches an empty channel, picks the threshold that
its own false-alarm budget allows, and flags anything above it. `calibrate` does exactly that,
so a reported detection probability always comes with the false-alarm rate it was set for.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import numpy as np

from sentinelspread.detector import features as F


@dataclass
class ThresholdDetector:
    """One feature + one threshold. `score` is the feature; detection is score > threshold."""

    name: str
    feature: Callable[[np.ndarray], float]
    threshold: float = float("inf")
    pfa: float = 0.0

    def score(self, x: np.ndarray) -> float:
        return float(self.feature(x))

    def scores(self, segments: Iterable[np.ndarray]) -> np.ndarray:
        return np.array([self.score(s) for s in segments], dtype=float)

    def calibrate(self, noise_segments: Sequence[np.ndarray], pfa: float = 0.01) -> float:
        """Set the threshold so at most `pfa` of noise-only segments are flagged."""
        if not 0.0 < pfa < 1.0:
            raise ValueError("pfa must be between 0 and 1")
        s = np.sort(self.scores(noise_segments))
        # index of the largest score we are willing to let through
        keep = int(np.ceil((1.0 - pfa) * len(s))) - 1
        keep = min(max(keep, 0), len(s) - 1)
        self.threshold = float(s[keep])
        self.pfa = pfa
        return self.threshold

    def detect(self, x: np.ndarray) -> bool:
        return self.score(x) > self.threshold

    def detection_rate(self, segments: Sequence[np.ndarray]) -> float:
        if len(segments) == 0:
            return 0.0
        return float(np.mean([self.detect(s) for s in segments]))


def energy_detector(noise_reference: float = 1.0) -> ThresholdDetector:
    return ThresholdDetector("energy", lambda x: F.energy_db(x, noise_reference))


def flatness_detector() -> ThresholdDetector:
    return ThresholdDetector("flatness", F.spectral_flatness)


def kurtosis_detector() -> ThresholdDetector:
    return ThresholdDetector("kurtosis", F.kurtosis_excess)


def squaring_detector() -> ThresholdDetector:
    return ThresholdDetector("squaring", F.squaring_peak_db)


def autocorr_detector() -> ThresholdDetector:
    return ThresholdDetector("autocorrelation", F.chip_autocorr)


def all_detectors(noise_reference: float = 1.0):
    return [energy_detector(noise_reference), flatness_detector(), kurtosis_detector(),
            squaring_detector(), autocorr_detector()]
