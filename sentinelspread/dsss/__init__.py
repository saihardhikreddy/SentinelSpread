"""
DSSS Spreading & Despreading module for SentinelSpread.
"""

from sentinelspread.dsss.pn_gen import PNGenerator, PRIMITIVE_POLYNOMIALS, generate_gold_code
from sentinelspread.dsss.spreader import DSSSSpreader, VALID_SPREADING_FACTORS
from sentinelspread.dsss.correlator import DSSSCorrelator

__all__ = [
    "PNGenerator",
    "PRIMITIVE_POLYNOMIALS",
    "generate_gold_code",
    "DSSSSpreader",
    "DSSSCorrelator",
    "VALID_SPREADING_FACTORS",
]
