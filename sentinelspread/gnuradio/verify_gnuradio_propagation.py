"""
SentinelSpread Stage 4 — Independent propagation verification.

Proves the GNU Radio flowgraph is actually doing DSP work at each stage,
rather than the embedded crypto/DSSS blocks just computing the right answer
while the RRC/channel/sync/Costas blocks are along for the ride.

Run with the radioconda Python (the one with gnuradio installed), from the
sentinelspread project root:

    C:\\Users\\csaih\\radioconda\\python.exe sentinelspread\\gnuradio\\verify_gnuradio_propagation.py

Two parts:
  PART 1 — Tap the flowgraph at every stage and check each stage's OWN
           signature in the captured samples (interpolation happened,
           noise variance matches the configured value, a frequency offset
           actually rotates phase, Costas removes that rotation).
  PART 2 — Mutation test: deliberately strip out the Costas loop while
           keeping a frequency offset large enough that, per the math below,
           it MUST scramble BPSK decisions without correction. If decode
           still succeeds with Costas removed, the block was never load-
           bearing and the earlier "PASS" was hollow. If it now fails
           (expected), that's real proof the block matters.
"""

import sys
import numpy as np

try:
    from gnuradio import gr, blocks, filter, channels, digital
except ImportError:
    print("[FATAL] GNU Radio not importable. Run this with radioconda's python.exe.")
    sys.exit(1)

from sentinelspread.gnuradio.blocks import crypto_dsss_tx, dsss_crypto_rx


SPS = 4
SAMP_RATE = 200_000
NOISE_VOLTAGE = 0.02
FREQ_OFFSET = 0.0005  # normalized to samp_rate -> 100 Hz actual offset
MESSAGE = "Propagation verification payload"
SF = 16


def build_rrc_taps():
    return filter.firdes.root_raised_cosine(np.sqrt(SPS), SPS, 1.0, 0.35, 41)


def run_tapped_flowgraph():
    """PART 1: run the real pipeline with a vector_sink_c tapped after
    every stage, and return the captured samples from each tap."""
    rrc_taps = build_rrc_taps()
    tb = gr.top_block("Tapped")

    tx = crypto_dsss_tx(message=MESSAGE, spreading_factor=SF)
    throttle = blocks.throttle(gr.sizeof_gr_complex, SAMP_RATE, True)
    tx_rrc = filter.interp_fir_filter_ccf(SPS, rrc_taps)
    chan = channels.channel_model(
        noise_voltage=NOISE_VOLTAGE, frequency_offset=FREQ_OFFSET,
        epsilon=1.0, taps=[1.0 + 0.0j], noise_seed=42,
    )
    rx_rrc = filter.fir_filter_ccf(1, rrc_taps)
    sync = digital.symbol_sync_cc(
        digital.TED_MUELLER_AND_MULLER, SPS, 0.045, 1.0, 1.0, 1.5, 1,
        digital.constellation_bpsk().base(), digital.IR_MMSE_8TAP, 128, [],
    )
    costas = digital.costas_loop_cc(0.0628, 2, False)
    rx = dsss_crypto_rx(expected_message=MESSAGE, spreading_factor=SF, verbose=False)

    tap_tx_rrc = blocks.vector_sink_c()
    tap_chan = blocks.vector_sink_c()
    tap_costas = blocks.vector_sink_c()

    tb.connect(tx, throttle, tx_rrc)
    tb.connect(tx_rrc, tap_tx_rrc)
    tb.connect(tx_rrc, chan)
    tb.connect(chan, tap_chan)
    tb.connect(chan, rx_rrc, sync, costas)
    tb.connect(costas, tap_costas)
    tb.connect(costas, rx)

    tb.run()

    return {
        "tx_rrc": np.array(tap_tx_rrc.data()),
        "chan": np.array(tap_chan.data()),
        "costas": np.array(tap_costas.data()),
        "rx_success": rx.success,
        "rx_message": rx.recovered_text,
        "n_chips_raw": tx.total_chips,
    }


def check_interpolation_real(chip_count, tx_rrc_samples):
    n = len(tx_rrc_samples)
    expected = chip_count * SPS
    print(f"\n[Stage: tx_rrc] input chips={chip_count}, output samples={n}, "
          f"expected={expected} (ratio {n/chip_count:.2f}, should be {SPS})")
    # Real pulse shaping means the 4 samples within one chip period are NOT
    # identical (a no-op/zero-order-hold filter would repeat the same value).
    mid = n // 2
    window = tx_rrc_samples[mid:mid+SPS]
    flat = np.allclose(window, window[0], atol=1e-6)
    print(f"  samples within one chip period: {window}")
    print(f"  {'[FAIL] flat/repeated -> filter is a no-op' if flat else '[OK] varies -> real pulse shaping'}")
    return not flat


def check_channel_effects_real(chan_samples, trail_flush_len=512):
    # The trail flush is a long run of constant +1.0 chips appended before
    # RRC shaping; after the RRC filter's transient settles, its middle
    # region approaches a near-constant envelope, so we can measure injected
    # noise and phase rotation directly against it.
    flush_samples_after_rrc = trail_flush_len * SPS
    region = chan_samples[-flush_samples_after_rrc:]
    settle = flush_samples_after_rrc // 4
    mid_region = region[settle:-settle] if len(region) >= 4 * settle else region

    # The tail is only constant in amplitude and per-sample phase STEP, not in
    # absolute value, once frequency_offset != 0 -- the channel rotates every
    # sample by 2*pi*FREQ_OFFSET rad, so the "constant" region actually traces
    # an arc/circle. Measuring std directly picks up that rotation's radius,
    # not the noise sitting on top of it. De-rotate first.
    n_idx = np.arange(len(mid_region))
    derot = mid_region * np.exp(-2j * np.pi * FREQ_OFFSET * n_idx)
    derot *= np.exp(-1j * np.angle(derot.mean()))
    measured_std = float(np.std(derot - derot.mean()))
    print(f"\n[Stage: chan] measuring on {len(mid_region)} settled trail-flush samples (de-rotated)")
    print(f"  configured noise_voltage={NOISE_VOLTAGE}, measured residual std≈{measured_std:.4f}")
    noise_ok = 0.3 * NOISE_VOLTAGE < measured_std < 4.0 * NOISE_VOLTAGE
    print(f"  {'[OK]' if noise_ok else '[SUSPECT]'} measured noise is "
          f"{'in the right ballpark' if noise_ok else 'NOT consistent with configured noise_voltage'}")

    phase_diffs = np.angle(mid_region[1:] * np.conj(mid_region[:-1]))
    mean_phase_step = float(np.mean(phase_diffs))
    expected_phase_step = 2 * np.pi * FREQ_OFFSET  # normalized offset -> radians/sample
    print(f"  configured freq offset -> expected phase step/sample≈{expected_phase_step:.5f} rad")
    print(f"  measured mean phase step/sample≈{mean_phase_step:.5f} rad")
    freq_ok = abs(abs(mean_phase_step) - abs(expected_phase_step)) < 0.5 * abs(expected_phase_step) + 1e-3
    print(f"  {'[OK]' if freq_ok else '[SUSPECT]'} measured rotation "
          f"{'matches' if freq_ok else 'does NOT match'} the configured frequency offset")
    return noise_ok, freq_ok


def check_costas_corrected(costas_samples, trail_flush_len=512):
    # After symbol_sync the stream is 1 sample per chip, so only the last
    # trail_flush_len samples are the constant flush; anything earlier is
    # +/-1 data whose sign flips add ~+/-pi phase jumps. Measure only the
    # settled flush, and square to strip any residual BPSK modulation.
    settle = trail_flush_len // 8
    tail = costas_samples[-trail_flush_len + settle:-settle]
    phase_diffs = np.angle(tail[1:] ** 2 * np.conj(tail[:-1] ** 2)) / 2
    mean_phase_step = float(np.mean(phase_diffs))
    print(f"\n[Stage: costas output] mean residual phase step/sample≈{mean_phase_step:.5f} rad "
          f"(pre-correction was ≈{2*np.pi*FREQ_OFFSET:.5f})")
    locked = abs(mean_phase_step) < 0.2 * abs(2 * np.pi * FREQ_OFFSET) + 1e-3
    print(f"  {'[OK] Costas loop removed the rotation -> real carrier tracking' if locked else '[SUSPECT] rotation still present after Costas'}")
    return locked


def mutation_test_remove_costas():
    """PART 2: same pipeline, Costas loop removed from the chain, same
    frequency offset. Per the phase-accumulation math this SHOULD fail."""
    rrc_taps = build_rrc_taps()
    tb = gr.top_block("MutationNoCostas")

    tx = crypto_dsss_tx(message=MESSAGE, spreading_factor=SF)
    throttle = blocks.throttle(gr.sizeof_gr_complex, SAMP_RATE, True)
    tx_rrc = filter.interp_fir_filter_ccf(SPS, rrc_taps)
    chan = channels.channel_model(
        noise_voltage=NOISE_VOLTAGE, frequency_offset=FREQ_OFFSET,
        epsilon=1.0, taps=[1.0 + 0.0j], noise_seed=42,
    )
    rx_rrc = filter.fir_filter_ccf(1, rrc_taps)
    sync = digital.symbol_sync_cc(
        digital.TED_MUELLER_AND_MULLER, SPS, 0.045, 1.0, 1.0, 1.5, 1,
        digital.constellation_bpsk().base(), digital.IR_MMSE_8TAP, 128, [],
    )
    rx = dsss_crypto_rx(expected_message=MESSAGE, spreading_factor=SF, verbose=False)

    # NOTE: costas loop is intentionally omitted from this chain.
    tb.connect(tx, throttle, tx_rrc, chan, rx_rrc, sync, rx)
    tb.run()

    print(f"\n[Mutation test: Costas loop removed, same freq_offset={FREQ_OFFSET}]")
    print(f"  recovered message: {rx.recovered_text!r}")
    print(f"  success: {rx.success}")
    if rx.success:
        print("  [SUSPECT] Decoded successfully WITHOUT Costas correction -> "
              "the Costas loop may not have been load-bearing in the original run.")
    else:
        print("  [OK] Failed as expected without carrier correction -> "
              "confirms the Costas loop was doing real work in the original run.")
    return rx.success


def main():
    print("=" * 70)
    print("  SentinelSpread GNU Radio propagation verification")
    print("=" * 70)

    result = run_tapped_flowgraph()
    print(f"\nBaseline (full pipeline) success={result['rx_success']}, "
          f"message={result['rx_message']!r}")

    ok_interp = check_interpolation_real(result["n_chips_raw"], result["tx_rrc"])
    ok_noise, ok_freq = check_channel_effects_real(result["chan"])
    ok_costas = check_costas_corrected(result["costas"])

    mutation_success = mutation_test_remove_costas()

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  RRC actually interpolates/shapes : {'PASS' if ok_interp else 'FAIL'}")
    print(f"  Channel actually injects noise   : {'PASS' if ok_noise else 'FAIL'}")
    print(f"  Channel actually rotates phase   : {'PASS' if ok_freq else 'FAIL'}")
    print(f"  Costas actually removes rotation : {'PASS' if ok_costas else 'FAIL'}")
    print(f"  Mutation test (Costas removed)   : "
          f"{'PASS (fails without Costas, as expected)' if not mutation_success else 'FAIL (still decodes -> Costas not load-bearing!)'}")
    print("=" * 70)

    all_ok = ok_interp and ok_noise and ok_freq and ok_costas and (not mutation_success)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
