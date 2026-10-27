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
import shutil
import sys
import subprocess
from pathlib import Path
import pytest

# The GNU Radio Python and grcc. Override with RADIOCONDA_PYTHON / RADIOCONDA_GRCC (any OS).
# The default is the current interpreter when it can import GNU Radio (so a Linux box with
# gnuradio installed just works), otherwise a radioconda path that is absent elsewhere, which
# makes these tests skip rather than fail where GNU Radio is not available.
def _default_gr_python() -> str:
    try:
        import gnuradio  # noqa: F401
        return sys.executable
    except Exception:
        return r"C:\Users\csaih\radioconda\python.exe"


RADIOCONDA_PYTHON = Path(os.environ.get("RADIOCONDA_PYTHON", _default_gr_python()))
GRCC_EXECUTABLE = Path(os.environ.get(
    "RADIOCONDA_GRCC",
    shutil.which("grcc") or r"C:\Users\csaih\radioconda\Scripts\grcc.exe"))
REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_in_radioconda(cmd_args: list[str]) -> subprocess.CompletedProcess:
    """Run command inside radioconda environment with proper PYTHONPATH."""
    if not RADIOCONDA_PYTHON.exists():
        pytest.skip(f"radioconda python not found at {RADIOCONDA_PYTHON}")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / 'sentinelspread' / 'gnuradio')])

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


def test_channel_switch_guards_never_transmit():
    """The pluto channel refuses to transmit without the cabling flag, enforces the bare-cable
    TX attenuation floor, and reports a missing board; an unknown channel is rejected. None of
    these reach a transmit, so the test is safe with or without a Pluto attached."""
    script = (
        "from sentinelspread.gnuradio.runner import run_software_loopback, run_pluto_loopback, "
        "HardwareNotReady, PlutoNotDetected\n"
        "def expect(exc, fn, **kw):\n"
        "    try:\n"
        "        fn(**kw)\n"
        "    except exc as e:\n"
        "        print('OK', exc.__name__, e)\n"
        "        return\n"
        "    raise SystemExit(f'{exc.__name__} not raised for {kw}')\n"
        "expect(ValueError, run_software_loopback, channel='bogus')\n"
        "expect(HardwareNotReady, run_software_loopback, channel='pluto')\n"
        "expect(HardwareNotReady, run_pluto_loopback, hardware_ready=True, direct_cable=True, tx_atten_db=40)\n"
        "expect(PlutoNotDetected, run_pluto_loopback, hardware_ready=True, pluto_uri='usb:9.9.9')\n"
    )
    proc = _run_in_radioconda(["-c", script])
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert proc.stdout.count("OK ") == 4
    assert "ADALM-Pluto not detected at usb:9.9.9" in proc.stdout
