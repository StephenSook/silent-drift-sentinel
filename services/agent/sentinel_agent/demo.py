"""Deterministic demo mode: replay a recorded run with realistic timing, so the
stream is identical every time even if a provider or the catalog hiccups. Same
event shape as the live stream, so the UI code path is identical."""
from __future__ import annotations

import asyncio
import json
from typing import Any

_TABLE = "urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)"

_RCA = (
    "CBPE-estimated ROC AUC for online_shoppers_purchase_intent dropped from 0.808 to 0.713 "
    "(-0.095), label-free since ground truth is not yet available for the current window. "
    "The drift scan attributes this to PageValues, which now emits a constant default in the "
    "upstream web_sessions table (a null/default regression), removing the model's strongest "
    "signal. This is lineage-guided correlation, not proof. Recommended fix: restore the "
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
        (0.6, "trace", {"node": "write_back", "kind": "tool_call", "message": "Writing drift_causation property, drift-degraded tag, and RCA document on the model, plus an incident on the upstream table"}),
        (1.0, "writeback", {
            "causation": {
                "drifted_feature": "PageValues", "root_cause_urn": _TABLE,
                "change_type": "null_default_regression",
                "drift_metric": "roc_auc 0.808->0.7131 (label-free CBPE), drop 0.0949",
                "model_owner": "urn:li:corpuser:jane.doe",
                "table_owner": "urn:li:corpGroup:data-engineering",
                "detected_at": "2026-07-07T22:23:47+00:00",
            },
            "result": {k: {"status": "done"} for k in ("structured_property", "tag", "document", "incident")},
        }),
        (0.4, "trace", {"node": "write_back", "kind": "tool_result", "message": "Wrote: structured_property=done, tag=done, document=done, incident=done"}),
    ]


async def demo_stream(model_urn: str):
    yield {"event": "start", "data": json.dumps({"model_urn": model_urn, "mode": "demo"})}
    for delay, event, data in _recorded(model_urn):
        await asyncio.sleep(delay)
        yield {"event": event, "data": json.dumps(data)}
    yield {"event": "done", "data": json.dumps({"ok": True})}
