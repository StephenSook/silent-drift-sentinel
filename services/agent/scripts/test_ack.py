"""Probe the Agent Context Kit tools: list them and invoke a read against our
model, so we wire the genuine ACK read into the agent against real behavior."""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from sentinel_agent import datahub_io  # noqa: E402

MODEL = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)"
TABLE = "urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)"

tools = datahub_io.agent_context_tools()
print("ACK tools:")
for t in tools:
    try:
        keys = list(t.args.keys())
    except Exception:  # noqa: BLE001
        keys = "?"
    print(f"  {t.name}  args={keys}")

# try a couple of reads
for name, payload in [
    ("get_entities", {"urns": [MODEL]}),
    ("get_lineage", {"urn": MODEL, "direction": "upstream"}),
    ("search", {"query": "web_sessions"}),
]:
    tool = next((t for t in tools if t.name == name), None)
    if not tool:
        print(f"\n[{name}] not present")
        continue
    print(f"\n[{name}] schema={tool.args}")
    try:
        out = tool.invoke(payload)
        print(f"[{name}] OK -> {str(out)[:300]}")
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] invoke error with {payload}: {type(e).__name__}: {e}")
