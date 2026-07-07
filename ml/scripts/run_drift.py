"""Produce the drift signal for the harmful scenario and prove the benign
control does not alarm. Saves artifacts/drift_signal.json (the object the agent
Detect node consumes) and prints the label-free-vs-true validation table.
"""
from __future__ import annotations

import json
import pathlib
import warnings

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

signal = DR.detect(ref, harmful_prod, model, MODEL_URN)
benign_signal = DR.detect(ref, benign_prod, model, MODEL_URN)

print("===== DRIFT SIGNAL (harmful: PageValues null/default regression) =====")
print(json.dumps(signal, indent=2))

print("\n===== BENIGN CONTROL (harmful flag must be false) =====")
print(f"  harmful={benign_signal['harmful']}  "
      f"estimated_current={benign_signal['performance']['estimated_current']}  "
      f"root_cause_feature={benign_signal['root_cause_feature']}  "
      f"change_type={benign_signal['change_type']}")

# Validation: CBPE label-free estimate vs true label-based metric on both.
print("\n===== label-free (CBPE) vs true (label-based) validation =====")
rows = []
for name, prod in [("clean", ref), ("harmful null->0", harmful_prod), ("benign x100", benign_prod)]:
    frame = DR.prediction_frame(model, prod, ref[D.TARGET].to_numpy())
    est = DR.cbpe_estimate(DR.prediction_frame(model, ref, ref[D.TARGET].to_numpy()), frame)
    act = DR.actual_metrics(frame)
    rows.append({"scenario": name, "true_auc": act["roc_auc"],
                 "cbpe_auc": round(est["roc_auc"], 4) if est["roc_auc"] else None,
                 "true_f1": act["f1"]})
print(pd.DataFrame(rows).to_string(index=False))

(ARTIFACTS / "drift_signal.json").write_text(json.dumps(signal, indent=2))
print(f"\nsaved -> {ARTIFACTS / 'drift_signal.json'}")
assert signal["harmful"] is True, "harmful scenario must alarm"
assert benign_signal["harmful"] is False, "benign control must not alarm"
assert signal["root_cause_feature"] == "PageValues", "root cause must localize to PageValues"
print("assertions passed: harmful alarms, benign does not, root cause = PageValues")
