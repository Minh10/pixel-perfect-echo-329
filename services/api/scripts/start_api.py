"""Start the API with the gitignored .env loaded into the process environment."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
os.chdir(root)
for name, value in dotenv_values(root / ".env").items():
    if value:
        os.environ[name] = value
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
