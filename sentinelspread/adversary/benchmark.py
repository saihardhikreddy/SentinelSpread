"""
The end-to-end trade: bit error rate at the keyed receiver against the adversary's probability of
detection, plain versus hardened, on one SNR axis.

Both sides share the Stage 5 SNR definition, per-sample SNR = 10*log10(0.25 / sigma**2), so a row
reads straight across: at this noise level the legitimate receiver sees this BER while the CNN
catches the burst this often. The point the benchmark makes is the shape of the two hardened
columns -- frequency hopping drops Pd at no BER cost because the keyed receiver removes it, and
power backoff drops Pd further only by giving up link margin (BER rises). The detection-driven
loop spends that margin only when hopping alone has not met the target.

BER is measured with a keyed numpy despread (spread -> AWGN -> correlator), so it needs no GNU
Radio; frequency hopping is invertible at the receiver and therefore does not enter the BER path,
only the transmit-amplitude of the chosen rung does.
"""

from typing import List, Optional, Sequence

import numpy as np

from sentinelspread.detector.evaluate import noise_segments, signal_segments
from sentinelspread.dsss.correlator import DSSSCorrelator
from sentinelspread.dsss.spreader import DSSSSpreader
from sentinelspread.eval.metrics import compute_ber

SIGNAL_POWER = 0.25   # the Stage 5 reference signal power the SNR axis is quoted against


def ber_at(sigma: float, spreading_factor: int, amplitude: float = 1.0, num_symbols: int = 4000,
           seed: int = 0) -> float:
    """BER of the keyed DSSS link at noise level `sigma` and transmit `amplitude`.

    Chips carry power SIGNAL_POWER * amplitude**2; noise is the real component of the same complex
    AWGN the detectors see (std sigma/sqrt(2) per dimension), so this BER sits on the same SNR
    axis as the detection rates.
    """
    rng = np.random.default_rng(seed)
    symbols = rng.choice([-1.0, 1.0], size=num_symbols)
    chip_amp = np.sqrt(SIGNAL_POWER) * float(amplitude)
    tx_chips, pn = DSSSSpreader(spreading_factor=spreading_factor, seed=777).spread(symbols)
    rx = tx_chips * chip_amp + rng.normal(0.0, sigma / np.sqrt(2), len(tx_chips))
    decisions = np.sign(DSSSCorrelator(spreading_factor=spreading_factor).despread(rx, pn))
    return float(compute_ber(symbols, decisions))


def ber_curve(sigmas: Sequence[float], spreading_factor: int, amplitude: float = 1.0,
              num_symbols: int = 4000, seed: int = 0) -> List[float]:
    return [ber_at(s, spreading_factor, amplitude, num_symbols, seed + i) for i, s in enumerate(sigmas)]


def benchmark(adversary, sigmas: Sequence[float], spreading_factor: int = 16, controller=None,
              pfa: float = 0.01, trials: int = 24, length: int = 2048, seed: int = 0) -> dict:
    """BER and Pd per noise level, plain and (if a controller is given) hardened.

    `adversary` is a fitted CNNAdversary; `controller` is an AdaptiveHardeningController wrapping it.
    """
    from sentinelspread.crypto.key_mgmt import generate_rsa_keypair
    rsa_keys = generate_rsa_keypair(key_bits=2048)
    if controller is not None and getattr(controller, "rsa_keys", None) is None:
        controller.rsa_keys = rsa_keys

    snr_db, ber_plain, pd_plain = [], [], []
    ber_hard, pd_hard, labels, levels = [], [], [], []
    for i, sigma in enumerate(sigmas):
        snr_db.append(float(10 * np.log10(SIGNAL_POWER / sigma ** 2)))

        cal = noise_segments(max(trials * 4, 100), length, sigma, seed=seed + 11 * i)
        adversary.calibrate(cal, pfa=pfa)
        sig = signal_segments(trials, length, sigma, spreading_factor, seed=seed + 1000 * (i + 1),
                              rsa_keys=rsa_keys)
        pd_plain.append(float(adversary.detection_rate(sig)))
        ber_plain.append(ber_at(sigma, spreading_factor, amplitude=1.0, seed=seed + i))

        if controller is not None:
            d = controller.harden(sigma, spreading_factor, seed=seed + 5 * i)
            pd_hard.append(d.pd)
            # same seed as the plain row, so a hop-only rung (amplitude 1.0) reproduces the plain
            # BER exactly and only transmit-power backoff moves it.
            ber_hard.append(ber_at(sigma, spreading_factor, amplitude=d.amplitude, seed=seed + i))
            labels.append(d.label)
            levels.append(d.level)

    out = {"snr_db": snr_db, "sigmas": list(sigmas), "spreading_factor": spreading_factor,
           "pfa": pfa, "ber_plain": ber_plain, "pd_plain": pd_plain}
    if controller is not None:
        out.update({"ber_hardened": ber_hard, "pd_hardened": pd_hard,
                    "hardening_label": labels, "hardening_level": levels})
    return out


def format_benchmark(result: dict) -> str:
    hardened = "pd_hardened" in result
    cols = ["SNR/samp", "BER plain", "Pd plain"]
    if hardened:
        cols += ["BER hard", "Pd hard", "hardening"]
    head = " | ".join(f"{c:>12}" if c != "hardening" else f"{c:<22}" for c in cols)
    lines = [head, "-" * len(head)]
    for i, snr in enumerate(result["snr_db"]):
        row = [f"{snr:+10.1f} dB", f"{result['ber_plain'][i]:12.2e}", f"{result['pd_plain'][i] * 100:11.0f}%"]
        if hardened:
            row += [f"{result['ber_hardened'][i]:12.2e}", f"{result['pd_hardened'][i] * 100:11.0f}%",
                    f"{result['hardening_label'][i]:<22}"]
        lines.append(" | ".join(row))
    lines.append(f"(Pd at false-alarm rate {result['pfa'] * 100:.0f}%, SF {result['spreading_factor']}, "
                 f"CNN adversary; FHSS is invertible so it does not change BER)")
    return "\n".join(lines)
