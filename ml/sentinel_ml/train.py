"""Train and calibrate the monitored LightGBM purchase-intent model.

Pipeline:
  1. Fit LightGBM on the earliest months (train_fit), early-stop on val.
  2. Isotonic-calibrate the frozen model on a later held-out slice (calib).
  3. Evaluate on the reference window (known-good, out-of-time): ROC-AUC, PR-AUC,
     F1, Brier, and ECE before vs after calibration, plus a reliability diagram.
  4. Persist artifacts for the drift detector and the DataHub lineage layer.
"""
from __future__ import annotations

import json
import pathlib

import joblib
import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sklearn.calibration import CalibratedClassifierCV  # noqa: E402
from sklearn.frozen import FrozenEstimator  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)

from . import data as D  # noqa: E402
from .metrics import expected_calibration_error, reliability_curve  # noqa: E402

ARTIFACTS = pathlib.Path(__file__).resolve().parents[1] / "artifacts"


def _fit_lightgbm(splits: dict[str, D.Split]) -> lgb.LGBMClassifier:
    tr, va = splits["train_fit"], splits["val"]
    pos = int(tr.y.sum())
    neg = int((~tr.y).sum())
    scale_pos_weight = neg / max(pos, 1)
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=1000,
        learning_rate=0.03,
        num_leaves=31,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(
        tr.X,
        tr.y,
        eval_set=[(va.X, va.y)],
        eval_metric="auc",
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    return model


def _save_reliability(y_true, prob_raw, prob_cal, path: pathlib.Path) -> None:
    conf_r, acc_r, _ = reliability_curve(y_true, prob_raw)
    conf_c, acc_c, _ = reliability_curve(y_true, prob_cal)
    fig, ax = plt.subplots(figsize=(5, 5), dpi=130)
    ax.plot([0, 1], [0, 1], "--", color="#888", lw=1, label="perfect")
    ax.plot(conf_r, acc_r, "o-", color="#e0a800", lw=1.5, label="raw LightGBM")
    ax.plot(conf_c, acc_c, "o-", color="#3b82f6", lw=1.5, label="isotonic-calibrated")
    ax.set_xlabel("predicted probability (confidence)")
    ax.set_ylabel("observed frequency (accuracy)")
    ax.set_title("Reliability diagram (reference window)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def run() -> dict:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    splits = D.temporal_splits()

    raw = _fit_lightgbm(splits)
    calibrated = CalibratedClassifierCV(
        FrozenEstimator(raw), method="isotonic"
    ).fit(splits["calib"].X, splits["calib"].y)

    ref = splits["reference"]
    y_ref = ref.y.to_numpy()
    prob_raw = raw.predict_proba(ref.X)[:, 1]
    prob_cal = calibrated.predict_proba(ref.X)[:, 1]
    pred_cal = (prob_cal >= 0.5).astype(int)

    metrics = {
        "split_sizes": {k: int(len(v.y)) for k, v in splits.items()},
        "positive_rate": {k: round(float(v.y.mean()), 4) for k, v in splits.items()},
        "reference": {
            "roc_auc": round(float(roc_auc_score(y_ref, prob_cal)), 4),
            "pr_auc": round(float(average_precision_score(y_ref, prob_cal)), 4),
            "f1_at_0.5": round(float(f1_score(y_ref, pred_cal)), 4),
            "brier_raw": round(float(brier_score_loss(y_ref, prob_raw)), 4),
            "brier_calibrated": round(float(brier_score_loss(y_ref, prob_cal)), 4),
            "ece_raw": round(float(expected_calibration_error(y_ref, prob_raw)), 4),
            "ece_calibrated": round(
                float(expected_calibration_error(y_ref, prob_cal)), 4
            ),
        },
        "best_iteration": int(getattr(raw, "best_iteration_", 0) or 0),
        "n_features": len(D.feature_columns()),
        "features": D.feature_columns(),
    }

    # Persist artifacts.
    joblib.dump(calibrated, ARTIFACTS / "model_calibrated.joblib")
    joblib.dump(raw, ARTIFACTS / "model_raw.joblib")
    (ARTIFACTS / "feature_metadata.json").write_text(
        json.dumps(
            {
                "numeric": D.NUMERIC_BASE + D.ENGINEERED,
                "categorical": D.CATEGORICAL,
                "target": D.TARGET,
                "all_features": D.feature_columns(),
            },
            indent=2,
        )
    )
    (ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    _save_reliability(y_ref, prob_raw, prob_cal, ARTIFACTS / "reliability.png")

    # Reference and production slices for the drift detector + lineage layer.
    for name in ("reference", "production"):
        s = splits[name]
        frame = s.X.copy()
        frame[D.TARGET] = s.y.to_numpy()
        frame["prob_calibrated"] = calibrated.predict_proba(s.X)[:, 1]
        frame.to_parquet(ARTIFACTS / f"{name}.parquet", index=False)

    return metrics


def _log_to_mlflow(metrics: dict) -> None:
    """Log the trained model to a local MLflow registry so DataHub's MLflow
    connector can ingest it as a real mlModel with real training metrics.
    Imported lazily so the core module and tests never require mlflow."""
    import os

    import mlflow
    import mlflow.sklearn

    calibrated = joblib.load(ARTIFACTS / "model_calibrated.joblib")
    raw = joblib.load(ARTIFACTS / "model_raw.joblib")
    mlflow.set_tracking_uri(
        os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ARTIFACTS.parent / 'mlflow.db'}")
    )
    mlflow.set_experiment("silent-drift-sentinel")
    with mlflow.start_run(run_name="online_shoppers_lgbm"):
        params = raw.get_params()
        keep = ["n_estimators", "learning_rate", "num_leaves", "subsample",
                "colsample_bytree", "reg_lambda", "scale_pos_weight"]
        mlflow.log_params({k: params[k] for k in keep if k in params})
        mlflow.log_metric("best_iteration", metrics["best_iteration"])
        for k, v in metrics["reference"].items():
            mlflow.log_metric(k.replace(".", "_"), v)
        mlflow.set_tags({
            "dataset": "UCI Online Shoppers Purchasing Intention",
            "task": "purchase_intent", "calibration": "isotonic", "algorithm": "LightGBM",
        })
        info = mlflow.sklearn.log_model(calibrated, artifact_path="model")
        mlflow.register_model(info.model_uri, "online_shoppers_purchase_intent")
    print("logged + registered to MLflow at", ARTIFACTS.parent / "mlflow.db")


if __name__ == "__main__":
    import sys

    m = run()
    print(json.dumps(m, indent=2))
    if "--mlflow" in sys.argv:
        _log_to_mlflow(m)
