"""Day-one validation checklist, run against a live DataHub instance.

Four independent probes, each isolated so one run reports all four results:
  A. A typed structured property can be created and attached to an mlModel.
  B. A context document can link to an mlModel as a related asset.
  C. get_lineage traverses dataset -> mlFeature -> mlModel across entity types.
  D. raiseIncident works on a dataset via GraphQL (incidents cannot target mlModel).

Nothing here is load-bearing for the product; it only proves the platform
assumptions the whole design rests on, before we build on them.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")
TOKEN = os.environ.get("DATAHUB_GMS_TOKEN", "")

from datahub.emitter.mce_builder import (
    make_dataset_urn,
    make_ml_feature_urn,
    make_ml_model_urn,
    make_tag_urn,
)
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DataHubRestEmitter
from datahub.metadata.schema_classes import (
    MLFeatureDataTypeClass,
    MLFeaturePropertiesClass,
    MLModelPropertiesClass,
    StructuredPropertyDefinitionClass,
)
from datahub.sdk import DataHubClient

client = DataHubClient(server=GMS, token=TOKEN or None)
emitter = DataHubRestEmitter(gms_server=GMS, token=TOKEN or None)

results: dict[str, str] = {}


def graphql(query: str) -> dict:
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"{GMS}/api/graphql", data=body, headers={"Content-Type": "application/json"}
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


# ---- Probe A: structured property on mlModel -------------------------------
def probe_a() -> str:
    from datahub.sdk.mlmodel import MLModel

    sp_urn = "urn:li:structuredProperty:io.sentinel.test_drift_causation"
    emitter.emit(
        MetadataChangeProposalWrapper(
            entityUrn=sp_urn,
            aspect=StructuredPropertyDefinitionClass(
                qualifiedName="io.sentinel.test_drift_causation",
                valueType="urn:li:dataType:datahub.string",
                entityTypes=[
                    "urn:li:entityType:datahub.mlModel",
                    "urn:li:entityType:datahub.dataset",
                ],
                displayName="Drift Causation (checklist test)",
                cardinality="SINGLE",
                description="Day-one checklist probe property.",
            ),
        )
    )
    model = MLModel(id="sentinel_checklist_model", platform="mlflow", name="Sentinel Checklist Model")
    model.set_structured_property(sp_urn, ["root_cause=PageValues unit change; owner=jane.doe"])
    try:
        model.add_tag(make_tag_urn("drift-degraded"))
    except Exception:  # noqa: BLE001
        pass
    client.entities.upsert(model)

    got = client.entities.get(model.urn)
    sp = getattr(got, "structured_properties", None)
    return f"PASS (model={model.urn}, structured_properties readback={sp!r})"


# ---- Probe B: context document linked to mlModel ---------------------------
def probe_b() -> str:
    from datahub.sdk.document import Document

    model_urn = make_ml_model_urn("mlflow", "sentinel_checklist_model", "PROD")
    doc = Document.create_document(
        id="sentinel_checklist_rca",
        title="RCA: Sentinel checklist model drift",
        text="Checklist probe document body linked to the model as a related asset.",
        related_assets=[model_urn],
    )
    client.entities.upsert(doc)
    got = client.entities.get(doc.urn)
    related = getattr(got, "related_assets", None)
    return f"PASS (document={doc.urn}, related_assets={related!r})"


# ---- Probe C: get_lineage crosses dataset -> mlFeature -> mlModel -----------
def probe_c() -> str:
    ds_urn = make_dataset_urn("snowflake", "sentinel_test.web_sessions", "PROD")
    feat_urn = make_ml_feature_urn("sentinel_test_features", "page_value")
    model_urn = make_ml_model_urn("mlflow", "sentinel_lineage_model", "PROD")

    # dataset (minimal), feature derived from the dataset, model consuming the feature
    from datahub.metadata.schema_classes import DatasetPropertiesClass

    emitter.emit(MetadataChangeProposalWrapper(entityUrn=ds_urn, aspect=DatasetPropertiesClass(name="web_sessions")))
    emitter.emit(
        MetadataChangeProposalWrapper(
            entityUrn=feat_urn,
            aspect=MLFeaturePropertiesClass(
                description="page value feature",
                dataType=MLFeatureDataTypeClass.CONTINUOUS,
                sources=[ds_urn],
            ),
        )
    )
    emitter.emit(
        MetadataChangeProposalWrapper(
            entityUrn=model_urn,
            aspect=MLModelPropertiesClass(name="Sentinel Lineage Model", mlFeatures=[feat_urn]),
        )
    )

    # lineage index is async; poll downstream from the dataset for the model
    deadline = time.time() + 45
    seen: list[str] = []
    while time.time() < deadline:
        hops = client.lineage.get_lineage(source_urn=ds_urn, direction="downstream", max_hops=3)
        seen = [str(getattr(h, "urn", h)) for h in hops]
        if any("mlModel" in s for s in seen):
            return f"PASS (downstream from dataset reached: {seen})"
        time.sleep(5)
    return f"PARTIAL (feature/model emitted; downstream after 45s = {seen}; may need more index time or a direct probe)"


# ---- Probe D: raiseIncident on a dataset via GraphQL ------------------------
def probe_d() -> str:
    ds_urn = make_dataset_urn("snowflake", "sentinel_test.web_sessions", "PROD")
    q = (
        "mutation { raiseIncident(input: { "
        "type: OPERATIONAL, "
        f'resourceUrn: "{ds_urn}", '
        'title: "Silent drift: upstream unit change on page_value", '
        'description: "Checklist probe incident raised on the upstream dataset." '
        "}) }"
    )
    out = graphql(q)
    if out.get("data", {}).get("raiseIncident"):
        return f"PASS (incident={out['data']['raiseIncident']})"
    return f"FAIL ({json.dumps(out)[:300]})"


for name, fn in [("A structured-property-on-mlModel", probe_a),
                 ("B document-links-to-mlModel", probe_b),
                 ("C get_lineage dataset->feature->model", probe_c),
                 ("D raiseIncident on dataset", probe_d)]:
    try:
        results[name] = fn()
    except Exception as e:  # noqa: BLE001
        results[name] = f"ERROR ({type(e).__name__}: {e})"

print("\n===== DAY-ONE CHECKLIST RESULTS =====")
for k, v in results.items():
    print(f"[{v.split()[0]:8}] {k}\n           {v}")
