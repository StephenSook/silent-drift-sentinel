"""Print exact signatures of the DataHub SDK calls the Sentinel depends on."""
from __future__ import annotations

import inspect

from datahub.sdk import DataHubClient
from datahub.sdk.mlmodel import MLModel


def sig(label, fn):
    try:
        print(f"{label}: {inspect.signature(fn)}")
    except Exception as e:  # noqa: BLE001
        print(f"{label}: <{e!r}>")


client = DataHubClient(server="http://localhost:8080")

sig("MLModel.set_structured_property", MLModel.set_structured_property)
sig("MLModel.add_owner", MLModel.add_owner)
sig("MLModel.add_tag", MLModel.add_tag)
sig("client.entities.create", client.entities.create)
sig("client.entities.upsert", client.entities.upsert)
sig("client.entities.get", client.entities.get)
sig("client.lineage.add_lineage", client.lineage.add_lineage)
sig("client.lineage.get_lineage", client.lineage.get_lineage)

from datahub.sdk.dataset import Dataset

print("\nDataset init params:", list(inspect.signature(Dataset.__init__).parameters))

from datahub.sdk.document import Document

print("Document init params:", list(inspect.signature(Document.__init__).parameters))
print("Document methods:", [m for m in dir(Document) if not m.startswith("_")])

from datahub.api.entities.structuredproperties.structuredproperties import (
    StructuredProperties,
)

sig("StructuredProperties.create", StructuredProperties.create)
print("StructuredProperties fields:", list(StructuredProperties.model_fields.keys()))

# low-level classes for the feature layer + structured property definition
from datahub.metadata.schema_classes import (
    MLFeaturePropertiesClass,
    MLFeatureTablePropertiesClass,
    StructuredPropertyDefinitionClass,
)

print("\nMLFeaturePropertiesClass fields:", [f for f in MLFeaturePropertiesClass.__init__.__code__.co_varnames][:12])
print("StructuredPropertyDefinitionClass fields:", [f for f in StructuredPropertyDefinitionClass.__init__.__code__.co_varnames][:14])
