"""The deterministic split write-back, executed by code (never the LLM):
  ON the model: a drift_causation structured property + a drift-degraded tag + a
    linked RCA document.
  ON the upstream dataset: a real incident (GraphQL raiseIncident).
A write-ahead log makes the whole thing idempotent: a re-run skips completed
writes, so a partial failure retries cleanly.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from datahub.emitter.mce_builder import make_tag_urn
from datahub.metadata.schema_classes import GlobalTagsClass, StructuredPropertiesClass

from . import config

SP_URN = "urn:li:structuredProperty:io.sentinel.drift_causation"


def _slug(urn: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", urn)[-80:]


def _wal_path(key: str):
    return config.WAL_DIR / f"{key}.json"


def _load_wal(key: str) -> dict[str, Any]:
    p = _wal_path(key)
    return json.loads(p.read_text()) if p.exists() else {"steps": {}}


def _save_wal(key: str, data: dict[str, Any]) -> None:
    config.WAL_DIR.mkdir(parents=True, exist_ok=True)
    _wal_path(key).write_text(json.dumps(data, indent=2))


def _graphql(query: str) -> dict[str, Any]:
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"{config.GMS_URL}/api/graphql", data=body, headers={"Content-Type": "application/json"}
    )
    if config.GMS_TOKEN:
        req.add_header("Authorization", f"Bearer {config.GMS_TOKEN}")
    with urllib.request.urlopen(req, timeout=25) as r:
        out = json.loads(r.read().decode())
    # a GraphQL-level failure returns HTTP 200 with an errors array; surface it
    # loudly instead of letting the step be silently marked done.
    if out.get("errors"):
        raise RuntimeError(f"GraphQL error: {out['errors']}")
    return out


def _causation_value(c: dict[str, Any]) -> str:
    table = (c.get("root_cause_urn") or "").split(",")
    table_name = table[1] if len(table) > 1 else c.get("root_cause_urn", "")
    return (
        f"{c['change_type']} on feature {c['drifted_feature']} (upstream {table_name}); "
        f"{c['drift_metric']}; notify {c['table_owner']}; detected {c['detected_at']}"
    )


def read_causation(model_urn: str) -> dict[str, Any] | None:
    """Re-fetch the drift_causation property + drift-degraded tag FROM DataHub, so
    the UI can prove the write-back landed on the real catalog (not just the agent's
    claim). Used by the write-back read-back check and the /api/verify endpoint.
    Returns None if the property is not present on the model."""
    from datahub.ingestion.graph.client import DataHubGraph, DataHubGraphConfig
    g = DataHubGraph(DataHubGraphConfig(server=config.GMS_URL, token=config.GMS_TOKEN))
    sp = g.get_aspect(model_urn, StructuredPropertiesClass)
    prop = next((a for a in (sp.properties or []) if a.propertyUrn == SP_URN), None) if sp else None
    if not prop:
        return None
    tags = g.get_aspect(model_urn, GlobalTagsClass)
    tag_present = bool(tags and any("drift-degraded" in t.tag for t in (tags.tags or [])))
    return {
        "property_urn": SP_URN,
        "value": prop.values[0] if prop.values else None,
        "tag_present": tag_present,
        "source": "datahub",
    }


def reset_writeback(model_urn: str, table_urn: str = "") -> dict[str, Any]:
    """Undo the write-back so the demo re-runs cleanly in front of judges: clear the
    drift_causation property + drift-degraded tag on the model, resolve the incident,
    and delete the write-ahead log so a re-run re-animates instead of skipping."""
    from datahub.emitter.mce_builder import make_tag_urn
    key = _slug(model_urn)
    wal = _load_wal(key)
    out: dict[str, Any] = {}

    # remove via GraphQL: the empty-aspect emit is rejected by the entity authz, but
    # these mutations go through the same edit path the write used.
    try:
        _graphql('mutation { removeStructuredProperties(input: { assetUrn: "%s", '
                 'structuredPropertyUrns: ["%s"] }) { properties { structuredProperty { urn } } } }'
                 % (model_urn, SP_URN))
        out["structured_property"] = "cleared"
    except Exception as e:  # noqa: BLE001
        out["structured_property"] = f"error: {type(e).__name__}"

    try:
        _graphql('mutation { removeTag(input: { tagUrn: "%s", resourceUrn: "%s" }) }'
                 % (make_tag_urn("drift-degraded"), model_urn))
        out["tag"] = "cleared"
    except Exception as e:  # noqa: BLE001
        out["tag"] = f"error: {type(e).__name__}"

    incident_urn = (wal.get("steps", {}).get("incident", {}) or {}).get("result")
    if isinstance(incident_urn, str) and incident_urn.startswith("urn:li:incident"):
        try:
            _graphql('mutation { updateIncidentStatus(urn: "%s", '
                     'input: { state: RESOLVED }) }' % incident_urn)
            out["incident"] = "resolved"
        except Exception as e:  # noqa: BLE001
            out["incident"] = f"error: {type(e).__name__}"
    else:
        out["incident"] = "none recorded"

    p = _wal_path(key)
    if p.exists():
        p.unlink()
        out["wal"] = "deleted"
    else:
        out["wal"] = "absent"
    return out


def write_back(model_urn: str, causation: dict[str, Any], rca_narrative: str,
               table_urn: str) -> dict[str, Any]:
    key = _slug(model_urn)
    wal = _load_wal(key)
    wal["causation"] = causation
    wal["model_urn"] = model_urn
    _save_wal(key, wal)

    results: dict[str, Any] = {}

    def step(name: str, fn) -> Any:
        if wal["steps"].get(name, {}).get("status") == "done":
            return {"status": "skipped", **wal["steps"][name]}
        try:
            out = fn()
            wal["steps"][name] = {"status": "done", "result": out}
        except Exception as e:  # noqa: BLE001 - one failed write must not kill the others; it stays retryable
            wal["steps"][name] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        _save_wal(key, wal)
        rec = wal["steps"][name]
        return {"status": rec["status"], **{k: v for k, v in rec.items() if k != "status"}}

    def _prop():
        # write via GraphQL (upsertStructuredProperties): the least-privilege service
        # token is authorized for this path, unlike the raw /aspects emit.
        value = _causation_value(causation)
        _graphql(
            'mutation { upsertStructuredProperties(input: { assetUrn: "%s", '
            'structuredPropertyInputParams: [{ structuredPropertyUrn: "%s", '
            'values: [{ stringValue: %s }] }] }) { properties { structuredProperty { urn } } } }'
            % (model_urn, SP_URN, json.dumps(value))
        )
        # read the property back from DataHub to confirm the write actually landed
        if not read_causation(model_urn):
            raise RuntimeError("drift_causation not present on read-back")
        return {"value": value, "verified": True}

    def _tag():
        # associate the pre-existing drift-degraded tag (the tag entity is created once
        # as infra; the agent only adds the association, staying least-privilege).
        _graphql('mutation { addTag(input: { tagUrn: "%s", resourceUrn: "%s" }) }'
                 % (make_tag_urn("drift-degraded"), model_urn))
        return "drift-degraded"

    def _doc():
        # the RCA narrative, written onto the model as its description: a visible,
        # rich artifact on the real DataHub model page.
        _graphql('mutation { updateDescription(input: { description: %s, resourceUrn: "%s" }) }'
                 % (json.dumps(rca_narrative), model_urn))
        return "rca-set-on-model-description"

    def _incident():
        table_name = table_urn.split(",")[1] if "," in table_urn else table_urn
        q = (
            "mutation { raiseIncident(input: { type: OPERATIONAL, "
            f'resourceUrn: "{table_urn}", '
            f'title: "Silent drift: {causation["change_type"]} on {causation["drifted_feature"]}", '
            f'description: "Traced from degraded model {model_urn}. {causation["drift_metric"]}. '
            f'Root cause in {table_name}. Owner: {causation["table_owner"]}." }}) }}'
        )
        out = _graphql(q)
        incident_urn = out.get("data", {}).get("raiseIncident")
        if not incident_urn:
            raise RuntimeError(f"raiseIncident returned no urn: {out}")
        return incident_urn

    def _slack() -> str:
        if not config.SLACK_WEBHOOK_URL:
            return "not configured"
        model_name = model_urn.split(",")[1] if "," in model_urn else model_urn
        table_name = table_urn.split(",")[1] if "," in table_urn else table_urn
        owner = (causation.get("table_owner") or "").split(":")[-1]
        text = (
            ":rotating_light: *Silent-Drift Sentinel* flagged a drift-degraded model\n"
            f"*Model:* `{model_name}`\n"
            f"*Cause:* `{causation.get('drifted_feature')}` "
            f"({causation.get('change_type')}) in `{table_name}`\n"
            f"*Impact:* {causation.get('drift_metric')}\n"
            f"*Owner to notify:* {owner}\n"
            "Recorded on the model (drift_causation property, drift-degraded tag, RCA doc). "
            "Incident raised on the upstream table."
        )
        body = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            config.SLACK_WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=10).read()
            return "notified"
        except Exception as e:  # noqa: BLE001 - a notification failure must not fail the write-back
            return f"error: {type(e).__name__}"

    results["structured_property"] = step("structured_property", _prop)
    results["tag"] = step("tag", _tag)
    results["document"] = step("document", _doc)
    results["incident"] = step("incident", _incident)
    results["slack"] = {"status": "done", "result": _slack()}
    return results
