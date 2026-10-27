"""
Stage 6 tests: the CNN adversary and the detection-driven hardening loop.

They need PyTorch, so the whole module skips cleanly where torch is not installed (the same way
the GNU Radio tests skip without GNU Radio). Sizes are kept small so the suite stays quick; the
network still has to actually learn, hop and trade BER for covertness for these to pass.
"""

import numpy as np
import pytest

pytest.importorskip("torch")

from sentinelspread.adversary import benchmark as bm
from sentinelspread.adversary.cnn import CNNAdversary
from sentinelspread.adversary.controller import AdaptiveHardeningController
from sentinelspread.adversary.dataset import build_dataset, iq_to_array
from sentinelspread.detector.evaluate import noise_segments, signal_segments

LENGTH = 2048


@pytest.fixture(scope="module")
def adversary():
    x, y, _ = build_dataset([0.3, 0.5, 0.8], per_class=120, length=LENGTH, spreading_factor=16, seed=1)
    return CNNAdversary(length=LENGTH, epochs=15, seed=0).fit(x, y)


def test_iq_to_array_removes_the_power_cue():
    rng = np.random.default_rng(0)
    cap = (rng.standard_normal(500) + 1j * rng.standard_normal(500)) * 5.0
    a = iq_to_array(cap)
    assert a.shape == (2, 500)
    # normalised to ~unit power regardless of the input's absolute scale
    assert abs(float(np.mean(a[0] ** 2 + a[1] ** 2)) - 1.0) < 0.2


def test_dataset_is_balanced_and_shaped():
    x, y, snr = build_dataset([0.5, 1.0], per_class=40, length=1024, seed=2)
    assert x.shape[1:] == (2, 1024)
    assert set(np.unique(y)) == {0, 1}
    assert y.sum() == (y == 0).sum()            # balanced
    assert len(snr) == len(y)


def test_cnn_detects_the_plain_burst(adversary):
    sigma = 0.4                                  # ~+2 dB/sample: well handled
    adversary.calibrate(noise_segments(120, LENGTH, sigma, seed=50), pfa=0.05)
    pd = adversary.detection_rate(signal_segments(30, LENGTH, sigma, 16, seed=9000))
    far = adversary.detection_rate(noise_segments(120, LENGTH, sigma, seed=77))
    assert pd > 0.8                              # catches the signal it was built to catch
    assert far <= 0.2                            # false alarm stays near its 5% budget


def test_hardening_loop_pushes_detection_down(adversary):
    ctrl = AdaptiveHardeningController(adversary=adversary, target_pd=0.3, length=LENGTH,
                                      probe_trials=20, pfa=0.05)
    d = ctrl.harden(sigma=0.4, spreading_factor=16, seed=3)
    assert d.fhss_cfg is not None and d.level >= 1     # it actually escalated to hopping
    assert d.pd <= d.pd_by_level[0]                     # no worse than plain
    assert d.pd <= 0.5                                  # and materially lower


def test_benchmark_runs_and_hopping_spends_no_power(adversary):
    ctrl = AdaptiveHardeningController(adversary=adversary, target_pd=0.3, length=LENGTH,
                                      probe_trials=16, pfa=0.05)
    res = bm.benchmark(adversary, [0.4, 0.8], spreading_factor=16, controller=ctrl, pfa=0.05,
                       trials=16, length=LENGTH, seed=4)
    assert len(res["snr_db"]) == 2
    for i in range(2):
        # frequency hopping is invertible: a hop-only rung keeps full transmit amplitude, so its
        # BER column equals the plain one; only a power-backoff rung (level >= 3) may raise BER.
        if res["hardening_level"][i] in (1, 2):
            assert res["ber_hardened"][i] == pytest.approx(res["ber_plain"][i], abs=1e-9)
        assert res["pd_hardened"][i] <= res["pd_plain"][i] + 1e-9   # hardening never helps the observer
