# SentinelSpread: Spread-Spectrum Covert Communication System

**SentinelSpread** is a software-defined communication system featuring Direct Sequence Spread Spectrum (DSSS) covert transmission, an independent statistical/ML detector suite, and dynamic hardening mechanisms.

Encryption hides what a message says. SentinelSpread also hides that it was sent: the payload is sealed with AES-256-GCM, spread with a pseudo-noise code and carried through a real GNU Radio flowgraph, and can be folded into ordinary images and audio. The repository holds the DSP pipeline and a web app built on it.

## Repository layout
- `sentinelspread/`: the DSP pipeline (Python package).
- `tests/`: pytest suite for the pipeline.
- `cli.py`: command line tool for stage testing and execution.
- `stego_crypto_api/`: FastAPI backend for the web app (steganography, watermarking, cryptography). It also keeps an `/api/radio` transmitter that drives the GNU Radio flowgraph; the page does not use it.
- `stego_crypto_frontend/`: the web app (Three.js scroll story plus a 20-tool workbench), served by the API.
- `steganography-and-watermarking/`: submodule with the earlier steganography and watermarking client apps.

## Pipeline modules
- `input/`: Text & audio input loading, saving, binary header type-tagging, and LSB image steganography.
- `crypto/`: AES-256 payload encryption & RSA key wrapping/exchange.
- `dsss/`: PN sequence generation, spreading, and correlator despreading.
- `modem/`: BPSK/QPSK modulation, RRC filtering, symbol timing & Costas loop carrier recovery.
- `channel/`: Simulated AWGN channel and swappable hardware SDR (Adalm Pluto / RTL-SDR) interface.
- `gnuradio/`: GNU Radio 3.10 blocks, the `sentinelspread_flowgraph.grc` transceiver, and the propagation verifier.
- `eval/`: BER benchmarking, processing gain, and PSD plot generation.
- `detector/`, `harden/`: planned (statistical/ML covert detectors; FHSS, adaptive power, FEC, session rotation).

## Status
| Stage | What it covers | State |
|---|---|---|
| 1 | Input, header tagging, AES-256-GCM + RSA-OAEP | done |
| 2 | BPSK/QPSK modem, RRC pulse shaping, AWGN, BER vs Eb/N0 | done |
| 3 | DSSS: PN generator, spreader, correlator, processing gain | done |
| 4 | GNU Radio software SDR loopback with timing and Costas recovery | done, see `STAGE4_VERIFICATION_REPORT.md` and `VERIFY_GNURADIO_PROPAGATION_RESULTS.md` |
| 5 | Detectors and hardening | planned |

Measured limit of the current receiver: it locks symbol timing and carrier phase on the raw chips before despreading, so it decodes cleanly up to a channel noise of σ ≈ 0.3 and fails by σ 0.4 at any spreading factor (checked at SF 16 and SF 64).

## Running the pipeline
```bash
pip install -r requirements.txt
python cli.py test-stage all          # run every stage's tests
python cli.py plot-ber                # BER vs SNR -> eval/ber_vs_snr.png
python cli.py plot-psd                # PSD flattening -> eval/psd_flattening.png
python cli.py benchmark-gain          # processing gain across spreading factors
```

GNU Radio parts need a Python with GNU Radio 3.10, for example [radioconda](https://github.com/ryanvolz/radioconda). `sdr-loopback` launches it from `C:\Users\csaih\radioconda\python.exe`; the verifier is run with it directly:
```bash
python cli.py sdr-loopback
<radioconda>/python -m sentinelspread.gnuradio.verify_gnuradio_propagation
```
`tests/test_gnuradio.py` skips its GNU Radio checks when GNU Radio is not installed. `MANUAL_TESTING_GUIDE.md` walks through testing by hand.

### Real RF on an ADALM-Pluto
The runner has a channel switch. `--channel sim` (the default) is the software channel model above. `--channel pluto` sends the same DSP chain through an ADALM-Pluto, TX1A cabled to RX1A. Only the channel changes: the Pluto sink and source take the channel model's place, and the RX side adds a DC blocker and an AGC.

Never fit antennas for this. The Pluto transmits at about +7 dBm at 0 dB attenuation, which is more than its receiver input can take. Use one of two cablings, and confirm it on the command line or the run refuses to transmit:
- `--attenuator-in-line`: TX1A → ~30 dB SMA attenuator → RX1A. Defaults: TX attenuation 20 dB, RX gain 40 dB.
- `--direct-cable`: a bare SMA male-to-male cable. The Pluto's own TX attenuator is the only protection. The run sets it to maximum before starting and after finishing, and refuses anything below 60 dB. Defaults: TX attenuation 70 dB, RX gain 50 dB.
```bash
<radioconda>/python -m sentinelspread.gnuradio.runner --channel pluto --direct-cable
```
It runs at 915 MHz and 2 MS/s (500 kchip/s, 4 samples per chip). With no `--uri` it uses the first Pluto that a USB scan finds. The run logs the device serial, RX power in dBFS, the DC offset before and after the DC blocker, and the carrier offset the Costas loop corrected. With no board attached, it stops before building the flowgraph with `ADALM-Pluto not detected at <uri>`.

## Running the web app
```bash
pip install -r stego_crypto_api/requirements.txt
python -m uvicorn main:app --app-dir stego_crypto_api --port 8001
```
Then open http://localhost:8001. The API serves the frontend from `stego_crypto_frontend/`.

The page needs no GNU Radio: its 20 tools cover steganography, watermarking, encryption and measurement. Images, audio and keys are processed per request and not stored. Chapter 02 shows readings recorded in the Stage 4 GNU Radio verification run.

The backend still has `/api/radio` (transmit, receive, WAV, status) for running the flowgraph locally. `POST /api/radio/transmit` accepts `"channel": "pluto"` with `direct_cable` or `attenuator_in_line`, and optionally `pluto_uri`, `pluto_freq_hz`, `tx_atten_db` and `rx_gain_db`. A Pluto run transmits and decodes in one call. `GET /api/radio/status` reports whether a Pluto is attached. GNU Radio runs in a separate process, controlled by two environment variables:
- `SENTINEL_RADIO_PYTHON`: the Python with GNU Radio (default `C:\Users\csaih\radioconda\python.exe`).
- `SENTINEL_PROJECT_ROOT`: where the `sentinelspread` package lives (default: this repository).

## Tests
```bash
python -m pytest tests              # pipeline: 36 tests
python -m pytest stego_crypto_api   # web API: 30 tests
```
