"""Vercel entrypoint: the SentinelSpread web app (FastAPI, in stego_crypto_api/).

The API modules import each other as top-level modules (`import crypto_engine`), so their folder
goes on the path before `main` is loaded. Locally, run it the same way: `uvicorn app:app`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "stego_crypto_api"))

from main import app  # noqa: E402

__all__ = ["app"]
