"""The eval scoring is pure, so it is tested directly (no model). It pins the alarm
confusion matrix, localization-as-attribution-quality, and change-type accuracy."""
from sentinel_ml import eval as EV


def _r(name, eh, ah, ef=None, af=None, ect=None, act=None):
    return {"name": name, "expected_harmful": eh, "actual_harmful": ah,
            "expected_feature": ef, "actual_feature": af,
            "expected_change_type": ect, "actual_change_type": act}


def test_perfect_suite_scores_all_ones():
    rep = EV.score([
        _r("clean", False, False),
        _r("null_default", True, True, "PageValues", "PageValues",
           "null_default_regression", "null_default_regression"),
        _r("unit", False, False, "PageValues", "PageValues", "unit_change", "unit_change"),
        _r("benign_below_threshold", False, False, "SpecialDay", None),
    ])
    assert rep["alarm"] == {"tp": 1, "fp": 0, "tn": 3, "fn": 0,
                            "precision": 1.0, "recall": 1.0, "accuracy": 1.0}
    # localization scored only where a root cause was proposed (null_default + unit)
    assert rep["localization_n"] == 2
    assert rep["localization_accuracy"] == 1.0
    assert rep["change_type_n"] == 2
    assert rep["change_type_accuracy"] == 1.0


def test_false_alarm_drops_precision():
    rep = EV.score([
        _r("benign_but_alarmed", False, True),
        _r("harmful", True, True, "X", "X", "unit_change", "unit_change"),
    ])
    assert rep["alarm"]["fp"] == 1
    assert rep["alarm"]["precision"] == 0.5
    assert rep["alarm"]["recall"] == 1.0


def test_missed_harmful_drops_recall():
    rep = EV.score([_r("missed", True, False, "X", None, "unit_change", None)])
    assert rep["alarm"]["fn"] == 1
    assert rep["alarm"]["recall"] == 0.0
    # no root cause was proposed, so localization is not scored here; the miss shows
    # up in recall instead
    assert rep["localization_n"] == 0


def test_wrong_feature_is_a_localization_miss():
    rep = EV.score([
        _r("mis_attributed", True, True, "PageValues", "ExitRates",
           "null_regression", "null_regression"),
    ])
    assert rep["localization_n"] == 1
    assert rep["localization_accuracy"] == 0.0
    # the change type still classified correctly even though the feature was wrong
    assert rep["change_type_accuracy"] == 1.0


def test_empty_suite_is_safe():
    rep = EV.score([])
    assert rep["n_scenarios"] == 0
    assert rep["alarm"]["precision"] is None
    assert rep["localization_accuracy"] is None
