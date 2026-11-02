import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.generate_data import generate  # noqa: E402


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    """Pipeline over freshly generated seed-8 data in a temp dir (does not touch data/synthetic)."""
    from src.detector import run_pipeline

    out = tmp_path_factory.mktemp("data")
    events, _, changes, scenarios = generate(100, 8)
    events.to_csv(out / "events.csv", index=False)
    changes.to_csv(out / "change_records.csv", index=False)
    p = run_pipeline(out / "events.csv", out / "change_records.csv")
    p.scenarios = scenarios
    return p


@pytest.fixture(autouse=True)
def isolated_run_log(tmp_path, monkeypatch):
    """Keep fake-LLM runs out of the real monitoring log in outputs/."""
    import src.agent

    monkeypatch.setattr(src.agent, "OUTPUT_DIR", tmp_path)


@pytest.fixture(scope="session")
def policy():
    from src.policy_retrieval import PolicyIndex

    return PolicyIndex()
