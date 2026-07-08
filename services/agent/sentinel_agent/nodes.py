"""The five graph nodes. Only root_cause calls the LLM (prose synthesis);
everything else is deterministic."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import config, datahub_io, fixgen, llm, writeback
from .state import DriftState, event


def _prior_matches(prior: dict[str, Any], signal: dict[str, Any]) -> bool:
    """True if a recorded drift_causation describes the same feature (and change type)
    as the current signal, so the agent can recognize its own prior diagnosis."""
    value = (prior or {}).get("causation_value") or ""
    feature = signal.get("root_cause_feature") or ""
    change_type = signal.get("change_type") or ""
    if not value or not feature or feature not in value:
        return False
    return not change_type or change_type in value


def route_after_detect(state: DriftState) -> str:
    """Route out of Detect: stop on a benign shift, recall a cause the agent already
    recorded on the model, otherwise walk the lineage for a fresh diagnosis."""
    if not state.drift_signal.get("harmful"):
        return "end"
    return "recall" if state.prior_causation else "traverse"


def detect(state: DriftState) -> dict[str, Any]:
    sig = state.drift_signal
    perf = sig.get("performance", {})
    trace = [event("detect", "info", f"Drift signal received for {state.model_urn}")]
    out: dict[str, Any] = {"root_cause_feature": sig.get("root_cause_feature", "")}
    if not sig.get("harmful"):
        trace.append(event("detect", "info", "Distribution drift detected but performance is unaffected; no alarm"))
        out["trace"] = trace
        return out
    trace.append(event(
        "detect", "alarm",
        f"Harmful drift: {perf.get('metric')} {perf.get('reference')} -> "
        f"{perf.get('estimated_current')} (label-free CBPE), drop {perf.get('estimated_drop')}",
    ))
    # close-the-loop: check whether the Sentinel already diagnosed and recorded this
    # exact cause on the model. If so, route to recall instead of re-doing the work.
    prior = writeback.read_recorded_state(state.model_urn)
    if prior and _prior_matches(prior, sig):
        out["prior_causation"] = prior
        trace.append(event(
            "detect", "info",
            "A drift_causation record already exists on this model in the catalog; "
            "this matches a cause the Sentinel already diagnosed",
        ))
    out["trace"] = trace
    return out


def recall(state: DriftState) -> dict[str, Any]:
    """The agent recognizes a cause it already recorded on the model and short-circuits:
    no re-diagnosis, no duplicate incident. The thesis made concrete, the next on-call
    agent inherits the knowledge straight from the model entity in the catalog."""
    prior = state.prior_causation or {}
    value = prior.get("causation_value") or ""
    fix = prior.get("fix_value")
    trace = [
        event("recall", "tool_call",
              "Reading the drift_causation the Sentinel previously wrote back from the catalog"),
        event("recall", "result", f"Known cause, already on record: {value}"),
    ]
    if fix:
        trace.append(event("recall", "info", f"A proposed fix is already recorded on the model: {fix}"))
    trace.append(event(
        "recall", "result",
        "No re-diagnosis and no duplicate incident. The next on-call agent inherited the "
        "knowledge from the model itself.",
    ))
    return {"trace": trace, "writeback_result": {"recalled": {"status": "recalled"}}}


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


# the reliable subset of the Agent Context Kit tools to hand the agentic loop (the
# broader set includes reads that error or add noise against a fresh catalog)
AGENTIC_TOOLS = ("get_entities", "get_lineage")


def _stream_writer():
    """The langgraph custom-stream writer if we are inside a streaming run, else None.
    Lets the agentic loop push each catalog read to the UI live instead of batching
    the whole investigation into one update at the end."""
    try:
        from langgraph.config import get_stream_writer
        return get_stream_writer()
    except Exception:  # noqa: BLE001 - not in a streaming context (tests, demo, approve)
        return None


def root_cause(state: DriftState) -> dict[str, Any]:
    # Reason over DataHub through the Agent Context Kit. Two modes: a real Claude
    # tool-calling loop (Claude decides which catalog reads to make, streamed live), or
    # a single synthesis over context gathered by fixed code. The agentic loop always
    # falls back to the synthesis on any error, so the live run can never break.
    use_agentic = state.agentic or config.AGENTIC_RCA
    narrative = ""
    ack_log: list[dict[str, str]] = []
    streamed_live = False
    if use_agentic:
        try:
            writer = _stream_writer()
            emit = None
            if writer is not None:
                emit = writer  # push each tool call to the custom stream as it happens
                streamed_live = True
            tools = [t for t in datahub_io.agent_context_tools() if t.name in AGENTIC_TOOLS]
            narrative, ack_log = llm.agentic_rca(
                state.drift_signal, state.lineage, tools, state.model_urn,
                state.source_table, emit=emit)
        except Exception:  # noqa: BLE001 - the agentic loop must never break the run
            narrative, ack_log, streamed_live = "", [], False
    if not narrative:
        _ctx, ack_log = datahub_io.gather_ack_context(state.model_urn, state.source_table)
        narrative = llm.synthesize_rca(state.drift_signal, state.lineage, ack_context=ack_log)
        streamed_live = False
    # when the tool calls streamed live, do not repeat them in the returned trace
    trace: list[dict[str, Any]] = [] if streamed_live else [
        event("root_cause", "tool_call", f"{e['tool']} (Agent Context Kit): {e['summary']}")
        for e in ack_log
    ]
    trace.append(event("root_cause", "thinking",
                       "Synthesizing root-cause analysis over the catalog context"))
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
