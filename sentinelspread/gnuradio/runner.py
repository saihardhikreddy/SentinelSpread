"""
SentinelSpread GNU Radio SDR Loopback Transceiver Runner.

One DSP chain, two channels (selected with `channel`):

  sim   (default)  Crypto + DSSS TX -> RRC TX -> Channel Model (AWGN + Freq Offset) -> RRC RX -> [receiver]
  pluto            Crypto + DSSS TX -> RRC TX -> ADALM-Pluto TX1A ==[cable + attenuation]==> RX1A
                   -> DC block -> AGC -> RRC RX -> [receiver]

and two receivers (selected with `receiver`):

  despread (default)  dsss_despread_rx: find the burst on the known header, estimate the carrier
                      from it, despread, then track phase on the despread symbols. Uses the
                      processing gain before synchronising, so it decodes below the noise floor.
  classic             Symbol Sync -> Costas Loop -> dsss_crypto_rx: locks on the raw chips first,
                      so it stops at about 0 dB chip SNR whatever the spreading factor.

The TX/RX DSP blocks are built by the same helpers in both modes; only the channel differs.

SAFETY (pluto): no antennas; TX1A is cabled to RX1A. Pluto TX is ~+7 dBm at 0 dB attenuation,
above the RX input's ~+2.5 dBm limit, so the cable must carry enough attenuation:
  * with an inline ~30 dB SMA attenuator (the default setup), or
  * direct_cable=True (bare SMA cable): the Pluto's own TX attenuator is the only protection,
    so it is forced to maximum before the flowgraph starts and after it ends, and any setting
    below DIRECT_CABLE_MIN_TX_ATTEN_DB is refused.
Pluto mode refuses to transmit unless the caller sets hardware_ready=True (CLI:
--attenuator-in-line, or --direct-cable) to confirm the cabling.
"""

import argparse
import os
import sys
import time
import numpy as np

try:
    from gnuradio import gr, blocks, filter, channels, digital, analog
    import pmt
    from sentinelspread.gnuradio.blocks import crypto_dsss_tx, dsss_crypto_rx, dsss_despread_rx
    GNURADIO_AVAILABLE = True
except ImportError:
    GNURADIO_AVAILABLE = False


# ADALM-Pluto defaults (all overridable). Detected on this bench with `iio_info -s`:
#   0456:b673 PlutoSDR (ADALM-PLUTO) serial=10447376de0b00091a0009009ada97eba2 [usb:3.1.5]
# The USB address changes with the port, and ip:192.168.2.1 needs the RNDIS link, which this
# machine does not have. So the default URI is "" = scan for the first Pluto.
PLUTO_URI = ""
PLUTO_FREQ_HZ = 915_000_000       # cabled, so the carrier is arbitrary inside the AD9363 range
PLUTO_SAMP_RATE = 2_000_000       # whole chain runs here: 4 samples/chip -> 500 kchip/s
PLUTO_TX_ATTEN_DB = 20            # TX attenuation in dB (higher = weaker)
PLUTO_RX_GAIN_DB = 40             # manual RX gain
PLUTO_BANDWIDTH = 2_000_000       # RF bandwidth ~= sample rate
BUFFER_SIZE = 0x8000              # 32768 samples per libiio buffer
PLUTO_TX_SCALE = 0.5              # DAC back-off: shaped stream peaks ~1.2, fc32 full scale is 1.0
PLUTO_SETTLE_S = 0.25             # discard this much RX capture (startup transients, AGC ramp)
PLUTO_MAX_TX_ATTEN_DB = 89.75     # AD936x TX attenuator range is 0..89.75 dB
DIRECT_CABLE_MIN_TX_ATTEN_DB = 60 # bare cable: +7 dBm - 60 dB = -53 dBm at RX, ~55 dB under its limit
DIRECT_CABLE_TX_ATTEN_DB = 70     # bare-cable starting point
DIRECT_CABLE_RX_GAIN_DB = 50     # measured: ~28 dB in-band SNR, peak ~-28 dBFS (30 dB gave ~15 dB SNR)

DEFAULT_MESSAGE = "SentinelSpread GNU Radio SDR Software Loopback Verification 2026"


class PlutoNotDetected(RuntimeError):
    """The ADALM-Pluto could not be opened at the requested URI."""


class HardwareNotReady(RuntimeError):
    """Pluto TX was requested without confirming the cabling, or below the bare-cable floor."""


# --------------------------------------------------------------------------------------------
# Shared DSP blocks (identical in both channel modes)
# --------------------------------------------------------------------------------------------

def make_rrc_taps(sps: int):
    """RRC filter taps (unity energy)."""
    return filter.firdes.root_raised_cosine(np.sqrt(sps), sps, 1.0, 0.35, 41)


def make_symbol_sync(sps: int):
    return digital.symbol_sync_cc(
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


def make_costas():
    return digital.costas_loop_cc(0.0628, 2, False)


RECEIVERS = ("despread", "classic")


def make_receiver(tb, upstream, receiver: str, message: str, spreading_factor: int, sps: int,
                  verbose: bool, search_window=None):
    """Connect `upstream` (matched-filtered samples) to the chosen receiver and return
    (rx_block, costas or None)."""
    if receiver == "despread":
        rx_block = dsss_despread_rx(expected_message=message, spreading_factor=spreading_factor,
                                    sps=sps, verbose=verbose)
        tb.connect(upstream, rx_block)
        return rx_block, None
    if receiver != "classic":
        raise ValueError(f"receiver must be one of {RECEIVERS}, not {receiver!r}")
    sync = make_symbol_sync(sps)
    costas = make_costas()
    rx_block = dsss_crypto_rx(expected_message=message, spreading_factor=spreading_factor,
                              verbose=verbose, search_window=search_window)
    tb.connect(upstream, sync, costas, rx_block)
    return rx_block, costas


# --------------------------------------------------------------------------------------------
# Simulated channel
# --------------------------------------------------------------------------------------------

def run_software_loopback(
    message: str = DEFAULT_MESSAGE,
    spreading_factor: int = 16,
    noise_voltage: float = 0.02,
    freq_offset: float = 0.0,
    timing_offset: float = 1.0,
    sps: int = 4,
    samp_rate: int = 200000,
    verbose: bool = True,
    channel: str = "sim",
    receiver: str = "despread",
    **pluto_kwargs,
) -> dict:
    """
    Executes a complete loopback. channel="sim" (default) runs the software channel model;
    channel="pluto" hands off to run_pluto_loopback (pluto_kwargs go there).
    Returns a dictionary of execution metrics and status.
    """
    if channel == "pluto":
        return run_pluto_loopback(message=message, spreading_factor=spreading_factor, sps=sps,
                                  verbose=verbose, receiver=receiver, **pluto_kwargs)
    if channel != "sim":
        raise ValueError(f"channel must be 'sim' or 'pluto', not {channel!r}")
    if pluto_kwargs:
        raise TypeError(f"Pluto settings given for the sim channel: {', '.join(pluto_kwargs)}")
    if not GNURADIO_AVAILABLE:
        raise RuntimeError("GNU Radio is not installed or importable in current Python environment.")

    # 1. RRC filter taps (unity energy)
    rrc_taps = make_rrc_taps(sps)

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

    # 4. Connect Signal Pipeline
    tb.connect(tx_block, throttle, tx_rrc, chan, rx_rrc)
    rx_block, _ = make_receiver(tb, rx_rrc, receiver, message, spreading_factor, sps, verbose)

    # 5. Execute flowgraph to completion
    tb.run()

    return {
        "success": rx_block.success,
        "recovered_message": rx_block.recovered_text,
        "original_message": message,
        "ber": rx_block.ber,
        "evm_db": rx_block.evm_db,
        "channel": "sim",
        "receiver": receiver,
    }


# --------------------------------------------------------------------------------------------
# ADALM-Pluto channel
# --------------------------------------------------------------------------------------------

def _import_pyiio():
    """Import libiio's Python binding. Outside an activated conda env, libiio.dll is not on
    PATH and the binding's find_library() fails, so add the env's DLL folder first."""
    dll_dir = os.path.join(sys.prefix, "Library", "bin")
    if os.path.isdir(dll_dir) and dll_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
    import iio
    return iio


def find_pluto(uri: str = PLUTO_URI) -> dict:
    """
    Hardware guard: open the IIO context and return the device identity. Raises
    PlutoNotDetected with a readable message instead of letting a flowgraph hang.
    Must be called while no flowgraph holds the device (libiio USB contexts are exclusive).
    """
    try:
        iio = _import_pyiio()
    except Exception as e:
        raise PlutoNotDetected(f"libiio is not importable in this Python ({e}).") from e

    if not uri:
        try:
            found = [u for u, desc in iio.scan_contexts().items() if "PlutoSDR" in desc]
        except Exception:
            found = []
        if not found:
            raise PlutoNotDetected("ADALM-Pluto not detected (USB scan found none). "
                                   "Check USB and that iio_info -s lists it.")
        uri = found[0]

    try:
        ctx = iio.Context(uri)
    except Exception as e:
        raise PlutoNotDetected(f"ADALM-Pluto not detected at {uri}. "
                               f"Check USB and that iio_info -s lists it. ({e})") from e
    try:
        attrs = ctx.attrs
        if ctx.find_device("ad9361-phy") is None:
            raise PlutoNotDetected(f"The IIO device at {uri} is not an AD936x/Pluto.")
        info = {
            "uri": uri,
            "backend": ctx.name,
            "hw_model": attrs.get("hw_model"),
            "hw_serial": attrs.get("hw_serial"),
            "fw_version": attrs.get("fw_version"),
            "phy_model": attrs.get("ad9361-phy,model"),
        }
    finally:
        del ctx
    return info


def set_pluto_tx_attenuation(uri: str, atten_db: float = PLUTO_MAX_TX_ATTEN_DB) -> float:
    """Set TX1 attenuation directly on the AD936x and return the read-back value in dB.
    Only callable while no flowgraph holds the device."""
    iio = _import_pyiio()
    ctx = iio.Context(uri)
    try:
        ch = ctx.find_device("ad9361-phy").find_channel("voltage0", True)
        ch.attrs["hardwaregain"].value = f"{-float(atten_db):.2f}"
        return -float(ch.attrs["hardwaregain"].value.split()[0])
    finally:
        del ctx


def run_pluto_loopback(
    message: str = DEFAULT_MESSAGE,
    spreading_factor: int = 16,
    sps: int = 4,
    pluto_uri: str = PLUTO_URI,
    freq_hz: int = PLUTO_FREQ_HZ,
    samp_rate: int = PLUTO_SAMP_RATE,
    tx_atten_db: float = PLUTO_TX_ATTEN_DB,
    rx_gain_db: float = PLUTO_RX_GAIN_DB,
    bandwidth: int = PLUTO_BANDWIDTH,
    buffer_size: int = BUFFER_SIZE,
    tx_scale: float = PLUTO_TX_SCALE,
    bursts: int = 3,
    hardware_ready: bool = False,
    direct_cable: bool = False,
    verbose: bool = True,
    receiver: str = "despread",
) -> dict:
    """
    Real-RF loopback on one ADALM-Pluto: the burst is transmitted on repeat out of TX1A while
    RX1A captures settle + `bursts` burst periods, then the flowgraph is stopped and the RX
    block searches one full burst period for the preamble and decodes.
    """
    if not hardware_ready:
        raise HardwareNotReady(
            "Refusing to transmit on the Pluto: confirm TX1A -> ~30 dB SMA attenuator -> RX1A "
            "(no antennas), then pass hardware_ready=True / --attenuator-in-line "
            "(or --direct-cable for a bare TX1A -> RX1A cable).")
    if direct_cable and tx_atten_db < DIRECT_CABLE_MIN_TX_ATTEN_DB:
        raise HardwareNotReady(
            f"Refusing TX attenuation {tx_atten_db} dB on a bare cable: with no external "
            f"attenuator it must be at least {DIRECT_CABLE_MIN_TX_ATTEN_DB} dB.")
    if not 0 <= tx_atten_db <= PLUTO_MAX_TX_ATTEN_DB:
        raise ValueError(f"TX attenuation must be 0..{PLUTO_MAX_TX_ATTEN_DB} dB")
    if not GNURADIO_AVAILABLE:
        raise RuntimeError("GNU Radio is not installed or importable in current Python environment.")
    try:
        from gnuradio import iio as gr_iio
    except ImportError as e:
        raise RuntimeError("gr-iio is missing from this GNU Radio install.") from e

    device = find_pluto(pluto_uri)
    uri = device["uri"]
    chip_rate = samp_rate / sps
    # Start from the quietest TX state so nothing strong reaches RX while the flowgraph comes up.
    preset = set_pluto_tx_attenuation(uri, PLUTO_MAX_TX_ATTEN_DB)
    if preset < PLUTO_MAX_TX_ATTEN_DB - 0.5:
        raise HardwareNotReady(f"Could not preset Pluto TX attenuation to max (read back {preset} dB).")
    if verbose:
        print(f"[pluto] context {uri} ({device['backend']} backend)  {device['hw_model']}  "
              f"serial={device['hw_serial']}  fw={device['fw_version']}")
        print(f"[pluto] cabling: {'bare TX1A->RX1A cable' if direct_cable else 'external attenuator'}; "
              f"TX attenuation preset to {preset} dB before start")
        print(f"[pluto] {freq_hz / 1e6:.3f} MHz, {samp_rate / 1e6:.3f} MS/s "
              f"({chip_rate / 1e3:.0f} kchip/s, sps={sps}), TX atten {tx_atten_db} dB, "
              f"RX gain {rx_gain_db} dB")

    rrc_taps = make_rrc_taps(sps)
    tb = gr.top_block("SentinelSpread_Pluto_Loopback")

    # TX: same source and shaping as sim; no throttle, the DAC clock paces the stream.
    tx_block = crypto_dsss_tx(message=message, spreading_factor=spreading_factor, repeat=True)
    tx_rrc = filter.interp_fir_filter_ccf(sps, rrc_taps)
    tx_gain = blocks.multiply_const_cc(tx_scale)
    tx = gr_iio.fmcomms2_sink_fc32(uri, [True, True], buffer_size, False)
    tx.set_len_tag_key("")
    tx.set_bandwidth(bandwidth)
    tx.set_frequency(freq_hz)
    tx.set_samplerate(samp_rate)
    tx.set_attenuation(0, float(tx_atten_db))
    tx.set_filter_params("Auto", "", 0, 0)

    # RX: hardware source, then the one hardware-only DSP addition (DC block) and an AGC that
    # brings the arbitrary RF level to the amplitude the sim chain runs at (rms ~0.5, the TX
    # stream's own level) so the sync/Costas loop gains match their verified tuning.
    rx = gr_iio.fmcomms2_source_fc32(uri, [True, True], buffer_size)
    rx.set_len_tag_key("")
    rx.set_frequency(freq_hz)
    rx.set_samplerate(samp_rate)
    rx.set_gain_mode(0, "manual")
    rx.set_gain(0, float(rx_gain_db))
    rx.set_quadrature(True)
    rx.set_rfdc(True)
    rx.set_bbdc(True)
    rx.set_filter_params("Auto", "", 0, 0)

    burst_samples = tx_block.total_chips * sps
    settle = int(PLUTO_SETTLE_S * samp_rate)
    capture = bursts * burst_samples
    skip = blocks.skiphead(gr.sizeof_gr_complex, settle)
    head = blocks.head(gr.sizeof_gr_complex, capture)
    dc_block = filter.dc_blocker_cc(32, True)
    agc = analog.agc2_cc(1e-2, 1e-3, 0.5, 1.0)
    agc.set_max_gain(1e5)
    rx_rrc = filter.fir_filter_ccf(1, rrc_taps)
    raw_tap = blocks.vector_sink_c()
    dc_tap = blocks.vector_sink_c()

    tb.connect(tx_block, tx_rrc, tx_gain, tx)
    tb.connect(rx, skip, head, dc_block, agc, rx_rrc)
    # Classic receiver: one burst period (+ slack) guarantees a whole preamble+payload inside the
    # capture. The despread receiver searches the whole capture for a burst that fits.
    rx_block, costas = make_receiver(tb, rx_rrc, receiver, message, spreading_factor, sps, verbose,
                                     search_window=tx_block.total_chips + 1000)
    tb.connect(head, raw_tap)
    tb.connect(dc_block, dc_tap)

    # The Pluto source and the repeating TX never end on their own: run until the capture is in.
    t0 = time.monotonic()
    timeout_s = 10.0 + (settle + capture) / samp_rate * 5
    tb.start()
    try:
        while head.nitems_written(0) < capture:
            if time.monotonic() - t0 > timeout_s:
                raise RuntimeError(f"Pluto RX stalled: {head.nitems_written(0)}/{capture} samples "
                                   f"in {timeout_s:.0f} s.")
            time.sleep(0.02)
        time.sleep(0.3)  # let the RX chain drain the tail of the capture
    finally:
        tb.stop()
        tb.wait()
        del tb, tx, rx
        import gc
        gc.collect()
        try:
            set_pluto_tx_attenuation(uri, PLUTO_MAX_TX_ATTEN_DB)
        except Exception as e:  # the run's result still stands; just say TX was left as-is
            print(f"[pluto] warning: could not reset TX attenuation to max: {e}", file=sys.stderr)
    elapsed = time.monotonic() - t0

    # Real-channel signatures the simulation does not have
    raw = np.asarray(raw_tap.data(), dtype=np.complex64)
    dc_out = np.asarray(dc_tap.data(), dtype=np.complex64)
    rx_power_dbfs = float(10 * np.log10(np.mean(np.abs(raw) ** 2) + 1e-20))
    peak_dbfs = float(20 * np.log10(np.max(np.abs(raw)) + 1e-20))
    dc_in = complex(np.mean(raw))
    dc_after = complex(np.mean(dc_out[1000:])) if len(dc_out) > 1000 else 0j
    if costas is not None:
        cfo_rad_per_chip = float(costas.get_frequency())
    elif rx_block.result is not None:
        cfo_rad_per_chip = rx_block.result.cfo_rad_per_chip
    else:
        cfo_rad_per_chip = float("nan")
    cfo_hz = cfo_rad_per_chip * chip_rate / (2 * np.pi)

    if verbose:
        print(f"[pluto] captured {len(raw)} samples ({elapsed:.2f} s wall), "
              f"RX power {rx_power_dbfs:.1f} dBFS, peak {peak_dbfs:.1f} dBFS")
        print(f"[pluto] DC offset in {dc_in.real:+.3e}{dc_in.imag:+.3e}j "
              f"(|{abs(dc_in):.3e}|) -> after dc_blocker |{abs(dc_after):.3e}|")
        print(f"[pluto] carrier offset {cfo_hz:+.1f} Hz "
              f"({cfo_rad_per_chip:+.3e} rad/chip)")

    return {
        "success": rx_block.success,
        "recovered_message": rx_block.recovered_text,
        "original_message": message,
        "ber": rx_block.ber,
        "evm_db": rx_block.evm_db,
        "channel": "pluto",
        "receiver": receiver,
        "device": device,
        "freq_hz": freq_hz,
        "samp_rate": samp_rate,
        "tx_atten_db": tx_atten_db,
        "direct_cable": direct_cable,
        "rx_gain_db": rx_gain_db,
        "captured_samples": int(len(raw)),
        "rx_power_dbfs": rx_power_dbfs,
        "rx_peak_dbfs": peak_dbfs,
        "dc_offset": [dc_in.real, dc_in.imag],
        "dc_offset_mag": abs(dc_in),
        "dc_after_block_mag": abs(dc_after),
        "cfo_hz": cfo_hz,
        "_raw_iq": raw,
    }


def main():
    parser = argparse.ArgumentParser(description="SentinelSpread GNU Radio SDR Loopback")
    parser.add_argument("--message", "-m", default=DEFAULT_MESSAGE, help="Test message")
    parser.add_argument("--sf", type=int, default=16, help="Spreading factor (default: 16)")
    parser.add_argument("--noise", type=float, default=0.02, help="Channel AWGN noise voltage (default: 0.02)")
    parser.add_argument("--freq-offset", type=float, default=0.0, help="Channel carrier frequency offset (default: 0.0)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress diagnostic printout")
    parser.add_argument("--receiver", choices=RECEIVERS, default="despread",
                        help="despread = despread-first receiver (default); classic = symbol sync + Costas on raw chips")
    parser.add_argument("--channel", choices=("sim", "pluto"), default="sim",
                        help="sim = GNU Radio channel model (default); pluto = real RF on an ADALM-Pluto")
    pluto = parser.add_argument_group("ADALM-Pluto (--channel pluto)")
    pluto.add_argument("--attenuator-in-line", action="store_true",
                       help="Confirm TX1A -> ~30 dB attenuator -> RX1A, no antennas. Required to transmit.")
    pluto.add_argument("--uri", default=PLUTO_URI, help="IIO URI (default: scan for the first Pluto)")
    pluto.add_argument("--freq", type=float, default=PLUTO_FREQ_HZ, help="Carrier in Hz (default: 915e6)")
    pluto.add_argument("--samp-rate", type=float, default=PLUTO_SAMP_RATE, help="Sample rate (default: 2e6)")
    pluto.add_argument("--direct-cable", action="store_true",
                       help=f"Confirm a bare TX1A -> RX1A cable, no attenuator, no antennas. Enforces TX "
                            f"attenuation >= {DIRECT_CABLE_MIN_TX_ATTEN_DB} dB.")
    pluto.add_argument("--tx-atten", type=float, default=None,
                       help=f"TX attenuation dB (default: {PLUTO_TX_ATTEN_DB}; {DIRECT_CABLE_TX_ATTEN_DB} with --direct-cable)")
    pluto.add_argument("--rx-gain", type=float, default=None,
                       help=f"RX manual gain dB (default: {PLUTO_RX_GAIN_DB}; {DIRECT_CABLE_RX_GAIN_DB} with --direct-cable)")
    pluto.add_argument("--save-iq", default=None, help="Write the raw RX capture to this .c64 file")

    args = parser.parse_args()

    if args.channel == "pluto":
        try:
            result = run_pluto_loopback(
                message=args.message,
                spreading_factor=args.sf,
                pluto_uri=args.uri,
                freq_hz=int(args.freq),
                samp_rate=int(args.samp_rate),
                bandwidth=int(args.samp_rate),
                tx_atten_db=args.tx_atten if args.tx_atten is not None else
                (DIRECT_CABLE_TX_ATTEN_DB if args.direct_cable else PLUTO_TX_ATTEN_DB),
                rx_gain_db=args.rx_gain if args.rx_gain is not None else
                (DIRECT_CABLE_RX_GAIN_DB if args.direct_cable else PLUTO_RX_GAIN_DB),
                hardware_ready=args.attenuator_in_line or args.direct_cable,
                direct_cable=args.direct_cable,
                verbose=not args.quiet,
                receiver=args.receiver,
            )
        except (PlutoNotDetected, HardwareNotReady) as e:
            print(f"[!] {e}", file=sys.stderr)
            sys.exit(2)
        if args.save_iq:
            result["_raw_iq"].tofile(args.save_iq)
    else:
        result = run_software_loopback(
            message=args.message,
            spreading_factor=args.sf,
            noise_voltage=args.noise,
            freq_offset=args.freq_offset,
            verbose=not args.quiet,
            receiver=args.receiver,
        )

    if result["success"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
