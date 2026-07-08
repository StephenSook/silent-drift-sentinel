"""FastAPI service that streams the agent run to the UI as Server-Sent Events.

Each LangGraph node update becomes one or more SSE events, so the front end can
render the agent detecting, traversing, reasoning, and writing back in real time.
A demo mode replays a recorded run so the stream is identical every time.
"""
from __future__ import annotations

import json
import os
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import MemorySaver
from sse_starlette.sse import EventSourceResponse

from . import config, datahub_io, demo
from .graph import build_graph
from .state import DriftState

app = FastAPI(title="Silent-Drift Sentinel Agent")
_ORIGINS = os.environ.get("SENTINEL_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


def _artifact(scenario: str, kind: str):
    # kind is "signal" or "chart"; the benign scenario reads the _benign variant
    suffix = "_benign" if scenario == "benign" else ""
    return config.ARTIFACTS_DIR / f"drift_{kind}{suffix}.json"

# HITL: one interrupt graph plus an in-process checkpointer. GET /api/stream runs
# the read-only nodes and stops before write_back (no mutation on a GET); the
# explicit POST /api/approve resumes the same thread to execute the write.
_CHECKPOINTER = MemorySaver()
_GRAPH = build_graph(checkpointer=_CHECKPOINTER, interrupt_before_writeback=True)


def _load_signal(scenario: str = "harmful") -> dict:
    return json.loads(_artifact(scenario, "signal").read_text())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/signal")
def signal(scenario: str = "harmful") -> dict:
    return _load_signal(scenario)


@app.get("/api/lineage")
def lineage(scenario: str = "harmful") -> dict:
    sig = _load_signal(scenario)
    return datahub_io.lineage_graph(
        config.MODEL_URN, sig.get("root_cause_feature", ""), harmful=bool(sig.get("harmful")),
    )


@app.get("/api/drift")
def drift(scenario: str = "harmful") -> dict:
    p = _artifact(scenario, "chart")
    return json.loads(p.read_text()) if p.exists() else {}


async def _live_stream(thread_id: str, scenario: str):
    sig = _load_signal(scenario)
    init = DriftState(
        drift_signal=sig, model_urn=config.MODEL_URN,
        root_cause_feature=sig.get("root_cause_feature", ""),
    )
    cfg = {"configurable": {"thread_id": thread_id}}
    yield {"event": "start", "data": json.dumps({"model_urn": config.MODEL_URN, "mode": "live"})}
    # runs detect -> traverse -> root_cause -> identify_owner, then interrupts
    async for chunk in _GRAPH.astream(init, config=cfg, stream_mode="updates"):
        for _node, update in chunk.items():
            if not isinstance(update, dict):  # e.g. the __interrupt__ marker
                continue
            for ev in (update.get("trace") or []):
                yield {"event": "trace", "data": json.dumps(ev)}
    # paused before write_back: ask the human to approve the mutation
    snap = _GRAPH.get_state(cfg)
    if snap.next and "write_back" in snap.next:
        yield {"event": "awaiting_approval", "data": json.dumps(
            {"thread_id": thread_id, "causation": snap.values.get("causation", {})}, default=str,
        )}
    else:
        yield {"event": "done", "data": json.dumps({"ok": True})}


@app.get("/api/stream")
async def stream(demo_mode: bool = False, scenario: str = "harmful"):
    if demo_mode:
        gen = demo.demo_stream(config.MODEL_URN, scenario)
    else:
        gen = _live_stream(uuid.uuid4().hex, scenario)
    return EventSourceResponse(gen, headers=_SSE_HEADERS)


@app.post("/api/approve")
async def approve(thread_id: str) -> dict:
    """Resume the interrupted graph to execute the write-back. This is the only
    path that mutates the catalog, and it is an explicit POST, not a GET."""
    cfg = {"configurable": {"thread_id": thread_id}}
    snap = _GRAPH.get_state(cfg)
    if not snap.next or "write_back" not in snap.next:
        return {"error": "no pending write-back for this thread"}
    trace: list = []
    writeback = None
    async for chunk in _GRAPH.astream(None, config=cfg, stream_mode="updates"):
        for _node, update in chunk.items():
            if not isinstance(update, dict):
                continue
            trace.extend(update.get("trace") or [])
            if update.get("writeback_result"):
                writeback = {
                    "causation": snap.values.get("causation", {}),
                    "result": update.get("writeback_result"),
                }
    return {"trace": trace, "writeback": json.loads(json.dumps(writeback, default=str))}
