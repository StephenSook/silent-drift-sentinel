"""The agentic root-cause loop is the primary-track differentiator, but it must never
break the live run. These tests pin the wiring: which path root_cause takes, and that
a failure in the agentic loop always falls back to the single synthesis. The loop
itself (real Claude + real tools) is verified live; here we mock both so the tests are
hermetic (no LangChain, no network)."""
import pytest

from sentinel_agent import config, datahub_io, llm, nodes
from sentinel_agent.state import DriftState

SIG = {"harmful": True, "root_cause_feature": "PageValues",
       "change_type": "null_default_regression", "performance": {}}


def _state():
    return DriftState(drift_signal=SIG, model_urn="urn:li:mlModel:m",
                      source_table="urn:li:dataset:t", lineage={"nodes": []})


def _boom(*_a, **_k):
    raise AssertionError("this path must not be taken")


def test_single_synthesis_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", False)
    monkeypatch.setattr(datahub_io, "gather_ack_context",
                        lambda m, t: ({}, [{"tool": "get_entities", "summary": "read owner"}]))
    monkeypatch.setattr(llm, "synthesize_rca", lambda s, l, ack_context=None: "SYNTH RCA")
    monkeypatch.setattr(llm, "agentic_rca", _boom)  # must not run when the flag is off
    out = nodes.root_cause(_state())
    assert out["rca_narrative"] == "SYNTH RCA"
    assert any(e["kind"] == "result" and e["message"] == "SYNTH RCA" for e in out["trace"])


def test_agentic_loop_used_when_flag_on(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", True)
    monkeypatch.setattr(datahub_io, "agent_context_tools", lambda: ["t"])
    monkeypatch.setattr(
        llm, "agentic_rca",
        lambda s, l, tools, m, st: ("AGENTIC RCA",
                                    [{"tool": "get_lineage", "summary": "walked lineage (11 upstream assets)"}]),
    )
    monkeypatch.setattr(llm, "synthesize_rca", _boom)  # must not fall back on success
    out = nodes.root_cause(_state())
    assert out["rca_narrative"] == "AGENTIC RCA"
    assert any("get_lineage" in e["message"] for e in out["trace"])


def test_agentic_failure_falls_back_to_synthesis(monkeypatch):
    monkeypatch.setattr(config, "AGENTIC_RCA", True)
    monkeypatch.setattr(datahub_io, "agent_context_tools", lambda: ["t"])

    def raises(*_a, **_k):
        raise RuntimeError("live loop failed")

    monkeypatch.setattr(llm, "agentic_rca", raises)
    monkeypatch.setattr(datahub_io, "gather_ack_context",
                        lambda m, t: ({}, [{"tool": "get_entities", "summary": "read owner"}]))
    monkeypatch.setattr(llm, "synthesize_rca", lambda s, l, ack_context=None: "FALLBACK RCA")
    out = nodes.root_cause(_state())
    assert out["rca_narrative"] == "FALLBACK RCA"


@pytest.mark.parametrize("out,expect", [
    ({"upstreams": {"total": 11}}, "upstream assets"),
    ({"name": "x", "owner": "y"}, "read"),
    ("web_sessions", "read"),
])
def test_tool_summary_is_a_short_phrase(out, expect):
    assert expect in llm._tool_summary("get_lineage", out)
