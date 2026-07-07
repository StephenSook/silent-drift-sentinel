"""Runtime configuration, loaded from the repo-root .env plus the environment."""
from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv

# repo root: services/agent/sentinel_agent/config.py -> parents[3]
_ROOT = pathlib.Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")

GMS_URL = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")
GMS_TOKEN = os.environ.get("DATAHUB_GMS_TOKEN") or None

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

MODEL_URN = os.environ.get(
    "SENTINEL_MODEL_URN",
    "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)",
)

# where the write-ahead log lives (gitignored)
WAL_DIR = pathlib.Path(__file__).resolve().parents[1] / ".wal"
