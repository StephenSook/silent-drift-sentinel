"""Fetch the UCI Online Shoppers Purchasing Intention dataset (id=468, CC BY 4.0)
and cache it locally. Prints the real schema so the training code is written
against ground truth, not assumptions.
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
CSV_PATH = RAW_DIR / "online_shoppers.csv"
UCI_ZIP = "https://archive.ics.uci.edu/static/public/468/online_shoppers_intention.zip"


def load() -> pd.DataFrame:
    try:
        from ucimlrepo import fetch_ucirepo

        ds = fetch_ucirepo(id=468)
        df = pd.concat([ds.data.features, ds.data.targets], axis=1)
        print("source: ucimlrepo id=468")
        return df
    except Exception as exc:  # noqa: BLE001
        print(f"ucimlrepo failed ({exc!r}); falling back to direct CSV/zip download", file=sys.stderr)
        return pd.read_csv(UCI_ZIP, compression="zip")


def main() -> None:
    df = load()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    print(f"saved -> {CSV_PATH}")
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    print("dtypes:")
    print(df.dtypes.to_string())
    target = df.columns[-1]
    print(f"\ntarget '{target}' value counts:")
    print(df[target].value_counts(dropna=False).to_string())
    print("\nhead:")
    print(df.head(3).to_string())
    print("\nunique counts per column:")
    print(df.nunique().to_string())


if __name__ == "__main__":
    main()
