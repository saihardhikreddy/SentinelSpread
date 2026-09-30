# Stage 4 — Propagation Verification Results

**Date:** 2026-10-01 (final, after the verification-script fixes)
**Script:** `sentinelspread/gnuradio/verify_gnuradio_propagation.py`
**Python:** `C:\Users\csaih\radioconda\python.exe`
**Command:** `python -m sentinelspread.gnuradio.verify_gnuradio_propagation`, run from `C:\Users\csaih\sentinelspread`

## Verdict

**ALL PASS, exit code `0`, identical on 4 of 4 consecutive runs.** The GNU Radio
flowgraph really propagates and transforms the signal at every stage, so
Stage 4 is real, not cosmetic.

No flowgraph code (`runner.py` / `blocks.py`) was changed. Every earlier
failure came from three measurement bugs in the verification script. All three
are fixed, and **no tolerance was changed** (still 0.3x–4x for noise, 50% for
rotation, 20% for Costas residual).

| Check | Result | Measured | Expected |
|---|---|---|---|
| RRC actually interpolates/shapes | **PASS** | 44543 chips became 178172 samples; samples within one chip period vary | ×4 (SPS) |
| Channel actually injects noise | **PASS** | std 0.0200 | noise_voltage 0.02 |
| Channel actually rotates phase | **PASS** | 0.00314 rad/sample | 2π × 0.0005 = 0.00314 |
| Costas actually removes rotation | **PASS** | −0.00002 rad/symbol residual | ≈ 0 (uncorrected would be ≈ 0.01257/symbol) |
| Mutation test (Costas removed) | **PASS** | decode fails: `DECRYPTION_ERROR: Crypto bundle data incomplete` | should fail |

Baseline full pipeline: `success=True`, message `'Propagation verification payload'`.

## Final script output (key lines, 4 runs, all identical)

```
[Stage: chan] measuring on 1024 settled trail-flush samples
  configured noise_voltage=0.02, measured residual std≈0.0200
  measured mean phase step/sample≈0.00314 rad
[Stage: costas output] mean residual phase step/sample≈-0.00002 rad (pre-correction was ≈0.00314)
  RRC actually interpolates/shapes : PASS
  Channel actually injects noise   : PASS
  Channel actually rotates phase   : PASS
  Costas actually removes rotation : PASS
  Mutation test (Costas removed)   : PASS (fails without Costas, as expected)
EXIT=0
```

## History of runs

| Run | Noise | Rotation | Costas | Exit |
|---|---|---|---|---|
| 1 — original script | FAIL (0.5002) | PASS | PASS (0.00001, by luck) | 1 |
| 2 — after the doc update (fix not actually applied) | FAIL (0.5002) | PASS | FAIL, varied every run (0.01258, −0.00942, −0.00471, +0.05031, −0.02670) | 1 |
| 3 — fixes 1 + 2 applied | PASS, only just (0.077–0.078 vs 0.08 limit) | PASS, but some runs read 0.00467 | PASS (−0.00002) | 0 |
| 4 — fixes 1 + 2 + 3 applied | **PASS (0.0200)** | **PASS (0.00314)** | **PASS (−0.00002)** | **0** |

## The three bugs fixed (all in `verify_gnuradio_propagation.py`)

### Fix 1 — Noise measured the rotation, not the noise (`check_channel_effects_real`)

**Bug:** `std(tail - mean(tail))` assumes the trail-flush tail is constant.
The channel's frequency offset rotates it by about 6.4 rad over the window, so
the tail traces a circle and the check measured the circle's size (the tail
amplitude is 0.5).

**Evidence** (channel-only sweep, `noise_diag.py` in the session scratchpad):

| noise_voltage | freq_offset | Old method | Offset removed |
|---|---|---|---|
| 0.0 | 0.0 | 0.0032 | 0.0032 |
| 0.02 | 0.0 | 0.0201 | 0.0201 |
| 0.0 | 0.0005 | **0.3918** | 0.0032 |
| 0.02 | 0.0005 | **0.3925** | 0.0200 |
| 0.1 | 0.0005 | 0.4052 | 0.0989 |

**Fix:** remove the known offset (2π·FREQ_OFFSET rad/sample) and the unknown
starting phase before measuring std.

Note: the verification doc's "Known-fixed issue (2026-10-01)" section described
this fix before it was actually in the script. It is in the script now.

### Fix 2 — Costas window covered mostly data chips (`check_costas_corrected`)

**Bug:** the check averaged phase steps over the last 2000 Costas output
samples. After `symbol_sync` the stream runs at one sample per chip, so only
the last ~512 samples are the flat trail flush. The other ~1490 are ±1 data
chips, and each sign flip is a phase jump of about π that `np.angle` rounds to
+π or −π almost at random. That made the result noise: always near a whole
multiple of π/1999, and different on every run.

**Evidence** (`costas_diag.py` in the session scratchpad):

| Window | Naive mean step | ±π jumps | Step with BPSK removed (x²) |
|---|---|---|---|
| Last 2000 (old) | +0.058 / −0.006 / +0.052 | ~755 | ~1e-5 |
| Settled flush only | −0.00004 every run | 0 | −0.00004 |

**Fix:** measure only the settled flush
(`costas_samples[-trail_flush_len + settle : -settle]`, settle = 64), and square
the samples first so any leftover BPSK sign flips don't count.

### Fix 3 — The settle guard never applied (`check_channel_effects_real`)

**Bug:** `region[settle:-settle] if len(region) > 4 * settle else region`,
with region = 2048 and settle = 512, evaluates 2048 > 2048, which is False. So
the check always measured all 2048 samples, including the RRC transient where
data turns into the flush. That inflated the noise to about 0.077 (just under
the 0.08 limit), and on some runs a data sign flip pushed the rotation reading
to 0.00467 (0.00314 + π/2047).

**Fix:** `>` → `>=`. It now measures the 1024 truly settled samples, as
intended, and the "measuring on N samples" line reads 1024.

## Code changes

```diff
@@ check_channel_effects_real
-    mid_region = region[settle:-settle] if len(region) > 4 * settle else region
+    mid_region = region[settle:-settle] if len(region) >= 4 * settle else region

-    measured_std = float(np.std(mid_region - np.mean(mid_region)))
+    # The channel's frequency offset rotates the "constant" tail through
+    # ~one full turn over this window, so de-rotate by the known offset (and
+    # the unknown initial phase) before measuring, or std measures the
+    # rotation's radius instead of the noise.
+    n_idx = np.arange(len(mid_region))
+    derot = mid_region * np.exp(-2j * np.pi * FREQ_OFFSET * n_idx)
+    derot *= np.exp(-1j * np.angle(np.mean(derot)))
+    measured_std = float(np.std(derot - np.mean(derot)))

@@ check_costas_corrected
-def check_costas_corrected(costas_samples):
-    n = len(costas_samples)
-    tail = costas_samples[max(0, n - 2000):]
-    phase_diffs = np.angle(tail[1:] * np.conj(tail[:-1]))
+def check_costas_corrected(costas_samples, trail_flush_len=512):
+    # After symbol_sync the stream is 1 sample per chip, so only the last
+    # trail_flush_len samples are the constant flush; anything earlier is
+    # +/-1 data whose sign flips add ~+/-pi phase jumps. Measure only the
+    # settled flush, and square to strip any residual BPSK modulation.
+    settle = trail_flush_len // 8
+    tail = costas_samples[-trail_flush_len + settle:-settle]
+    phase_diffs = np.angle(tail[1:] ** 2 * np.conj(tail[:-1] ** 2)) / 2
```

## Why these fixes don't make the checks weaker

- No tolerance changed.
- Each check still fails if its stage were inert:
  - With no noise, the noise check reads ≈0.0032, below its 0.006 lower limit.
  - With no offset, the rotation check reads ≈0.
  - Without Costas, the leftover rotation would be ≈0.01257 rad/symbol, far above the ≈0.0016 limit.
  - The mutation test is unchanged and still fails without Costas.
- The corrected measurements match the configured values almost exactly
  (0.0200 vs 0.02, 0.00314 vs 0.00314) instead of just clearing a loose
  tolerance.

## Note on the run command

A bare `python path\to\script.py` fails with
`ModuleNotFoundError: No module named 'sentinelspread'`. Use
`$env:PYTHONPATH='C:\Users\csaih\sentinelspread'` or `python -m ...` from the
project root (both are now in the verification doc).
