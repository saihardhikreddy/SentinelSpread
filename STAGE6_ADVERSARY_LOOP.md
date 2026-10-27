# Stage 6 — The CNN Adversary and the Closed Hardening Loop

**SentinelSpread: Covert Spread-Spectrum Communication Suite**
*Stage 6: a learned detector hunts the signal, and the transmitter hardens only as far as it must to stay hidden.*

Stage 5 measured the burst against five fixed, hand-built statistics and a random forest over
them. Stage 6 closes the **Build → Attack → Harden** cycle the project is named for: it trains a
convolutional "Blue Team" detector straight on raw I/Q, then gives the transmitter a "Red Team"
response that reads the detector's own confidence and escalates hardening only as far as needed.
Everything here is a working, tested module under `sentinelspread/adversary/`, measured on the
same numpy channel model (`sentinelspread/dsss/simulate.py`) the GNU Radio flowgraph uses.

## The adversary (`adversary/cnn.py`)

A small 1-D CNN over a capture of shape `(2, length)` — in-phase and quadrature. Three strided
convolutions, a global average pool and a linear head; it trains in seconds on CPU. Two choices
keep it honest rather than flattering:

- **Per-capture power normalisation.** Every capture is divided by its own RMS before the network
  sees it (`dataset.iq_to_array`). Without this the CNN would separate the classes on absolute
  power alone and be nothing but the Stage 5 radiometer. Removing the power cue forces a decision
  on *structure*, which is the only thing that survives a signal below the noise floor.
- **The Stage 5 observer model.** Captures come from `detector.evaluate`: chip-rate sampling,
  payload region only, and per-capture noise drawn from a ±0.5 dB uncertainty band. The CNN's
  probability output is thresholded on noise-only scores at a chosen false-alarm rate, exactly as
  every Stage 5 detector is, so its probability of detection is quoted on the same footing.

## The closed loop (`adversary/controller.py`)

At each operating point the controller climbs an escalation ladder until the adversary's Pd falls
under a target, measuring Pd the honest way at each rung (re-calibrate on noise, then run on fresh
hardened captures):

| Rung | Measure | Cost at the keyed receiver |
|---|---|---|
| 0 | plain DSSS | — |
| 1 | FHSS, 8 channels, 64-chip dwell | none (hopping is invertible) |
| 2 | FHSS, 16 channels, 32-chip dwell | none |
| 3 | FHSS 16×32 + 0.7× transmit amplitude | link margin (BER rises) |
| 4 | FHSS 16×16 + 0.5× transmit amplitude | more link margin |

Hopping is tried before power backoff on purpose: the receiver regenerates the hop schedule from
the session key and removes it, so hopping costs nothing at the legitimate receiver, while
dropping transmit power buys covertness only by spending link margin. The loop stops at the first
rung that meets the target — the least structure radiated and the least power spent to stay hidden.

## The trade (`adversary/benchmark.py`)

Bit error rate at the keyed receiver (a numpy despread, no GNU Radio needed) against the CNN's
probability of detection, plain and hardened, on one SNR axis
(`SNR/sample = 10·log₁₀(0.25 / σ²)`). A representative run, SF 16:

```
    SNR/samp |    BER plain |     Pd plain |     BER hard |      Pd hard | hardening
      +4.4 dB |     0.00e+00 |         100% |     0.00e+00 |           0% | fhss-8x64
      +0.0 dB |     0.00e+00 |          79% |     0.00e+00 |           0% | fhss-8x64
      -2.9 dB |     0.00e+00 |          79% |     0.00e+00 |           0% | fhss-8x64
      -6.0 dB |     2.25e-03 |          50% |     2.25e-03 |           0% | fhss-8x64
(Pd at false-alarm rate 1%, SF 16, CNN adversary; FHSS is invertible so it does not change BER)
```

Reading this:

- **The CNN is a real threat to plain DSSS.** It catches the burst 100% at +4 dB and still
  50–79% once the signal is at or below the noise floor — more than the single Stage 5 statistics
  manage, because it learns its own structure cue rather than relying on one fixed test.
- **Key-derived hopping answers it at no link cost.** FHSS takes Pd to 0% across the band while
  the keyed receiver's BER column is unchanged — the hop schedule is removed before despreading.
- **Power backoff is held in reserve.** At these SNRs hopping alone meets the target, so the loop
  never climbs to the power-backoff rungs; those are what it reaches for when hopping is not
  enough, trading a little BER for the last of the covertness.

## Running it

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional, Stage 6 only
python cli.py attack-benchmark                 # train the CNN, then BER vs Pd, plain and hardened
python cli.py attack-benchmark --no-harden     # plain BER/Pd only
python cli.py test-stage stage6                # the Stage 6 test suite (skips without torch)
```

`tests/test_adversary.py` skips cleanly when PyTorch is not installed, the same way the GNU Radio
tests skip without GNU Radio.
