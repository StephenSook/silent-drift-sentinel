"""Evaluate the drift detector + root-cause localizer over a labeled scenario suite,
using the real trained model. Writes ml/artifacts/eval_report.json and prints a
per-scenario table. This turns "it finds the root cause" from a claim into a number:
alarm precision/recall, root-cause localization accuracy, and change-type accuracy.

Run: python ml/scripts/run_eval.py  (needs the trained model + reference parquet in
ml/artifacts, produced by ml/scripts/train.py).
"""
from __future__ import annotations

import json
import pathlib
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from sentinel_ml import drift as DR  # noqa: E402
from sentinel_ml import eval as EV  # noqa: E402

MODEL_URN = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)"
ARTIFACTS = pathlib.Path(__file__).resolve().parents[1] / "artifacts"


def main() -> dict:
    model, raw, ref = DR.load()
    least = DR.least_important_numeric(raw)

    # Each scenario: how to build the production window from the reference, plus the
    # ground truth. expected_feature None means nothing was corrupted (a true negative
    # must not alarm). A benign scenario leaves change_type unscored (None).
    suite = [
        {"name": "clean (no change)", "prod": lambda r: r.copy(),
         "expected_harmful": False, "expected_feature": None, "expected_change_type": None},
        {"name": "null/default regression (PageValues -> 0)",
         "prod": lambda r: DR.inject_null_regression(r, "PageValues", 0.0),
         "expected_harmful": True, "expected_feature": "PageValues",
         "expected_change_type": "null_default_regression"},
        {"name": "unit change (PageValues x100)",
         "prod": lambda r: DR.inject_unit_bug(r, "PageValues", 100.0),
         "expected_harmful": False, "expected_feature": "PageValues",
         "expected_change_type": "unit_change"},
        {"name": "default-value regression (PageValues 95% stuck)",
         "prod": lambda r: DR.inject_default_value(r, "PageValues", 0.95),
         "expected_harmful": True, "expected_feature": "PageValues",
         "expected_change_type": "default_value_regression"},
        {"name": f"benign shift ({least}, unimportant)",
         "prod": lambda r: DR.inject_benign(r, least),
         "expected_harmful": False, "expected_feature": least, "expected_change_type": None},
    ]

    results = []
    for sc in suite:
        sig = DR.detect(ref, sc["prod"](ref), model, MODEL_URN)
        results.append({
            "name": sc["name"],
            "expected_harmful": sc["expected_harmful"],
            "actual_harmful": sig["harmful"],
            "expected_feature": sc["expected_feature"],
            "actual_feature": sig["root_cause_feature"],
            "expected_change_type": sc["expected_change_type"],
            "actual_change_type": sig["change_type"],
        })

    report = EV.score(results)
    report["model_urn"] = MODEL_URN
    report["reference_auc"] = DR.REFERENCE_AUC

    print("===== drift detector evaluation =====")
    table = [{
        "scenario": s["name"], "harmful?": f"{s['actual_harmful']}",
        "ok": s["alarm_ok"], "root_cause": s["actual_feature"],
        "loc_ok": s["localization_ok"], "change_type": s["actual_change_type"],
        "ct_ok": s["change_type_ok"],
    } for s in report["scenarios"]]
    print(pd.DataFrame(table).to_string(index=False))
    a = report["alarm"]
    print(f"\nalarm  precision={a['precision']} recall={a['recall']} accuracy={a['accuracy']}"
          f"  (tp={a['tp']} fp={a['fp']} tn={a['tn']} fn={a['fn']})")
    print(f"localization accuracy = {report['localization_accuracy']} over {report['localization_n']} corrupted scenarios")
    print(f"change-type accuracy  = {report['change_type_accuracy']} over {report['change_type_n']} scenarios")

    (ARTIFACTS / "eval_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nsaved -> {ARTIFACTS / 'eval_report.json'}")

    # core invariants the whole demo rests on
    assert a["recall"] == 1.0, "every harmful scenario must alarm"
    assert a["fp"] == 0, "no benign scenario may alarm (the agent must not cry wolf)"
    assert report["localization_accuracy"] == 1.0, "root cause must localize to the corrupted feature"
    print("core invariants passed")
    return report


if __name__ == "__main__":
    main()
