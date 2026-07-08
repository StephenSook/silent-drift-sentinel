"""The five-node LangGraph state machine. Optionally interrupts before the
write-back for human approval (the mutation gate)."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import DriftState


def build_graph(checkpointer=None, interrupt_before_writeback: bool = False):
    g = StateGraph(DriftState)
    g.add_node("detect", nodes.detect)
    g.add_node("recall", nodes.recall)
    g.add_node("traverse", nodes.traverse)
    g.add_node("root_cause", nodes.root_cause)
    g.add_node("identify_owner", nodes.identify_owner)
    g.add_node("propose_fix", nodes.propose_fix)
    g.add_node("write_back", nodes.write_back)

    g.add_edge(START, "detect")
    # Route out of Detect: a benign shift stops here (the agent does not cry wolf); a
    # cause already recorded on the model is recalled (no re-diagnosis, no duplicate
    # incident); anything else gets a fresh lineage walk.
    g.add_conditional_edges(
        "detect",
        nodes.route_after_detect,
        {"traverse": "traverse", "recall": "recall", "end": END},
    )
    g.add_edge("recall", END)
    g.add_edge("traverse", "root_cause")
    g.add_edge("root_cause", "identify_owner")
    g.add_edge("identify_owner", "propose_fix")
    g.add_edge("propose_fix", "write_back")
    g.add_edge("write_back", END)

    compile_kwargs = {}
    if interrupt_before_writeback:
        compile_kwargs["interrupt_before"] = ["write_back"]
    return g.compile(checkpointer=checkpointer, **compile_kwargs)
