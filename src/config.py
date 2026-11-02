"""Shared settings. Every threshold here is a documented teaching choice, not a calibrated value."""

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "synthetic"
POLICY_DIR = ROOT / "policies"
OUTPUT_DIR = ROOT / "outputs"

# Time window: 14 baseline days, then 14 evaluation days (chronological split).
START_DATE = date(2026, 10, 5)
BASELINE_DAYS = 14
EVAL_DAYS = 14
SPLIT_DATE = date(2026, 10, 19)  # first evaluation day; baseline uses days strictly before it
TZ_OFFSET_HOURS = -4  # all synthetic timestamps use a fixed UTC-04:00 offset

# Baseline / rule settings
MIN_BASELINE_DAYS = 5        # fewer active baseline days -> "insufficient_baseline"
HOUR_TOLERANCE = 1           # a login hour within +/-1h of any baseline login hour is "usual"
FAILED_BURST_MIN = 5         # absolute failed-login count that triggers the burst rule
FAILED_Z_MIN = 3.0           # or: z-score >= 3 with at least FAILED_Z_FLOOR failures
FAILED_Z_FLOOR = 3
SIGMA_FLOOR = 0.5            # avoid divide-by-zero when a user's history has no variation

# Illustrative score weights (see docs/architecture.md). Capped at 100.
WEIGHTS = {
    "off_hours_login": 20,
    "new_system": 25,
    "failed_login_burst": 20,
    "failures_then_success": 20,
    "unusual_privileged_action": 20,
    "new_location": 15,
}
MEDIUM_THRESHOLD = 40
HIGH_THRESHOLD = 70

# Isolation Forest comparison model
IF_CONTAMINATION = 0.03
IF_RANDOM_STATE = 8

# Local LLM (Ollama)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "180"))
AGENT_MAX_STEPS = 6
