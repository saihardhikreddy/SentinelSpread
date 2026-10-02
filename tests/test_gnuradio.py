"""
Stage 4 GNU Radio Software SDR Loopback Tests.
Verifies end-to-end transceiver operation in GNU Radio:
- GRC compilation of sentinelspread_flowgraph.grc
- Software SDR transceiver loopback message recovery (PASS/FAIL)
- Constellation EVM and post-despreading BER
- Carrier frequency offset tracking via Costas loop
- Variable spreading factors (SF=16, SF=32)
"""

import os
import sys
import subprocess
from pathlib import Path
import pytest

RADIOCONDA_PYTHON = Path(r"C:\Users\csaih\radioconda\python.exe")
GRCC_EXECUTABLE = Path(r"C:\Users\csaih\radioconda\Scripts\grcc.exe")
REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_in_radioconda(cmd_args: list[str]) -> subprocess.CompletedProcess:
    """Run command inside radioconda environment with proper PYTHONPATH."""
    if not RADIOCONDA_PYTHON.exists():
        pytest.skip(f"radioconda python not found at {RADIOCONDA_PYTHON}")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT};{REPO_ROOT / 'sentinelspread' / 'gnuradio'}"

    full_cmd = [str(RADIOCONDA_PYTHON)] + cmd_args
    return subprocess.run(
        full_cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_grc_compilation():
    """Verify sentinelspread_flowgraph.grc compiles cleanly with grcc."""
    if not GRCC_EXECUTABLE.exists():
        pytest.skip(f"grcc compiler not found at {GRCC_EXECUTABLE}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    grc_file = REPO_ROOT / "sentinelspread" / "gnuradio" / "sentinelspread_flowgraph.grc"
    output_dir = REPO_ROOT / "sentinelspread" / "gnuradio"

    proc = subprocess.run(
        [str(GRCC_EXECUTABLE), "--output", str(output_dir), str(grc_file)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0, f"grcc failed with error: {proc.stderr}\n{proc.stdout}"
    assert "Compilation error" not in proc.stdout
    generated_py = output_dir / "sentinelspread_flowgraph.py"
    assert generated_py.exists(), "grcc did not generate sentinelspread_flowgraph.py"


def test_gnuradio_transceiver_loopback():
    """Verify end-to-end message recovery through GNU Radio SDR loopback."""
    test_msg = "SentinelSpread GNU Radio Verification 2026"
    cmd = [
        "-m", "sentinelspread.gnuradio.runner",
        "--message", test_msg,
        "--sf", "16",
        "--noise", "0.02",
        "--freq-offset", "0.0",
    ]
    proc = _run_in_radioconda(cmd)

    assert proc.returncode == 0, f"Loopback failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "[PASS - EXACT MATCH]" in proc.stdout
    assert f"Recovered Message       : '{test_msg}'" in proc.stdout
    assert "BER after Despreading   : 0.000000" in proc.stdout


def test_gnuradio_with_frequency_offset():
    """Verify Costas loop acquires carrier lock under normalized frequency offset."""
    test_msg = "Testing Carrier Recovery with Offset"
    cmd = [
        "-m", "sentinelspread.gnuradio.runner",
        "--message", test_msg,
        "--sf", "16",
        "--noise", "0.02",
        "--freq-offset", "0.0005",
    ]
    proc = _run_in_radioconda(cmd)

    assert proc.returncode == 0, f"Offset loopback failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "[PASS - EXACT MATCH]" in proc.stdout
    assert f"Recovered Message       : '{test_msg}'" in proc.stdout


def test_gnuradio_different_spreading_factor():
    """Verify loopback with spreading factor SF=32."""
    test_msg = "Spreading Factor 32 Verification"
    cmd = [
        "-m", "sentinelspread.gnuradio.runner",
        "--message", test_msg,
        "--sf", "32",
        "--noise", "0.02",
        "--freq-offset", "0.0",
    ]
    proc = _run_in_radioconda(cmd)

    assert proc.returncode == 0, f"SF=32 loopback failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "[PASS - EXACT MATCH]" in proc.stdout
    assert f"Recovered Message       : '{test_msg}'" in proc.stdout
