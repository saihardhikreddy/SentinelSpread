# SentinelSpread: Spread-Spectrum Covert Communication System

**SentinelSpread** is a software-defined communication system featuring Direct Sequence Spread Spectrum (DSSS) covert transmission, an independent statistical/ML detector suite, and dynamic hardening mechanisms.

## Project Structure
- `input/`: Text & audio input loading, saving, and binary header type-tagging.
- `crypto/`: AES-256 payload encryption & RSA key wrapping/exchange.
- `dsss/`: PN sequence generation, spreading, and correlator despreading.
- `modem/`: BPSK/QPSK modulation, RRC filtering, symbol timing & Costas loop carrier recovery.
- `channel/`: Simulated AWGN channel and swappable hardware SDR (Adalm Pluto / RTL-SDR) interface.
- `detector/`: Statistical (entropy, cyclostationary) and Machine Learning covert detectors.
- `harden/`: Frequency Hopping (FHSS), adaptive power control, FEC, and session rotation.
- `eval/`: BER benchmarking, detection metrics, and PSD plot generation.
- `cli.py`: Command line tool for stage testing and execution.

## Stage 1: Input & Crypto Stage
Testing stage 1 functionality:
```bash
python cli.py test-stage crypto
```
