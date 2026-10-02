"""
GNU Radio worker for the SentinelSpread web API. Runs under radioconda's Python
(the interpreter that has `gnuradio`), launched by radio.py as a subprocess:

    python radio_worker.py transmit <workdir> '<json args>'
    python radio_worker.py receive  <workdir>

It reuses the verified flowgraph blocks from the sentinelspread project, unchanged
(crypto_dsss_tx, dsss_crypto_rx, RRC, channel_model, symbol_sync, Costas). The two halves
are split so the receiver can run in a fresh process:

  transmit: crypto_dsss_tx -> RRC interp -> channel_model -> file_sink(tx.c64) (+ signal.wav)
            saves meta.json: RSA private key (PEM), symbol count, transmitted bits
  receive : file_source(tx.c64) -> RRC -> symbol_sync -> Costas -> dsss_crypto_rx
            restores the TX-side state the RX block expects, then reports BER / EVM / text

Result JSON goes to <workdir>/result_<mode>.json; GNU Radio's console output goes to stdout.
"""

import json
import sys
from pathlib import Path

import numpy as np
from gnuradio import blocks, channels, digital, filter, gr
from scipy.io import wavfile

from sentinelspread.gnuradio.blocks import crypto_dsss_tx, dsss_crypto_rx

SPS = 4
SAMP_RATE = 200_000          # nominal sample rate of the baseband stream
WAV_RATE = 48_000            # declared WAV rate: slowed ~4x so the burst is audible
RRC_ALPHA = 0.35


def rrc_taps():
    return filter.firdes.root_raised_cosine(np.sqrt(SPS), SPS, 1.0, RRC_ALPHA, 41)


def make_sync():
    return digital.symbol_sync_cc(
        digital.TED_MUELLER_AND_MULLER, SPS, 0.045, 1.0, 1.0, 1.5, 1,
        digital.constellation_bpsk().base(), digital.IR_MMSE_8TAP, 128, [],
    )


def write_wav(path: Path, iq: np.ndarray) -> None:
    real = np.real(iq).astype(np.float64)
    peak = float(np.max(np.abs(real))) if len(real) else 1.0
    pcm = (real / (peak if peak > 1e-12 else 1.0) * 0.9 * 32767.0).astype(np.int16)
    wavfile.write(str(path), WAV_RATE, pcm)


def transmit(workdir: Path, args: dict) -> dict:
    from Crypto.PublicKey import RSA  # noqa: F401  (pycryptodome, used via sentinelspread)

    sf = int(args["spreading_factor"])
    noise = float(args["noise_voltage"])
    freq = float(args.get("freq_offset", 0.0005))

    tb = gr.top_block("SentinelSpread_TX")
    tx = crypto_dsss_tx(message=args["message"], spreading_factor=sf)
    tx_rrc = filter.interp_fir_filter_ccf(SPS, rrc_taps())
    chan = channels.channel_model(
        noise_voltage=noise, frequency_offset=freq, epsilon=1.0, taps=[1.0 + 0.0j], noise_seed=42,
    )
    clean = blocks.vector_sink_c()       # pre-channel samples: lets us report a true SNR
    sink = blocks.file_sink(gr.sizeof_gr_complex, str(workdir / "tx.c64"))
    sink.set_unbuffered(False)
    tb.connect(tx, tx_rrc)
    tb.connect(tx_rrc, clean)
    tb.connect(tx_rrc, chan, sink)
    tb.run()
    tb.wait()

    clean_iq = np.asarray(clean.data(), dtype=np.complex64)
    tx_iq = np.fromfile(workdir / "tx.c64", dtype=np.complex64)
    write_wav(workdir / "signal.wav", tx_iq)

    sig_power = float(np.mean(np.abs(clean_iq) ** 2))
    # Measured noise: the burst ends in a constant tail. De-rotate the known carrier offset and
    # take the spread of the settled middle of that tail (same method as the Stage 4 check).
    tail = tx_iq[-2048:]
    mid = tail[512:-512]
    k = np.arange(len(mid))
    d = mid * np.exp(-2j * np.pi * freq * k)
    d = d * np.exp(-1j * np.angle(np.mean(d)))
    measured_noise = float(np.std(d - np.mean(d)))
    meta = {
        "private_key_pem": crypto_dsss_tx.LAST_PRIV_KEY.export_key().decode(),
        "num_symbols": int(crypto_dsss_tx.LAST_NUM_SYMBOLS),
        "tx_bits": [int(b) for b in crypto_dsss_tx.LAST_TX_BITS],
        "spreading_factor": sf,
        "noise_voltage": noise,
        "freq_offset": freq,
        "message_bytes": len(args["message"].encode()),
    }
    (workdir / "meta.json").write_text(json.dumps(meta))

    return {
        "num_chips": int(tx.total_chips),
        "num_symbols": meta["num_symbols"],
        "bundle_bytes": meta["num_symbols"] // 8,
        "samples": int(len(tx_iq)),
        "duration_s": len(tx_iq) / SAMP_RATE,
        "audio_s": len(tx_iq) / WAV_RATE,
        "signal_power": sig_power,
        "measured_noise_std": measured_noise,
        "applied_drift_rad": float(2 * np.pi * freq),
        "snr_db": float(10 * np.log10(sig_power / max(noise ** 2, 1e-12))) if noise > 0 else None,
        "processing_gain_db": float(10 * np.log10(sf)),
    }


def receive(workdir: Path) -> dict:
    from Crypto.PublicKey import RSA

    meta = json.loads((workdir / "meta.json").read_text())
    # Restore the TX-side state the RX block reads from class attributes.
    crypto_dsss_tx.LAST_PRIV_KEY = RSA.import_key(meta["private_key_pem"])
    crypto_dsss_tx.LAST_NUM_SYMBOLS = meta["num_symbols"]
    crypto_dsss_tx.LAST_TX_BITS = np.asarray(meta["tx_bits"], dtype=int)

    tb = gr.top_block("SentinelSpread_RX")
    src = blocks.file_source(gr.sizeof_gr_complex, str(workdir / "tx.c64"), False)
    rx_rrc = filter.fir_filter_ccf(1, rrc_taps())
    sync = make_sync()
    costas = digital.costas_loop_cc(0.0628, 2, False)
    # expected_message=None: decrypt-and-return-whatever (no ground-truth comparison)
    rx = dsss_crypto_rx(
        expected_message=None, spreading_factor=meta["spreading_factor"],
        expected_num_symbols=meta["num_symbols"], verbose=True,
    )
    costas_tap = blocks.vector_sink_c()
    tb.connect(src, rx_rrc, sync, costas, rx)
    tb.connect(costas, costas_tap)
    tb.run()
    tb.wait()

    # Residual carrier rotation: squared phase step over the settled constant tail (BPSK-free),
    # per symbol, the same measurement the Stage 4 verification uses.
    out = np.asarray(costas_tap.data(), dtype=np.complex64)
    tail = out[-456:-56] if len(out) > 600 else out[-100:]
    drift = None
    if len(tail) > 10:
        drift = float(np.mean(np.angle(tail[1:] ** 2 * np.conj(tail[:-1] ** 2)) / 2))

    total = meta["num_symbols"]
    return {
        "success": bool(rx.success),
        "recovered_text": rx.recovered_text if rx.success else None,
        "error": None if rx.success else str(rx.recovered_text or "No payload recovered"),
        "total_bits": total,
        "bit_errors": int(round(rx.ber * total)),
        "ber": float(rx.ber),
        "evm_db": float(rx.evm_db),
        "residual_drift_rad": drift,
    }


def main():
    mode, workdir = sys.argv[1], Path(sys.argv[2])
    out = transmit(workdir, json.loads(sys.argv[3])) if mode == "transmit" else receive(workdir)
    (workdir / f"result_{mode}.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
