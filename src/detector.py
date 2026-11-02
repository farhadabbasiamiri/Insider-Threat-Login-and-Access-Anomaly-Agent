"""Run the full detection pipeline: ingest -> baselines -> features -> rules + Isolation Forest."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config import IF_CONTAMINATION, IF_RANDOM_STATE, SPLIT_DATE
from src.features import FEATURE_COLUMNS, Baseline, build_baselines, build_feature_table
from src.ingest import ValidationReport, load_change_records, load_events
from src.scoring import score_user_day

IF_FEATURES = [c for c in FEATURE_COLUMNS if c != "failure_rate"]  # failure_rate can be NaN


def isolation_forest_scores(features: pd.DataFrame) -> pd.DataFrame:
    """Unsupervised outlier scores over evaluation user-days. No labels are used."""
    X = features[IF_FEATURES].astype(float).to_numpy()
    model = IsolationForest(n_estimators=300, contamination=IF_CONTAMINATION, random_state=IF_RANDOM_STATE)
    model.fit(X)
    raw = model.decision_function(X)  # lower = more anomalous; < 0 = outlier at the chosen contamination
    out = pd.DataFrame(index=features.index)
    out["if_decision"] = np.round(raw, 4)
    out["if_outlier"] = model.predict(X) == -1  # sklearn: -1 outlier, 1 inlier
    return out


@dataclass
class PipelineResult:
    events: pd.DataFrame
    report: ValidationReport
    baselines: dict[str, Baseline]
    features: pd.DataFrame
    evidence: dict[tuple[str, date], dict]
    findings: pd.DataFrame   # features + rule score + IF columns, one row per user-day
    details: dict[tuple[str, date], dict]
    changes: pd.DataFrame

    @property
    def user_ids(self) -> set[str]:
        return set(self.events["user_id"].unique())


def run_pipeline(events_path: Path | str | None = None, changes_path: Path | str | None = None,
                 split: date = SPLIT_DATE) -> PipelineResult:
    events, report = load_events(events_path)
    baselines = build_baselines(events, split)
    features, evidence = build_feature_table(events, baselines, split)

    details, scores = {}, []
    for _, row in features.iterrows():
        key = (row["user_id"], row["day"])
        d = score_user_day(row.to_dict(), evidence[key], baselines[row["user_id"]])
        details[key] = d
        scores.append({"risk_score": d["risk_score"], "risk_label": d["risk_label"],
                       "reasons": "; ".join(r["rule"] for r in d["reasons"])})
    findings = pd.concat([features, pd.DataFrame(scores, index=features.index),
                          isolation_forest_scores(features)], axis=1)
    findings = findings.sort_values(["risk_score", "if_decision"], ascending=[False, True]).reset_index(drop=True)
    return PipelineResult(events, report, baselines, features, evidence, findings, details,
                          load_change_records(changes_path))


@lru_cache(maxsize=1)
def default_pipeline() -> PipelineResult:
    return run_pipeline()
