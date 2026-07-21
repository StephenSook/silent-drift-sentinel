"""The Agent Context Kit read tools report some failures in-band: a read that fails
server-side (a search-index query while the index rebuilds, an auth rejection) comes
back as a normal return value carrying an "error" key instead of raising. The trace
built from those calls is shown to the person watching the run, so a failed read must
never be reported as a successful one."""
from sentinel_agent import datahub_io

MODEL = "urn:li:mlModel:m"
TABLE = "urn:li:dataset:t"


class FakeTool:
    def __init__(self, name, out):
        self.name = name
        self._out = out

    def invoke(self, _payload):
        if isinstance(self._out, Exception):
            raise self._out
        return self._out


def _tools(monkeypatch, tools):
    monkeypatch.setattr(datahub_io, "agent_context_tools", lambda: tools)


def test_in_band_error_is_reported_as_a_failed_read(monkeypatch):
    _tools(monkeypatch, [
        FakeTool("get_entities", [{"error": "401 Client Error: Unauthorized\nfor url: x"}]),
        FakeTool("get_lineage", {"upstreams": {"total": 3}}),
    ])
    ctx, log = datahub_io.gather_ack_context(MODEL, TABLE)
    entity_calls = [e for e in log if e["tool"] == "get_entities"]
    assert entity_calls, "the get_entities call must still appear in the trace"
    for entry in entity_calls:
        assert entry["summary"].startswith("read failed: 401 Client Error")
    assert ctx["model"] is None and ctx["table"] is None


def test_successful_reads_keep_their_summaries(monkeypatch):
    _tools(monkeypatch, [
        FakeTool("get_entities", [{"urn": MODEL, "name": "model"}]),
        FakeTool("get_lineage", {"upstreams": {"total": 11}}),
    ])
    ctx, log = datahub_io.gather_ack_context(MODEL, TABLE)
    summaries = [e["summary"] for e in log]
    assert "fetched model metadata + owner" in summaries
    assert "walked upstream lineage (11 upstream assets)" in summaries
    assert ctx["model"] and ctx["lineage"]["upstreams"]["total"] == 11


def test_raised_exception_still_logs_an_error(monkeypatch):
    _tools(monkeypatch, [
        FakeTool("get_entities", RuntimeError("boom")),
        FakeTool("get_lineage", {"upstreams": {"total": 0}}),
    ])
    _ctx, log = datahub_io.gather_ack_context(MODEL, TABLE)
    assert any(e["summary"] == "error: RuntimeError" for e in log)


def test_missing_tool_is_skipped_not_logged(monkeypatch):
    _tools(monkeypatch, [FakeTool("get_lineage", {"upstreams": {"total": 1}})])
    _ctx, log = datahub_io.gather_ack_context(MODEL, TABLE)
    assert [e["tool"] for e in log] == ["get_lineage"]
