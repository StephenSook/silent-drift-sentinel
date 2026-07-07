"""DataHub reads: deterministic aspect-based lineage traversal (reliable,
structured) plus the Agent Context Kit tools the LLM can call. The write path
lives in writeback.py and never touches the LLM."""
from __future__ import annotations

from typing import Any

from datahub.ingestion.graph.client import DataHubGraph, DataHubGraphConfig
from datahub.metadata.schema_classes import (
    MLFeaturePropertiesClass,
    MLModelPropertiesClass,
    OwnershipClass,
    SchemaMetadataClass,
)

from . import config


def _graph() -> DataHubGraph:
    return DataHubGraph(DataHubGraphConfig(server=config.GMS_URL, token=config.GMS_TOKEN))


def traverse_lineage(model_urn: str, drifted_feature: str) -> dict[str, Any]:
    """Walk model -> features -> the drifted feature's source table -> owners.
    Deterministic aspect reads (immediate, no dependence on the async graph index)."""
    g = _graph()
    mp = g.get_aspect(model_urn, MLModelPropertiesClass)
    model_own = g.get_aspect(model_urn, OwnershipClass)
    result: dict[str, Any] = {
        "model_urn": model_urn,
        "model_owner": model_own.owners[0].owner if model_own and model_own.owners else None,
        "consumes_features": list(mp.mlFeatures or []) if mp else [],
        "training_metrics": {m.name: m.value for m in (mp.trainingMetrics or [])} if mp else {},
        "feature_urn": None,
        "source_table": None,
        "table_owner": None,
        "table_columns": 0,
    }
    if mp and mp.mlFeatures:
        feat = next((f for f in mp.mlFeatures if drifted_feature in f), None)
        if feat:
            result["feature_urn"] = feat
            fp = g.get_aspect(feat, MLFeaturePropertiesClass)
            if fp and fp.sources:
                source = fp.sources[0]
                result["source_table"] = source
                src_own = g.get_aspect(source, OwnershipClass)
                result["table_owner"] = (
                    src_own.owners[0].owner if src_own and src_own.owners else None
                )
                schema = g.get_aspect(source, SchemaMetadataClass)
                result["table_columns"] = len(schema.fields) if schema else 0
    return result


def lineage_graph(model_urn: str, drifted_feature: str) -> dict[str, Any]:
    """Nodes + edges for the UI lineage DAG, with the root-cause path flagged."""
    g = _graph()
    mp = g.get_aspect(model_urn, MLModelPropertiesClass)
    model_own = g.get_aspect(model_urn, OwnershipClass)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def short(urn: str) -> str:
        try:
            return urn.split(",")[1].split(".")[-1]
        except IndexError:
            return urn

    nodes.append({
        "id": model_urn, "kind": "model", "label": "purchase_intent", "status": "degraded",
        "owner": (model_own.owners[0].owner.split(":")[-1] if model_own and model_own.owners else None),
        "metrics": ({m.name: m.value for m in (mp.trainingMetrics or [])} if mp else {}),
    })
    seen: set[str] = set()
    for f in (mp.mlFeatures or []) if mp else []:
        fname = f.split(",")[-1].rstrip(")")
        is_root = bool(drifted_feature and drifted_feature in f)
        nodes.append({"id": f, "kind": "feature", "label": fname,
                      "status": "drifted" if is_root else "ok"})
        edges.append({"id": f"e-{f}-model", "source": f, "target": model_urn, "root": is_root})
        fp = g.get_aspect(f, MLFeaturePropertiesClass)
        for src in (fp.sources or []) if fp else []:
            if src not in seen:
                seen.add(src)
                src_own = g.get_aspect(src, OwnershipClass)
                nodes.append({"id": src, "kind": "dataset", "label": short(src),
                              "status": "ok",
                              "owner": (src_own.owners[0].owner.split(":")[-1]
                                        if src_own and src_own.owners else None)})
            edges.append({"id": f"e-{src}-{f}", "source": src, "target": f, "root": is_root})

    for n in nodes:
        if n["kind"] == "dataset" and any(e["root"] and e["source"] == n["id"] for e in edges):
            n["status"] = "changed"
    for dep in (mp.deployments or []) if mp else []:
        nodes.append({"id": dep, "kind": "deployment", "label": short(dep), "status": "ok"})
        edges.append({"id": f"e-model-{dep}", "source": model_urn, "target": dep, "root": False})

    return {"nodes": nodes, "edges": edges, "drifted_feature": drifted_feature}


def agent_context_tools():
    """Agent Context Kit read tools (LangChain BaseTools) the LLM can call to
    gather extra catalog context. Satisfies the hackathon Agent Context Kit
    requirement; the tools are read-only (include_mutations=False)."""
    from datahub.sdk import DataHubClient
    from datahub_agent_context.langchain_tools import build_langchain_tools

    client = DataHubClient(server=config.GMS_URL, token=config.GMS_TOKEN)
    return build_langchain_tools(client, include_mutations=False)
