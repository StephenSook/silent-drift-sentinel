import numpy as np
import pandas as pd

from sentinel_ml import drift as DR


def _synth(n, rng, shift=None):
    data = {}
    for c in DR.NUMERIC:
        vals = rng.normal(0.0, 1.0, n)
        if shift and c == shift[0]:
            vals = vals + shift[1]
        data[c] = vals
    for c in DR.CATEGORICAL:
        data[c] = pd.Categorical(rng.integers(0, 3, n))
    return pd.DataFrame(data)


def test_classify_change_type():
    assert DR.classify_change_type(
        {"cardinality_ana": 1, "cardinality_ref": 353, "null_rate_ana": 0.0,
         "null_rate_ref": 0.0, "range_ref": [0, 270], "range_ana": [0, 0],
         "top_value_share_ana": 1.0}
    ) == "null_default_regression"
    assert DR.classify_change_type(
        {"cardinality_ana": 353, "cardinality_ref": 353, "null_rate_ana": 0.0,
         "null_rate_ref": 0.0, "range_ref": [0, 270], "range_ana": [0, 27078],
         "top_value_share_ana": 0.1}
    ) == "unit_change"
    assert DR.classify_change_type({}) == "none"


def test_injections():
    df = pd.DataFrame({"PageValues": [1.0, 2.0, 3.0]})
    assert DR.inject_unit_bug(df, "PageValues", 100.0)["PageValues"].tolist() == [100, 200, 300]
    assert DR.inject_null_regression(df, "PageValues", 0.0)["PageValues"].tolist() == [0, 0, 0]


def test_per_feature_drift_flags_shifted_feature():
    rng = np.random.default_rng(42)
    target = DR.NUMERIC[0]
    ref = _synth(1500, rng)
    ana = _synth(1500, rng, shift=(target, 5.0))  # strong shift on one numeric feature
    fd = DR.per_feature_drift(ref, ana)
    assert "p_adj_bh" in fd.columns
    drifted = set(fd[fd["drifted"]]["feature"])
    assert target in drifted
    # the top drifted feature by effect size is the shifted one
    assert fd[fd["drifted"]].iloc[0]["feature"] == target
