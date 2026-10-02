"""
SentinelSpread GNU Radio Software SDR Loopback Transceiver Runner.
Executes the full end-to-end signal chain:
Crypto + DSSS TX (Embedded Block) -> RRC TX -> Channel Model (AWGN + Freq Offset) -> RRC RX -> Symbol Sync -> Costas Loop -> DSSS + Crypto RX (Embedded Block).
"""

import argparse
import sys
import numpy as np

try:
    from gnuradio import gr, blocks, filter, channels, digital
    import pmt
    from sentinelspread.gnuradio.blocks import crypto_dsss_tx, dsss_crypto_rx
    GNURADIO_AVAILABLE = True
except ImportError:
    GNURADIO_AVAILABLE = False


def run_software_loopback(
    message: str = "SentinelSpread GNU Radio SDR Software Loopback Verification 2026",
    spreading_factor: int = 16,
    noise_voltage: float = 0.02,
    freq_offset: float = 0.0,
    timing_offset: float = 1.0,
    sps: int = 4,
    samp_rate: int = 200000,
    verbose: bool = True,
) -> dict:
    """
    Executes a complete software loopback inside GNU Radio.
    Returns a dictionary of execution metrics and status.
    """
    if not GNURADIO_AVAILABLE:
        raise RuntimeError("GNU Radio is not installed or importable in current Python environment.")

    # 1. RRC filter taps (unity energy)
    rrc_taps = filter.firdes.root_raised_cosine(np.sqrt(sps), sps, 1.0, 0.35, 41)

    # 2. Instantiate Top Block
    tb = gr.top_block("SentinelSpread_SDR_Loopback")

    # 3. Instantiate Blocks
    tx_block = crypto_dsss_tx(message=message, spreading_factor=spreading_factor)
    throttle = blocks.throttle(gr.sizeof_gr_complex, samp_rate, True)
    tx_rrc = filter.interp_fir_filter_ccf(sps, rrc_taps)

    chan = channels.channel_model(
        noise_voltage=noise_voltage,
        frequency_offset=freq_offset,
        epsilon=timing_offset,
        taps=[1.0 + 0.0j],
        noise_seed=42,
    )

    rx_rrc = filter.fir_filter_ccf(1, rrc_taps)

    sync = digital.symbol_sync_cc(
        digital.TED_MUELLER_AND_MULLER,
        sps,
        0.045,
        1.0,
        1.0,
        1.5,
        1,
        digital.constellation_bpsk().base(),
        digital.IR_MMSE_8TAP,
        128,
        [],
    )

    costas = digital.costas_loop_cc(0.0628, 2, False)

    rx_block = dsss_crypto_rx(
        expected_message=message,
        spreading_factor=spreading_factor,
        verbose=verbose,
    )

    # 4. Connect Signal Pipeline
    tb.connect(tx_block, throttle, tx_rrc, chan, rx_rrc, sync, costas, rx_block)

    # 5. Execute flowgraph to completion
    tb.run()

    return {
        "success": rx_block.success,
        "recovered_message": rx_block.recovered_text,
        "original_message": message,
        "ber": rx_block.ber,
        "evm_db": rx_block.evm_db,
    }


def main():
    parser = argparse.ArgumentParser(description="SentinelSpread GNU Radio Software SDR Loopback")
    parser.add_argument("--message", "-m", default="SentinelSpread GNU Radio SDR Software Loopback Verification 2026", help="Test message")
    parser.add_argument("--sf", type=int, default=16, help="Spreading factor (default: 16)")
    parser.add_argument("--noise", type=float, default=0.02, help="Channel AWGN noise voltage (default: 0.02)")
    parser.add_argument("--freq-offset", type=float, default=0.0, help="Channel carrier frequency offset (default: 0.0)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress diagnostic printout")

    args = parser.parse_args()

    result = run_software_loopback(
        message=args.message,
        spreading_factor=args.sf,
        noise_voltage=args.noise,
        freq_offset=args.freq_offset,
        verbose=not args.quiet,
    )

    if result["success"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
