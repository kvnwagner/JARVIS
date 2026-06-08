from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import uvicorn


if __name__ == "__main__":
    host = os.getenv("JARVIS_API_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_API_PORT", "8000"))
    uvicorn.run("api.app:app", host=host, port=port, log_level="info")
