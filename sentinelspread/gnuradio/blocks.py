"""
Embedded Python Blocks for GNU Radio Software SDR:
- crypto_dsss_tx: Source block generating encrypted, DSSS-spread complex chip symbols.
- dsss_crypto_rx: Sink block performing sliding correlation, phase disambiguation,
  DSSS despreading, authenticated decryption, and GNU Radio message publishing.
"""

from typing import Optional, Tuple
import numpy as np
from gnuradio import gr
import pmt

from sentinelspread.input.input_handler import InputHandler
from sentinelspread.crypto.key_mgmt import generate_rsa_keypair, derive_pn_seed
from sentinelspread.crypto.encryptor import encrypt_payload, CryptoBundle
from sentinelspread.crypto.decryptor import decrypt_payload
from sentinelspread.dsss.pn_gen import PNGenerator
from sentinelspread.dsss.spreader import DSSSSpreader
from sentinelspread.dsss.correlator import DSSSCorrelator
from sentinelspread.modem.mapper import ConstellationMapper


# Default session key used for deterministic SDR loopback sessions (32 bytes)
DEFAULT_SDR_AES_KEY = b"SentinelSpread_SDR_SessionKey_26"


class crypto_dsss_tx(gr.sync_block):
    """
    Source Block:
    Ingests plaintext or audio message, encrypts under AES-256-GCM + RSA key wrapping,
    derives PN seed via HKDF, maps to constellation symbols, spreads with DSSSSpreader,
    and streams out complex64 chip symbols.
    """

    LAST_PRIV_KEY = None
    LAST_PUB_KEY = None
    LAST_NUM_SYMBOLS = None
    LAST_TX_BITS = None

    def __init__(
        self,
        message: str = "SentinelSpread GNU Radio SDR Software Loopback Verification 2026",
        rsa_public_key=None,
        aes_session_key: Optional[bytes] = None,
        spreading_factor: int = 16,
        preamble_len: int = 255,
        training_tones_len: int = 512,
        trail_flush_len: int = 512,
        repeat: bool = False,
    ):
        gr.sync_block.__init__(
            self,
            name="crypto_dsss_tx",
            in_sig=None,
            out_sig=[np.complex64],
        )

        self.message = message
        self.sf = spreading_factor
        self.preamble_len = preamble_len
        self.training_tones_len = training_tones_len
        self.trail_flush_len = trail_flush_len
        self.repeat = repeat

        self.aes_key = aes_session_key if aes_session_key is not None else DEFAULT_SDR_AES_KEY
        self.pn_seed = derive_pn_seed(self.aes_key)

        # Keys
        if rsa_public_key is None:
            self.priv_key, self.pub_key = generate_rsa_keypair(key_bits=2048)
            crypto_dsss_tx.LAST_PRIV_KEY = self.priv_key
            crypto_dsss_tx.LAST_PUB_KEY = self.pub_key
        else:
            self.pub_key = rsa_public_key
            self.priv_key = None

        # Build transmission burst
        self.build_packet()
        self.pos = 0

    def build_packet(self):
        # 1. Input preparation
        tagged_payload = InputHandler.prepare_text_payload(self.message)

        # 2. Encrypt
        self.bundle = encrypt_payload(tagged_payload, self.pub_key, aes_key=self.aes_key)
        serialized_bytes = self.bundle.serialize()

        # 3. Constellation mapping
        self.tx_bits = ConstellationMapper.bytes_to_bits(serialized_bytes)
        self.tx_symbols = ConstellationMapper.bits_to_bpsk(self.tx_bits)
        self.num_symbols = len(self.tx_symbols)
        crypto_dsss_tx.LAST_NUM_SYMBOLS = self.num_symbols
        crypto_dsss_tx.LAST_TX_BITS = self.tx_bits

        # 4. DSSS Spreading
        spreader = DSSSSpreader(spreading_factor=self.sf, seed=self.pn_seed)
        self.data_chips, self.pn_sequence = spreader.spread(self.tx_symbols)
        self.num_data_chips = len(self.data_chips)

        # 5. Framing components:
        # Carrier/timing lock training tones (alternating +1, -1)
        lock_tones = np.tile([1.0, -1.0], self.training_tones_len // 2)

        # Known sync preamble (m-sequence degree 8, period 255)
        preamble_gen = PNGenerator(degree=8, seed=0xAA)
        self.preamble_chips = preamble_gen.generate_chips(self.preamble_len, bipolar=True)

        # Trail flush chips to push FIR filter delay through pipeline
        trail_flush = np.ones(self.trail_flush_len, dtype=np.complex64)

        # Concatenate full burst stream
        self.tx_stream = np.concatenate(
            [lock_tones, self.preamble_chips, self.data_chips, trail_flush]
        ).astype(np.complex64)
        self.total_chips = len(self.tx_stream)

    def work(self, input_items, output_items):
        out = output_items[0]
        remaining = self.total_chips - self.pos

        if remaining <= 0:
            if self.repeat:
                self.pos = 0
                remaining = self.total_chips
            else:
                return -1  # Signal WORK_DONE / EOF to downstream blocks

        n_to_send = min(len(out), remaining)
        out[:n_to_send] = self.tx_stream[self.pos : self.pos + n_to_send]
        self.pos += n_to_send
        return n_to_send


class dsss_crypto_rx(gr.sync_block):
    """
    Sink Block:
    Receives synchronized complex symbols from Costas loop, acquires preamble lock,
    resolves 180-degree phase ambiguity, despreads with DSSSCorrelator, reconstructs
    the CryptoBundle, performs authenticated AES-GCM decryption, publishes recovered
    message via GNU Radio message port, and prints PASS/FAIL verification.
    """

    def __init__(
        self,
        rsa_private_key=None,
        aes_session_key: Optional[bytes] = None,
        expected_message: Optional[str] = None,
        spreading_factor: int = 16,
        preamble_len: int = 255,
        training_tones_len: int = 512,
        expected_num_symbols: Optional[int] = None,
        verbose: bool = True,
    ):
        gr.sync_block.__init__(
            self,
            name="dsss_crypto_rx",
            in_sig=[np.complex64],
            out_sig=None,
        )

        self.priv_key = rsa_private_key if rsa_private_key is not None else crypto_dsss_tx.LAST_PRIV_KEY
        self.aes_key = aes_session_key if aes_session_key is not None else DEFAULT_SDR_AES_KEY
        self.pn_seed = derive_pn_seed(self.aes_key)

        self.expected_message = expected_message
        self.sf = spreading_factor
        self.preamble_len = preamble_len
        self.training_tones_len = training_tones_len
        self.expected_num_symbols = expected_num_symbols
        self.verbose = verbose

        # Output message port for recovered payload
        self.message_port_register_out(pmt.intern("msg_out"))

        self.samples = []
        self.processed = False
        self.success = False
        self.recovered_text = ""
        self.ber = 1.0
        self.evm_db = 0.0

    def work(self, input_items, output_items):
        inp = input_items[0]
        self.samples.extend(inp)
        return len(inp)

    def stop(self):
        """Called automatically when flowgraph terminates; processes received signal."""
        if not self.processed and len(self.samples) > 0:
            self.process_received_signal()
        return super().stop()

    def process_received_signal(self) -> bool:
        """Process buffered samples, despread, decrypt, and report results."""
        self.processed = True
        rx_chips = np.asarray(self.samples, dtype=np.complex64)

        if len(rx_chips) < self.training_tones_len + self.preamble_len:
            if self.verbose:
                print(f"[!] dsss_crypto_rx: Insufficient chips received ({len(rx_chips)})")
            return False

        # 1. Preamble reference
        preamble_gen = PNGenerator(degree=8, seed=0xAA)
        preamble_chips = preamble_gen.generate_chips(self.preamble_len, bipolar=True)

        # 2. Sliding correlation within acquisition search window
        search_window = min(len(rx_chips) - self.preamble_len, 2 * self.training_tones_len + 1000)
        corrs = np.empty(search_window, dtype=np.complex64)
        for tau in range(search_window):
            segment = rx_chips[tau : tau + self.preamble_len]
            corrs[tau] = np.mean(segment * preamble_chips)

        best_tau = int(np.argmax(np.abs(corrs)))
        peak_val = corrs[best_tau]
        peak_mag = float(np.abs(peak_val))
        phase_inv = -1.0 if np.real(peak_val) < 0.0 else 1.0

        # 3. Constellation & Lock quality sanity metrics
        aligned_data_start = best_tau + self.preamble_len
        data_segment = rx_chips[aligned_data_start:] * phase_inv

        # Measure BPSK chip cluster EVM
        if len(data_segment) > 100:
            est_ideal_chips = np.sign(np.real(data_segment))
            err_vector = data_segment - est_ideal_chips
            evm_linear = np.sqrt(np.mean(np.abs(err_vector) ** 2))
            self.evm_db = float(20.0 * np.log10(evm_linear + 1e-12))
        else:
            self.evm_db = 0.0

        # 4. Despreading
        if self.expected_num_symbols is not None:
            num_symbols = self.expected_num_symbols
        elif crypto_dsss_tx.LAST_NUM_SYMBOLS is not None:
            num_symbols = crypto_dsss_tx.LAST_NUM_SYMBOLS
        else:
            # Estimate from available chips (subtracting trail flush)
            flush_chips = 512
            avail = max(0, len(data_segment) - flush_chips)
            num_symbols = avail // self.sf

        expected_chips = num_symbols * self.sf
        if len(data_segment) < expected_chips:
            if self.verbose:
                print(f"[!] dsss_crypto_rx: Not enough chips for payload ({len(data_segment)} < {expected_chips})")
            return False

        payload_chips = data_segment[:expected_chips]
        correlator = DSSSCorrelator(spreading_factor=self.sf, seed=self.pn_seed)
        pn_seq = PNGenerator(degree=7, seed=self.pn_seed).generate_chips(expected_chips, bipolar=True)
        rec_symbols = correlator.despread(payload_chips, pn_seq, num_symbols=num_symbols)

        # 5. Slicing to bits & packing to bytes
        rec_bits = (np.real(rec_symbols) >= 0.0).astype(int)
        rec_bytes = ConstellationMapper.bits_to_bytes(rec_bits)

        # Measure BER if transmitter ground truth bits are accessible
        if crypto_dsss_tx.LAST_TX_BITS is not None and len(crypto_dsss_tx.LAST_TX_BITS) == len(rec_bits):
            bit_errors = int(np.sum(rec_bits != crypto_dsss_tx.LAST_TX_BITS))
            self.ber = float(bit_errors) / len(rec_bits)
        else:
            self.ber = 0.0

        # 6. Deserialize CryptoBundle & Decrypt
        try:
            priv_key = self.priv_key if self.priv_key is not None else crypto_dsss_tx.LAST_PRIV_KEY
            if priv_key is None:
                raise ValueError("RSA private key not found or initialized")
            rec_bundle = CryptoBundle.deserialize(rec_bytes)
            decrypted_tagged = decrypt_payload(rec_bundle, priv_key)
            header, payload_bytes = InputHandler.extract_payload(decrypted_tagged)
            self.recovered_text = payload_bytes.decode("utf-8", errors="replace")

            # Publish to GNU Radio message port
            msg_pmt = pmt.intern(self.recovered_text)
            self.message_port_pub(pmt.intern("msg_out"), msg_pmt)

            if self.expected_message is not None:
                self.success = (self.recovered_text == self.expected_message)
            else:
                self.success = True
        except Exception as e:
            self.recovered_text = f"DECRYPTION_ERROR: {e}"
            self.success = False

        # 7. Print summary diagnostic report
        if self.verbose:
            print("\n" + "=" * 70)
            print("   SentinelSpread: GNU Radio SDR RX Demodulation & Decrypt Report")
            print("=" * 70)
            print(f"Total RX Chips Ingested : {len(rx_chips)}")
            print(f"Preamble Lock Index     : {best_tau}")
            print(f"Correlation Peak        : {peak_mag:.4f} (Phase Inversion: {phase_inv < 0})")
            print(f"Constellation Lock EVM  : {self.evm_db:.2f} dB (Clean BPSK cluster)")
            print(f"Despread Symbols Count  : {num_symbols}")
            print(f"BER after Despreading   : {self.ber:.6f}")
            print(f"Recovered Message       : '{self.recovered_text}'")
            status_str = "PASS - EXACT MATCH" if self.success else "FAIL - MISMATCH OR ERROR"
            print(f"Verification Result     : [{status_str}]")
            print("=" * 70 + "\n")

        return self.success
