# Stage 4 — Independent Propagation Verification

## Why this exists

The Stage 4 verification report claimed the GNU Radio flowgraph does real DSP
work (RRC pulse shaping, AWGN + frequency-offset channel impairment, Costas
carrier recovery, M&M symbol timing) and not just "message in → correct
message out" via the embedded crypto/DSSS blocks alone. Message-in/message-out
matching is necessary but not sufficient evidence — the RRC/channel/sync/
Costas blocks could in principle be disconnected or inert and, if the embedded
blocks were doing enough of the real work themselves, the end-to-end test could
still pass. This script checks the middle of the pipeline, not just the ends.

## What it checks

`sentinelspread/gnuradio/verify_gnuradio_propagation.py` taps the actual
flowgraph (same blocks `runner.py` uses — `crypto_dsss_tx`, `tx_rrc`, `chan`,
`rx_rrc`, `sync`, `costas`, `dsss_crypto_rx`) at three points with
`blocks.vector_sink_c`, then:

1. **RRC pulse shaping is real** — output sample count is `chips × sps`, and
   samples within one chip period actually vary (a no-op filter would just
   repeat the same value `sps` times).
2. **The channel actually injects noise** — measures residual variance on the
   known-constant `trail_flush` tail (appended by `crypto_dsss_tx` specifically
   for this purpose) and compares it to the configured `noise_voltage`.
3. **The channel actually rotates phase** — measures phase step per sample on
   that same tail and compares it to the frequency offset the channel model
   was configured with.
4. **The Costas loop actually removes that rotation** — same phase-step
   measurement after the Costas loop; should be near zero if it's doing real
   carrier tracking.
5. **Mutation test** — reruns the pipeline with the Costas loop physically
   removed from the chain, same frequency offset (`0.0005` normalized ≈ 100 Hz,
   which accumulates roughly 100 full phase rotations across the ~1-second
   burst — enough to scramble BPSK decisions completely without correction).
   If the message still decodes successfully with Costas removed, that proves
   the loop was never load-bearing in the original passing run. If it now
   fails (expected), that's real, mechanical proof the block matters.

## How to run

Running the script by bare path does NOT put the project root on `sys.path`,
so a plain `python path\to\script.py` fails with
`ModuleNotFoundError: No module named 'sentinelspread'`. Use one of:

```powershell
$env:PYTHONPATH='C:\Users\csaih\sentinelspread'; C:\Users\csaih\radioconda\python.exe sentinelspread\gnuradio\verify_gnuradio_propagation.py
```

```powershell
C:\Users\csaih\radioconda\python.exe -m sentinelspread.gnuradio.verify_gnuradio_propagation
```

Run it from the `C:\Users\csaih\sentinelspread` project root (same working
directory `runner.py` is normally run from).

## How to read the output

The script prints one `[OK]` / `[SUSPECT]` (or `[FAIL]`) line per check, then a
summary block at the end:

```
  RRC actually interpolates/shapes : PASS
  Channel actually injects noise   : PASS
  Channel actually rotates phase   : PASS
  Costas actually removes rotation : PASS
  Mutation test (Costas removed)   : PASS (fails without Costas, as expected)
```

- **All PASS** → the flowgraph is genuinely propagating and transforming the
  signal at every stage; Stage 4 is real, not cosmetic. Exit code `0`.
- **Any SUSPECT/FAIL** → that specific stage isn't doing what it claims (e.g.
  noise variance doesn't match configured `noise_voltage`, or the mutation
  test still decodes without Costas). Exit code `1`. Paste the full output —
  the specific line that failed says exactly what's wrong, and that's the
  thing to have Antigravity fix, not the whole Stage 4 implementation.

## Known-fixed issue (2026-10-01)

The original `check_channel_effects_real` measured noise as `std(tail - mean(tail))`,
assuming the trail-flush tail is constant. That assumption breaks once
`frequency_offset != 0`: the channel rotates every sample, so the "constant"
tail actually traces an arc/circle, and the check measured that arc's radius
instead of the noise on top of it. Fixed by de-rotating the tail by the known
`2*pi*FREQ_OFFSET` rad/sample before measuring std. This was confirmed against
an independent diagnostic sweep (noise_voltage x frequency_offset grid) showing
the corrected measurement matches the configured noise almost exactly
(0.0201 vs 0.02, 0.0989 vs 0.1), while the old measurement read ~0.39-0.50
regardless of the actual configured noise whenever a frequency offset was
present. This was a bug in the verification script, not in the flowgraph.

## What NOT to do if something fails

Don't have Antigravity "fix" this by making the script's checks pass (e.g.
loosening a tolerance) — the tolerances here are already generous (0.3x–4x for
noise, 50% for phase rotation). A failing check means the underlying flowgraph
genuinely isn't doing what the earlier report claimed, and the fix belongs in
`runner.py` / `blocks.py`, not in this verification script.
