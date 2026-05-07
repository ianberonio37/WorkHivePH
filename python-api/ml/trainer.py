"""
GBM Failure Classifier (Stage 1 ML) — WorkHive Predictive Maintenance.

Train:  build_feature_matrix() -> label -> GradientBoostingClassifier -> joblib.dump
Serve:  joblib.load -> predict_proba -> risk_score (0-1) + risk_level

Key design decisions:
  - Metric: Recall (not Accuracy) — class imbalance: failures are rare events.
    A model that always says "no failure" gets 95%+ Accuracy but is useless.
    Target Recall > 0.80 at threshold 0.5.
  - Data warning: model writes data_warning=True when n_samples < 500.
    UI uses this to show a "Model still learning" notice.
  - Model artifacts: .pkl stored in artifacts/ directory, NEVER committed to git.
    .gitignore covers *.pkl. Artifacts are regenerated on Railway on each deploy.
  - Retrain: weekly via pg_cron -> trigger-ml-retrain edge function -> /ml/train.
"""

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

from .feature_engineering import FEATURE_COLS

MODEL_DIR   = Path(__file__).parent / "artifacts"
MODEL_PATH  = MODEL_DIR / "failure_predictor_v1.pkl"
META_PATH   = MODEL_DIR / "model_meta.json"

DATA_THRESHOLD_WARN = 500   # warn below this — model may not be reliable
DATA_THRESHOLD_MIN  = 100   # skip training entirely below this


def train(df: pd.DataFrame) -> dict:
    """
    Trains the GBM classifier on the feature matrix.
    df must have FEATURE_COLS columns. 'will_fail' label is auto-generated
    from fault frequency patterns when not present (semi-supervised approach).

    Returns a training report dict.
    """
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        recall_score, precision_score, f1_score,
        classification_report, roc_auc_score,
    )

    MODEL_DIR.mkdir(exist_ok=True)

    if df.empty or len(df) < DATA_THRESHOLD_MIN:
        return {
            "status":  "skipped",
            "reason":  f"Only {len(df)} asset-level rows — need >= {DATA_THRESHOLD_MIN} to train.",
            "n_samples": len(df),
        }

    X = df[FEATURE_COLS].fillna(0)

    # Auto-generate label if not present:
    # High-risk heuristic — any of these signals = will_fail label
    if "will_fail" not in df.columns:
        y = (
            (df.get("fault_count_30d", 0) >= 2)  |       # 2+ faults in 30d
            (df.get("days_until_mtbf", 0) < 0)   |       # past expected failure date
            (df.get("repeat_fault_count", 0) >= 2) |      # repeat root causes
            (df.get("pm_overdue_days", 0) > 30)           # PM > 30d overdue
        ).astype(int)
    else:
        y = df["will_fail"].astype(int)

    if y.sum() < 5:
        return {
            "status":  "skipped",
            "reason":  "Fewer than 5 positive (failure) examples — cannot train binary classifier.",
            "n_samples": len(df),
        }

    stratify = y if y.sum() > 5 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify
    )

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )),
    ])
    pipe.fit(X_train, y_train)

    y_pred  = pipe.predict(X_test)
    y_proba = pipe.predict_proba(X_test)[:, 1]

    recall    = float(recall_score(y_test, y_pred, zero_division=0))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    f1        = float(f1_score(y_test, y_pred, zero_division=0))
    try:
        auc = float(roc_auc_score(y_test, y_proba))
    except Exception:
        auc = None

    # Feature importance
    model     = pipe.named_steps["model"]
    importances = [
        {"feature": col, "importance": round(float(imp), 4)}
        for col, imp in sorted(
            zip(FEATURE_COLS, model.feature_importances_),
            key=lambda x: x[1], reverse=True
        )
    ]

    joblib.dump(pipe, MODEL_PATH)

    meta = {
        "trained_at":    datetime.now(timezone.utc).isoformat(),
        "n_samples":     len(df),
        "n_positive":    int(y.sum()),
        "recall":        round(recall, 3),
        "precision":     round(precision, 3),
        "f1":            round(f1, 3),
        "auc":           round(auc, 3) if auc is not None else None,
        "data_warning":  len(df) < DATA_THRESHOLD_WARN,
        "feature_cols":  FEATURE_COLS,
        "top_features":  importances[:5],
    }
    META_PATH.write_text(json.dumps(meta, indent=2))

    return {"status": "trained", **meta}


def predict(features: dict) -> dict:
    """
    Single-asset risk prediction.
    features: dict with FEATURE_COLS keys (missing keys default to 0).
    Returns: risk_score (0-1), risk_level, model_version, recall, data_warning.
    Falls back to rules-v1 scoring if model artifact does not exist.
    """
    if not MODEL_PATH.exists():
        return _rules_fallback(features)

    try:
        pipe = joblib.load(MODEL_PATH)
        meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    except Exception as e:
        return {**_rules_fallback(features), "fallback_reason": str(e)}

    row   = pd.DataFrame([{col: features.get(col, 0) for col in FEATURE_COLS}])
    proba = float(pipe.predict_proba(row)[0, 1])

    risk_level = _risk_level(proba)

    return {
        "risk_score":    round(proba, 3),
        "risk_level":    risk_level,
        "model_version": "ml-v1",
        "recall":        meta.get("recall"),
        "data_warning":  meta.get("data_warning", False),
        "top_features":  meta.get("top_features", []),
    }


def predict_batch(feature_rows: list[dict]) -> list[dict]:
    """Batch predict for multiple assets at once (used by batch-risk-scoring)."""
    if not MODEL_PATH.exists():
        return [_rules_fallback(f) for f in feature_rows]

    try:
        pipe = joblib.load(MODEL_PATH)
        meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    except Exception:
        return [_rules_fallback(f) for f in feature_rows]

    X      = pd.DataFrame([{col: f.get(col, 0) for col in FEATURE_COLS} for f in feature_rows])
    probas = pipe.predict_proba(X)[:, 1]

    return [
        {
            "risk_score":    round(float(p), 3),
            "risk_level":    _risk_level(float(p)),
            "model_version": "ml-v1",
            "recall":        meta.get("recall"),
            "data_warning":  meta.get("data_warning", False),
        }
        for p in probas
    ]


def get_model_meta() -> dict:
    """Returns the last training metadata, or empty dict if not trained yet."""
    if not META_PATH.exists():
        return {"status": "untrained", "model_version": "rules-v1"}
    try:
        return json.loads(META_PATH.read_text())
    except Exception:
        return {"status": "unreadable"}


# ── Fallback: rules-based risk score ─────────────────────────────────────────
# Mirrors the 4-component formula in python-api/analytics/predictive.py.
# Active when model artifact not yet trained.

def _rules_fallback(features: dict) -> dict:
    count_30d      = float(features.get("fault_count_30d",   0))
    pm_overdue     = float(features.get("pm_overdue_days",   0))
    days_until_mtbf = float(features.get("days_until_mtbf",  0))
    repeat_count   = float(features.get("repeat_fault_count", 0))
    mtbf_days      = float(features.get("mtbf_days",          0))

    # Component A: PM overdue (30%)
    pm_score = max(0.0, min(1.0, 1.0 - pm_overdue / max(mtbf_days, 30) * 0.5))

    # Component B: Fault frequency (30%)
    fault_score = max(0.0, min(1.0, count_30d / 5.0))

    # Component C: Time to next failure (20%)
    time_score = 0.5
    if mtbf_days > 0:
        time_score = max(0.0, min(1.0, 1.0 - days_until_mtbf / mtbf_days))

    # Component D: Repeat fault (20%)
    repeat_score = min(1.0, repeat_count / 5.0)

    risk_score = round(0.30 * pm_score + 0.30 * fault_score + 0.20 * time_score + 0.20 * repeat_score, 3)

    return {
        "risk_score":    risk_score,
        "risk_level":    _risk_level(risk_score),
        "model_version": "rules-v1",
        "recall":        None,
        "data_warning":  True,
    }


def _risk_level(score: float) -> str:
    if score >= 0.85:   return "critical"
    if score >= 0.70:   return "high"
    if score >= 0.40:   return "medium"
    return "low"
