"""Run the agent once against the live DataHub, using the drift signal the ML
detector produced. This is the deterministic core loop end to end."""
from __future__ import annotations

import json
import pathlib

from sentinel_agent import config
from sentinel_agent.graph import build_graph
from sentinel_agent.state import DriftState

SIGNAL = pathlib.Path(__file__).resolve().parents[3] / "ml" / "artifacts" / "drift_signal.json"


def main() -> None:
    signal = json.loads(SIGNAL.read_text())
    app = build_graph()
    init = DriftState(
        drift_signal=signal,
        model_urn=config.MODEL_URN,
        root_cause_feature=signal.get("root_cause_feature", ""),
    )
    final = app.invoke(init)
    state = final if isinstance(final, dict) else final.model_dump()

    print("===== AGENT TRACE =====")
    for ev in state["trace"]:
        msg = ev["message"]
        print(f"[{ev['node']}/{ev['kind']}] {msg[:220]}")
    print("\n===== WRITE-BACK RESULT =====")
    print(json.dumps(state["writeback_result"], indent=2, default=str))


if __name__ == "__main__":
    main()
