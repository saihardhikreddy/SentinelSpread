"""
Detection evaluation: build noise-only and signal-present captures, calibrate every detector on
the noise, then measure what fraction of signal captures each one flags.

Captures carry a noise uncertainty: the true noise level of each capture is drawn from a few
tenths of a dB around the nominal one, because no real receiver knows its own noise floor
exactly (thermal drift, gain settling, interference). This is what separates the detectors. A
radiometer only measures total power, so once the signal adds less than that uncertainty it
cannot tell a quiet channel from an occupied one at any false-alarm budget. Detectors that look
for structure rather than power are unaffected.

The observer samples at the chip rate (`observer_sps=1`), i.e. its bandwidth matches the signal.
Capturing at the transmitter's 4 samples per chip would leave the burst in a quarter of the
observed band, which any spectrum shape test spots immediately and which no observer worth
modelling would do.
"""

from typing import Callable, Optional, Sequence

import numpy as np

from sentinelspread.detector.ml import MLDetector
from sentinelspread.detector.statistical import all_detectors

DEFAULT_MESSAGE = "Meet at the north gate, 21:40."
NOISE_UNCERTAINTY_DB = 0.5
DEFAULT_LENGTH = 2048


def _levels(n: int, sigma: float, uncertainty_db: float, rng) -> np.ndarray:
    """Per-capture true noise standard deviations around the nominal `sigma`."""
    if uncertainty_db <= 0:
        return np.full(n, sigma)
    return sigma * 10 ** (rng.uniform(-uncertainty_db, uncertainty_db, n) / 20)


def noise_segments(n: int, length: int, sigma: float, seed: int = 0,
                   uncertainty_db: float = NOISE_UNCERTAINTY_DB) -> list:
    """n captures of complex AWGN, each at its own level inside the uncertainty band."""
    rng = np.random.default_rng(seed)
    return [(rng.standard_normal(length) + 1j * rng.standard_normal(length)) * (s / np.sqrt(2))
            for s in _levels(n, sigma, uncertainty_db, rng)]


def signal_segments(n: int, length: int, sigma: float, spreading_factor: int = 16,
                    seed: int = 1000, message: str = DEFAULT_MESSAGE,
                    transform: Optional[Callable[[np.ndarray], np.ndarray]] = None,
                    freq_offset: float = 0.0005,
                    uncertainty_db: float = NOISE_UNCERTAINTY_DB,
                    observer_sps: int = 1, rsa_keys=None) -> list:
    """n captures of the payload region of a burst, in noise drawn from the same band, decimated
    to `observer_sps` samples per chip. `transform` (optional) rewrites the chip stream before
    the channel: this is how a hardening measure is evaluated against the detectors. `rsa_keys`
    (optional) reuses one keypair across captures instead of generating a fresh one each time:
    the key wrapping does not affect what a key-free observer sees, so sharing it only speeds up
    bulk generation (e.g. training the CNN adversary) and leaves the detector statistics unchanged."""
    from sentinelspread.dsss.simulate import build_burst, channel

    sps = 4
    step = max(1, sps // max(observer_sps, 1))
    rng = np.random.default_rng(seed)
    out = []
    for i, level in enumerate(_levels(n, sigma, uncertainty_db, rng)):
        burst = build_burst(f"{message} #{i}", spreading_factor, rsa_keys=rsa_keys)
        chips = burst["chips"]
        if transform is not None:
            chips = transform(chips)
        y = channel(chips, float(level), freq_offset=freq_offset, seed=seed + i)
        # payload only: skip the known header and the constant trail, so what is being detected
        # is the spread data itself and not the framing.
        start = 800 * sps
        out.append(y[start:start + length * step:step])
    return out


def sweep(sigmas: Sequence[float], trials: int = 24, length: int = 8192, spreading_factor: int = 16,
          pfa: float = 0.01, signal_power: float = 0.25, include_ml: bool = True,
          transform: Optional[Callable[[np.ndarray], np.ndarray]] = None, seed: int = 0,
          uncertainty_db: float = NOISE_UNCERTAINTY_DB, observer_sps: int = 1) -> dict:
    """Detection rate per detector per noise level, each calibrated to the same false-alarm rate.

    Returns {"snr_db": [...], "sigmas": [...], "pfa": pfa, "rates": {name: [...]},
             "measured_pfa": {name: [...]}}
    """
    rates, measured = {}, {}
    snr_db = [float(10 * np.log10(signal_power / s ** 2)) for s in sigmas]

    for si, sigma in enumerate(sigmas):
        kw = {"uncertainty_db": uncertainty_db}
        cal = noise_segments(max(trials * 4, 100), length, sigma, seed=seed + 10 * si, **kw)
        held = noise_segments(max(trials * 2, 50), length, sigma, seed=seed + 10 * si + 5, **kw)
        sig = signal_segments(trials, length, sigma, spreading_factor, seed=seed + 1000 * (si + 1),
                              transform=transform, observer_sps=observer_sps, **kw)

        dets = all_detectors(noise_reference=sigma ** 2)
        if include_ml:
            train_sig = signal_segments(max(trials, 16), length, sigma, spreading_factor,
                                        seed=seed + 50_000 * (si + 1), transform=transform,
                                        observer_sps=observer_sps, **kw)
            dets.append(MLDetector(noise_reference=sigma ** 2).fit(cal, train_sig))
        for d in dets:
            d.calibrate(cal, pfa=pfa)
            rates.setdefault(d.name, []).append(d.detection_rate(sig))
            measured.setdefault(d.name, []).append(d.detection_rate(held))

    return {"snr_db": snr_db, "sigmas": list(sigmas), "pfa": pfa, "rates": rates,
            "measured_pfa": measured, "uncertainty_db": uncertainty_db}


def format_sweep(result: dict) -> str:
    names = list(result["rates"])
    head = f"{'SNR/sample':>11} | " + " | ".join(f"{n:>14}" for n in names)
    lines = [head, "-" * len(head)]
    for i, snr in enumerate(result["snr_db"]):
        cells = " | ".join(f"{result['rates'][n][i] * 100:13.0f}%" for n in names)
        lines.append(f"{snr:+10.1f} dB | {cells}")
    lines.append(f"(detection rate at false-alarm rate {result['pfa'] * 100:.0f}%, "
                 f"noise uncertainty +-{result.get('uncertainty_db', 0)} dB)")
    return "\n".join(lines)
