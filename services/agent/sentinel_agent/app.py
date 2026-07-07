"""FastAPI service that streams the agent run to the UI as Server-Sent Events.

Each LangGraph node update becomes one or more SSE events, so the front end can
render the agent detecting, traversing, reasoning, and writing back in real time.
A demo mode replays a recorded run so the stream is identical every time.
"""
from __future__ import annotations

import json
import os
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

_SIGNAL = pathlib.Path(__file__).resolve().parents[3] / "ml" / "artifacts" / "drift_signal.json"
_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


def _load_signal() -> dict:
    return json.loads(_SIGNAL.read_text())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/signal")
def signal() -> dict:
    return _load_signal()


@app.get("/api/lineage")
def lineage() -> dict:
    sig = _load_signal()
    return datahub_io.lineage_graph(config.MODEL_URN, sig.get("root_cause_feature", ""))


@app.get("/api/drift")
def drift() -> dict:
    p = _SIGNAL.parent / "drift_chart.json"
    return json.loads(p.read_text()) if p.exists() else {}


async def _live_stream():
    sig = _load_signal()
    graph = build_graph()
    init = DriftState(
        drift_signal=sig, model_urn=config.MODEL_URN,
        root_cause_feature=sig.get("root_cause_feature", ""),
    )
    yield {"event": "start", "data": json.dumps({"model_urn": config.MODEL_URN, "mode": "live"})}
    async for chunk in graph.astream(init, stream_mode="updates"):
        for _node, update in chunk.items():
            for ev in (update.get("trace") or []):
                yield {"event": "trace", "data": json.dumps(ev)}
            if update.get("writeback_result"):
                yield {"event": "writeback", "data": json.dumps(
                    {"causation": update.get("causation"), "result": update.get("writeback_result")},
                    default=str,
                )}
    yield {"event": "done", "data": json.dumps({"ok": True})}


@app.get("/api/stream")
async def stream(demo_mode: bool = False):
    gen = demo.demo_stream(config.MODEL_URN) if demo_mode else _live_stream()
    return EventSourceResponse(gen, headers=_SSE_HEADERS)
