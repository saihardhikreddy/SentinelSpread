"""
SentinelSpread Command Line Interface (CLI)
Provides single entry-point for testing stages, running simulations, and executing pipeline commands.
"""

import argparse
from pathlib import Path
import sys
import pytest

from sentinelspread.input.input_handler import InputHandler
from sentinelspread.crypto.key_mgmt import generate_rsa_keypair, export_key, import_key
from sentinelspread.crypto.encryptor import encrypt_payload, CryptoBundle
from sentinelspread.crypto.decryptor import decrypt_payload
from sentinelspread.eval.plot_ber import run_ber_simulation
from sentinelspread.eval.processing_gain import run_processing_gain_benchmark
from sentinelspread.eval.plot_psd import compute_and_plot_psd


def run_stage_tests(stage_name: str) -> int:
    """Run pytest suite targeted at a specific project stage."""
    print(f"\n==========================================")
    print(f"   SentinelSpread: Testing Stage '{stage_name}'")
    print(f"==========================================\n")

    stage_lower = stage_name.lower()
    if stage_lower in ("crypto", "input", "stage1", "1"):
        test_args = [
            "-v",
            "tests/test_input.py",
            "tests/test_crypto.py",
            "tests/test_stage1.py",
        ]
    elif stage_lower in ("modem", "stage2", "2"):
        test_args = [
            "-v",
            "tests/test_modem.py",
        ]
    elif stage_lower in ("dsss", "stage3", "3"):
        test_args = [
            "-v",
            "tests/test_dsss.py",
        ]
    elif stage_lower in ("gnuradio", "stage4", "4", "sdr"):
        test_args = [
            "-v",
            "tests/test_gnuradio.py",
        ]
    elif stage_lower in ("all", "full"):
        test_args = [
            "-v",
            "tests/",
        ]
    else:
        print(f"[!] Unknown stage '{stage_name}'. Available: 'stage1', 'stage2', 'stage3', 'stage4', 'all'")
        return 1

    return pytest.main(test_args)


def handle_encrypt(args):
    """CLI handler for encrypting input payloads."""
    input_path = Path(args.input)
    
    # Generate temporary or specified RSA keypair
    if args.key and Path(args.key).is_file():
        pub_key = import_key(args.key)
        print(f"[*] Loaded public key from {args.key}")
    else:
        print("[*] Generating transient 2048-bit RSA keypair...")
        priv_key, pub_key = generate_rsa_keypair(key_bits=2048)
        if args.save_keys:
            export_key(priv_key, "keys/private_key.pem")
            export_key(pub_key, "keys/public_key.pem")
            print("[+] Saved RSA keys to keys/private_key.pem and keys/public_key.pem")

    if args.type == "audio" or (input_path.is_file() and input_path.suffix.lower() in (".wav", ".wave")):
        print(f"[*] Processing audio payload: {input_path}")
        tagged_data = InputHandler.prepare_audio_payload(input_path)
    else:
        if input_path.is_file():
            print(f"[*] Processing text file payload: {input_path}")
            tagged_data = InputHandler.prepare_text_payload(input_path)
        else:
            print(f"[*] Processing inline text string payload")
            tagged_data = InputHandler.prepare_text_payload(args.input)

    print(f"[*] Header attached. Total payload size before crypto: {len(tagged_data)} bytes")
    bundle = encrypt_payload(tagged_data, pub_key)
    serialized = bundle.serialize()

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(serialized)
    print(f"[+] Encrypted bundle written to {output_file} ({len(serialized)} bytes)")


def handle_decrypt(args):
    """CLI handler for decrypting bundles."""
    if not Path(args.key).is_file():
        print(f"[!] Error: Private key file not found: {args.key}")
        sys.exit(1)

    priv_key = import_key(args.key)
    bundle_bytes = Path(args.input).read_bytes()
    bundle = CryptoBundle.deserialize(bundle_bytes)

    decrypted_tagged = decrypt_payload(bundle, priv_key)
    header, payload = InputHandler.extract_payload(decrypted_tagged)

    print(f"[+] Decrypted successfully!")
    print(f"    - Type: {header.payload_type.name}")
    print(f"    - Original Length: {header.original_length} bytes")

    output_path = Path(args.out)
    InputHandler.save_payload(header, payload, output_path)
    print(f"[+] Saved recovered payload to {output_path}")


def handle_sdr_loopback(args):
    """CLI handler for running GNU Radio SDR software loopback."""
    radioconda_python = Path(r"C:\Users\csaih\radioconda\python.exe")
    repo_root = Path(__file__).resolve().parent
    if not radioconda_python.is_file():
        print(f"[!] Error: radioconda python not found at {radioconda_python}")
        sys.exit(1)

    import subprocess
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root};{repo_root / 'sentinelspread' / 'gnuradio'}"

    cmd = [
        str(radioconda_python),
        "-m", "sentinelspread.gnuradio.runner",
        "--message", args.message,
        "--sf", str(args.sf),
        "--noise", str(args.noise),
        "--freq-offset", str(args.freq_offset),
    ]

    proc = subprocess.run(cmd, cwd=str(repo_root), env=env)
    sys.exit(proc.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="SentinelSpread: DSSS Covert Communication System & Detector Suite"
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    # Command: test-stage
    test_parser = subparsers.add_parser("test-stage", help="Run test suite for a specific stage")
    test_parser.add_argument(
        "stage",
        type=str,
        help="Stage name to test (e.g. 'crypto', 'input', 'stage1', 'stage4', 'all')",
    )

    # Command: sdr-loopback
    sdr_parser = subparsers.add_parser("sdr-loopback", help="Run GNU Radio Software SDR loopback transceiver")
    sdr_parser.add_argument("--message", "-m", default="SentinelSpread GNU Radio SDR Software Loopback Verification 2026", help="Test message")
    sdr_parser.add_argument("--sf", type=int, default=16, help="Spreading factor (default: 16)")
    sdr_parser.add_argument("--noise", type=float, default=0.02, help="Channel AWGN noise voltage (default: 0.02)")
    sdr_parser.add_argument("--freq-offset", type=float, default=0.0, help="Channel carrier frequency offset (default: 0.0)")

    # Command: plot-ber
    plot_parser = subparsers.add_parser("plot-ber", help="Simulate modem BER vs SNR and save plot figure")
    plot_parser.add_argument("--out", "-o", default="eval/ber_vs_snr.png", help="Output PNG path for plot")

    # Command: plot-psd
    psd_parser = subparsers.add_parser("plot-psd", help="Compute PSD flattening comparison and save plot figure")
    psd_parser.add_argument("--sf", type=int, default=16, help="Spreading factor to analyze (default: 16)")
    psd_parser.add_argument("--out", "-o", default="eval/psd_flattening.png", help="Output PNG path for plot")

    # Command: benchmark-gain
    subparsers.add_parser("benchmark-gain", help="Empirically verify processing gain Gp across spreading factors")

    # Command: encrypt
    enc_parser = subparsers.add_parser("encrypt", help="Prepare & Encrypt a text or audio payload")
    enc_parser.add_argument("--input", "-i", required=True, help="Input string or path to text/WAV file")
    enc_parser.add_argument("--type", "-t", choices=["text", "audio"], default="text", help="Payload type")
    enc_parser.add_argument("--out", "-o", default="encrypted_bundle.bin", help="Output encrypted file path")
    enc_parser.add_argument("--key", "-k", help="Path to RSA public key PEM file")
    enc_parser.add_argument("--save-keys", action="store_true", help="Save generated RSA keys to disk")

    # Command: decrypt
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt an encrypted payload bundle")
    dec_parser.add_argument("--input", "-i", required=True, help="Path to encrypted bundle binary file")
    dec_parser.add_argument("--key", "-k", required=True, help="Path to RSA private key PEM file")
    dec_parser.add_argument("--out", "-o", default="recovered_output.dat", help="Output path for recovered payload")

    args = parser.parse_args()

    if args.command == "test-stage":
        sys.exit(run_stage_tests(args.stage))
    elif args.command == "sdr-loopback":
        handle_sdr_loopback(args)
    elif args.command == "plot-ber":
        run_ber_simulation(save_path=args.out)
    elif args.command == "plot-psd":
        compute_and_plot_psd(sf=args.sf, save_path=args.out)
    elif args.command == "benchmark-gain":
        run_processing_gain_benchmark()
    elif args.command == "encrypt":
        handle_encrypt(args)
    elif args.command == "decrypt":
        handle_decrypt(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
