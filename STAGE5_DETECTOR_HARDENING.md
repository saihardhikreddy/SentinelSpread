# Stage 5 — Detector Suite and Hardening

**SentinelSpread: Covert Spread-Spectrum Communication Suite**
*Stage 5: what a key-less observer can measure, and the countermeasures that move the line.*

Stage 4 proved the link works end to end. Stage 5 asks the next question: standing outside the
link with no key, how well can an observer tell the channel is occupied at all — and which
transmitter-side measures push that detection line further out. Everything here is a working,
tested library module under `sentinelspread/detector/` and `sentinelspread/harden/`, measured
on the numpy channel model in `sentinelspread/dsss/simulate.py` (the same burst, RRC filters and
channel the GNU Radio flowgraph uses).

## The detectors (`sentinelspread/detector/`)

Each detector computes one number from a capture, with no key, and flags "occupied" when that
number crosses a threshold. The threshold is set by calibration: the observer watches a stretch
of what it believes is empty channel, and picks the threshold that lets through at most its
chosen **false-alarm rate** (`pfa`). Every detection rate below is quoted at `pfa = 1%`.

| Detector | Statistic | What it responds to |
|---|---|---|
| `energy` | mean power vs a noise reference, in dB | total energy (the classic radiometer) |
| `flatness` | 1 − geo-mean/arith-mean of the PSD | a tone or a non-flat spectrum |
| `kurtosis` | \|excess kurtosis\| of the samples | non-Gaussian amplitude |
| `squaring` | peak-to-mean of the spectrum of x² | a BPSK carrier (x² removes the ±1) |
| `autocorrelation` | strongest non-zero-lag \|autocorrelation\| | repeating chip structure |
| `ml` | random forest over all five features | whatever combination separates best |

Two modelling choices make the results honest rather than flattering:

- **Noise uncertainty (±0.5 dB).** No receiver knows its own noise floor exactly. Each capture's
  true noise level is drawn from a ±0.5 dB band around nominal. This is what defeats the
  radiometer at low SNR: once the signal adds less power than the floor's own wobble, more
  integration does not help — the classic SNR wall.
- **Matched observer bandwidth.** The observer samples at the chip rate, so the signal fills its
  whole band. Capturing at the transmitter's 4×-oversampled rate would leave the burst in a
  quarter of the band, which any spectrum-shape test spots at once — not a realistic observer.

### Measured: plain DSSS, SF 16

```
 SNR/sample |  energy | flatness | kurtosis | squaring | autocorr |     ml
      +6.0 dB |   100%  |      0%  |    100%  |    100%  |    100%  |   100%
      +0.0 dB |   100%  |      0%  |    100%  |    100%  |     96%  |   100%
      -6.0 dB |   100%  |      0%  |     88%  |    100%  |     75%  |   100%
     -12.0 dB |   100%  |      0%  |      0%  |    100%  |      8%  |   100%
     -18.1 dB |    21%  |      0%  |      4%  |      0%  |      4%  |    50%
(detection rate at pfa = 1%, noise uncertainty ±0.5 dB)
```

Reading this:

- **Spreading defeats the spectrum-shape test outright.** `flatness` sits at 0% everywhere: a
  DSSS signal spread across the whole observed band looks like noise to a flatness test. This is
  the property DSSS is built on.
- **Carrier-squaring is the real threat.** `squaring` catches the burst 100% of the time down to
  −12 dB, because squaring a BPSK signal cancels its modulation and leaves a carrier tone that
  survives the spreading.
- **The radiometer hits the SNR wall.** `energy` holds until the signal power falls below the
  noise uncertainty, then collapses (21% at −18 dB).
- **The ML detector is the strongest single tool**, because it leans on whichever feature still
  carries information (it reports `squaring` as its dominant feature until that fails).

## The hardening (`sentinelspread/harden/`)

| Module | Measure | Verified by |
|---|---|---|
| `fhss` | key-derived frequency hopping over the chip stream | invertibility; squaring-detector reduction |
| `fec` | Hamming(7,4) + interleaving, rate 4/7 | round trip; single-error-per-word correction |
| `power` | adaptive transmit-amplitude policy | raises below target SNR, backs off above, step-limited |
| `rotation` | HKDF key ratchet, one AES key per epoch | determinism; per-epoch distinctness; one-way chain |

FHSS is the measure aimed at the squaring detector. The carrier tone that squaring relies on
only builds up while the carrier stays at one frequency; hopping the carrier on a key-derived
schedule spreads that tone's energy across the hop set, so its peak drops by roughly the number
of hops. The hop schedule comes from the same HKDF path as the PN seed, so the receiver
regenerates it and removes it before despreading.

### Measured: effect of FHSS, SF 16

```
 SNR/samp | squaring plain | squaring FHSS | autocorr plain | autocorr FHSS
    +0.0 dB |          100%  |         100%  |          100%  |           0%
    -6.0 dB |          100%  |          17%  |           71%  |           4%
   -12.0 dB |          100%  |           4%  |            4%  |           8%
```

FHSS takes the squaring detector from a certain catch (100%) down to 4–17% once the signal is at
or below the noise floor, and removes the autocorrelation detector's purchase almost entirely.
At +0 dB the signal is still strong enough that each hop's tone is individually visible, so
hopping alone is not enough there — power control (keeping the transmit level only as high as the
link needs) is the complementary measure at high SNR.

## Running it

```bash
python cli.py detect-sweep            # plain DSSS, all detectors, SF 16
python cli.py detect-sweep --fhss     # with FHSS applied to the signal
python cli.py detect-sweep --sf 64    # more spreading
python cli.py test-stage 5            # the Stage 5 test suite
```

## Scope and honest limits

- Numbers are from the **numpy channel model**, not the live GNU Radio chain. The model mirrors
  the burst, the RRC filters and the channel, and the despread-first receiver was cross-checked
  against the real flowgraph, but the detector sweep itself has not been run inside GNU Radio.
- The hardening modules are **verified primitives**, not yet wired into the live
  `/api/radio` transmit path or the Pluto loopback. Doing that end to end (hopping on transmit,
  de-hopping and FEC-decoding on receive, a feedback loop for power) is the natural next step.
- Detection results depend on the observer model (bandwidth, capture length, noise uncertainty,
  false-alarm budget). The ones here use a chip-rate observer, 2048-sample captures, ±0.5 dB
  uncertainty and pfa = 1%; other assumptions move the lines.
