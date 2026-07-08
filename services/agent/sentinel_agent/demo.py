"""Deterministic demo mode: replay a recorded run with realistic timing, so the
stream is identical every time even if a provider or the catalog hiccups. Same
event shape as the live stream, so the UI code path is identical."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from . import fixgen, writeback

_TABLE = "urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)"

_CAUSATION = {
    "drifted_feature": "PageValues", "root_cause_urn": _TABLE,
    "change_type": "null_default_regression",
    "drift_metric": "roc_auc 0.808->0.7131 (label-free CBPE), drop 0.0949",
    "model_owner": "urn:li:corpuser:jane.doe",
    "table_owner": "urn:li:corpGroup:data-engineering",
    "detected_at": "2026-07-07T22:23:47+00:00",
}

_FIX = fixgen.generate_fix(_CAUSATION, {"reference": {"min": 0, "max": 361}})

_RCA = (
    "CBPE-estimated ROC AUC for online_shoppers_purchase_intent dropped from 0.808 to 0.713 "
    "(-0.095), label-free since ground truth is not yet available for the current window. "
    "The drift scan attributes this to PageValues, which now emits a constant default in the "
    "upstream web_sessions table (a null/default regression), removing the model's strongest "
    "signal. This is lineage-guided correlation, not proof. Recommended fix: restore the "
    "PageValues population in the web_sessions pipeline and backfill the affected window."
)

# A second harmful scenario, a DIFFERENT bug class: an upstream default fill pins
# ~95% of PageValues rows to one dominant value (a default_value_regression, not a
# full null collapse). Same lineage walk and write-back, but the agent classifies a
# different change_type and generates a not_constant guardrail instead of not_null.
_CAUSATION_DEFAULT = {
    "drifted_feature": "PageValues", "root_cause_urn": _TABLE,
    "change_type": "default_value_regression",
    "drift_metric": "roc_auc 0.808->0.7251 (label-free CBPE), drop 0.0829",
    "model_owner": "urn:li:corpuser:jane.doe",
    "table_owner": "urn:li:corpGroup:data-engineering",
    "detected_at": "2026-07-07T22:23:47+00:00",
}

_FIX_DEFAULT = fixgen.generate_fix(_CAUSATION_DEFAULT, {"reference": {"min": 0, "max": 361}})

_RCA_DEFAULT = (
    "CBPE-estimated ROC AUC for online_shoppers_purchase_intent dropped from 0.808 to 0.725 "
    "(-0.083), label-free since ground truth is not yet available for the current window. "
    "The drift scan attributes this to PageValues, where an upstream default fill now pins "
    "about 95% of rows in the web_sessions table to a single dominant value (a default-value "
    "regression, distinct from a full null collapse), flattening the model's strongest signal. "
    "This is lineage-guided correlation, not proof. Recommended fix: restore the real "
    "PageValues population in the web_sessions pipeline and backfill the affected window."
)


def _recorded(model_urn: str) -> list[dict[str, Any]]:
    return [
        (0.4, "trace", {"node": "detect", "kind": "info", "message": f"Drift signal received for {model_urn}"}),
        (0.7, "trace", {"node": "detect", "kind": "alarm", "message": "Harmful drift: roc_auc 0.808 -> 0.7131 (label-free CBPE), drop 0.0949"}),
        (0.6, "trace", {"node": "traverse", "kind": "tool_call", "message": "Walking DataHub lineage: model -> features -> source table -> owner"}),
        (0.9, "trace", {"node": "traverse", "kind": "tool_result", "message": f"Reached upstream table {_TABLE} via feature PageValues; table owner urn:li:corpGroup:data-engineering"}),
        (0.5, "trace", {"node": "root_cause", "kind": "tool_call", "message": "get_entities (Agent Context Kit): fetched model metadata + owner"}),
        (0.5, "trace", {"node": "root_cause", "kind": "tool_call", "message": "get_lineage (Agent Context Kit): walked upstream lineage (11 upstream assets)"}),
        (0.5, "trace", {"node": "root_cause", "kind": "tool_call", "message": "get_entities (Agent Context Kit): fetched upstream table schema + owner"}),
        (0.4, "trace", {"node": "root_cause", "kind": "thinking", "message": "Synthesizing root-cause analysis over the catalog context"}),
        (1.4, "trace", {"node": "root_cause", "kind": "result", "message": _RCA}),
        (0.5, "trace", {"node": "identify_owner", "kind": "result", "message": "Owner to notify: urn:li:corpGroup:data-engineering"}),
        (0.6, "trace", {"node": "propose_fix", "kind": "tool_call", "message": f"Generating a data-quality guardrail for {_FIX['column']} in {_FIX['table']} ({_FIX['change_type']})"}),
        (0.9, "trace", {"node": "propose_fix", "kind": "result", "message": f"Proposed fix: {_FIX['summary']}", "fix": _FIX}),
        (0.7, "awaiting_approval", {"thread_id": "demo", "causation": _CAUSATION, "proposed_fix": _FIX}),
        (1.2, "trace", {"node": "write_back", "kind": "tool_call", "message": "Writing drift_causation + proposed_fix properties, the drift-degraded tag, and the RCA onto the model, plus an incident on the upstream table"}),
        (1.0, "writeback", {
            "causation": _CAUSATION,
            "proposed_fix": _FIX,
            "result": {k: {"status": "done"} for k in ("structured_property", "tag", "document", "proposed_fix", "incident", "slack")},
        }),
        (0.4, "trace", {"node": "write_back", "kind": "tool_result", "message": "Wrote: structured_property=done, tag=done, document=done, proposed_fix=done, incident=done. Notified data-engineering in Slack."}),
    ]


def _recorded_default(model_urn: str) -> list[dict[str, Any]]:
    return [
        (0.4, "trace", {"node": "detect", "kind": "info", "message": f"Drift signal received for {model_urn}"}),
        (0.7, "trace", {"node": "detect", "kind": "alarm", "message": "Harmful drift: roc_auc 0.808 -> 0.7251 (label-free CBPE), drop 0.0829"}),
        (0.6, "trace", {"node": "traverse", "kind": "tool_call", "message": "Walking DataHub lineage: model -> features -> source table -> owner"}),
        (0.9, "trace", {"node": "traverse", "kind": "tool_result", "message": f"Reached upstream table {_TABLE} via feature PageValues; table owner urn:li:corpGroup:data-engineering"}),
        (0.5, "trace", {"node": "root_cause", "kind": "tool_call", "message": "get_entities (Agent Context Kit): fetched model metadata + owner"}),
        (0.5, "trace", {"node": "root_cause", "kind": "tool_call", "message": "get_lineage (Agent Context Kit): walked upstream lineage (11 upstream assets)"}),
        (0.5, "trace", {"node": "root_cause", "kind": "tool_call", "message": "get_entities (Agent Context Kit): fetched upstream table schema + owner"}),
        (0.4, "trace", {"node": "root_cause", "kind": "thinking", "message": "Synthesizing root-cause analysis over the catalog context"}),
        (1.4, "trace", {"node": "root_cause", "kind": "result", "message": _RCA_DEFAULT}),
        (0.5, "trace", {"node": "identify_owner", "kind": "result", "message": "Owner to notify: urn:li:corpGroup:data-engineering"}),
        (0.6, "trace", {"node": "propose_fix", "kind": "tool_call", "message": f"Generating a data-quality guardrail for {_FIX_DEFAULT['column']} in {_FIX_DEFAULT['table']} ({_FIX_DEFAULT['change_type']})"}),
        (0.9, "trace", {"node": "propose_fix", "kind": "result", "message": f"Proposed fix: {_FIX_DEFAULT['summary']}", "fix": _FIX_DEFAULT}),
        (0.7, "awaiting_approval", {"thread_id": "demo", "causation": _CAUSATION_DEFAULT, "proposed_fix": _FIX_DEFAULT}),
        (1.2, "trace", {"node": "write_back", "kind": "tool_call", "message": "Writing drift_causation + proposed_fix properties, the drift-degraded tag, and the RCA onto the model, plus an incident on the upstream table"}),
        (1.0, "writeback", {
            "causation": _CAUSATION_DEFAULT,
            "proposed_fix": _FIX_DEFAULT,
            "result": {k: {"status": "done"} for k in ("structured_property", "tag", "document", "proposed_fix", "incident", "slack")},
        }),
        (0.4, "trace", {"node": "write_back", "kind": "tool_result", "message": "Wrote: structured_property=done, tag=done, document=done, proposed_fix=done, incident=done. Notified data-engineering in Slack."}),
    ]


def _recorded_benign(model_urn: str) -> list[Any]:
    return [
        (0.4, "trace", {"node": "detect", "kind": "info", "message": f"Drift signal received for {model_urn}"}),
        (1.1, "trace", {"node": "detect", "kind": "info", "message": "PageValues shifted hard (a unit rescale, roughly x100), so raw input drift is high. CBPE estimates performance is unchanged (0.808 -> 0.815, label-free): the model is a gradient-boosted tree, invariant to a monotonic rescale."}),
        (0.8, "trace", {"node": "detect", "kind": "result", "message": "No alarm. No lineage walk, no write-back, nobody paged. Drift is not degradation, and the agent does not cry wolf."}),
    ]


def _recorded_recall(model_urn: str) -> list[Any]:
    """The close-the-loop beat: a re-run recognizes the cause the Sentinel already
    wrote onto the model and short-circuits, instead of re-diagnosing."""
    value = writeback._causation_value(_CAUSATION)
    return [
        (0.4, "trace", {"node": "detect", "kind": "info", "message": f"Drift signal received for {model_urn}"}),
        (0.7, "trace", {"node": "detect", "kind": "alarm", "message": "Harmful drift: roc_auc 0.808 -> 0.7131 (label-free CBPE), drop 0.0949"}),
        (0.7, "trace", {"node": "detect", "kind": "info", "message": "A drift_causation record already exists on this model in the catalog; this matches a cause the Sentinel already diagnosed"}),
        (0.6, "trace", {"node": "recall", "kind": "tool_call", "message": "Reading the drift_causation the Sentinel previously wrote back from the catalog"}),
        (1.1, "trace", {"node": "recall", "kind": "result", "message": f"Known cause, already on record: {value}"}),
        (0.7, "trace", {"node": "recall", "kind": "info", "message": f"A proposed fix is already recorded on the model: {_FIX['summary']}"}),
        (0.9, "trace", {"node": "recall", "kind": "result", "message": "No re-diagnosis and no duplicate incident. The next on-call agent inherited the knowledge from the model itself."}),
    ]


async def demo_stream(model_urn: str, scenario: str = "harmful"):
    if scenario == "benign":
        recorded = _recorded_benign(model_urn)
    elif scenario == "recall":
        recorded = _recorded_recall(model_urn)
    elif scenario == "default":
        recorded = _recorded_default(model_urn)
    else:
        recorded = _recorded(model_urn)
    yield {"event": "start", "data": json.dumps({"model_urn": model_urn, "mode": "demo"})}
    for delay, event, data in recorded:
        await asyncio.sleep(delay)
        yield {"event": event, "data": json.dumps(data)}
    yield {"event": "done", "data": json.dumps({"ok": True})}
