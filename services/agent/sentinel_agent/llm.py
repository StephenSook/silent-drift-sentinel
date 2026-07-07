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


def synthesize_rca(drift_signal: dict[str, Any], lineage: dict[str, Any]) -> str:
    llm = ChatAnthropic(
        model=config.ANTHROPIC_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=700,
    )
    human = (
        f"Drift signal:\n{json.dumps(drift_signal, indent=2)}\n\n"
        f"Lineage the agent walked:\n{json.dumps(lineage, indent=2)}\n\n"
        "Write the RCA."
    )
    msg = llm.invoke([("system", RCA_SYSTEM), ("human", human)])
    content = msg.content if isinstance(msg.content, str) else " ".join(
        b.get("text", "") for b in msg.content if isinstance(b, dict)
    )
    return _sanitize(content.strip())
