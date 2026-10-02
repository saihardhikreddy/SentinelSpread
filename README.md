# SentinelSpread: Spread-Spectrum Covert Communication System

**SentinelSpread** is a software-defined communication system featuring Direct Sequence Spread Spectrum (DSSS) covert transmission, an independent statistical/ML detector suite, and dynamic hardening mechanisms.

Encryption hides what a message says. SentinelSpread also hides that it was sent: the payload is sealed with AES-256-GCM, spread with a pseudo-noise code and carried through a real GNU Radio flowgraph, and can be folded into ordinary images and audio. The repository holds the DSP pipeline and a web app that runs all of it.

## Repository layout
- `sentinelspread/`: the DSP pipeline (Python package).
- `tests/`: pytest suite for the pipeline.
- `cli.py`: command line tool for stage testing and execution.
- `stego_crypto_api/`: FastAPI backend for the web app (steganography, watermarking, cryptography, and the `/api/radio` transmitter that drives the GNU Radio flowgraph).
- `stego_crypto_frontend/`: the web app (Three.js scroll story plus a 21-tool workbench), served by the API.
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

## Running the web app
```bash
pip install -r stego_crypto_api/requirements.txt
python -m uvicorn main:app --app-dir stego_crypto_api --port 8001
```
Then open http://localhost:8001. The API serves the frontend from `stego_crypto_frontend/`.

The Transmit tool and the live check in chapter 02 run the GNU Radio flowgraph in a separate process. Two environment variables control it:
- `SENTINEL_RADIO_PYTHON`: the Python with GNU Radio (default `C:\Users\csaih\radioconda\python.exe`).
- `SENTINEL_PROJECT_ROOT`: where the `sentinelspread` package lives (default: this repository).

Without GNU Radio the site still works: Transmit reports that the radio is unavailable, and the other 20 tools are unaffected. Images, audio and keys are processed per request and not stored; radio transmissions are kept in the system temp folder for an hour.

## Tests
```bash
python -m pytest tests              # pipeline: 35 tests
python -m pytest stego_crypto_api   # web API: 25 tests
```
