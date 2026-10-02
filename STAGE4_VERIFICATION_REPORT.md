# Stage 4: GNU Radio Software SDR — Implementation & Verification Report

**SentinelSpread: Covert Spread-Spectrum Communication Suite**  
*Stage 4 Verification: Software-Defined Radio (SDR) Loopback via GNU Radio 3.10*

---

## 1. Executive Summary

Stage 4 transitions SentinelSpread from pure-Python simulation into an industrial Software-Defined Radio (SDR) framework using **GNU Radio 3.10.12.0** (installed via `radioconda` at `C:\Users\csaih\radioconda\python.exe`). 

In accordance with `STAGE4_GNURADIO_INSTRUCTIONS.md`, physical hardware interfaces (e.g. Adalm Pluto / RTL-SDR) were superseded by a **high-fidelity software loopback flowgraph**. The architecture combines:
- Custom **Embedded Python Blocks** wrapping SentinelSpread's verified cryptographic and DSSS spreading/despreading layers at the message frame level.
- High-rate C++ DSP blocks from GNU Radio for root-raised-cosine (RRC) pulse shaping, channel impairment modeling (AWGN + carrier frequency offset), symbol timing synchronization, and carrier recovery.

All acceptance criteria have been achieved:
- Zero crashes or hangs during execution.
- $100\%$ bit-exact message recovery with authenticated AES-256-GCM verification.
- Constellation EVM of $\approx -32.8\text{ dB}$ and post-despreading $\text{BER} = 0.000000$.
- Complete regression safety: all $32/32$ tests pass across Stages 1 through 4.

---

## 2. Architecture & Signal Pipeline

### 2.1 Block Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                 SentinelSpread SDR Flowgraph                                      |
|                                                                                                   |
|  +--------------------+         +--------------------+         +-------------------------------+  |
|  |  crypto_dsss_tx    |         |  blocks_throttle   |         | interp_fir_filter_ccf         |  |
|  | (Embedded Source)  | ------> |    (samp_rate)     | ------> |           (TX RRC)            |  |
|  +--------------------+         +--------------------+         +-------------------------------+  |
|                                                                                |                  |
|                                                                                v                  |
|  +--------------------+         +--------------------+         +-------------------------------+  |
|  |  digital_costas_   |         | digital_symbol_    |         |    channels_channel_model     |  |
|  |  loop_cc (Order 2) | <------ | sync_cc (M&M TED)  | <------ | (AWGN + Carrier Freq Offset)  |  |
|  +--------------------+         +--------------------+         +-------------------------------+  |
|           |                                                                    ^                  |
|           v                                                                    |                  |
|  +--------------------+                                                +----------------+         |
|  |  dsss_crypto_rx    |                                                | fir_filter_ccf |         |
|  |  (Embedded Sink)   |                                                |    (RX RRC)    |         |
|  +--------------------+                                                +----------------+         |
|           |                                                                                       |
|           +---> Publishes to PMT message port: 'msg_out'                                          |
|           +---> Verifies bit-exact payload match: [PASS - EXACT MATCH]                            |
+---------------------------------------------------------------------------------------------------+
```

### 2.2 System Components

| Component / Block | Implementation Type | Description & Parameters |
| :--- | :--- | :--- |
| **`crypto_dsss_tx`** | Embedded Python Source | Generates encrypted payload (AES-256-GCM + RSA key wrapping), derives PN seed via HKDF-SHA256, maps bits to BPSK symbols, spreads using `DSSSSpreader` ($SF=16$), appends M-sequence preamble ($N=255$) and lock training tones, and streams `complex64` chips. Signals EOF by returning `-1`. |
| **`blocks.throttle`** | GNU Radio C++ Core | Regulates flowgraph sample processing rate ($f_s = 200\text{ kSps}$). |
| **TX RRC Filter** | `filter.interp_fir_filter_ccf` | Interpolation factor $sps = 4$, excess bandwidth $\alpha = 0.35$, $N_{\text{taps}} = 41$. |
| **Channel Model** | `channels.channel_model` | Applies additive Gaussian noise ($\sigma_n = 0.02$) and carrier frequency offset ($\Delta f / f_s = 0.0005$). |
| **RX RRC Filter** | `filter.fir_filter_ccf` | Decimation factor $1$, matched RRC filter taps matching transmitter. |
| **Symbol Sync** | `digital.symbol_sync_cc` | Mueller & Müller timing error detector (TED), damping factor $1.0$, loop bandwidth $0.045$, MMSE 8-tap interpolator. |
| **Carrier Recovery** | `digital.costas_loop_cc` | 2nd-order Costas loop for BPSK tracking ($w = 0.0628\text{ rad/sample}$). |
| **`dsss_crypto_rx`** | Embedded Python Sink | Performs sliding correlation to acquire preamble index, corrects Costas $180^\circ$ phase ambiguity, measures constellation EVM, despreads via `DSSSCorrelator`, reconstructs `CryptoBundle`, performs authenticated decryption, calculates BER, and publishes recovered plaintext to PMT message port `msg_out`. |

---

## 3. Actual Terminal Execution Outputs

### A. Standalone GRC Generated Script (`sentinelspread_flowgraph.py`)

```powershell
PS C:\Users\csaih\sentinelspread> $env:PYTHONPATH = "C:\Users\csaih\sentinelspread;C:\Users\csaih\sentinelspread\sentinelspread\gnuradio"; & "C:\Users\csaih\radioconda\python.exe" sentinelspread/gnuradio/sentinelspread_flowgraph.py

======================================================================
   SentinelSpread: GNU Radio SDR RX Demodulation & Decrypt Report
======================================================================
Total RX Chips Ingested : 48632
Preamble Lock Index     : 521
Correlation Peak        : 0.8115 (Phase Inversion: False)
Constellation Lock EVM  : -32.85 dB (Clean BPSK cluster)
Despread Symbols Count  : 2960
BER after Despreading   : 0.000000
Recovered Message       : 'SentinelSpread GNU Radio SDR Software Loopback Verification 2026'
Verification Result     : [PASS - EXACT MATCH]
======================================================================
```

### B. CLI Software SDR Loopback Tool (`cli.py sdr-loopback`)

```powershell
PS C:\Users\csaih\sentinelspread> python cli.py sdr-loopback --message "Testing SentinelSpread SDR Loopback Clean" --sf 16

======================================================================
   SentinelSpread: GNU Radio SDR RX Demodulation & Decrypt Report
======================================================================
Total RX Chips Ingested : 45688
Preamble Lock Index     : 521
Correlation Peak        : 0.8115 (Phase Inversion: False)
Constellation Lock EVM  : -32.83 dB (Clean BPSK cluster)
Despread Symbols Count  : 2776
BER after Despreading   : 0.000000
Recovered Message       : 'Testing SentinelSpread SDR Loopback Clean'
Verification Result     : [PASS - EXACT MATCH]
======================================================================
```

### C. GRC Flowgraph Compiler (`grcc`)

```powershell
PS C:\Users\csaih\sentinelspread> $env:PYTHONPATH = "C:\Users\csaih\sentinelspread"; & "C:\Users\csaih\radioconda\Scripts\grcc.exe" --output sentinelspread/gnuradio sentinelspread/gnuradio/sentinelspread_flowgraph.grc
<<< Welcome to GNU Radio Companion Compiler 3.10.12.0 >>>

Block paths:
	C:\Users\csaih\AppData\Roaming\.local\state\gnuradio
	C:\Users\csaih\radioconda\Library\share\gnuradio\grc\blocks

>>> Loading: C:\Users\csaih\sentinelspread\sentinelspread\gnuradio\sentinelspread_flowgraph.grc
>>> Generating: C:\Users\csaih\sentinelspread\sentinelspread\gnuradio\sentinelspread_flowgraph.py
>>> Warning: The block 'blocks_throttle_0' is deprecated.
```

### D. Stage 4 Test Suite (`cli.py test-stage 4`)

```powershell
PS C:\Users\csaih\sentinelspread> python cli.py test-stage 4

==========================================
   SentinelSpread: Testing Stage '4'
==========================================

============================= test session starts =============================
platform win32 -- Python 3.13.0rc3, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\csaih\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\csaih\sentinelspread
plugins: anyio-4.12.1
collecting ... collected 4 items

tests/test_gnuradio.py::test_grc_compilation PASSED                      [ 25%]
tests/test_gnuradio.py::test_gnuradio_transceiver_loopback PASSED        [ 50%]
tests/test_gnuradio.py::test_gnuradio_with_frequency_offset PASSED       [ 75%]
tests/test_gnuradio.py::test_gnuradio_different_spreading_factor PASSED  [100%]

============================== 4 passed in 9.05s ==============================
```

### E. Full Test Suite Across All Stages (`cli.py test-stage all`)

```powershell
PS C:\Users\csaih\sentinelspread> python cli.py test-stage all

==========================================
   SentinelSpread: Testing Stage 'all'
==========================================

============================= test session starts =============================
platform win32 -- Python 3.13.0rc3, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\csaih\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\csaih\sentinelspread
plugins: anyio-4.12.1
collecting ... collected 32 items

tests/test_crypto.py::test_rsa_key_generation_and_export_import PASSED   [  3%]
tests/test_crypto.py::test_aes_rsa_encryption_decryption_roundtrip PASSED [  6%]
tests/test_crypto.py::test_crypto_bundle_serialization PASSED            [  9%]
tests/test_crypto.py::test_tamper_detection PASSED                       [ 12%]
tests/test_crypto.py::test_derive_pn_seed PASSED                         [ 15%]
tests/test_dsss.py::test_pn_generator_degree7_and_10_properties PASSED   [ 18%]
tests/test_dsss.py::test_pn_generator_seed_derivation_from_aes_key PASSED [ 21%]
tests/test_dsss.py::test_dsss_spreader_dimensions_and_gain[16] PASSED    [ 25%]
tests/test_dsss.py::test_dsss_spreader_dimensions_and_gain[32] PASSED    [ 28%]
tests/test_dsss.py::test_dsss_spreader_dimensions_and_gain[64] PASSED    [ 31%]
tests/test_dsss.py::test_dsss_spreader_dimensions_and_gain[128] PASSED   [ 34%]
tests/test_dsss.py::test_sliding_correlator_acquisition_and_early_late PASSED [ 37%]
tests/test_dsss.py::test_processing_gain_empirical_vs_theoretical PASSED [ 40%]
tests/test_dsss.py::test_dsss_negative_snr_decode_success_vs_unspread_control PASSED [ 43%]
tests/test_dsss.py::test_end_to_end_crypto_dsss_pipeline PASSED          [ 46%]
tests/test_gnuradio.py::test_grc_compilation PASSED                      [ 50%]
tests/test_gnuradio.py::test_gnuradio_transceiver_loopback PASSED        [ 53%]
tests/test_gnuradio.py::test_gnuradio_with_frequency_offset PASSED       [ 56%]
tests/test_gnuradio.py::test_gnuradio_different_spreading_factor PASSED  [ 59%]
tests/test_input.py::test_header_pack_unpack PASSED                      [ 62%]
tests/test_input.py::test_header_invalid_magic PASSED                    [ 65%]
tests/test_input.py::test_text_input_preparation PASSED                  [ 68%]
tests/test_input.py::test_audio_input_preparation PASSED                 [ 71%]
tests/test_modem.py::test_constellation_mapper_bpsk PASSED               [ 75%]
tests/test_modem.py::test_constellation_mapper_qpsk_gray PASSED          [ 78%]
tests/test_modem.py::test_rrc_filter_taps PASSED                         [ 81%]
tests/test_modem.py::test_modem_clean_loopback[BPSK] PASSED              [ 84%]
tests/test_modem.py::test_modem_clean_loopback[QPSK] PASSED              [ 87%]
tests/test_modem.py::test_modem_ber_vs_snr_progression[BPSK] PASSED      [ 90%]
tests/test_modem.py::test_modem_ber_vs_snr_progression[QPSK] PASSED      [ 93%]
tests/test_stage1.py::test_stage1_text_roundtrip PASSED                  [ 96%]
tests/test_stage1.py::test_stage1_audio_roundtrip PASSED                 [100%]

============================= 32 passed in 12.60s =============================
```

---

## 4. Acceptance Verification Checklist

| Criterion | Requirement | Verification Result | Status |
| :--- | :--- | :--- | :---: |
| **1. Autonomous Execution** | Flowgraph runs to completion without hanging or crashing (`python sentinelspread_flowgraph.py`). | `crypto_dsss_tx` signals EOF (`-1`); top block terminates cleanly with exit code `0`. | **PASS** |
| **2. End-to-End Recovery** | Bit-exact recovery of plaintext message with authenticated AES-GCM tag verification. | `Recovered Message: '...'` matches input byte-for-byte; MAC check passes. | **PASS** |
| **3. Constellation & BER** | Constellation cluster lock quality and symbol/bit error rate logging. | Constellation EVM: **$-32.85\text{ dB}$**, Post-Despreading BER: **$0.000000$**. | **PASS** |
| **4. Real Console Output** | Pasting actual, unsimulated terminal execution records. | All execution records captured and documented verbatim. | **PASS** |
| **5. Regression Safety** | Pure-Python stages 1–3 must remain untouched and fully operational. | All 28 pure-Python unit tests continue to pass; total suite passes **$32/32$** ($100\%$). | **PASS** |

---

## 5. File Inventory for Stage 4

- [`sentinelspread/gnuradio/blocks.py`](file:///C:/Users/csaih/sentinelspread/sentinelspread/gnuradio/blocks.py) — Embedded Python source and sink blocks.
- [`sentinelspread/gnuradio/runner.py`](file:///C:/Users/csaih/sentinelspread/sentinelspread/gnuradio/runner.py) — Python transceiver execution harness.
- [`sentinelspread/gnuradio/sentinelspread_flowgraph.grc`](file:///C:/Users/csaih/sentinelspread/sentinelspread/gnuradio/sentinelspread_flowgraph.grc) — GNU Radio Companion diagram definition.
- [`sentinelspread/gnuradio/sentinelspread_flowgraph.py`](file:///C:/Users/csaih/sentinelspread/sentinelspread/gnuradio/sentinelspread_flowgraph.py) — Generated flowgraph script with autonomous execution.
- [`tests/test_gnuradio.py`](file:///C:/Users/csaih/sentinelspread/tests/test_gnuradio.py) — Stage 4 automated test suite.
- [`cli.py`](file:///C:/Users/csaih/sentinelspread/cli.py) — Single entry point CLI updated with `sdr-loopback` and `test-stage 4`.
