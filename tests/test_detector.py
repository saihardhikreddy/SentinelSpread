"""Stage 5 detector suite: features, threshold calibration, and the evaluation sweep."""
import numpy as np
import pytest

from sentinelspread.detector import FEATURE_NAMES, all_detectors, feature_vector
from sentinelspread.detector.evaluate import noise_segments, signal_segments, sweep


def test_feature_vector_shape_and_order():
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(2048) + 1j * rng.standard_normal(2048)) / np.sqrt(2)
    v = feature_vector(x, noise_reference=1.0)
    assert v.shape == (len(FEATURE_NAMES),) and np.all(np.isfinite(v))


def test_threshold_calibration_holds_the_false_alarm_rate():
    # Calibrate on noise, then measure the false-alarm rate on independent noise: ~= the target.
    for det in all_detectors(noise_reference=1.0):
        cal = noise_segments(300, 2048, sigma=1.0, seed=1)
        held = noise_segments(300, 2048, sigma=1.0, seed=2)
        det.calibrate(cal, pfa=0.05)
        fa = det.detection_rate(held)
        assert fa <= 0.15, f"{det.name} false-alarm {fa:.2f} far above the 5% target"


def test_strong_signal_is_detected_by_the_structure_detectors():
    # Spreading is designed to defeat the flatness (spectrum-shape) detector, so it is excluded
    # here and checked separately in test_spreading_defeats_the_flatness_detector. Every other
    # detector should flag a strong (+0 dB) spread burst.
    cal = noise_segments(200, 2048, sigma=0.5, seed=3)
    sig = signal_segments(20, 2048, sigma=0.5, spreading_factor=16, seed=4000, observer_sps=1)
    for det in all_detectors(noise_reference=0.25):
        if det.name == "flatness":
            continue
        det.calibrate(cal, pfa=0.05)
        assert det.detection_rate(sig) >= 0.8, f"{det.name} missed a +0 dB signal"


def test_spreading_defeats_the_flatness_detector():
    # A matched-bandwidth flatness test cannot see DSSS: the spread signal is noise-like.
    r = sweep([0.5], trials=16, length=2048, spreading_factor=16, pfa=0.01,
              include_ml=False, observer_sps=1, seed=0)
    assert r["rates"]["flatness"][0] <= 0.3


def test_energy_detector_hits_the_noise_uncertainty_wall():
    # With noise uncertainty, the radiometer fails at deep negative SNR while a structure-aware
    # detector (squaring) still works. This is the SNR-wall result.
    r = sweep([0.5, 4.0], trials=20, length=2048, spreading_factor=16, pfa=0.01,
              include_ml=False, observer_sps=1, uncertainty_db=0.5, seed=0)
    assert r["snr_db"][1] < -15
    assert r["rates"]["energy"][1] < 0.6          # radiometer degraded far below the floor
    assert r["rates"]["squaring"][0] >= 0.9       # structure detector still fine near 0 dB


def test_ml_detector_trains_and_reports_importances():
    from sentinelspread.detector import MLDetector

    cal = noise_segments(120, 2048, sigma=0.5, seed=5)
    sig = signal_segments(60, 2048, sigma=0.5, spreading_factor=16, seed=9000, observer_sps=1)
    ml = MLDetector(noise_reference=0.25).fit(cal, sig)
    ml.calibrate(cal, pfa=0.05)
    assert ml.detection_rate(sig) >= 0.8
    imp = ml.importances()
    # importances() rounds each value to 4 decimals, so the sum can drift by up to 0.5e-4 per feature
    assert set(imp) == set(FEATURE_NAMES) and abs(sum(imp.values()) - 1.0) <= 0.5e-4 * len(FEATURE_NAMES)
