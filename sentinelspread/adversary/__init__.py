"""
Stage 6 — the adversary and the closed hardening loop.

Stage 5 measured the signal against fixed, hand-built statistics (energy, flatness, kurtosis,
carrier-squaring, chip-autocorrelation) and a random forest over them. This stage closes the
Build -> Attack -> Harden cycle the project is named for:

  cnn         a convolutional "Blue Team" detector that learns straight from raw I/Q captures,
              with no hand-designed feature. It is the modern adversary the Stage 5 detectors
              only approximate.
  controller  the "Red Team" response: a closed loop that reads the CNN's detection confidence
              and escalates hardening (key-derived frequency hopping, then transmit-power
              backoff) only as far as it needs to push that confidence under a target.
  benchmark   the end-to-end trade: bit error rate at the keyed receiver against the CNN's
              probability of detection, plain versus hardened, on one SNR axis.

The CNN needs PyTorch; everything else is numpy and reuses the Stage 3-5 modules unchanged.
`sentinelspread.adversary.cnn` imports torch lazily so this package stays importable without it.
"""

from sentinelspread.adversary.dataset import build_dataset, iq_to_array, segments_to_array

__all__ = ["build_dataset", "iq_to_array", "segments_to_array"]
