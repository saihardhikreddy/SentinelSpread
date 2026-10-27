# SentinelSpread — Handoff for Claude Code on Windows

This file hands off work done in a Linux Claude Code session. Read it top to bottom before
touching anything. The repo is **complete and green**; the main open task is the slide deck
(section 7). The user is the author (`saihardhikreddy` / course 23AID203 / Amrita, Group 8).

---

## 1. What SentinelSpread is

A covert software-defined-radio comms project: **Build → Attack → Harden**. A payload is
AES-encrypted, hidden in audio/image (steganography), spread with a pseudo-noise code so it sits
**below the noise floor** (negative SNR), modulated (BPSK/QPSK), carried through a real **GNU Radio**
flowgraph (or an **ADALM-Pluto** over a cable), then the project **attacks its own signal** with
key-free detectors + a CNN, and **hardens** against them (FHSS, FEC, power control, key ratchet).

Layout: `sentinelspread/` (DSP pipeline) · `stego_crypto_api/` (FastAPI backend) ·
`stego_crypto_frontend/` (web app) · `tests/` · `cli.py`.

---

## 2. Current state — everything below is DONE and verified

| Stage | What | State |
|---|---|---|
| 1 | Input/header, AES-256-GCM + RSA-OAEP | done |
| 2 | BPSK/QPSK modem, RRC, AWGN, BER vs Eb/N0 | done |
| 3 | DSSS PN/spreader/correlator, processing gain | done |
| 4 | GNU Radio 3.10 flowgraph + **real ADALM-Pluto loopback** | done, hardware-verified |
| 5 | 5 key-free detectors + RandomForest + FHSS/FEC/power/key-ratchet hardening | done |
| 6 | **PyTorch CNN adversary + closed-loop detection-driven hardening** | done (new this session) |
| web | 20-tool workbench + **new ADALM-Pluto SDR section** | done (new this session) |

Test results from the Linux session: **pipeline 70/70**, **web API 32/32**, **GNU Radio propagation 5/5**.
Real Pluto loopback (direct cable, 915 MHz, 2 MS/s): symbol SNR **22.3 dB**, **BER 0.000000**, exact message recovered.

---

## 3. What the last (Linux) session added — do NOT redo

Commit on `main` after `7451f49`:

- **`sentinelspread/adversary/`** (new, Stage 6): `cnn.py` (PyTorch CNN detector on raw I/Q),
  `controller.py` (escalates FHSS → transmit-power backoff until the CNN's Pd < target),
  `benchmark.py` (BER-vs-Pd), `dataset.py`. CLI: `python cli.py attack-benchmark`.
- **`tests/test_adversary.py`** — 5 tests, skip cleanly if torch is absent.
- **`sentinelspread/detector/evaluate.py`** — `signal_segments()` gained an optional `rsa_keys`
  (shared keypair → fast bulk capture generation). Backward compatible.
- **GNU Radio tests** (`tests/test_gnuradio.py`) now honor `RADIOCONDA_PYTHON` / `RADIOCONDA_GRCC`
  and default to the current interpreter when it imports GNU Radio. **Windows default preserved**
  (`C:\Users\csaih\radioconda\python.exe`), so on this machine they just work.
- **Web SDR section**: `stego_crypto_frontend/` (index.html/workbench.js/styles.css) got an
  "ADALM-Pluto SDR" tool group — live link status, covert transmit & recover (sim or Pluto),
  self-attack & harden sweep. Backend: `stego_crypto_api/radio.py` added `/api/radio/detect-sweep`;
  `radio_worker.py` `probe` honors `SENTINEL_PLUTO_URI`, plus a `detect` worker mode.
- **Two radio web tests** got the `@needs_gnuradio` skip guard the rest already had.
- Docs: `STAGE6_ADVERSARY_LOOP.md`, README + requirements (torch marked optional).

---

## 4. Setup on Windows

You already have **radioconda** at `C:\Users\csaih\radioconda` (the project's default). Use it for
anything that needs GNU Radio or the Pluto; use a normal Python for the rest.

```powershell
cd <repo>
git pull                                           # get the pushed commits
pip install -r requirements.txt                    # numpy scipy pycryptodome sklearn matplotlib pytest
pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional, Stage 6 CNN only
pip install -r stego_crypto_api\requirements.txt   # fastapi uvicorn pillow httpx python-multipart
```

For the Pluto on Windows you also need the IIO/pyadi bindings (radioconda ships most): confirm
`python -c "import iio, adi"` works in radioconda. The Pluto is normally reachable at
`usb:` (USB scan) or `ip:192.168.2.1`.

---

## 5. How to run everything

```powershell
# Tests
python -m pytest tests                 # pipeline (GNU Radio tests run under radioconda python)
python -m pytest stego_crypto_api      # web API
python cli.py test-stage all

# DSP / evaluation
python cli.py plot-ber                 # BER vs SNR
python cli.py benchmark-gain           # processing gain across spreading factors
python cli.py detect-sweep             # Stage 5 detector sweep
python cli.py detect-sweep --fhss      # same, hardened
python cli.py attack-benchmark         # Stage 6: CNN adversary, BER vs Pd, plain vs hardened (needs torch)

# GNU Radio software loopback (no hardware)
C:\Users\csaih\radioconda\python.exe -m sentinelspread.gnuradio.verify_gnuradio_propagation

# Web app (serves the frontend + the SDR section)
python -m uvicorn main:app --app-dir stego_crypto_api --port 8001
#   then open http://localhost:8001  -> scroll to Workbench -> "SDR / Pluto" group
```

The web app's radio endpoints shell out to GNU Radio via two env vars (defaults already point to
radioconda on this machine): `SENTINEL_RADIO_PYTHON` (the GNU Radio python) and
`SENTINEL_PROJECT_ROOT` (this repo). Set `SENTINEL_PLUTO_URI=ip:192.168.2.1` if the USB scan
doesn't list the Pluto.

---

## 6. The ADALM-Pluto — SAFETY, read before transmitting

- **Cable only, never antennas.** Transmitting with antennas radiates over the air; at 915 MHz
  that is **licensed spectrum in India** (not ISM) and illegal to emit on without a licence.
- Confirmed-safe cabling: **direct cable** `TX1A → RX1A` (the run forces TX attenuation ≥ 60 dB) or
  **attenuator in line** `TX1A → ~30 dB SMA attenuator → RX1A`. The run refuses to transmit unless
  you pass `--direct-cable` or `--attenuator-in-line`.
- Verified-working command (direct cable):
  ```powershell
  C:\Users\csaih\radioconda\python.exe -m sentinelspread.gnuradio.runner --channel pluto --direct-cable --uri ip:192.168.2.1 --sf 64
  ```
- In the web app, the "Covert transmit & recover" tool has a **Channel** selector; the Pluto
  option is enabled only when the board is detected, and it uses the direct-cable path.

---

## 7. OPEN TASK — the slide deck (not done yet)

The project idea deck is a Canva presentation (owned by a teammate's account, 15 slides,
"Secure SDR Covert Channel: Build, Attack & Harden"). It could **not** be edited from the Linux
session (different Canva account). The user wants it updated to match the now-complete project.
Build a corrected **.pptx** (the user can import it into Canva: File → Import). Fixes needed:

1. **Slide 6 "Literature Survey" is from a different project** — its entries are Google Maps
   routing, "Attention is All You Need", travel recommendation systems, GPT travel assistants.
   Replace with real references (use slide 14's): Rabie et al. *Secure Audio Steganography using
   LSB + AES* (2021); Simon et al. *Spread Spectrum Communications Handbook*; O'Shea & Hoydis
   *Deep Learning for the Physical Layer* (2017); Proakis & Salehi *Digital Communications*.
2. **Slide 10 "Work Completed"** named files `audio_stego.py` / `live_sdr_sim.py` that don't exist
   (real: `audio_stego_engine.py` + the `sentinelspread` package). It said "AES-128-CBC" for the
   whole system — correct only for the **audio** stego layer; the DSSS pipeline/text crypto is
   **AES-256-GCM**. Fix both.
3. **"Remaining Work" (slides 8/12) is now DONE** — the "PyTorch CNN adversary + closed-loop
   hardening" it listed as future work is implemented (Stage 6). Reframe as completed results.
4. **Update "Current Results"** with the verified numbers in section 2 above (real Pluto BER 0 at
   22.3 dB symbol SNR; CNN Pd 100%→0% under FHSS; 70/70 + 32/32 + 5/5 tests; sub-noise decode at −14.9 dB SF 128).

On Windows, build it with the `pptx` skill (pptxgenjs needs Node; if Node is absent, use
`python-pptx`, which is how the Linux session was going to do it).

---

## 8. Other optional follow-ups

- The user asked earlier whether **image steganography asks for a password**: it does **not**
  (`/api/stego/embed` + `/extract` take image + text only; only *audio* stego and the crypto tools
  take a password). If they want image stego password-protected, that's a small feature to add.
- The hero chapter copy in `index.html` still says "60 passing / 5 / 5"; counts are now higher.
  Cosmetic — update if you touch that file.

---

## 9. Deploying to Vercel (context)

The web app can deploy to Vercel (`pyproject.toml` has the manifest), but **the SDR/Pluto section
cannot run there** — Vercel is serverless with no GNU Radio and no Pluto, and `.vercelignore`
keeps the DSP pipeline out. On Vercel the 20 crypto/stego/watermark tools work; the SDR section
shows "radio offline". **Demo the SDR section locally on this Windows machine**, where it works
fully. Vercel deploys from the GitHub repo's git integration on push to `main`.
