"""
BER vs Eb/N0 Evaluation Script for BPSK and QPSK Modems over AWGN Channel.
Generates publication-quality BER vs Eb/N0 comparison curves for laboratory reports.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import erfc

from sentinelspread.channel.awgn import add_awgn_ebn0
from sentinelspread.modem.modem import Modem


def theoretical_ber(ebn0_db: np.ndarray) -> np.ndarray:
    """
    Exact theoretical BER for BPSK and Gray-coded QPSK over AWGN channel.
    P_b = 0.5 * erfc(sqrt(10^(Eb/N0_dB / 10)))
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    return 0.5 * erfc(np.sqrt(ebn0_lin))


def run_ber_simulation(
    schemes=("BPSK", "QPSK"),
    ebn0_range_db=np.arange(-3, 11, 1),
    min_errors=100,
    max_bits_per_point=1000000,
    block_bits=50000,
    sps=4,
    save_path="eval/ber_vs_snr.png",
) -> Path:
    """
    Runs adaptive BER vs Eb/N0 simulation for BPSK and QPSK modems over AWGN.
    Ensures statistical reliability by accumulating up to min_errors (default 100)
    or up to max_bits_per_point (default 1,000,000).
    """
    results = {}
    np.random.seed(42)

    for scheme in schemes:
        bits_per_symbol = 1 if scheme == "BPSK" else 2
        modem = Modem(scheme=scheme, sps=sps)

        ebn0_points = []
        ber_points = []
        reliable_flags = []

        print(f"[*] Simulating {scheme} modem performance over AWGN channel...")

        for ebn0_db in ebn0_range_db:
            total_bits = 0
            total_errors = 0

            while total_errors < min_errors and total_bits < max_bits_per_point:
                # Generate random bit block
                tx_bits = np.random.randint(0, 2, size=block_bits)
                if scheme == "QPSK" and len(tx_bits) % 2 != 0:
                    tx_bits = tx_bits[:-1]

                # Modulate
                tx_iq = modem.modulate(tx_bits)

                # Channel AWGN noise with exact Eb/N0
                rx_iq = add_awgn_ebn0(
                    tx_iq,
                    ebn0_db=ebn0_db,
                    bits_per_symbol=bits_per_symbol,
                    sps=sps,
                )

                # Demodulate with preamble ref_bits assistance
                rx_bits = modem.demodulate(rx_iq, expected_num_bits=len(tx_bits), ref_bits=tx_bits[:32])

                # Count bit errors
                errors = np.sum(tx_bits != rx_bits)
                total_errors += int(errors)
                total_bits += len(tx_bits)

            ber = float(total_errors) / float(total_bits) if total_bits > 0 else 0.0
            is_reliable = total_errors >= 20

            print(
                f"    - {scheme} @ Eb/N0 = {ebn0_db:2d} dB: BER = {ber:.2e} "
                f"({total_errors} errors / {total_bits} bits) [{'Reliable' if is_reliable else 'Low Confidence'}]"
            )

            if ber > 0:
                ebn0_points.append(ebn0_db)
                ber_points.append(ber)
                reliable_flags.append(is_reliable)

        results[scheme] = {
            "ebn0": np.array(ebn0_points),
            "ber": np.array(ber_points),
            "reliable": np.array(reliable_flags),
        }

    # Generate Publication Plot
    plt.figure(figsize=(9.5, 6.5))

    # 1. Theoretical Benchmark Curve
    ebn0_fine = np.linspace(ebn0_range_db.min(), ebn0_range_db.max(), 200)
    theory_ber_vals = theoretical_ber(ebn0_fine)
    plt.semilogy(
        ebn0_fine,
        theory_ber_vals,
        "k--",
        linewidth=2.0,
        label="Theoretical BPSK/QPSK (AWGN)",
        zorder=1,
    )

    # 2. Simulated Curves
    colors = {"BPSK": "#1f77b4", "QPSK": "#ff7f0e"}
    markers = {"BPSK": "o", "QPSK": "s"}

    for scheme, data in results.items():
        ebn0_vals = data["ebn0"]
        ber_vals = data["ber"]
        rel = data["reliable"]

        if len(ber_vals) == 0:
            continue

        c = colors[scheme]
        m = markers[scheme]

        # Draw full trend line
        plt.semilogy(
            ebn0_vals,
            ber_vals,
            "-",
            color=c,
            linewidth=1.8,
            alpha=0.85,
            label=f"Simulated {scheme}",
            zorder=2,
        )

        # Draw reliable points (filled markers)
        rel_mask = rel == True
        if np.any(rel_mask):
            plt.semilogy(
                ebn0_vals[rel_mask],
                ber_vals[rel_mask],
                m,
                color=c,
                markersize=7,
                markerfacecolor=c,
                markeredgecolor=c,
                zorder=3,
            )

        # Draw low confidence points (open markers)
        unrel_mask = rel == False
        if np.any(unrel_mask):
            plt.semilogy(
                ebn0_vals[unrel_mask],
                ber_vals[unrel_mask],
                m,
                color=c,
                markersize=7,
                markerfacecolor="none",
                markeredgecolor=c,
                markeredgewidth=1.5,
                label=f"{scheme} (<20 errors, low confidence)",
                zorder=3,
            )

    plt.title("SentinelSpread: BER vs $E_b/N_0$ Performance over AWGN Channel", fontsize=13, pad=12)
    plt.xlabel("Energy per Bit to Noise Density Ratio $E_b/N_0$ (dB)", fontsize=11)
    plt.ylabel("Bit Error Rate (BER)", fontsize=11)
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.ylim([1e-6, 1.0])
    plt.xlim([ebn0_range_db.min(), ebn0_range_db.max()])
    plt.legend(fontsize=10, loc="lower left")
    plt.tight_layout()

    out_file = Path(save_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=300)
    plt.close()

    print(f"\n[+] Saved corrected BER vs Eb/N0 plot figure to {out_file.resolve()}")
    return out_file


if __name__ == "__main__":
    run_ber_simulation()
