# SentinelSpread: Technical Status & Handoff Report

**Project Title:** SentinelSpread: Spread-Spectrum Covert Communication System & Detector Suite  
**Repository Path:** `D:\CLI Projects\software defined communication`  
**Current Status:** Stages 1 & 2 Fully Implemented and Empirically Validated (17/17 Pytest Suite Passing)  
**Git Base Commit:** `429a1ce`  

---

## 1. System Overview & Objective

**SentinelSpread** is a modular Software-Defined Communication (SDR) framework engineered to achieve covert, secure data transmission operating below the channel noise floor (\(SNR < 0\text{ dB}\)). The architecture couples military-grade hybrid authenticated cryptography with Direct Sequence Spread Spectrum (DSSS) modulation, backed by an evaluation suite capable of assessing probability of detection (\(P_d\)) against energy, statistical entropy, cyclostationary, and Machine Learning detectors.

```
+---------------------------------------------------------------------------------------------------------+
|                                        TRANSMIT PIPELINE (TX)                                           |
|                                                                                                         |
|  +--------------+     +---------------+     +----------------+     +--------------+     +------------+  |
|  | Payload In   | --> | Hybrid Crypto | --> | DSSS Spreading | --> | Baseband     | --> | SDR / AWGN |  |
|  | (Text/Audio) |     | (AES-GCM/RSA) |     | (PN Sequences) |     | (BPSK/QPSK)  |     | Channel    |  |
|  +--------------+     +---------------+     +----------------+     +--------------+     +------------+  |
+---------------------------------------------------------------------------------------------------------+
                                                       |
                                                       v
+---------------------------------------------------------------------------------------------------------+
|                                        RECEIVE PIPELINE (RX)                                            |
|                                                                                                         |
|  +--------------+     +---------------+     +----------------+     +--------------+     +------------+  |
|  | Recovered    | <-- | Hybrid Decrypt| <-- | DSSS Despread  | <-- | Costas/RRC   | <-- | SDR / AWGN |  |
|  | Data Output  |     | (Unwrap/Auth) |     | (Correlator)   |     | Matched Filter|    | Ingestion  |  |
|  +--------------+     +---------------+     +----------------+     +--------------+     +------------+  |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Directory Layout & Module Index

```
D:/CLI Projects/software defined communication/
├── cli.py                        # Unified command-line interface
├── config.yaml                   # Central system configuration
├── requirements.txt              # Dependency specifications
├── eval/
│   └── ber_vs_snr.png            # Waterfall BER curve simulation artifact
├── sentinelspread/               # Core library
│   ├── input/                    # Stage 1: Payload ingest, header encoding/decoding
│   │   ├── header.py             # Binary magic header ('SSPD') & payload type tagging
│   │   └── input_handler.py      # Serialization for UTF-8 text and raw WAV audio
│   ├── crypto/                   # Stage 1: Hybrid authenticated cryptography
│   │   ├── key_mgmt.py           # RSA-2048 keypair generation & PEM serialization
│   │   ├── encryptor.py          # AES-256-GCM encryption + RSA-OAEP session key wrapping
│   │   └── decryptor.py          # Session key unwrapping & AES-GCM authenticated decryption
│   ├── modem/                    # Stage 2: Baseband modulation & synchronization
│   │   ├── mapper.py             # BPSK & Gray-coded QPSK constellation mapping
│   │   ├── rrc.py                # Root-Raised Cosine (RRC) pulse shaping & matched filtering
│   │   ├── sync.py               # Costas loop carrier sync, M&M timing recovery, phase resolver
│   │   └── modem.py              # End-to-end unified baseband transceiver
│   ├── channel/                  # Stage 2: Physical/Simulated channel
│   │   └── awgn.py               # Energy-calibrated AWGN channel generator (Eb/N0 & SNR modes)
│   ├── eval/                     # Evaluation & Metrics
│   │   ├── metrics.py            # Bit Error Rate (BER) & Symbol Error Rate (SER) computation
│   │   └── plot_ber.py           # Monte Carlo simulation engine with adaptive sampling
│   ├── dsss/                     # [Stage 3] PN sequence generators & correlator
│   ├── detector/                 # [Stage 5] Statistical & ML covert detection suite
│   └── harden/                   # [Stage 6] FHSS, power control & FEC coding
└── tests/
    ├── test_input.py             # Unit tests for input handler & header integrity
    ├── test_crypto.py            # Unit tests for AES-GCM + RSA key management & tampering checks
    ├── test_stage1.py            # End-to-end pipeline tests for Stage 1
    └── test_modem.py             # Unit tests for BPSK/QPSK mapper, RRC filter, and BER progression
```

---

## 3. Implemented Modules Deep Dive

### 3.1 Stage 1: Input Handler & Header Specification (`sentinelspread/input/`)
* **Header Structure (`header.py`):** 16-byte packed binary preamble formatted as `>4sBBII`:
  * `magic`: `b"SSPD"` (4 bytes)
  * `version`: `0x01` (1 byte)
  * `payload_type`: `0x01` (`TEXT`), `0x02` (`AUDIO`) (1 byte)
  * `original_length`: Uncompressed byte length of original payload (4 bytes)
  * `reserved`: 4 bytes for alignment and future expansion flags.
* **Payload Handler (`input_handler.py`):** Encapsulates text strings/files and audio PCM WAV streams with header tagging, and generates synthetic sine-wave WAV files for testing.

### 3.2 Stage 1: Authenticated Cryptography (`sentinelspread/crypto/`)
* **Key Architecture (`key_mgmt.py`):** Generates 2048-bit RSA keypairs (`PKCS1_OAEP` with SHA-256) for asymmetric key exchange.
* **Session Cryptography (`encryptor.py` / `decryptor.py`):**
  * Generates a cryptographically secure, ephemeral 256-bit AES key per message session.
  * Encrypts the tagged payload under **AES-256-GCM**, producing authenticated ciphertext and a 128-bit integrity tag against tampering.
  * Encapsulates output into a serialized `CryptoBundle` binary stream (`key_len | nonce_len | tag_len | wrapped_key | nonce | tag | ciphertext`).

### 3.3 Stage 2: Baseband Modem & Synchronization (`sentinelspread/modem/`)
* **Constellation Mapping (`mapper.py`):**
  * **BPSK:** Bit \(0 \to -1.0\), Bit \(1 \to +1.0\) (\(E_s = 1.0\), \(k = 1\)).
  * **QPSK (Gray Coded):** Maps bit pairs \([b_0, b_1]\) to \(\frac{1}{\sqrt{2}} [(\pm 1) + j(\pm 1)]\) (\(E_s = 1.0\), \(k = 2\)).
* **Pulse Shaping (`rrc.py`):**
  * Square-Root Raised Cosine (RRC) filter with roll-off factor \(\alpha = 0.35\), \(sps = 4\) samples/symbol, and \(span = 10\) symbols (\(N = 41\) taps).
  * Filter taps are energy-normalized (\(\sum h[n]^2 = 1.0\)) to ensure unitary gain across cascaded TX and RX filters.
* **Synchronization & Carrier Recovery (`sync.py`):**
  * **Timing Recovery:** Symbol downsampler aligning at optimal eye-diagram opening.
  * **Carrier Recovery:** 2nd-order Costas Loop tracking phase error \(\phi_e = \operatorname{Im}\{z\} \cdot \operatorname{sgn}(\operatorname{Re}\{z\})\) (for BPSK) and \(\phi_e = \operatorname{Im}\{z\}\operatorname{sgn}(\operatorname{Re}\{z\}) - \operatorname{Re}\{z\}\operatorname{sgn}(\operatorname{Im}\{z\})\) (for QPSK).
  * **Phase Disambiguation:** 32-bit known preamble correlator that resolves \(90^\circ\) and \(180^\circ\) constellation rotational ambiguities.

---

## 4. Mathematical Noise Modeling & Channel Calibration

### 4.1 \(E_b/N_0\) Noise Formulation (`sentinelspread/channel/awgn.py`)
To ensure simulated BER accurately reproduces theoretical communications performance, the AWGN channel scales variance based on oversampling factor \(sps\) and bits per symbol \(k\):

$$\text{Bit Energy: } E_b = \frac{E_s}{k}$$

$$\text{Noise Spectral Density: } N_0 = \frac{E_b}{10^{(E_b/N_0)_{\text{dB}} / 10}}$$

$$\text{Per-Dimension Noise Variance: } \sigma_{\text{dim}} = \sqrt{\frac{N_0 \cdot sps}{2}}$$

$$w[n] \sim \mathcal{CN}(0, 2\sigma_{\text{dim}}^2) = \mathcal{N}(0, \sigma_{\text{dim}}^2) + j\mathcal{N}(0, \sigma_{\text{dim}}^2)$$

### 4.2 Matched Filter Processing Gain Alignment
Because the RRC filter at the receiver performs matched filtering with unit energy ($\sum h[n]^2 = 1.0$), it collapses the $sps$ noise bandwidth down by a factor of $sps$, preserving the signal-to-noise ratio:

$$\left(\frac{E_b}{N_0}\right)_{\text{RX}} = \left(\frac{E_b}{N_0}\right)_{\text{channel}}$$

This eliminates artificial offsets and aligns the simulation directly with the closed-form BPSK/QPSK theoretical error probability:

$$P_b = Q\left(\sqrt{\frac{2E_b}{N_0}}\right) = \frac{1}{2}\operatorname{erfc}\left(\sqrt{\frac{E_b}{N_0}}\right)$$

---

## 5. Empirical Verification & Simulation Results

### 5.1 Monte Carlo Simulation Data

The simulation engine in `plot_ber.py` was executed with adaptive block sampling (accumulating 50,000-bit chunks up to 1,000,000 bits until $\ge 100$ bit errors are logged):

| $E_b/N_0$ (dB) | Theoretical BER | BPSK Simulated | QPSK Simulated | Bit Errors / Sample Count | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **-3 dB** | $1.58 \times 10^{-1}$ | $1.59 \times 10^{-1}$ | $1.59 \times 10^{-1}$ | ~7,970 / 50,000 | Confirmed |
| **-2 dB** | $1.31 \times 10^{-1}$ | $1.31 \times 10^{-1}$ | $1.29 \times 10^{-1}$ | ~6,500 / 50,000 | Confirmed |
| **-1 dB** | $1.04 \times 10^{-1}$ | $1.05 \times 10^{-1}$ | $1.03 \times 10^{-1}$ | ~5,200 / 50,000 | Confirmed |
| **0 dB** | $7.86 \times 10^{-2}$ | $7.70 \times 10^{-2}$ | $7.82 \times 10^{-2}$ | ~3,900 / 50,000 | Confirmed |
| **1 dB** | $5.63 \times 10^{-2}$ | $5.57 \times 10^{-2}$ | $5.79 \times 10^{-2}$ | ~2,800 / 50,000 | Confirmed |
| **2 dB** | $3.75 \times 10^{-2}$ | $3.93 \times 10^{-2}$ | $3.71 \times 10^{-2}$ | ~1,900 / 50,000 | Confirmed |
| **3 dB** | $2.28 \times 10^{-2}$ | $2.21 \times 10^{-2}$ | $2.32 \times 10^{-2}$ | ~1,100 / 50,000 | Confirmed |
| **4 dB** | $1.25 \times 10^{-2}$ | $1.28 \times 10^{-2}$ | $1.26 \times 10^{-2}$ | ~640 / 50,000 | Confirmed |
| **5 dB** | $5.95 \times 10^{-3}$ | $5.42 \times 10^{-3}$ | $5.96 \times 10^{-3}$ | ~280 / 50,000 | Confirmed |
| **6 dB** | $2.38 \times 10^{-3}$ | $2.44 \times 10^{-3}$ | $2.50 \times 10^{-3}$ | ~125 / 50,000 | Confirmed |
| **7 dB** | $7.73 \times 10^{-4}$ | $6.00 \times 10^{-4}$ | $7.40 \times 10^{-4}$ | ~115 / 180,000 | Confirmed |
| **8 dB** | $1.91 \times 10^{-4}$ | $2.28 \times 10^{-4}$ | $2.16 \times 10^{-4}$ | ~110 / 500,000 | Confirmed |
| **9 dB** | $3.36 \times 10^{-5}$ | $3.00 \times 10^{-5}$ | $3.60 \times 10^{-5}$ | ~33 / 1,000,000 | Confirmed |
| **10 dB** | $3.87 \times 10^{-6}$ | $2.00 \times 10^{-6}$ | $4.00 \times 10^{-6}$ | ~3 / 1,000,000 | Low Conf. (Expected) |

### 5.2 BER vs $E_b/N_0$ Performance Plot

The generated plot file is stored at `eval/ber_vs_snr.png`.

---

## 6. Verification & Automated Test Status

All 17 tests passed via `pytest`:
* `tests/test_input.py` (4 passed): Verifies `Header` packing/unpacking, byte-level corruption rejection, and audio/text I/O.
* `tests/test_crypto.py` (4 passed): Verifies RSA-2048 keypair generation, AES-256-GCM encryption/decryption roundtrips, and cryptographic rejection of tampered ciphertexts.
* `tests/test_stage1.py` (2 passed): Full Stage 1 integration test (Input handler -> Crypto bundle -> Decryptor -> Output verification).
* `tests/test_modem.py` (7 passed): Verifies BPSK/QPSK mapping, RRC filter unit-energy properties, clean loopback BER = 0.0, and monotonic waterfall error reduction under AWGN.

```bash
# Command to reproduce:
python cli.py test-stage all
```

---

## 7. Next Implementation Roadmap (Stages 3 to 6)

This section provides the implementation specifications for subsequent development stages:

### Stage 3: Direct Sequence Spread Spectrum (DSSS) Core (`sentinelspread/dsss/`)
1. **PN Sequence Generators (`pn_gen.py`):**
   * Maximum-length sequences (m-sequences) generated via configurable LFSR polynomials (e.g., degree 7, 10, 15).
   * Gold code generation combining pairs of preferred m-sequences with low cross-correlation.
   * Session-derived seeding: Derive LFSR initial register state directly from the negotiated AES key hash (`SHA256(aes_key)`).
2. **Spreader & Despreader (`spreader.py`, `correlator.py`):**
   * TX: Multiply each data symbol by $L_c$ chips (Spreading Factor $SF \in \{16, 32, 64, 128\}$).
   * RX: Coherent sliding-correlator and early-late gate for chip-level synchronization and despreading.
   * Target: Processing gain $G_p = 10 \log_{10}(SF)\text{ dB}$, enabling error-free message recovery at negative SNR (e.g., $-10\text{ dB}$).

### Stage 4: Hardware SDR Interfacing (`sentinelspread/channel/sdr.py`)
1. **Adalm-Pluto SDR (TX):** Interfacing via `pyadi-iio` / `libiio` at 915 MHz ISM band.
2. **RTL-SDR (RX):** Interfacing via `pyrtlsdr` with hardware gain calibration and DC offset compensation.
3. **Loopback & Over-The-Air (OTA) Validation:** End-to-end transmission across physical RF link.

### Stage 5: Covert Detector Suite (`sentinelspread/detector/`)
1. **Radiometer / Energy Detector (`energy.py`):** Neyman-Pearson decision threshold over noise floor.
2. **Spectral Entropy Detector (`entropy.py`):** Measures spectral flatness vs. structured transmissions.
3. **Cyclostationary Feature Detector (`cyclostationary.py`):** Spectral Correlation Function (SCF) at chip and symbol rates.
4. **Machine Learning Classifier (`ml_detector.py`):** CNN/Random Forest trained on IQ spectrograms.

### Stage 6: Dynamic Hardening & Anti-Jamming (`sentinelspread/harden/`)
1. **FHSS Layer (`fhss.py`):** Pseudo-random carrier frequency hopping across 50 ISM channels.
2. **Adaptive Power Control (`power_control.py`):** Dynamically bounds transmit power below detector threshold.
3. **Forward Error Correction (`fec.py`):** Convolutional / Viterbi or Reed-Solomon coding.
