"""The five graph nodes. Only root_cause calls the LLM (prose synthesis);
everything else is deterministic."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import datahub_io, llm, writeback
from .state import DriftState, event


def detect(state: DriftState) -> dict[str, Any]:
    sig = state.drift_signal
    perf = sig.get("performance", {})
    trace = [event("detect", "info", f"Drift signal received for {state.model_urn}")]
    if not sig.get("harmful"):
        trace.append(event("detect", "info", "Distribution drift detected but performance is unaffected; no alarm"))
    else:
        trace.append(event(
            "detect", "alarm",
            f"Harmful drift: {perf.get('metric')} {perf.get('reference')} -> "
            f"{perf.get('estimated_current')} (label-free CBPE), drop {perf.get('estimated_drop')}",
        ))
    return {"root_cause_feature": sig.get("root_cause_feature", ""), "trace": trace}


def traverse(state: DriftState) -> dict[str, Any]:
    trace = [event("traverse", "tool_call",
                   "Walking DataHub lineage: model -> features -> source table -> owner")]
    lin = datahub_io.traverse_lineage(state.model_urn, state.root_cause_feature)
    trace.append(event("traverse", "tool_result",
                       f"Reached upstream table {lin.get('source_table')} via feature "
                       f"{state.root_cause_feature}; table owner {lin.get('table_owner')}"))
    return {
        "lineage": lin,
        "source_table": lin.get("source_table") or "",
        "table_owner": lin.get("table_owner") or "",
        "model_owner": lin.get("model_owner") or "",
        "trace": trace,
    }


def root_cause(state: DriftState) -> dict[str, Any]:
    # Read DataHub through the Agent Context Kit tools, then reason over the result.
    _ctx, ack_log = datahub_io.gather_ack_context(state.model_urn, state.source_table)
    trace = [
        event("root_cause", "tool_call", f"{e['tool']} (Agent Context Kit): {e['summary']}")
        for e in ack_log
    ]
    trace.append(event("root_cause", "thinking",
                       "Synthesizing root-cause analysis over the catalog context"))
    narrative = llm.synthesize_rca(state.drift_signal, state.lineage, ack_context=ack_log)
    trace.append(event("root_cause", "result", narrative))
    return {"rca_narrative": narrative, "trace": trace}


def identify_owner(state: DriftState) -> dict[str, Any]:
    owner = state.table_owner or state.model_owner or "unknown"
    return {"trace": [event("identify_owner", "result", f"Owner to notify: {owner}")]}


def write_back(state: DriftState) -> dict[str, Any]:
    if not state.approved:
        return {"trace": [event("write_back", "blocked", "Awaiting human approval before writing to the catalog")]}
    sig = state.drift_signal
    perf = sig.get("performance", {})
    causation = {
        "drifted_feature": state.root_cause_feature,
        "root_cause_urn": state.source_table,
        "change_type": sig.get("change_type", "unknown"),
        "drift_metric": (f"{perf.get('metric')} {perf.get('reference')}->"
                         f"{perf.get('estimated_current')} (label-free CBPE), "
                         f"drop {perf.get('estimated_drop')}"),
        "model_owner": state.model_owner,
        "table_owner": state.table_owner,
        "detected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    trace = [event("write_back", "tool_call",
                   "Writing drift_causation property, drift-degraded tag, and RCA document on "
                   "the model, plus an incident on the upstream table")]
    result = writeback.write_back(state.model_urn, causation, state.rca_narrative, state.source_table)
    summary = ", ".join(f"{k}={v.get('status')}" for k, v in result.items())
    trace.append(event("write_back", "tool_result", f"Wrote: {summary}"))
    return {"causation": causation, "writeback_result": result, "trace": trace}
