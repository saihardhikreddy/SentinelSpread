"""Detector suite for SentinelSpread: statistical and ML signal classification.

What an observer without the key can tell from a capture. `features` computes key-free
statistics, `statistical` turns one into a detector calibrated to a false-alarm budget, `ml`
trains a classifier over all of them, and `evaluate` sweeps detection rate against noise level.
"""

from sentinelspread.detector.features import FEATURE_NAMES, feature_vector
from sentinelspread.detector.ml import MLDetector
from sentinelspread.detector.statistical import (
    ThresholdDetector,
    all_detectors,
    autocorr_detector,
    energy_detector,
    flatness_detector,
    kurtosis_detector,
    squaring_detector,
)

__all__ = [
    "FEATURE_NAMES",
    "feature_vector",
    "ThresholdDetector",
    "MLDetector",
    "all_detectors",
    "energy_detector",
    "flatness_detector",
    "kurtosis_detector",
    "squaring_detector",
    "autocorr_detector",
]
