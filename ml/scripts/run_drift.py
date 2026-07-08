"""Produce the drift signal for the harmful scenario and prove the benign
control does not alarm. Saves artifacts/drift_signal.json (the object the agent
Detect node consumes) and prints the label-free-vs-true validation table.
"""
from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from sentinel_ml import data as D  # noqa: E402
from sentinel_ml import drift as DR  # noqa: E402

MODEL_URN = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)"
ARTIFACTS = pathlib.Path(__file__).resolve().parents[1] / "artifacts"

model, raw, ref = DR.load()

# Harmful: upstream job starts emitting PageValues = 0 (null/default regression).
harmful_prod = DR.inject_null_regression(ref, "PageValues", 0.0)
# Benign control: unit rescale (dollars -> cents). Big shift, no performance impact.
benign_prod = DR.inject_unit_bug(ref, "PageValues", 100.0)
# Default-value regression: an upstream default fill pins ~95% of PageValues rows to
# one dominant value. Harmful like the null case, but a different bug class, so the
# agent produces a different diagnosis and a different generated guardrail.
default_prod = DR.inject_default_value(ref, "PageValues", 0.95)

signal = DR.detect(ref, harmful_prod, model, MODEL_URN)
benign_signal = DR.detect(ref, benign_prod, model, MODEL_URN)
default_signal = DR.detect(ref, default_prod, model, MODEL_URN)

print("===== DRIFT SIGNAL (harmful: PageValues null/default regression) =====")
print(json.dumps(signal, indent=2))

print("\n===== BENIGN CONTROL (harmful flag must be false) =====")
print(f"  harmful={benign_signal['harmful']}  "
      f"estimated_current={benign_signal['performance']['estimated_current']}  "
      f"root_cause_feature={benign_signal['root_cause_feature']}  "
      f"change_type={benign_signal['change_type']}")

print("\n===== DEFAULT-VALUE REGRESSION (harmful, different change_type) =====")
print(f"  harmful={default_signal['harmful']}  "
      f"estimated_current={default_signal['performance']['estimated_current']}  "
      f"root_cause_feature={default_signal['root_cause_feature']}  "
      f"change_type={default_signal['change_type']}")

# Validation: CBPE label-free estimate vs true label-based metric on both.
print("\n===== label-free (CBPE) vs true (label-based) validation =====")
rows = []
for name, prod in [("clean", ref), ("harmful null->0", harmful_prod),
                   ("benign x100", benign_prod), ("default 95% fill", default_prod)]:
    frame = DR.prediction_frame(model, prod, ref[D.TARGET].to_numpy())
    est = DR.cbpe_estimate(DR.prediction_frame(model, ref, ref[D.TARGET].to_numpy()), frame)
    act = DR.actual_metrics(frame)
    rows.append({"scenario": name, "true_auc": act["roc_auc"],
                 "cbpe_auc": round(est["roc_auc"], 4) if est["roc_auc"] else None,
                 "true_f1": act["f1"]})
print(pd.DataFrame(rows).to_string(index=False))

(ARTIFACTS / "drift_signal.json").write_text(json.dumps(signal, indent=2))
print(f"\nsaved -> {ARTIFACTS / 'drift_signal.json'}")

# Drift chart data for the UI: PageValues reference vs production distribution.
pv_ref = ref["PageValues"].to_numpy()
pv_prod = harmful_prod["PageValues"].to_numpy()
_hi = float(np.percentile(pv_ref[pv_ref > 0], 95)) if (pv_ref > 0).any() else 1.0
_edges = np.linspace(0.0, max(_hi, 1.0), 21)
chart = {
    "feature": "PageValues",
    "bins": [round(float(e), 1) for e in _edges],
    "reference_hist": [int(x) for x in np.histogram(pv_ref, bins=_edges)[0]],
    "production_hist": [int(x) for x in np.histogram(pv_prod, bins=_edges)[0]],
    "performance": signal["performance"],
    "drifted": signal["drifted_features"],
}
(ARTIFACTS / "drift_chart.json").write_text(json.dumps(chart, indent=2))
print(f"saved -> {ARTIFACTS / 'drift_chart.json'}")

# Benign-scenario artifacts: the control that shifts hard yet correctly does NOT
# alarm (a monotonic unit rescale the tree model is invariant to). This is the
# anti-toy proof the UI shows alongside the harmful case.
(ARTIFACTS / "drift_signal_benign.json").write_text(json.dumps(benign_signal, indent=2))
pv_prod_b = benign_prod["PageValues"].to_numpy()
_hi_b = float(np.percentile(pv_prod_b[pv_prod_b > 0], 95)) if (pv_prod_b > 0).any() else 1.0
_edges_b = np.linspace(0.0, max(_hi_b, 1.0), 21)
chart_b = {
    "feature": "PageValues",
    "bins": [round(float(e), 1) for e in _edges_b],
    "reference_hist": [int(x) for x in np.histogram(pv_ref, bins=_edges_b)[0]],
    "production_hist": [int(x) for x in np.histogram(pv_prod_b, bins=_edges_b)[0]],
    "performance": benign_signal["performance"],
    "drifted": benign_signal["drifted_features"],
}
(ARTIFACTS / "drift_chart_benign.json").write_text(json.dumps(chart_b, indent=2))
print(f"saved -> {ARTIFACTS / 'drift_signal_benign.json'} and drift_chart_benign.json")

# Default-value-scenario artifacts: harmful, but a different bug class than the null
# collapse. ~95% of PageValues rows are pinned to one dominant value, so the agent
# classifies it as default_value_regression and generates a not_constant guardrail
# instead of not_null. Edges come from the reference window (the default fill sits
# inside the natural range), so the dominant-value spike is visible.
(ARTIFACTS / "drift_signal_default.json").write_text(json.dumps(default_signal, indent=2))
pv_prod_d = default_prod["PageValues"].to_numpy()
_hi_d = float(np.percentile(pv_ref[pv_ref > 0], 95)) if (pv_ref > 0).any() else 1.0
_edges_d = np.linspace(0.0, max(_hi_d, 1.0), 21)
chart_d = {
    "feature": "PageValues",
    "bins": [round(float(e), 1) for e in _edges_d],
    "reference_hist": [int(x) for x in np.histogram(pv_ref, bins=_edges_d)[0]],
    "production_hist": [int(x) for x in np.histogram(pv_prod_d, bins=_edges_d)[0]],
    "performance": default_signal["performance"],
    "drifted": default_signal["drifted_features"],
}
(ARTIFACTS / "drift_chart_default.json").write_text(json.dumps(chart_d, indent=2))
print(f"saved -> {ARTIFACTS / 'drift_signal_default.json'} and drift_chart_default.json")

assert signal["harmful"] is True, "harmful scenario must alarm"
assert benign_signal["harmful"] is False, "benign control must not alarm"
assert signal["root_cause_feature"] == "PageValues", "root cause must localize to PageValues"
assert default_signal["harmful"] is True, "default-value scenario must alarm"
assert default_signal["root_cause_feature"] == "PageValues", (
    "default root cause must localize to PageValues")
assert default_signal["change_type"] == "default_value_regression", (
    "default scenario must classify as default_value_regression")
print("assertions passed: harmful + default alarm, benign does not, "
      "root cause = PageValues, default change_type = default_value_regression")
