"""The agentic root-cause loop is the primary-track differentiator, but it must never
break the live run. These tests pin the wiring: which path root_cause takes, that the
tool set handed to Claude is restricted to the reliable reads, that a per-request flag
turns it on, and that any failure falls back to the single synthesis. The loop itself
(real Claude + real tools + live streaming) is verified live; here we mock both so the
tests are hermetic (no LangChain, no network; get_stream_writer is absent, so the
tool calls land in the returned trace rather than the custom stream)."""
import pytest

from sentinel_agent import config, datahub_io, llm, nodes
from sentinel_agent.state import DriftState

SIG = {"harmful": True, "root_cause_feature": "PageValues",
       "change_type": "null_default_regression", "performance": {}}


class FakeTool:
    def __init__(self, name):
        self.name = name


def _state(agentic=False):
    return DriftState(drift_signal=SIG, model_urn="urn:li:mlModel:m",
                      source_table="urn:li:dataset:t", lineage={"nodes": []}, agentic=agentic)


def _boom(*_a, **_k):
    raise AssertionError("this path must not be taken")


def test_single_synthesis_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", False)
    monkeypatch.setattr(datahub_io, "gather_ack_context",
                        lambda m, t: ({}, [{"tool": "get_entities", "summary": "read owner"}]))
    monkeypatch.setattr(llm, "synthesize_rca", lambda s, lin, ack_context=None: "SYNTH RCA")
    monkeypatch.setattr(llm, "agentic_rca", _boom)  # must not run when the flag is off
    out = nodes.root_cause(_state())
    assert out["rca_narrative"] == "SYNTH RCA"
    assert any(e["kind"] == "result" and e["message"] == "SYNTH RCA" for e in out["trace"])


def test_agentic_loop_used_and_tools_restricted(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", True)
    monkeypatch.setattr(datahub_io, "agent_context_tools",
                        lambda: [FakeTool("get_entities"), FakeTool("search"), FakeTool("get_lineage")])
    seen = {}

    def fake_agentic(s, lin, tools, m, st, emit=None):
        seen["tools"] = [t.name for t in tools]
        return "AGENTIC RCA", [{"tool": "get_lineage", "summary": "walked lineage (11 upstream assets)"}]

    monkeypatch.setattr(llm, "agentic_rca", fake_agentic)
    monkeypatch.setattr(llm, "synthesize_rca", _boom)  # must not fall back on success
    out = nodes.root_cause(_state())
    assert out["rca_narrative"] == "AGENTIC RCA"
    assert seen["tools"] == ["get_entities", "get_lineage"]  # the flaky search read is dropped
    assert any("get_lineage" in e["message"] for e in out["trace"])


def test_per_request_state_flag_turns_agentic_on(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", False)  # env off, but the request opts in
    monkeypatch.setattr(datahub_io, "agent_context_tools", lambda: [FakeTool("get_lineage")])
    monkeypatch.setattr(llm, "agentic_rca",
                        lambda s, lin, tools, m, st, emit=None: ("AGENTIC RCA", []))
    monkeypatch.setattr(llm, "synthesize_rca", _boom)
    out = nodes.root_cause(_state(agentic=True))
    assert out["rca_narrative"] == "AGENTIC RCA"


def test_agentic_failure_falls_back_to_synthesis(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", True)
    monkeypatch.setattr(datahub_io, "agent_context_tools", lambda: [FakeTool("get_lineage")])

    def raises(*_a, **_k):
        raise RuntimeError("live loop failed")

    monkeypatch.setattr(llm, "agentic_rca", raises)
    monkeypatch.setattr(datahub_io, "gather_ack_context",
                        lambda m, t: ({}, [{"tool": "get_entities", "summary": "read owner"}]))
    monkeypatch.setattr(llm, "synthesize_rca", lambda s, lin, ack_context=None: "FALLBACK RCA")
    out = nodes.root_cause(_state())
    assert out["rca_narrative"] == "FALLBACK RCA"


@pytest.mark.parametrize("out,expect", [
    ({"upstreams": {"total": 11}}, "upstream assets"),
    ({"name": "x", "owner": "y"}, "read"),
    ("web_sessions", "read"),
])
def test_tool_summary_is_a_short_phrase(out, expect):
    assert expect in llm._tool_summary("get_lineage", out)
