"""Print constructor signatures for the aspect classes and URN builders the
lineage emission needs, against the installed acryl-datahub."""
from __future__ import annotations

import inspect

from datahub.emitter import mce_builder as B
from datahub.metadata import schema_classes as S

CLASSES = [
    "SchemaMetadataClass", "SchemaFieldClass", "SchemaFieldDataTypeClass",
    "NumberTypeClass", "StringTypeClass", "BooleanTypeClass",
    "OtherSchemaClass",
    "MLFeatureTablePropertiesClass", "MLFeaturePropertiesClass",
    "MLModelPropertiesClass", "MLModelGroupPropertiesClass",
    "MLModelDeploymentPropertiesClass",
    "MLHyperParamClass", "MLMetricClass",
    "OwnershipClass", "OwnerClass", "OwnershipTypeClass", "AuditStampClass",
    "DataProcessInstancePropertiesClass",
]
for cn in CLASSES:
    c = getattr(S, cn, None)
    if c is None:
        print(f"{cn}: MISSING")
        continue
    try:
        print(f"{cn}: {list(inspect.signature(c.__init__).parameters)[1:]}")
    except (ValueError, TypeError) as e:
        print(f"{cn}: <{e}>")

print("\n--- builders ---")
for b in ["make_dataset_urn", "make_schema_field_urn", "make_ml_model_urn",
          "make_ml_model_group_urn", "make_ml_feature_urn", "make_ml_feature_table_urn",
          "make_ml_model_deployment_urn", "make_user_urn", "make_group_urn",
          "make_data_platform_urn", "make_data_process_instance_urn", "make_ml_primary_key_urn"]:
    fn = getattr(B, b, None)
    if fn is None:
        print(f"{b}: MISSING")
    else:
        print(f"{b}: {inspect.signature(fn)}")
