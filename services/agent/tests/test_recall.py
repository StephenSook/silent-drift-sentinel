"""Close-the-loop: on a re-run the agent recognizes a drift_causation it already
wrote onto the model and short-circuits (no re-diagnosis, no duplicate incident).
These tests pin the routing, the match logic, and the recall node without a network
(they import only the pure agent nodes, never the LangGraph runtime)."""
from sentinel_agent import nodes, writeback
from sentinel_agent.state import DriftState

MODEL = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)"
HARMFUL = {
    "harmful": True,
    "root_cause_feature": "PageValues",
    "change_type": "null_default_regression",
    "performance": {"metric": "roc_auc", "reference": 0.808, "estimated_current": 0.7131, "estimated_drop": 0.0949},
}
BENIGN = {"harmful": False, "root_cause_feature": "", "performance": {}}
PRIOR = {
    "causation_value": ("null_default_regression on feature PageValues (upstream "
                        "ecommerce.web_sessions); roc_auc 0.808->0.7131 (label-free CBPE), "
                        "drop 0.0949; notify urn:li:corpGroup:data-engineering; detected 2026-07-08T00:00:00"),
    "fix_value": "not_null + not_constant on PageValues",
    "tag_present": True,
    "source": "datahub",
}


def _state(sig, prior=None):
    return DriftState(drift_signal=sig, model_urn=MODEL, prior_causation=prior or {})


def test_match_true_for_same_feature_and_change_type():
    assert nodes._prior_matches(PRIOR, HARMFUL) is True


def test_match_false_for_a_different_feature():
    other = {"causation_value": "unit_change on feature Administrative (upstream x)"}
    assert nodes._prior_matches(other, HARMFUL) is False


def test_match_false_when_no_record():
    assert nodes._prior_matches({}, HARMFUL) is False


def test_route_recalls_when_prior_present():
    assert nodes.route_after_detect(_state(HARMFUL, PRIOR)) == "recall"


def test_route_traverses_when_no_prior():
    assert nodes.route_after_detect(_state(HARMFUL)) == "traverse"


def test_route_ends_when_benign():
    assert nodes.route_after_detect(_state(BENIGN)) == "end"


def test_detect_stashes_prior_when_it_matches(monkeypatch):
    monkeypatch.setattr(writeback, "read_recorded_state", lambda urn: PRIOR)
    out = nodes.detect(_state(HARMFUL))
    assert out["prior_causation"] == PRIOR


def test_detect_ignores_prior_that_does_not_match(monkeypatch):
    stale = {"causation_value": "unit_change on feature Administrative (upstream x)"}
    monkeypatch.setattr(writeback, "read_recorded_state", lambda urn: stale)
    out = nodes.detect(_state(HARMFUL))
    assert "prior_causation" not in out


def test_detect_never_reads_catalog_on_benign(monkeypatch):
    seen = []
    monkeypatch.setattr(writeback, "read_recorded_state", lambda urn: seen.append(urn))
    out = nodes.detect(_state(BENIGN))
    assert "prior_causation" not in out
    assert seen == []  # a benign shift stops at Detect and touches nothing


def test_recall_node_reports_the_recorded_cause_and_skips_the_write_path():
    out = nodes.recall(_state(HARMFUL, PRIOR))
    text = " ".join(e["message"] for e in out["trace"])
    assert "PageValues" in text and "null_default_regression" in text
    assert "inherited the knowledge" in text
    # the recall path must NOT run the real split write-back or raise a second incident
    assert out["writeback_result"] == {"recalled": {"status": "recalled"}}


def test_recorded_value_round_trips_through_the_matcher():
    # the exact string the write path stores must satisfy the recall matcher, so a
    # real second run recognizes a real first run.
    value = writeback._causation_value({
        "change_type": "null_default_regression", "drifted_feature": "PageValues",
        "root_cause_urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)",
        "drift_metric": "roc_auc 0.808->0.7131 (label-free CBPE), drop 0.0949",
        "table_owner": "urn:li:corpGroup:data-engineering", "detected_at": "2026-07-08T00:00:00",
    })
    assert nodes._prior_matches({"causation_value": value}, HARMFUL) is True
