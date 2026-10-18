"""Hardening layer for SentinelSpread: FHSS, FEC, adaptive power control, and key rotation.

  fhss      frequency hopping over the chip stream (apply_fhss / remove_fhss / fhss_transform)
  fec       Hamming(7,4) forward error correction with interleaving (encode / decode)
  power     adaptive transmit-amplitude policy (PowerPolicy)
  rotation  HKDF key ratchet for per-epoch session keys (KeyRatchet)
"""

from sentinelspread.harden.fec import decode as fec_decode
from sentinelspread.harden.fec import encode as fec_encode
from sentinelspread.harden.fhss import apply_fhss, fhss_transform, hop_schedule, remove_fhss
from sentinelspread.harden.power import PowerPolicy
from sentinelspread.harden.rotation import KeyRatchet

__all__ = [
    "apply_fhss",
    "remove_fhss",
    "fhss_transform",
    "hop_schedule",
    "fec_encode",
    "fec_decode",
    "PowerPolicy",
    "KeyRatchet",
]
