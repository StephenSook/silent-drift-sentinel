"""The five graph nodes. Only root_cause calls the LLM (prose synthesis);
everything else is deterministic."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import datahub_io, fixgen, llm, writeback
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
    # Compute the causation object here, before the write-back gate, so the
    # human approving the write can see exactly what will be recorded.
    owner = state.table_owner or state.model_owner or "unknown"
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
    return {
        "causation": causation,
        "trace": [event("identify_owner", "result", f"Owner to notify: {owner}")],
    }


def propose_fix(state: DriftState) -> dict[str, Any]:
    # Metadata-aware code-gen: from the diagnosed change_type + the exact column and
    # upstream table, generate the data-quality guardrail that would have caught this
    # regression. Deterministic (template, not the LLM), so it stays out of the write path.
    fix = fixgen.generate_fix(state.causation, state.drift_signal)
    return {
        "proposed_fix": fix,
        "trace": [
            event("propose_fix", "tool_call",
                  f"Generating a data-quality guardrail for {fix['column']} in "
                  f"{fix['table']} ({fix['change_type']})"),
            event("propose_fix", "result", f"Proposed fix: {fix['summary']}", fix=fix),
        ],
    }


def write_back(state: DriftState) -> dict[str, Any]:
    # Reached only after the human-in-the-loop interrupt is resumed. Deterministic:
    # writes the causation computed upstream, never anything the LLM produced live.
    trace = [event("write_back", "tool_call",
                   "Writing drift_causation + proposed_fix properties, the drift-degraded tag, and "
                   "the RCA onto the model, plus an incident on the upstream table")]
    result = writeback.write_back(
        state.model_urn, state.causation, state.rca_narrative, state.source_table,
        proposed_fix=state.proposed_fix,
    )
    summary = ", ".join(f"{k}={v.get('status')}" for k, v in result.items())
    trace.append(event("write_back", "tool_result", f"Wrote: {summary}"))
    return {"writeback_result": result, "trace": trace}
