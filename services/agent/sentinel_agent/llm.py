"""Claude produces the root-cause narrative (prose only). It never decides what
to write structurally, so it stays out of the write path."""
from __future__ import annotations

import json
from typing import Any

from . import config

RCA_SYSTEM = (
    "You are an on-call ML reliability agent writing a root-cause analysis for the "
    "engineer who owns a production model. Be factual, specific, and technical. "
    "State: the estimated performance impact (note it is label-free, from CBPE), the "
    "drifted feature, the upstream table and the change type, and a concrete recommended "
    "fix. Do not overstate: this is lineage-guided correlation, not proof. "
    "Plain builder voice, no marketing language, no em-dashes. 4 to 7 sentences."
)

AGENTIC_SYSTEM = (
    "You are an on-call ML reliability agent. A production model is silently degrading. "
    "You have read-only DataHub tools (the Agent Context Kit): entity metadata, lineage, "
    "and ownership. Investigate the catalog with these tools to confirm the upstream "
    "source of the drift before you conclude, then write the root-cause analysis. When "
    "you have enough evidence, stop calling tools and write the final RCA as prose: the "
    "label-free performance impact (CBPE), the drifted feature, the upstream table and "
    "the change type, the owner to notify, and a concrete fix. Do not overstate: this is "
    "lineage-guided correlation, not proof. Plain builder voice, no marketing language, "
    "no em-dashes, 4 to 7 sentences."
)


def _sanitize(text: str) -> str:
    # honor the project em-dash ban even if the model slips
    return text.replace(" — ", ", ").replace("—", ", ").replace("–", "-")


def _extract(content: Any) -> str:
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict))


def _fallback_rca(drift_signal: dict[str, Any], lineage: dict[str, Any]) -> str:
    """Deterministic RCA floor: if BOTH LLM providers fail, the live run still emits
    a sensible narrative instead of crashing the SSE stream mid-demo."""
    feat = drift_signal.get("root_cause_feature") or drift_signal.get("drifted_feature") or "the drifted feature"
    metric = drift_signal.get("drift_metric") or drift_signal.get("estimated_metric") or "an estimated performance drop"
    change = drift_signal.get("change_type", "an upstream data change")
    table = next(
        (n.get("label") for n in lineage.get("nodes", [])
         if n.get("kind") == "dataset" and n.get("status") == "changed"),
        "the upstream source table",
    )
    return _sanitize(
        f"The model's label-free performance estimate (CBPE) shows {metric}. The Sentinel "
        f"traced this to {change} on the feature {feat}, sourced from {table}. This is "
        f"lineage-guided correlation, not proof: the drift in {feat} coincides with the "
        f"model degradation along the exact upstream path. Recommended fix: add a "
        f"data-quality guard on {feat} in {table} (a not-null / range assertion), correct "
        f"the affected rows, then re-validate the model."
    )


def synthesize_rca(drift_signal: dict[str, Any], lineage: dict[str, Any],
                   ack_context: list[dict[str, str]] | None = None) -> str:
    human = (
        f"Drift signal:\n{json.dumps(drift_signal, indent=2)}\n\n"
        f"Lineage the agent walked:\n{json.dumps(lineage, indent=2)}\n\n"
    )
    if ack_context:
        human += (
            f"Catalog reads via the Agent Context Kit:\n{json.dumps(ack_context, indent=2)}\n\n"
        )
    human += "Write the RCA."
    try:
        # imported at call time so the pure agent modules stay importable (and the
        # hermetic tests run) without the heavy LangChain dependency present.
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model=config.ANTHROPIC_MODEL, api_key=config.ANTHROPIC_API_KEY, max_tokens=700,
            timeout=config.LLM_TIMEOUT, max_retries=1,
        )
        msg = llm.invoke([("system", RCA_SYSTEM), ("human", human)])
        return _sanitize(_extract(msg.content).strip())
    except Exception:  # noqa: BLE001 - primary provider failed; try the cross-provider fallback
        try:
            import litellm
            resp = litellm.completion(
                model=config.FALLBACK_MODEL,
                messages=[{"role": "system", "content": RCA_SYSTEM},
                          {"role": "user", "content": human}],
                max_tokens=700, timeout=config.LLM_TIMEOUT,
            )
            return _sanitize((resp.choices[0].message.content or "").strip())
        except Exception:  # noqa: BLE001 - both providers down: deterministic floor keeps the run alive
            return _fallback_rca(drift_signal, lineage)


def _tool_summary(name: str, out: Any) -> str:
    """A short, honest phrase describing what an Agent Context Kit tool call returned,
    for the streamed trace."""
    if isinstance(out, dict):
        ups = out.get("upstreams")
        if isinstance(ups, dict) and ups.get("total") is not None:
            return f"walked lineage ({ups['total']} upstream assets)"
        keys = ", ".join(list(out.keys())[:3])
        return f"read {keys}" if keys else "read entity"
    text = str(out)
    return f"read {text[:60]}" if text else "read entity"


def agentic_rca(drift_signal: dict[str, Any], lineage: dict[str, Any], tools: list,
                model_urn: str, source_table: str, emit=None) -> tuple[str, list[dict[str, str]]]:
    """A real Claude tool-calling loop: Claude decides which Agent Context Kit reads to
    make (entities, lineage, ownership) to confirm the cause, then writes the RCA. This
    is the agent genuinely using the catalog, not reasoning over a fixed context blob.
    Returns (narrative, tool_call_log). Raises on failure so the caller can fall back.
    If `emit` is given, each tool call is pushed to it live (for streaming to the UI)."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    base = ChatAnthropic(
        model=config.ANTHROPIC_MODEL, api_key=config.ANTHROPIC_API_KEY, max_tokens=900,
        timeout=config.LLM_TIMEOUT, max_retries=1,
    )
    llm = base.bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}
    human = (
        f"Model: {model_urn}\nUpstream table under suspicion: {source_table}\n\n"
        f"Drift signal:\n{json.dumps(drift_signal, indent=2)}\n\n"
        f"Lineage the agent already walked:\n{json.dumps(lineage, indent=2)}\n\n"
        "Investigate with the tools to confirm the upstream cause, then write the RCA."
    )
    messages: list = [SystemMessage(content=AGENTIC_SYSTEM), HumanMessage(content=human)]
    log: list[dict[str, str]] = []
    ai = None
    for _ in range(max(1, config.AGENTIC_MAX_STEPS)):
        ai = llm.invoke(messages)
        messages.append(ai)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            break
        for tc in calls:
            tool = tools_by_name.get(tc["name"])
            try:
                out = tool.invoke(tc["args"]) if tool is not None else f"unknown tool {tc['name']}"
                summary = _tool_summary(tc["name"], out)
            except Exception as e:  # noqa: BLE001 - a tool error is fed back, not fatal
                out = f"error: {type(e).__name__}: {e}"
                summary = f"error: {type(e).__name__}"
            log.append({"tool": tc["name"], "summary": summary})
            if emit is not None:
                emit({"node": "root_cause", "kind": "tool_call",
                      "message": f"{tc['name']} (Agent Context Kit): {summary}"})
            messages.append(ToolMessage(content=str(out)[:4000], tool_call_id=tc["id"]))
        # fill the gap while Claude reasons over the tool results into the final RCA
        if emit is not None:
            emit({"node": "root_cause", "kind": "thinking",
                  "message": "Reading the catalog results and reasoning about the cause"})
    narrative = _extract(ai.content).strip() if ai is not None else ""
    if not narrative:
        # the loop ended on a tool call; force a final prose synthesis with no tools
        messages.append(HumanMessage(content="Write the final RCA now, prose only, no tool calls."))
        narrative = _extract(base.invoke(messages).content).strip()
    if not narrative:
        raise RuntimeError("agentic RCA produced no narrative")
    return _sanitize(narrative), log
