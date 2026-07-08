"""Two-layer drift detection.

Layer 1 (primary, headline): NannyML CBPE label-free performance estimation.
  Answers "is the model actually degrading" from calibrated probabilities alone,
  and we validate the estimate against the true (label-based) performance in a
  controlled experiment.
Layer 2 (diagnostic, root-cause only): per-feature drift (KS numeric, Chi-squared
  categorical) with Benjamini-Hochberg FDR correction and magnitude metrics
  (Wasserstein / Jensen-Shannon), a multivariate PCA reconstruction check, and
  data-quality checks (null rate, cardinality, range). Distribution drift is a
  diagnostic, never a proxy for performance.

The injected failure is a realistic upstream pipeline bug on one influential
feature. A benign shift on an unimportant feature is the control that must not
raise a performance alarm.
"""
from __future__ import annotations

import pathlib

import joblib
import nannyml as nml
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import jensenshannon
from sklearn.decomposition import PCA
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.multitest import multipletests

from . import data as D

ARTIFACTS = pathlib.Path(__file__).resolve().parents[1] / "artifacts"
NUMERIC = D.NUMERIC_BASE + D.ENGINEERED
CATEGORICAL = D.CATEGORICAL


def _restore_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    for c in CATEGORICAL:
        if c in df.columns and str(df[c].dtype) != "category":
            df[c] = df[c].astype("category")
    return df


def load() -> tuple:
    # These joblib artifacts are produced by our own train.py in this repo and
    # never sourced externally, so joblib.load (pickle) is trusted here.
    model = joblib.load(ARTIFACTS / "model_calibrated.joblib")
    raw = joblib.load(ARTIFACTS / "model_raw.joblib")
    ref = _restore_categoricals(pd.read_parquet(ARTIFACTS / "reference.parquet"))
    return model, raw, ref


def prediction_frame(model, features: pd.DataFrame, y: np.ndarray | None) -> pd.DataFrame:
    """Score features and return a CBPE-ready frame (prob, pred [, y] + features)."""
    X = features[D.feature_columns()]
    prob = model.predict_proba(X)[:, 1]
    out = features.copy()
    out["prob"] = prob
    out["pred"] = (prob >= 0.5).astype(int)
    if y is not None:
        out["y"] = np.asarray(y).astype(int)
    return out


# ---- realistic injected failures + benign control ----------------------------
def inject_unit_bug(df: pd.DataFrame, col: str = "PageValues", factor: float = 100.0) -> pd.DataFrame:
    out = df.copy()
    out[col] = out[col] * factor
    return out


def inject_null_regression(df: pd.DataFrame, col: str = "PageValues", value: float = 0.0) -> pd.DataFrame:
    out = df.copy()
    out[col] = value
    return out


def least_important_numeric(raw_model, ref: pd.DataFrame | None = None) -> str:
    imp = dict(zip(D.feature_columns(), raw_model.feature_importances_))
    numeric_imp = {f: imp[f] for f in NUMERIC}
    if ref is not None:
        # exclude zero-variance features: shifting a constant column produces no real
        # distribution shift, which would make a benign-shift control a vacuous no-op.
        with_var = {f: v for f, v in numeric_imp.items() if float(ref[f].std()) > 1e-9}
        numeric_imp = with_var or numeric_imp
    return min(numeric_imp, key=numeric_imp.get)


def inject_benign(df: pd.DataFrame, col: str, shift_std: float = 1.5) -> pd.DataFrame:
    """A visible but harmless distribution shift on an unimportant feature."""
    out = df.copy()
    std = float(np.std(out[col]))
    # a real shift even if the column happens to be near-constant, so the control is
    # never a silent no-op
    out[col] = out[col] + (shift_std * std if std > 1e-9 else 1.0)
    return out


def inject_default_value(df: pd.DataFrame, col: str = "PageValues", frac: float = 0.95,
                         value: float | None = None, seed: int = 0) -> pd.DataFrame:
    """Overwrite a fraction of rows with a single dominant default (a stuck default
    fill upstream), leaving a real minority. One value dominates while cardinality
    stays above one: the default_value_regression signature (distinct from a full
    collapse to a constant, which is null_default_regression)."""
    out = df.copy()
    rng = np.random.default_rng(seed)
    mask = rng.random(len(out)) < frac
    if value is None:
        nz = out[col][out[col] > 0]
        value = float(nz.median()) if len(nz) else 1.0
    out.loc[mask, col] = float(value)
    return out


# ---- Layer 1: CBPE ----------------------------------------------------------
def _metric_value(res, metric: str) -> float | None:
    df = res.to_df()
    for col in df.columns:
        flat = " ".join(map(str, col)) if isinstance(col, tuple) else str(col)
        if metric in flat and "value" in flat and "sampling" not in flat and "boundary" not in flat:
            return float(df[col].mean())
    return None


def cbpe_estimate(reference_frame: pd.DataFrame, analysis_frame: pd.DataFrame,
                  metrics=("roc_auc", "f1"), chunk_size: int = 300) -> dict:
    est = nml.CBPE(
        problem_type="classification_binary",
        y_pred_proba="prob",
        y_pred="pred",
        y_true="y",
        metrics=list(metrics),
        chunk_size=chunk_size,
    )
    est.fit(reference_frame)
    res = est.estimate(analysis_frame)
    return {m: _metric_value(res, m) for m in metrics}


def actual_metrics(frame_with_y: pd.DataFrame) -> dict:
    y = frame_with_y["y"].to_numpy()
    prob = frame_with_y["prob"].to_numpy()
    pred = frame_with_y["pred"].to_numpy()
    return {
        "roc_auc": round(float(roc_auc_score(y, prob)), 4),
        "f1": round(float(f1_score(y, pred)), 4),
    }


# ---- Layer 2: per-feature drift with FDR ------------------------------------
def _js_distance(a: pd.Series, b: pd.Series, bins: int = 30) -> float:
    lo = float(min(a.min(), b.min()))
    hi = float(max(a.max(), b.max()))
    if hi <= lo:
        return 0.0
    edges = np.linspace(lo, hi, bins + 1)
    pa, _ = np.histogram(a, bins=edges, density=True)
    pb, _ = np.histogram(b, bins=edges, density=True)
    pa = pa + 1e-12
    pb = pb + 1e-12
    return float(jensenshannon(pa, pb))


def _cramers_v(table: np.ndarray, chi2: float) -> float:
    """Effect size for a categorical contingency table, comparable to KS (0-1)."""
    n = float(table.sum())
    r, c = table.shape
    denom = n * (min(r, c) - 1)
    return float(np.sqrt(chi2 / denom)) if denom > 0 else 0.0


def per_feature_drift(ref: pd.DataFrame, ana: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    # KS for numeric, Chi-squared for categorical. Rank by a comparable effect
    # size (KS statistic vs Cramer's V), never the raw statistics, which live on
    # different scales. Benjamini-Hochberg FDR correction across all features.
    rows = []
    for f in NUMERIC:
        s, p = stats.ks_2samp(ref[f], ana[f])
        rows.append({"feature": f, "test": "KS", "statistic": float(s), "p_value": float(p),
                     "effect": float(s), "wasserstein": float(stats.wasserstein_distance(ref[f], ana[f])),
                     "js": _js_distance(ref[f], ana[f])})
    for f in CATEGORICAL:
        cats = sorted(set(ref[f].astype(str)) | set(ana[f].astype(str)))
        rc = ref[f].astype(str).value_counts().reindex(cats, fill_value=0)
        ac = ana[f].astype(str).value_counts().reindex(cats, fill_value=0)
        table = np.vstack([rc.to_numpy(), ac.to_numpy()])
        table = table[:, table.sum(axis=0) > 0]
        try:
            chi2, p, _, _ = stats.chi2_contingency(table)
            effect = _cramers_v(table, chi2)
        except ValueError:
            chi2, p, effect = 0.0, 1.0, 0.0
        rows.append({"feature": f, "test": "chi2", "statistic": float(chi2), "p_value": float(p),
                     "effect": effect, "wasserstein": np.nan, "js": np.nan})
    out = pd.DataFrame(rows)
    out["p_adj_bh"] = multipletests(out["p_value"], method="fdr_bh")[1]
    out["drifted"] = out["p_adj_bh"] < alpha
    return out.sort_values(["drifted", "effect"], ascending=[False, False]).reset_index(drop=True)


def pca_reconstruction_drift(ref: pd.DataFrame, ana: pd.DataFrame) -> dict:
    scaler = StandardScaler().fit(ref[NUMERIC])
    Xr = scaler.transform(ref[NUMERIC])
    Xa = scaler.transform(ana[NUMERIC])
    pca = PCA(n_components=0.9, svd_solver="full").fit(Xr)

    def recon_err(X):
        return ((X - pca.inverse_transform(pca.transform(X))) ** 2).sum(axis=1)

    er, ea = recon_err(Xr), recon_err(Xa)
    z = (ea.mean() - er.mean()) / (er.std() + 1e-12)
    return {"ref_mean": float(er.mean()), "ana_mean": float(ea.mean()), "z": float(z), "alarm": bool(z > 3)}


def data_quality(ref: pd.DataFrame, ana: pd.DataFrame, feature: str) -> dict:
    return {
        "feature": feature,
        "null_rate_ref": round(float(ref[feature].isna().mean()), 4),
        "null_rate_ana": round(float(ana[feature].isna().mean()), 4),
        "range_ref": [round(float(ref[feature].min()), 2), round(float(ref[feature].max()), 2)],
        "range_ana": [round(float(ana[feature].min()), 2), round(float(ana[feature].max()), 2)],
        "cardinality_ref": int(ref[feature].nunique()),
        "cardinality_ana": int(ana[feature].nunique()),
        "top_value_share_ana": round(float(ana[feature].value_counts(normalize=True).iloc[0]), 4),
    }


def classify_change_type(dq: dict) -> str:
    """Infer the upstream bug class from the data-quality fingerprint."""
    if not dq:
        return "none"
    if dq["cardinality_ana"] == 1 and dq["cardinality_ref"] > 10:
        return "null_default_regression"
    if dq["null_rate_ana"] > dq["null_rate_ref"] + 0.1:
        return "null_regression"
    if dq.get("top_value_share_ana", 0) > 0.9 and dq["cardinality_ref"] > 10:
        return "default_value_regression"
    rr, ra = dq["range_ref"], dq["range_ana"]
    if rr[1] > 0 and ra[1] > 0 and (ra[1] / rr[1] > 5 or rr[1] / max(ra[1], 1e-9) > 5):
        return "unit_change"
    return "distribution_shift"


REFERENCE_AUC = 0.808  # validated on the held-out test window at training time
HARMFUL_AUC_DROP = 0.03


def detect(reference_features: pd.DataFrame, production_features: pd.DataFrame,
           model, model_urn: str, reference_auc: float = REFERENCE_AUC) -> dict:
    """Run both layers on a production window and return the drift signal the
    agent consumes. Label-free: uses CBPE estimated performance, not true labels.
    """
    ref_frame = prediction_frame(model, reference_features,
                                 reference_features[D.TARGET].to_numpy())
    y_prod = (production_features[D.TARGET].to_numpy()
              if D.TARGET in production_features else None)
    prod_frame = prediction_frame(model, production_features, y_prod)

    est = cbpe_estimate(ref_frame, prod_frame)
    est_auc = est.get("roc_auc")
    drop = None if est_auc is None else round(reference_auc - est_auc, 4)
    harmful = bool(drop is not None and drop > HARMFUL_AUC_DROP)

    fd = per_feature_drift(reference_features, production_features)
    drifted = fd[fd["drifted"]]
    root = drifted.iloc[0]["feature"] if len(drifted) else None
    dq = data_quality(reference_features, production_features, root) if root else {}

    return {
        "model_urn": model_urn,
        "harmful": harmful,
        "performance": {
            "metric": "roc_auc",
            "reference": reference_auc,
            "estimated_current": None if est_auc is None else round(est_auc, 4),
            "estimated_drop": drop,
            "label_free": True,
        },
        "root_cause_feature": root,
        "change_type": classify_change_type(dq),
        "drifted_features": [
            {
                "feature": r.feature, "test": r.test,
                "statistic": round(float(r.statistic), 4),
                "p_adj_bh": round(float(r.p_adj_bh), 6),
                "wasserstein": None if pd.isna(r.wasserstein) else round(float(r.wasserstein), 4),
            }
            for r in drifted.itertuples()
        ],
        "data_quality": dq,
    }
