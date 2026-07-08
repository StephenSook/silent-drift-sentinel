"""Claude produces the root-cause narrative (prose only). It never decides what
to write structurally, so it stays out of the write path."""
from __future__ import annotations

import json
from typing import Any

from langchain_anthropic import ChatAnthropic

from . import config

RCA_SYSTEM = (
    "You are an on-call ML reliability agent writing a root-cause analysis for the "
    "engineer who owns a production model. Be factual, specific, and technical. "
    "State: the estimated performance impact (note it is label-free, from CBPE), the "
    "drifted feature, the upstream table and the change type, and a concrete recommended "
    "fix. Do not overstate: this is lineage-guided correlation, not proof. "
    "Plain builder voice, no marketing language, no em-dashes. 4 to 7 sentences."
)


def _sanitize(text: str) -> str:
    # honor the project em-dash ban even if the model slips
    return text.replace(" — ", ", ").replace("—", ", ").replace("–", "-")


def _extract(content: Any) -> str:
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict))


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
        llm = ChatAnthropic(
            model=config.ANTHROPIC_MODEL, api_key=config.ANTHROPIC_API_KEY, max_tokens=700,
        )
        msg = llm.invoke([("system", RCA_SYSTEM), ("human", human)])
        return _sanitize(_extract(msg.content).strip())
    except Exception:  # noqa: BLE001 - provider failover so a live run survives an outage
        import litellm
        resp = litellm.completion(
            model=config.FALLBACK_MODEL,
            messages=[{"role": "system", "content": RCA_SYSTEM},
                      {"role": "user", "content": human}],
            max_tokens=700,
        )
        return _sanitize((resp.choices[0].message.content or "").strip())
