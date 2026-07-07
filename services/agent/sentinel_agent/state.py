"""Typed LangGraph state. The trace accumulates across nodes (add reducer) so the
streaming UI can replay the agent's steps."""
from __future__ import annotations

import operator
from typing import Annotated, Any

from pydantic import BaseModel, Field


class DriftState(BaseModel):
    # input
    drift_signal: dict[str, Any]
    model_urn: str

    # traverse
    lineage: dict[str, Any] = Field(default_factory=dict)
    root_cause_feature: str = ""
    source_table: str = ""
    table_owner: str = ""
    model_owner: str = ""

    # root-cause synthesis (LLM, prose only)
    rca_narrative: str = ""

    # write-back
    causation: dict[str, Any] = Field(default_factory=dict)
    writeback_result: dict[str, Any] = Field(default_factory=dict)

    # human-in-the-loop
    approved: bool = True

    # streaming trace: list of {node, kind, message, ...}, accumulated
    trace: Annotated[list[dict[str, Any]], operator.add] = Field(default_factory=list)


def event(node: str, kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"node": node, "kind": kind, "message": message, **extra}
