"""FastAPI service that streams the agent run to the UI as Server-Sent Events.

Each LangGraph node update becomes one or more SSE events, so the front end can
render the agent detecting, traversing, reasoning, and writing back in real time.
A demo mode replays a recorded run so the stream is identical every time.
"""
from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import MemorySaver
from sse_starlette.sse import EventSourceResponse

from . import config, datahub_io, demo, writeback
from .graph import build_graph
from .state import DriftState


def _callbacks() -> list:
    """Langfuse tracing callback for the LangGraph run, if configured. LangGraph
    propagates it through every node, turning the run into a real judge-viewable
    trace. No-op (empty list) when Langfuse keys are absent or the SDK is missing."""
    if not config.LANGFUSE_ENABLED:
        return []
    try:
        try:
            from langfuse.langchain import CallbackHandler  # langfuse v3
        except ImportError:
            from langfuse.callback import CallbackHandler  # langfuse v2
        return [CallbackHandler()]
    except Exception as e:  # noqa: BLE001 - tracing must never break the agent
        print(f"[langfuse] disabled ({type(e).__name__})")
        return []


def _flush_langfuse() -> None:
    """Push queued traces to Langfuse now, so a judge who just ran the agent sees
    the trace immediately instead of waiting for the background flush interval."""
    if not config.LANGFUSE_ENABLED:
        return
    try:
        from langfuse import get_client
        get_client().flush()
    except Exception:  # noqa: BLE001 - tracing must never break the agent
        pass

# HITL: a durable Postgres checkpointer with an in-process fallback, plus the
# interrupt graph, built at startup. GET /api/stream runs the read-only nodes and
# stops before write_back; POST /api/approve resumes the same thread to write.
_GRAPH = None
_pool = None


@asynccontextmanager
async def _lifespan(_app):
    global _GRAPH, _pool
    checkpointer = MemorySaver()
    mode = "memory (in-process)"
    if config.DATABASE_URL:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool
            _pool = AsyncConnectionPool(
                conninfo=config.DATABASE_URL, max_size=5, open=False,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            )
            await _pool.open()
            saver = AsyncPostgresSaver(_pool)
            await saver.setup()
            checkpointer = saver
            mode = "postgres (durable)"
        except Exception as e:  # noqa: BLE001 - checkpoint storage must never block startup
            print(f"[checkpointer] postgres unavailable ({type(e).__name__}); falling back to memory")
    _GRAPH = build_graph(checkpointer=checkpointer, interrupt_before_writeback=True)
    print(f"[checkpointer] {mode}")
    yield
    if _pool is not None:
        await _pool.close()


app = FastAPI(title="Silent-Drift Sentinel Agent", lifespan=_lifespan)
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


@app.get("/api/model-card")
def model_card() -> dict:
    p = config.ARTIFACTS_DIR / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else {}


@app.get("/api/verify")
def verify() -> dict:
    """Live proof: re-fetch the drift_causation property back FROM DataHub so the UI
    shows it as confirmed by the catalog, not just claimed by the agent."""
    found = writeback.read_causation(config.MODEL_URN)
    return {"present": found is not None, "causation": found}


@app.post("/api/reset")
def reset() -> dict:
    """Clear the write-back (property + tag + incident + WAL) so the live demo
    re-runs cleanly from a pristine model for the next judge."""
    return {"reset": writeback.reset_writeback(config.MODEL_URN)}


async def _live_stream(thread_id: str, scenario: str):
    sig = _load_signal(scenario)
    init = DriftState(
        drift_signal=sig, model_urn=config.MODEL_URN,
        root_cause_feature=sig.get("root_cause_feature", ""),
    )
    cfg = {"configurable": {"thread_id": thread_id}, "callbacks": _callbacks()}
    yield {"event": "start", "data": json.dumps({"model_urn": config.MODEL_URN, "mode": "live"})}
    # runs detect -> traverse -> root_cause -> identify_owner, then interrupts
    async for chunk in _GRAPH.astream(init, config=cfg, stream_mode="updates"):
        for _node, update in chunk.items():
            if not isinstance(update, dict):  # e.g. the __interrupt__ marker
                continue
            for ev in (update.get("trace") or []):
                yield {"event": "trace", "data": json.dumps(ev)}
    _flush_langfuse()
    # paused before write_back: ask the human to approve the mutation
    snap = await _GRAPH.aget_state(cfg)
    if snap.next and "write_back" in snap.next:
        yield {"event": "awaiting_approval", "data": json.dumps(
            {"thread_id": thread_id, "causation": snap.values.get("causation", {}),
             "proposed_fix": snap.values.get("proposed_fix", {})}, default=str,
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
    cfg = {"configurable": {"thread_id": thread_id}, "callbacks": _callbacks()}
    snap = await _GRAPH.aget_state(cfg)
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
    _flush_langfuse()
    return {"trace": trace, "writeback": json.loads(json.dumps(writeback, default=str))}
