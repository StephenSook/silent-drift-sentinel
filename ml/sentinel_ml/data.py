"""Load, feature-engineer, and temporally split the Online Shoppers dataset.

The temporal split is the honest backbone of the whole drift story:
train_fit and val come from earlier months, calib and reference from later
months, and production from the latest months. The reference window (known-good,
held-out) is what NannyML compares production against, so it must be a real
out-of-time slice, not a random sample of training rows.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import pandas as pd

RAW_CSV = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "online_shoppers.csv"

TARGET = "Revenue"

# Chronological order for the string Month column (dataset covers Feb..Dec, no Jan/Apr).
MONTH_NUM = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "June": 6, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

NUMERIC_BASE = [
    "Administrative", "Administrative_Duration", "Informational",
    "Informational_Duration", "ProductRelated", "ProductRelated_Duration",
    "BounceRates", "ExitRates", "PageValues", "SpecialDay",
]
CATEGORICAL = [
    "Month", "VisitorType", "Weekend", "OperatingSystems", "Browser",
    "Region", "TrafficType",
]
ENGINEERED = ["total_pages", "total_duration", "avg_product_duration", "product_ratio"]

# Time-ordered window boundaries as cumulative fractions of the sorted rows.
SPLIT_FRACTIONS = {
    "train_fit": 0.50,
    "val": 0.60,
    "calib": 0.72,
    "reference": 0.84,
    "production": 1.00,
}


@dataclass
class Split:
    """A named, time-ordered slice with features X and boolean target y."""

    name: str
    X: pd.DataFrame
    y: pd.Series


def load_raw() -> pd.DataFrame:
    if not RAW_CSV.exists():
        raise FileNotFoundError(
            f"{RAW_CSV} missing. Run: python ml/scripts/fetch_data.py"
        )
    return pd.read_csv(RAW_CSV)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add honest session-behavior features. Deterministic, no leakage."""
    out = df.copy()
    out["total_pages"] = (
        out["Administrative"] + out["Informational"] + out["ProductRelated"]
    )
    out["total_duration"] = (
        out["Administrative_Duration"]
        + out["Informational_Duration"]
        + out["ProductRelated_Duration"]
    )
    out["avg_product_duration"] = out["ProductRelated_Duration"] / (
        out["ProductRelated"] + 1.0
    )
    out["product_ratio"] = out["ProductRelated"] / (out["total_pages"] + 1.0)
    return out


def feature_columns() -> list[str]:
    return NUMERIC_BASE + ENGINEERED + CATEGORICAL


def _as_model_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Cast categoricals to pandas 'category' dtype so LightGBM handles them natively."""
    X = df[feature_columns()].copy()
    for col in CATEGORICAL:
        X[col] = X[col].astype("category")
    return X


def temporal_splits() -> dict[str, Split]:
    """Return the five time-ordered splits keyed by name."""
    df = engineer_features(load_raw())
    df["_mnum"] = df["Month"].map(MONTH_NUM)
    if df["_mnum"].isna().any():
        bad = df.loc[df["_mnum"].isna(), "Month"].unique()
        raise ValueError(f"Unmapped Month values: {bad}")
    df = df.sort_values("_mnum", kind="stable").reset_index(drop=True)

    n = len(df)
    splits: dict[str, Split] = {}
    prev_i = 0
    for name, frac in SPLIT_FRACTIONS.items():
        i = int(round(frac * n))
        chunk = df.iloc[prev_i:i]
        splits[name] = Split(
            name=name,
            X=_as_model_frame(chunk),
            y=chunk[TARGET].astype(bool).reset_index(drop=True),
        )
        splits[name].X.reset_index(drop=True, inplace=True)
        prev_i = i
    return splits
