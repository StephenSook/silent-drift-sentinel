"""Diagnose ML lineage traversal on the entities the checklist emitted.

The agent traverses UPSTREAM from the degraded model (model -> feature -> source
dataset), so that direction is the one that must work. We also test downstream
(impact) and the raw relationships, and print everything so we know exactly what
the graph index holds.
"""
from __future__ import annotations

import json
import os
import urllib.request

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")

from datahub.emitter.mce_builder import (
    make_dataset_urn,
    make_ml_feature_urn,
    make_ml_model_urn,
)
from datahub.sdk import DataHubClient

client = DataHubClient(server=GMS)

ds = make_dataset_urn("snowflake", "sentinel_test.web_sessions", "PROD")
feat = make_ml_feature_urn("sentinel_test_features", "page_value")
model = make_ml_model_urn("mlflow", "sentinel_lineage_model", "PROD")


def show(label, source, direction):
    try:
        hops = client.lineage.get_lineage(source_urn=source, direction=direction, max_hops=2)
        urns = [str(getattr(h, "urn", h)) for h in hops]
        print(f"{label}: {len(urns)} result(s): {urns}")
    except Exception as e:  # noqa: BLE001
        print(f"{label}: ERROR {type(e).__name__}: {e}")


def relationships(urn, types, direction):
    q = urllib.parse.urlencode(
        {"urn": urn, "types": types, "direction": direction}, doseq=False
    )
    url = f"{GMS}/relationships?{q}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode())
        rels = [e.get("entity") for e in data.get("relationships", [])]
        print(f"relationships {direction} {types} of {urn.split(',')[1] if ',' in urn else urn}: {rels}")
    except Exception as e:  # noqa: BLE001
        print(f"relationships ERROR: {e}")


import urllib.parse  # noqa: E402

print("=== entity existence ===")
for u in (ds, feat, model):
    try:
        e = client.entities.get(u)
        print(f"  EXISTS {type(e).__name__}: {u}")
    except Exception as ex:  # noqa: BLE001
        print(f"  MISSING: {u} ({ex})")

print("\n=== get_lineage ===")
show("model upstream (want feature+dataset)", model, "upstream")
show("dataset downstream (want feature+model)", ds, "downstream")
show("feature upstream (want dataset)", feat, "upstream")
show("feature downstream (want model)", feat, "downstream")

print("\n=== raw relationships (graph edges) ===")
relationships(model, "Consumes", "OUTGOING")
relationships(feat, "DerivedFrom", "OUTGOING")
relationships(ds, "DerivedFrom", "INCOMING")

print("\n=== GraphQL searchAcrossLineage (model, upstream) ===")
body = json.dumps(
    {
        "query": (
            "query($u:String!){ searchAcrossLineage(input:{urn:$u, direction:UPSTREAM, "
            'query:"*", count:20}){ total searchResults{ degree entity{ urn type } } } }'
        ),
        "variables": {"u": model},
    }
).encode()
req = urllib.request.Request(
    f"{GMS}/api/graphql", data=body, headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        out = json.loads(resp.read().decode())
    sal = out.get("data", {}).get("searchAcrossLineage", {})
    print(f"  total={sal.get('total')}")
    for r in sal.get("searchResults", []):
        print(f"    degree={r.get('degree')} {r['entity']['type']} {r['entity']['urn']}")
except Exception as e:  # noqa: BLE001
    print(f"  GraphQL ERROR: {e}")
