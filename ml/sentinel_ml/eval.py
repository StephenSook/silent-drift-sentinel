"""Score the drift detector + root-cause localizer over a labeled scenario suite.

For each scenario we injected a known upstream bug (or a benign shift, or nothing)
and check the three things the agent depends on:
  - alarm: does the harmful flag fire only when performance actually degrades
    (precision / recall against the ground-truth label)
  - localization: on a corrupted feature, does the root cause point at that feature
  - taxonomy: is the change type classified correctly

The scoring is pure (no model, no I/O) so it is unit-tested directly. run_eval.py
drives the real trained model through it and writes ml/artifacts/eval_report.json.
"""
from __future__ import annotations

from typing import Any


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def score(results: list[dict[str, Any]]) -> dict[str, Any]:
    """results: one dict per scenario with expected_/actual_ harmful, feature,
    change_type (expected_feature None means nothing was corrupted)."""
    tp = fp = tn = fn = 0
    loc_total = loc_hit = 0
    ct_total = ct_hit = 0
    per: list[dict[str, Any]] = []

    for r in results:
        eh, ah = bool(r["expected_harmful"]), bool(r["actual_harmful"])
        if eh and ah:
            tp += 1
        elif not eh and not ah:
            tn += 1
        elif ah and not eh:
            fp += 1
        else:
            fn += 1

        # Localization is attribution quality: among scenarios where the detector
        # proposed a root cause, how often it named the corrupted feature. A wrong
        # feature counts as a miss here; a total miss (no root cause on a harmful
        # scenario) is captured by alarm recall, not double-counted here.
        ef = r.get("expected_feature")
        loc_ok = ct_ok = None
        loc_scored = bool(ef) and r.get("actual_feature") is not None
        if loc_scored:
            loc_total += 1
            loc_ok = r.get("actual_feature") == ef
            loc_hit += int(bool(loc_ok))
            ect = r.get("expected_change_type")
            if ect:
                ct_total += 1
                ct_ok = r.get("actual_change_type") == ect
                ct_hit += int(bool(ct_ok))

        per.append({
            "name": r.get("name"),
            "expected_harmful": eh, "actual_harmful": ah, "alarm_ok": eh == ah,
            "expected_feature": ef, "actual_feature": r.get("actual_feature"),
            "localization_ok": loc_ok,
            "expected_change_type": r.get("expected_change_type"),
            "actual_change_type": r.get("actual_change_type"),
            "change_type_ok": ct_ok,
        })

    n = len(results)
    return {
        "n_scenarios": n,
        "alarm": {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": _ratio(tp, tp + fp),
            "recall": _ratio(tp, tp + fn),
            "accuracy": _ratio(tp + tn, n),
        },
        "localization_accuracy": _ratio(loc_hit, loc_total),
        "localization_n": loc_total,
        "change_type_accuracy": _ratio(ct_hit, ct_total),
        "change_type_n": ct_total,
        "scenarios": per,
    }
