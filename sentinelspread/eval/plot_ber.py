"""
Monte Carlo Bit Error Rate (BER) simulation engine with adaptive block sampling.
Generates BER vs Eb/N0 waterfall comparison curves for BPSK and QPSK against theory.
"""

from pathlib import Path
from typing import Optional
import numpy as np
from scipy.special import erfc
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sentinelspread.modem.modem import Modem
from sentinelspread.channel.awgn import add_awgn_ebn0
from sentinelspread.eval.metrics import compute_ber


def theoretical_ber(eb_n0_db: float) -> float:
    """Theoretical BER for BPSK and Gray-coded QPSK over AWGN: Pb = 0.5 * erfc(sqrt(Eb/N0))."""
    eb_n0_lin = 10.0 ** (eb_n0_db / 10.0)
    return float(0.5 * erfc(np.sqrt(eb_n0_lin)))


def simulate_point_adaptive(
    scheme: str,
    ebn0_db: float,
    chunk_size: int = 50000,
    max_bits: int = 1000000,
    min_errors: int = 100,
    sps: int = 4,
    span: int = 10,
    rng: Optional[np.random.Generator] = None,
) -> tuple[float, int, int]:
    """
    Adaptive Monte Carlo simulation at a single Eb/N0 operating point.
    Accumulates in chunk_size increments until min_errors observed or max_bits reached.

    Returns:
        (ber, total_errors, total_bits)
    """
    if rng is None:
        rng = np.random.default_rng()

    modem = Modem(scheme=scheme, sps=sps, span=span, enable_costas=False)
    bits_per_symbol = 1 if scheme.upper() == "BPSK" else 2

    total_errors = 0
    total_bits = 0

    while total_bits < max_bits:
        # Generate random bit chunk
        current_chunk = chunk_size
        if scheme.upper() == "QPSK" and current_chunk % 2 != 0:
            current_chunk += 1

        tx_bits = rng.integers(0, 2, size=current_chunk)
        tx_iq = modem.modulate(tx_bits)

        # Transmit through AWGN
        k = bits_per_symbol
        eb = 1.0 / float(k)
        n0 = eb / (10.0 ** (ebn0_db / 10.0))
        sigma_dim = np.sqrt((n0 * sps) / 2.0)

        noise = rng.normal(0.0, sigma_dim, len(tx_iq)) + 1j * rng.normal(0.0, sigma_dim, len(tx_iq))
        rx_iq = tx_iq + noise

        rx_bits = modem.demodulate(rx_iq, expected_num_bits=len(tx_bits))
        err = np.count_nonzero(tx_bits != rx_bits)

        total_errors += int(err)
        total_bits += len(tx_bits)

        if total_errors >= min_errors:
            break

    ber = total_errors / total_bits if total_bits > 0 else 0.0
    return ber, total_errors, total_bits


def run_ber_simulation(
    snr_range: Optional[list[float]] = None,
    save_path: str = "eval/ber_vs_snr.png",
    verbose: bool = True,
) -> dict:
    """
    Run full Monte Carlo sweep from -3 dB to 10 dB in 1 dB steps for BPSK and QPSK.
    Generates and saves the comparison plot to save_path.
    """
    if snr_range is None:
        snr_range = [float(x) for x in range(-3, 11)]

    rng = np.random.default_rng(2026)

    ebn0_arr = []
    theory_arr = []
    bpsk_arr = []
    qpsk_arr = []

    if verbose:
        print("\n" + "=" * 80)
        print("   SentinelSpread Baseband Modem Monte Carlo BER Simulation")
        print("=" * 80)
        print(f"{'Eb/N0 (dB)':>10} | {'Theoretical':>12} | {'BPSK Sim':>12} | {'QPSK Sim':>12} | {'Status':>10}")
        print("-" * 80)

    for snr in snr_range:
        th = theoretical_ber(snr)
        b_ber, b_err, b_bits = simulate_point_adaptive("BPSK", snr, rng=rng)
        q_ber, q_err, q_bits = simulate_point_adaptive("QPSK", snr, rng=rng)

        ebn0_arr.append(snr)
        theory_arr.append(th)
        bpsk_arr.append(b_ber)
        qpsk_arr.append(q_ber)

        status = "Confirmed" if (b_err >= 50 or snr < 9) else "Low Conf."
        if verbose:
            print(f"{snr:>10.1f} | {th:>12.2e} | {b_ber:>12.2e} | {q_ber:>12.2e} | {status:>10}")

    # Generate plot
    out_file = Path(save_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 6))
    plt.semilogy(ebn0_arr, theory_arr, "k--", label=r"Theory: $P_b = \frac{1}{2}\mathrm{erfc}(\sqrt{E_b/N_0})$", linewidth=2)
    plt.semilogy(ebn0_arr, bpsk_arr, "bo-", label="Simulated BPSK", markersize=6)
    plt.semilogy(ebn0_arr, qpsk_arr, "rs--", label="Simulated QPSK (Gray)", markersize=6)

    plt.grid(True, which="both", linestyle=":", alpha=0.6)
    plt.xlabel(r"$E_b/N_0$ (dB)", fontsize=12)
    plt.ylabel("Bit Error Rate (BER)", fontsize=12)
    plt.title("SentinelSpread: Baseband Modem BER Performance vs Theory", fontsize=14, fontweight="bold")
    plt.ylim([1e-6, 1.0])
    plt.xlim([min(ebn0_arr), max(ebn0_arr)])
    plt.legend(fontsize=11, loc="lower left")
    plt.tight_layout()

    plt.savefig(out_file, dpi=300)
    plt.close()

    if verbose:
        print("=" * 80)
        print(f"[+] Simulation completed. Waterfall curve saved to: {out_file}\n")

    return {
        "ebn0": ebn0_arr,
        "theory": theory_arr,
        "bpsk": bpsk_arr,
        "qpsk": qpsk_arr,
        "plot_path": str(out_file),
    }


if __name__ == "__main__":
    run_ber_simulation()
