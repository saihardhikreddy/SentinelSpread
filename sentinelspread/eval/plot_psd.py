"""
Power Spectral Density (PSD) analysis and plotting:
Demonstrates DSSS spectral flattening and covert spreading below the channel noise floor.

FIX (applied after review): the original version pulse-shaped both the narrowband
symbols and the spread chips with the SAME `sps`, which silently made the chip
rate equal to the original symbol rate instead of SF times faster -- so the two
curves overlapped almost exactly and the plot failed to show any spreading effect
at all. The fix pulse-shapes the narrowband comparison signal at `sps * sf`
samples/symbol (same absolute symbol duration as SF chips at the real chip rate),
so both signals live on the same absolute time/frequency axis and the spread
signal's genuinely wider, flatter PSD is visible.
"""

from pathlib import Path
from typing import Optional
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sentinelspread.dsss.spreader import DSSSSpreader
from sentinelspread.modem.rrc import RRCFilter


def compute_and_plot_psd(
    sf: int = 16,
    num_symbols: int = 5000,
    sample_rate: float = 1e6,
    save_path: str = "eval/psd_flattening.png",
    verbose: bool = True,
) -> str:
    """
    Generate narrowband unspread vs. wideband DSSS spread PSD comparison.
    Shows the processing gain bandwidth expansion and spectral power density reduction.
    """
    rng = np.random.default_rng(42)
    sps_chip = 4

    # 1. Generate random binary symbols
    symbols = rng.choice([-1.0, 1.0], size=num_symbols).astype(complex)

    # 2. Narrowband pulse-shaped transmission.
    # Pulse-shaped at sps_chip * sf samples/symbol so its symbol duration equals
    # SF chip-periods at the real chip rate -- i.e. both signals share the same
    # absolute sample rate / time axis, which is what makes the bandwidth ratio
    # between them meaningful.
    rrc_symbol = RRCFilter(rrc_alpha=0.35, sps=sps_chip * sf, span=10)
    tx_narrowband = rrc_symbol.shape_pulses(symbols)

    # 3. Spread transmission, pulse-shaped at the real chip rate (sps_chip samples/chip).
    spreader = DSSSSpreader(spreading_factor=sf, seed=12345)
    spread_chips, _ = spreader.spread(symbols)
    rrc_chip = RRCFilter(rrc_alpha=0.35, sps=sps_chip, span=10)
    tx_spread = rrc_chip.shape_pulses(spread_chips)

    sig_nb = tx_narrowband
    sig_sp = tx_spread

    # Equalize average transmit power (fair comparison of shape, not absolute level)
    sig_nb = sig_nb / np.std(sig_nb)
    sig_sp = sig_sp / np.std(sig_sp)

    # 4. Compute PSD via Welch periodogram
    nperseg_nb = min(1024, len(sig_nb) // 4)
    nperseg_sp = min(1024, len(sig_sp) // 4)
    f_nb, psd_nb = signal.welch(sig_nb, fs=sample_rate, nperseg=nperseg_nb, return_onesided=False)
    f_sp, psd_sp = signal.welch(sig_sp, fs=sample_rate, nperseg=nperseg_sp, return_onesided=False)

    # FFT-shift to center around DC (0 Hz)
    f_nb = np.fft.fftshift(f_nb) / 1e3  # kHz
    psd_nb = np.fft.fftshift(psd_nb)
    f_sp = np.fft.fftshift(f_sp) / 1e3
    psd_sp = np.fft.fftshift(psd_sp)

    psd_nb_db = 10.0 * np.log10(psd_nb + 1e-12)
    psd_sp_db = 10.0 * np.log10(psd_sp + 1e-12)

    # 5. Plot
    out_file = Path(save_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 6))
    plt.plot(f_nb, psd_nb_db, "r-", label="Narrowband Signal (Unspread)", linewidth=1.5, alpha=0.8)
    plt.plot(f_sp, psd_sp_db, "b-", label=f"DSSS Spread Signal (SF={sf})", linewidth=1.5, alpha=0.85)

    noise_floor_db = float(np.mean(psd_sp_db) + 2.0)
    plt.axhline(noise_floor_db, color="gray", linestyle="--", linewidth=1.5, label="Receiver Noise Floor Threshold")

    plt.xlabel("Frequency Offset (kHz)", fontsize=12)
    plt.ylabel("Power Spectral Density (dB/Hz)", fontsize=12)
    plt.title(f"SentinelSpread: DSSS Spectral Flattening & Covert Spreading (SF={sf})", fontsize=14, fontweight="bold")
    plt.grid(True, which="both", linestyle=":", alpha=0.6)
    plt.legend(loc="upper right", fontsize=11)
    plt.xlim([-500, 500])
    plt.ylim([min(np.min(psd_nb_db), np.min(psd_sp_db)) - 5, max(np.max(psd_nb_db), np.max(psd_sp_db)) + 5])
    plt.tight_layout()

    plt.savefig(out_file, dpi=300)
    plt.close()

    if verbose:
        print(f"[+] PSD comparison plot saved to: {out_file}")

    return str(out_file)


if __name__ == "__main__":
    compute_and_plot_psd()
