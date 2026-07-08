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
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DataHubRestEmitter
from datahub.metadata.schema_classes import (
    GlobalTagsClass,
    StructuredPropertiesClass,
    StructuredPropertyDefinitionClass,
    StructuredPropertyValueAssignmentClass,
    TagAssociationClass,
)
from datahub.sdk import DataHubClient

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
        return json.loads(r.read().decode())


def ensure_property_definition(emitter: DataHubRestEmitter) -> None:
    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=SP_URN,
        aspect=StructuredPropertyDefinitionClass(
            qualifiedName="io.sentinel.drift_causation",
            valueType="urn:li:dataType:datahub.string",
            entityTypes=["urn:li:entityType:datahub.mlModel", "urn:li:entityType:datahub.dataset"],
            displayName="Drift Causation",
            cardinality="SINGLE",
            description="The upstream data change the Silent-Drift Sentinel traced a model degradation to.",
        ),
    ))


def _causation_value(c: dict[str, Any]) -> str:
    table = (c.get("root_cause_urn") or "").split(",")
    table_name = table[1] if len(table) > 1 else c.get("root_cause_urn", "")
    return (
        f"{c['change_type']} on feature {c['drifted_feature']} (upstream {table_name}); "
        f"{c['drift_metric']}; notify {c['table_owner']}; detected {c['detected_at']}"
    )


def write_back(model_urn: str, causation: dict[str, Any], rca_narrative: str,
               table_urn: str) -> dict[str, Any]:
    key = _slug(model_urn)
    wal = _load_wal(key)
    wal["causation"] = causation
    wal["model_urn"] = model_urn
    _save_wal(key, wal)

    emitter = DataHubRestEmitter(gms_server=config.GMS_URL, token=config.GMS_TOKEN)
    client = DataHubClient(server=config.GMS_URL, token=config.GMS_TOKEN)
    results: dict[str, Any] = {}

    def step(name: str, fn) -> Any:
        if wal["steps"].get(name, {}).get("status") == "done":
            return {"status": "skipped", **wal["steps"][name]}
        out = fn()
        wal["steps"][name] = {"status": "done", "result": out}
        _save_wal(key, wal)
        return {"status": "done", "result": out}

    def _prop():
        ensure_property_definition(emitter)
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=model_urn,
            aspect=StructuredPropertiesClass(properties=[
                StructuredPropertyValueAssignmentClass(
                    propertyUrn=SP_URN, values=[_causation_value(causation)]
                )
            ]),
        ))
        return _causation_value(causation)

    def _tag():
        emitter.emit(MetadataChangeProposalWrapper(
            entityUrn=model_urn,
            aspect=GlobalTagsClass(tags=[TagAssociationClass(tag=make_tag_urn("drift-degraded"))]),
        ))
        return "drift-degraded"

    def _doc():
        from datahub.sdk.document import Document
        doc = Document.create_document(
            id=f"drift-rca-{key}",
            title=f"Drift RCA: {model_urn.split(',')[1]}",
            text=rca_narrative,
            related_assets=[model_urn],
        )
        client.entities.upsert(doc)
        return str(doc.urn)

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
        return out.get("data", {}).get("raiseIncident", out)

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
