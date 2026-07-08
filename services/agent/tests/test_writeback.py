"""The split write-back is the project's novel core; these tests pin the two
load-bearing invariants without a network: the WAL makes a re-run idempotent, and
the incident targets the DATASET while the properties/tag target the mlModel (the
'incidents cannot be raised on mlModel' design constraint)."""
from sentinel_agent import config, writeback

MODEL = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)"
TABLE = "urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)"
CAUSATION = {
    "change_type": "null_default_regression",
    "drifted_feature": "PageValues",
    "root_cause_urn": TABLE,
    "drift_metric": "roc_auc 0.808->0.7131 (label-free CBPE), drop 0.0949",
    "table_owner": "urn:li:corpGroup:data-engineering",
    "detected_at": "2026-07-08T00:00:00",
}


def test_causation_value_contains_the_key_facts():
    v = writeback._causation_value(CAUSATION)
    for token in ("null_default_regression", "PageValues", "ecommerce.web_sessions", "data-engineering"):
        assert token in v


def test_slug_is_filesystem_safe():
    s = writeback._slug(MODEL)
    assert "/" not in s and "(" not in s and ":" not in s


def _mock(monkeypatch, tmp_path):
    """Isolate the WAL, silence Slack, stub the read-back, and record every GraphQL
    mutation so the split can be asserted without hitting DataHub."""
    monkeypatch.setattr(config, "WAL_DIR", tmp_path)
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", None)
    monkeypatch.setattr(writeback, "read_causation", lambda urn: {"value": "present"})
    calls: list[str] = []
    monkeypatch.setattr(
        writeback, "_graphql",
        lambda q: (calls.append(q), {"data": {"raiseIncident": "urn:li:incident:test"}})[1],
    )
    return calls


def test_write_back_all_steps_done(monkeypatch, tmp_path):
    calls = _mock(monkeypatch, tmp_path)
    res = writeback.write_back(MODEL, CAUSATION, "rca narrative", TABLE, proposed_fix={"dbt": "x"})
    assert set(res) == {"structured_property", "tag", "document", "proposed_fix", "incident", "slack"}
    for k in ("structured_property", "tag", "document", "proposed_fix", "incident"):
        assert res[k]["status"] == "done"
    assert len(calls) >= 5  # property, tag, description, fix, incident


def test_incident_targets_dataset_not_model(monkeypatch, tmp_path):
    calls = _mock(monkeypatch, tmp_path)
    writeback.write_back(MODEL, CAUSATION, "rca", TABLE)
    incident = next(q for q in calls if "raiseIncident" in q)
    # the incident RESOURCE is the upstream dataset, never the mlModel (the metamodel
    # constraint). The model may still appear in the description as context.
    assert f'resourceUrn: "{TABLE}"' in incident
    assert f'resourceUrn: "{MODEL}"' not in incident


def test_property_and_fix_target_the_model(monkeypatch, tmp_path):
    calls = _mock(monkeypatch, tmp_path)
    writeback.write_back(MODEL, CAUSATION, "rca", TABLE, proposed_fix={"dbt": "x"})
    prop_writes = [q for q in calls if "upsertStructuredProperties" in q]
    assert prop_writes and all(MODEL in q for q in prop_writes)
    assert any(writeback.SP_URN in q for q in prop_writes)
    assert any(writeback.FIX_SP_URN in q for q in prop_writes)


def test_wal_makes_rerun_idempotent(monkeypatch, tmp_path):
    calls = _mock(monkeypatch, tmp_path)
    writeback.write_back(MODEL, CAUSATION, "rca", TABLE)
    n1 = len(calls)
    writeback.write_back(MODEL, CAUSATION, "rca", TABLE)  # re-run against the same WAL
    assert len(calls) == n1  # every step skipped from the WAL; no new catalog writes


def test_wal_rewrites_when_the_diagnosis_changes(monkeypatch, tmp_path):
    # the scenario-switch fix: a DIFFERENT cause must not reuse the prior run's WAL and
    # silently skip the catalog writes (which would leave the old cause on the model).
    calls = _mock(monkeypatch, tmp_path)
    writeback.write_back(MODEL, CAUSATION, "rca", TABLE)  # null_default_regression
    n1 = len(calls)
    other = {**CAUSATION, "change_type": "default_value_regression"}
    writeback.write_back(MODEL, other, "rca", TABLE)  # a structurally different cause
    assert len(calls) > n1  # the stale WAL is cleared, so the new cause is written
    assert any("default_value_regression" in q for q in calls)
