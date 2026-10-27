"""
The closed hardening loop (the "Red Team" response).

The controller holds a trained CNN adversary and, at a given operating point, walks an escalation
ladder until the adversary's probability of detection falls under a target. Cheap, reliable
measures come first:

  0  plain DSSS
  1  FHSS, 8 channels, 64-chip dwell          (key-derived hopping, fully invertible, no BER cost)
  2  FHSS, 16 channels, 32-chip dwell
  3  FHSS, 16 channels, 32-chip dwell + 0.7x transmit amplitude   (power backoff begins)
  4  FHSS, 16 channels, 16-chip dwell + 0.5x transmit amplitude

Frequency hopping is tried before power backoff on purpose: the receiver regenerates the hop
schedule from the session key and removes it, so hopping costs nothing at the keyed receiver,
while dropping transmit power buys covertness only by spending link margin (higher BER). The loop
stops at the first rung that meets the target, so it radiates the least structure and spends the
least power needed to stay under the adversary — which is the whole point of detection-driven
hardening.

Pd at each rung is measured the honest way: the adversary is re-calibrated on noise at this
operating point (so its false-alarm rate is held), then run on freshly generated hardened
captures.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

from sentinelspread.detector.evaluate import noise_segments, signal_segments
from sentinelspread.dsss.simulate import DEFAULT_SDR_AES_KEY
from sentinelspread.harden.fhss import apply_fhss


def power_transform(amplitude: float) -> Callable[[np.ndarray], np.ndarray]:
    """Scale the whole chip stream by `amplitude` (<1 lowers transmit power -> lower Pd, higher BER)."""
    def t(chips: np.ndarray) -> np.ndarray:
        return np.asarray(chips) * float(amplitude)
    return t


def _compose(fhss_cfg: Optional[dict], amplitude: float, aes_key: bytes) -> Optional[Callable]:
    """Build the chips->chips transform for a ladder rung (FHSS first, then amplitude)."""
    if fhss_cfg is None and amplitude >= 1.0:
        return None

    def t(chips: np.ndarray) -> np.ndarray:
        out = np.asarray(chips, dtype=np.complex128)
        if fhss_cfg is not None:
            out = apply_fhss(out, aes_key, **fhss_cfg)
        if amplitude < 1.0:
            out = out * float(amplitude)
        return out
    return t


# (label, fhss config or None, transmit amplitude)
DEFAULT_LADDER: List[Tuple[str, Optional[dict], float]] = [
    ("plain", None, 1.0),
    ("fhss-8x64", {"chips_per_hop": 64, "num_channels": 8}, 1.0),
    ("fhss-16x32", {"chips_per_hop": 32, "num_channels": 16}, 1.0),
    ("fhss-16x32 + power-0.7", {"chips_per_hop": 32, "num_channels": 16}, 0.7),
    ("fhss-16x16 + power-0.5", {"chips_per_hop": 16, "num_channels": 16}, 0.5),
]


@dataclass
class HardeningDecision:
    level: int
    label: str
    pd: float
    amplitude: float
    fhss_cfg: Optional[dict]
    transform: Optional[Callable] = field(default=None, repr=False)
    pd_by_level: List[float] = field(default_factory=list)
    met_target: bool = False


@dataclass
class AdaptiveHardeningController:
    adversary: object                       # a fitted CNNAdversary (or any detector with the same API)
    target_pd: float = 0.2
    aes_key: bytes = DEFAULT_SDR_AES_KEY
    length: int = 2048
    probe_trials: int = 24
    pfa: float = 0.01
    ladder: List[Tuple[str, Optional[dict], float]] = field(default_factory=lambda: list(DEFAULT_LADDER))
    rsa_keys: object = None

    def _pd_at(self, sigma: float, spreading_factor: int, transform: Optional[Callable], seed: int) -> float:
        cal = noise_segments(max(self.probe_trials * 4, 100), self.length, sigma, seed=seed)
        self.adversary.calibrate(cal, pfa=self.pfa)
        sig = signal_segments(self.probe_trials, self.length, sigma, spreading_factor,
                              seed=seed + 777, transform=transform, rsa_keys=self.rsa_keys)
        return float(self.adversary.detection_rate(sig))

    def harden(self, sigma: float, spreading_factor: int = 16, seed: int = 0) -> HardeningDecision:
        """Climb the ladder at this operating point until Pd <= target (or the top rung is reached)."""
        if self.rsa_keys is None:
            from sentinelspread.crypto.key_mgmt import generate_rsa_keypair
            self.rsa_keys = generate_rsa_keypair(key_bits=2048)
        pd_by_level: List[float] = []
        chosen: Optional[HardeningDecision] = None
        for level, (label, fhss_cfg, amp) in enumerate(self.ladder):
            transform = _compose(fhss_cfg, amp, self.aes_key)
            pd = self._pd_at(sigma, spreading_factor, transform, seed=seed + 31 * level)
            pd_by_level.append(pd)
            if pd <= self.target_pd and chosen is None:
                chosen = HardeningDecision(level, label, pd, amp, fhss_cfg, transform, [], True)
        if chosen is None:  # nothing met the target: take the strongest rung
            level = len(self.ladder) - 1
            label, fhss_cfg, amp = self.ladder[level]
            chosen = HardeningDecision(level, label, pd_by_level[level], amp, fhss_cfg,
                                       _compose(fhss_cfg, amp, self.aes_key), [], False)
        chosen.pd_by_level = pd_by_level
        return chosen
