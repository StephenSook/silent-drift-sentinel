"""The five-node LangGraph state machine. Optionally interrupts before the
write-back for human approval (the mutation gate)."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import DriftState


def build_graph(checkpointer=None, interrupt_before_writeback: bool = False):
    g = StateGraph(DriftState)
    g.add_node("detect", nodes.detect)
    g.add_node("traverse", nodes.traverse)
    g.add_node("root_cause", nodes.root_cause)
    g.add_node("identify_owner", nodes.identify_owner)
    g.add_node("write_back", nodes.write_back)

    g.add_edge(START, "detect")
    g.add_edge("detect", "traverse")
    g.add_edge("traverse", "root_cause")
    g.add_edge("root_cause", "identify_owner")
    g.add_edge("identify_owner", "write_back")
    g.add_edge("write_back", END)

    compile_kwargs = {}
    if interrupt_before_writeback:
        compile_kwargs["interrupt_before"] = ["write_back"]
    return g.compile(checkpointer=checkpointer, **compile_kwargs)
