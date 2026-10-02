"""
Empirical Processing Gain (Gp) measurement and theoretical verification.
Gp = 10 * log10(SF) dB.
"""

from typing import Dict, List, Optional
import numpy as np

from sentinelspread.dsss.spreader import DSSSSpreader, VALID_SPREADING_FACTORS
from sentinelspread.dsss.correlator import DSSSCorrelator


def measure_processing_gain(
    sf: int = 16,
    num_symbols: int = 10000,
    input_snr_db: float = 0.0,
    seed: Optional[int] = 42,
) -> Dict[str, float]:
    """
    Empirically measure DSSS processing gain Gp:
        Gp_measured = SNR_out_dB - SNR_in_dB

    Parameters:
        sf: Spreading factor (16, 32, 64, 128).
        num_symbols: Number of Monte Carlo symbols.
        input_snr_db: Channel chip SNR in dB.
        seed: Random seed for repeatability.

    Returns:
        dict containing 'sf', 'theory_gp_db', 'measured_gp_db', 'delta_db'.
    """
    rng = np.random.default_rng(seed)

    # 1. Generate random BPSK symbols
    symbols = rng.choice([-1.0, 1.0], size=num_symbols)

    # 2. Spread symbols
    spreader = DSSSSpreader(spreading_factor=sf, seed=123)
    tx_chips, pn_sequence = spreader.spread(symbols)

    # 3. Add calibrated AWGN channel noise
    signal_power = np.mean(tx_chips ** 2)
    snr_lin = 10.0 ** (input_snr_db / 10.0)
    noise_power = signal_power / snr_lin
    sigma = np.sqrt(noise_power)

    noise = rng.normal(0.0, sigma, len(tx_chips))
    rx_chips = tx_chips + noise

    # Measured input SNR
    snr_in_measured = signal_power / np.mean(noise ** 2)
    snr_in_db = float(10.0 * np.log10(snr_in_measured))

    # 4. Despread
    correlator = DSSSCorrelator(spreading_factor=sf)
    despread_symbols = correlator.despread(rx_chips, pn_sequence)

    # Output SNR: signal vs residual noise
    out_noise = despread_symbols - symbols
    snr_out_measured = np.mean(symbols ** 2) / np.mean(out_noise ** 2)
    snr_out_db = float(10.0 * np.log10(snr_out_measured))

    # Processing gain
    measured_gp = snr_out_db - snr_in_db
    theory_gp = float(10.0 * np.log10(sf))
    delta = abs(measured_gp - theory_gp)

    return {
        "sf": sf,
        "theory_gp_db": round(theory_gp, 3),
        "measured_gp_db": round(measured_gp, 3),
        "delta_db": round(delta, 3),
    }


def run_processing_gain_benchmark(
    spreading_factors: Optional[List[int]] = None,
    verbose: bool = True,
) -> List[Dict[str, float]]:
    """Benchmark processing gain across multiple spreading factors."""
    if spreading_factors is None:
        spreading_factors = list(VALID_SPREADING_FACTORS)

    results = []
    if verbose:
        print("\n" + "=" * 65)
        print("   SentinelSpread: Empirical Processing Gain Verification")
        print("=" * 65)
        print(f"{'SF':>6} | {'Theoretical Gp':>16} | {'Measured Gp':>14} | {'Error (dB)':>12}")
        print("-" * 65)

    for sf in spreading_factors:
        res = measure_processing_gain(sf=sf)
        results.append(res)
        if verbose:
            print(
                f"{res['sf']:>6d} | {res['theory_gp_db']:>13.2f} dB | {res['measured_gp_db']:>11.2f} dB | {res['delta_db']:>9.2f} dB"
            )

    if verbose:
        print("=" * 65 + "\n")

    return results


if __name__ == "__main__":
    run_processing_gain_benchmark()
