"""Verify the agent's deterministic lineage traversal by reading aspects
directly (immediate, no graph-index dependency): given the degraded model and a
drifted feature, walk model -> feature -> source table -> owner.
"""
from __future__ import annotations

import os

from datahub.emitter.mce_builder import make_ml_model_urn
from datahub.ingestion.graph.client import DataHubGraph, DataHubGraphConfig
from datahub.metadata.schema_classes import (
    MLFeaturePropertiesClass,
    MLModelPropertiesClass,
    OwnershipClass,
    SchemaMetadataClass,
)

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")
graph = DataHubGraph(DataHubGraphConfig(server=GMS, token=os.environ.get("DATAHUB_GMS_TOKEN")))

MODEL = make_ml_model_urn("mlflow", "online_shoppers_purchase_intent", "PROD")
DRIFTED_FEATURE = "PageValues"  # from the drift signal

mp = graph.get_aspect(MODEL, MLModelPropertiesClass)
own = graph.get_aspect(MODEL, OwnershipClass)
print(f"degraded model: {MODEL}")
print(f"  owner: {own.owners[0].owner}")
print(f"  consumes {len(mp.mlFeatures)} features; training metrics: "
      f"{[(m.name, m.value) for m in mp.trainingMetrics][:3]}")

feat = next(f for f in mp.mlFeatures if DRIFTED_FEATURE in f)
fp = graph.get_aspect(feat, MLFeaturePropertiesClass)
print(f"  drifted feature {DRIFTED_FEATURE} -> {feat}")
source = fp.sources[0]
print(f"    derived from: {source}")

ds_own = graph.get_aspect(source, OwnershipClass)
ds_schema = graph.get_aspect(source, SchemaMetadataClass)
print(f"    source table owner: {ds_own.owners[0].owner}")
print(f"    source table columns: {len(ds_schema.fields)} "
      f"(incl. {DRIFTED_FEATURE}: {any(f.fieldPath == DRIFTED_FEATURE for f in ds_schema.fields)})")

print("\nROOT-CAUSE PATH (deterministic, aspect-based):")
print(f"  {MODEL.split(',')[1]}  [degraded]")
print(f"    <- feature {DRIFTED_FEATURE}")
print(f"    <- {source.split(',')[1]}  [upstream table where the bug originated]")
print(f"    owner to notify: {ds_own.owners[0].owner}")
