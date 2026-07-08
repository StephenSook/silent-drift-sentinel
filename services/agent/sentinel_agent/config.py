"""Runtime configuration, loaded from the repo-root .env plus the environment."""
from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv

# repo root: services/agent/sentinel_agent/config.py -> parents[3]; override with
# SENTINEL_ROOT when the agent is deployed outside the repo tree.
_ROOT = pathlib.Path(os.environ.get("SENTINEL_ROOT") or pathlib.Path(__file__).resolve().parents[3])
load_dotenv(_ROOT / ".env")

# where the ML pipeline's drift_signal.json / drift_chart.json live
ARTIFACTS_DIR = pathlib.Path(os.environ.get("SENTINEL_ARTIFACTS_DIR") or (_ROOT / "ml" / "artifacts"))

GMS_URL = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")
GMS_TOKEN = os.environ.get("DATAHUB_GMS_TOKEN") or None

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

# LiteLLM fallback for the RCA narrative when the primary provider errors. Prefers
# a genuine cross-provider fallback (Gemini) when GEMINI_API_KEY is present, else a
# second Anthropic model. Override explicitly with SENTINEL_FALLBACK_MODEL.
FALLBACK_MODEL = os.environ.get("SENTINEL_FALLBACK_MODEL") or (
    "gemini/gemini-2.5-flash" if os.environ.get("GEMINI_API_KEY")
    else "anthropic/claude-haiku-4-5-20251001"
)

MODEL_URN = os.environ.get(
    "SENTINEL_MODEL_URN",
    "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)",
)

# Optional Slack Incoming Webhook: the agent posts the finding to the owning team
# on write-back, closing the loop to a human. No-op if unset.
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# where the write-ahead log lives (gitignored)
WAL_DIR = pathlib.Path(__file__).resolve().parents[1] / ".wal"
