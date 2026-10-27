"""
Radio routes: the live software-SDR transmission feature.

The API server runs under a normal Python, but GNU Radio only exists in radioconda's
interpreter, so each step runs radio_worker.py there as a subprocess (the same approach the
project's CLI uses for `sdr-loopback`). The worker reuses the verified flowgraph blocks.

    POST /api/radio/transmit   message -> encrypt -> DSSS -> RRC -> channel -> tx.c64 (+ .wav)
    GET  /api/radio/wav/{id}   the rendered audio of that transmission
    POST /api/radio/receive    tx.c64 -> RRC -> sync -> Costas -> despread -> decrypt
    GET  /api/radio/status     whether the GNU Radio runtime is reachable, whether an ADALM-Pluto
                               is attached right now, plus constants

`channel` on /transmit picks the channel: "sim" (default, the GNU Radio channel model above) or
"pluto" (real RF on an ADALM-Pluto, TX1A cabled to RX1A). A Pluto run transmits and receives in
one go, so its /transmit response already carries the decode and /receive returns it again.
Pluto mode refuses to transmit unless the request confirms the cabling (attenuator_in_line, or
direct_cable for a bare cable, which also enforces a TX attenuation floor) and answers 400 with
"ADALM-Pluto not detected ..." when no board is attached.

Renders live in a temp directory keyed by transmission id and are pruned. Receive always reads
the lossless .c64, never the lossy .wav. NOTE: the per-transmission RSA private key is kept in
that temp directory so a separate receive process can decrypt: fine for a local demo where the
transmitter and receiver are the same machine, not a pattern for a real deployment.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/radio", tags=["Software SDR"])

RADIO_PYTHON = Path(os.environ.get("SENTINEL_RADIO_PYTHON", r"C:\Users\csaih\radioconda\python.exe"))
# The DSP package lives in this repository (../sentinelspread); override to use another checkout.
PROJECT_ROOT = Path(os.environ.get("SENTINEL_PROJECT_ROOT", Path(__file__).resolve().parent.parent))
WORKER = Path(__file__).with_name("radio_worker.py")
STORE = Path(tempfile.gettempdir()) / "sentinelspread_radio"
KEEP_SECONDS = 3600
KEEP_COUNT = 25
SIGNAL_POWER = 0.25          # measured mean |x|^2 of the shaped TX stream (independent of message/SF)
ID_RE = re.compile(r"^[0-9a-f]{12}$")
SPREADING_FACTORS = (16, 32, 64, 128)
MAX_MESSAGE_CHARS = 1000
# Mirrors sentinelspread.gnuradio.runner (not importable here: that module needs GNU Radio).
PLUTO_TX_ATTEN_DB = 20
PLUTO_RX_GAIN_DB = 40
DIRECT_CABLE_MIN_TX_ATTEN_DB = 60
DIRECT_CABLE_TX_ATTEN_DB = 70
DIRECT_CABLE_RX_GAIN_DB = 50


class TransmitRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    spreading_factor: int = Field(16, description="Spreading factor: 16, 32, 64 or 128")
    noise_voltage: float = Field(0.02, ge=0.0, le=20.0, description="Channel AWGN standard deviation")
    freq_offset: float = Field(0.0005, ge=-0.01, le=0.01, description="Carrier offset, normalised to the sample rate")
    channel: Literal["sim", "pluto"] = Field("sim", description="sim = software channel model; pluto = real RF on an ADALM-Pluto")
    receiver: Literal["despread", "classic"] = Field(
        "despread", description="despread = despread-first receiver (decodes below the noise floor); "
                                "classic = symbol sync + Costas on the raw chips")
    pluto_uri: str = Field("", pattern=r"^(|usb:[0-9.]*|ip:[A-Za-z0-9.\-]+)$", description="IIO URI; empty = first Pluto found")
    pluto_freq_hz: int = Field(915_000_000, ge=325_000_000, le=3_800_000_000, description="Carrier frequency (AD9363 range)")
    tx_atten_db: Optional[float] = Field(None, ge=0.0, le=89.75, description="Pluto TX attenuation in dB (higher = weaker)")
    rx_gain_db: Optional[float] = Field(None, ge=0.0, le=71.0, description="Pluto RX manual gain in dB")
    attenuator_in_line: bool = Field(False, description="Confirms TX1A -> ~30 dB SMA attenuator -> RX1A, no antennas")
    direct_cable: bool = Field(False, description=f"Confirms a bare TX1A -> RX1A cable, no antennas; TX attenuation must be >= {DIRECT_CABLE_MIN_TX_ATTEN_DB} dB")


class ReceiveRequest(BaseModel):
    transmission_id: str


def _run_worker(mode: str, workdir: Path, extra: Optional[dict] = None, timeout: int = 180) -> subprocess.CompletedProcess:
    if not RADIO_PYTHON.is_file():
        raise HTTPException(503, f"The GNU Radio runtime was not found at {RADIO_PYTHON}. Set SENTINEL_RADIO_PYTHON.")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [str(RADIO_PYTHON), str(WORKER), mode, str(workdir)]
    if extra is not None:
        cmd.append(json.dumps(extra))
    try:
        return subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "The GNU Radio flowgraph took too long and was stopped.")


def _prune() -> None:
    if not STORE.is_dir():
        return
    dirs = sorted((d for d in STORE.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)
    now = time.time()
    for i, d in enumerate(dirs):
        if i >= KEEP_COUNT or now - d.stat().st_mtime > KEEP_SECONDS:
            shutil.rmtree(d, ignore_errors=True)


def _workdir(transmission_id: str) -> Path:
    if not ID_RE.match(transmission_id):
        raise HTTPException(400, "That is not a valid transmission id.")
    d = STORE / transmission_id
    if not ((d / "tx.c64").is_file() or (d / "result_pluto.json").is_file()):
        raise HTTPException(404, "That transmission has expired or does not exist. Transmit again.")
    return d


def _console(proc: subprocess.CompletedProcess) -> str:
    text = (proc.stdout or "").strip()
    return text[-4000:]


def _probe_pluto() -> dict:
    """Ask the radioconda worker whether an ADALM-Pluto can be opened right now."""
    STORE.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="probe_", dir=STORE))
    try:
        proc = _run_worker("probe", workdir, timeout=30)
        result_file = workdir / "result_probe.json"
        if proc.returncode != 0 or not result_file.is_file():
            return {"detected": False, "detail": "The Pluto probe failed to run."}
        return json.loads(result_file.read_text())
    except HTTPException as e:
        return {"detected": False, "detail": str(e.detail)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.get("/status")
def radio_status():
    ok = RADIO_PYTHON.is_file() and WORKER.is_file()
    return {
        "available": ok,
        "channels": ["sim", "pluto"],
        "pluto": _probe_pluto() if ok else {"detected": False, "detail": "GNU Radio runtime not found"},
        "spreading_factors": list(SPREADING_FACTORS),
        "signal_power": SIGNAL_POWER,
        "max_message_chars": MAX_MESSAGE_CHARS,
        "detail": None if ok else f"GNU Radio runtime not found at {RADIO_PYTHON}",
    }


class DetectSweepRequest(BaseModel):
    spreading_factor: int = Field(16, description="Spreading factor: 16, 32, 64 or 128")


@router.post("/detect-sweep")
def radio_detect_sweep(req: DetectSweepRequest):
    """Run the Stage 5 self-attack: detection rate per key-free detector vs noise, plain and with
    FHSS hardening. Numpy only, so it does not need a Pluto or GNU Radio runtime beyond the Python."""
    if req.spreading_factor not in SPREADING_FACTORS:
        raise HTTPException(400, f"Spreading factor must be one of {', '.join(map(str, SPREADING_FACTORS))}.")
    STORE.mkdir(parents=True, exist_ok=True)
    _prune()
    workdir = Path(tempfile.mkdtemp(prefix="detect_", dir=STORE))
    try:
        proc = _run_worker("detect", workdir, req.model_dump(), timeout=180)
        result_file = workdir / "result_detect.json"
        if proc.returncode != 0 or not result_file.is_file():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
            raise HTTPException(500, f"The detector sweep failed: {tail[0]}")
        return json.loads(result_file.read_text())
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _pluto_transmit(req: TransmitRequest) -> dict:
    if not (req.attenuator_in_line or req.direct_cable):
        raise HTTPException(400, "Refusing to transmit on the Pluto: confirm the cabling first. Set attenuator_in_line "
                                 "(TX1A -> ~30 dB attenuator -> RX1A) or direct_cable (bare TX1A -> RX1A cable). No antennas.")
    tx_atten = req.tx_atten_db if req.tx_atten_db is not None else (
        DIRECT_CABLE_TX_ATTEN_DB if req.direct_cable else PLUTO_TX_ATTEN_DB)
    rx_gain = req.rx_gain_db if req.rx_gain_db is not None else (
        DIRECT_CABLE_RX_GAIN_DB if req.direct_cable else PLUTO_RX_GAIN_DB)
    if req.direct_cable and tx_atten < DIRECT_CABLE_MIN_TX_ATTEN_DB:
        raise HTTPException(400, f"On a bare cable the TX attenuation must be at least {DIRECT_CABLE_MIN_TX_ATTEN_DB} dB.")

    STORE.mkdir(parents=True, exist_ok=True)
    _prune()
    tid = uuid.uuid4().hex[:12]
    workdir = STORE / tid
    workdir.mkdir()
    args = {**req.model_dump(), "tx_atten_db": tx_atten, "rx_gain_db": rx_gain}
    try:
        proc = _run_worker("pluto", workdir, args, timeout=120)
        result_file = workdir / "result_pluto.json"
        if proc.returncode != 0 or not result_file.is_file():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
            raise HTTPException(500, f"The Pluto flowgraph failed: {tail[0]}")
        result = json.loads(result_file.read_text())
        if result.get("refused"):
            raise HTTPException(400, result["error"])
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    return {
        "transmission_id": tid,
        "channel": "pluto",
        "spreading_factor": req.spreading_factor,
        "console": _console(proc),
        **result,
    }


@router.post("/transmit")
def radio_transmit(req: TransmitRequest):
    if req.spreading_factor not in SPREADING_FACTORS:
        raise HTTPException(400, f"Spreading factor must be one of {', '.join(map(str, SPREADING_FACTORS))}.")
    if req.channel == "pluto":
        return _pluto_transmit(req)
    STORE.mkdir(parents=True, exist_ok=True)
    _prune()
    tid = uuid.uuid4().hex[:12]
    workdir = STORE / tid
    workdir.mkdir()
    try:
        proc = _run_worker("transmit", workdir, req.model_dump())
        result_file = workdir / "result_transmit.json"
        if proc.returncode != 0 or not result_file.is_file():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
            raise HTTPException(500, f"The transmitter failed: {tail[0]}")
        result = json.loads(result_file.read_text())
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    result.pop("signal_power", None)
    return {
        "transmission_id": tid,
        "channel": "sim",
        "wav_url": f"/api/radio/wav/{tid}",
        "spreading_factor": req.spreading_factor,
        "noise_voltage": req.noise_voltage,
        "console": _console(proc),
        **result,
    }


@router.get("/wav/{transmission_id}")
def radio_wav(transmission_id: str):
    wav = _workdir(transmission_id) / "signal.wav"
    if not wav.is_file():
        raise HTTPException(404, "No audio was rendered for that transmission.")
    return FileResponse(wav, media_type="audio/wav", filename=f"sentinel_{transmission_id}.wav")


@router.post("/receive")
def radio_receive(req: ReceiveRequest):
    workdir = _workdir(req.transmission_id)
    pluto_file = workdir / "result_pluto.json"
    if pluto_file.is_file():
        # Real-RF runs decode during /transmit; hand back that stored result.
        result = json.loads(pluto_file.read_text())
        if not result["success"]:
            raise HTTPException(400, detail={
                "message": "The Pluto loopback ran but the payload did not decode intact. Check the cabling "
                           "and try a higher RX gain.",
                "bit_errors": result["bit_errors"], "total_bits": result["total_bits"],
                "ber": result["ber"], "evm_db": result["evm_db"], "console": "",
            })
        return {**result, "console": ""}
    proc = _run_worker("receive", workdir)
    result_file = workdir / "result_receive.json"
    if proc.returncode != 0 or not result_file.is_file():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
        raise HTTPException(500, f"The receiver failed: {tail[0]}")
    result = json.loads(result_file.read_text())
    result["console"] = _console(proc)
    if not result["success"]:
        # A readable 400, not a 500: the receiver ran fine, the signal just did not survive.
        if result.get("receiver") == "classic":
            hint = ("Lower the channel noise and try again. With the classic receiver a higher spreading factor "
                    "will not help: it locks symbol timing and carrier phase on the raw chips before despreading.")
        else:
            hint = "Lower the channel noise or raise the spreading factor and try again."
        raise HTTPException(400, detail={
            "message": "Could not decode this transmission. AES-GCM accepts a message only if every bit "
                       "is intact, so any residual bit error rejects it entirely. " + hint,
            "bit_errors": result["bit_errors"],
            "total_bits": result["total_bits"],
            "ber": result["ber"],
            "evm_db": result["evm_db"],
            "console": result["console"],
        })
    return result
