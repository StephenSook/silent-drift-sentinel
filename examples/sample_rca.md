# Sample root-cause analysis (live agent output)

## The `drift_causation` structured property written onto the model

```
null_default_regression on feature PageValues (upstream ecommerce.web_sessions);
roc_auc 0.808->0.7131 (label-free CBPE), drop 0.0949; notify urn:li:corpGroup:data-engineering;
detected 2026-07-07T22:23:47+00:00
```

Written to `urn:li:mlModel:(urn:li:dataPlatform:mlflow,online_shoppers_purchase_intent,PROD)`, alongside a `drift-degraded` tag and the RCA document below, with a matching incident on the upstream dataset.

## The RCA document (Claude, over Agent Context Kit reads)

CBPE-estimated ROC AUC for online_shoppers_purchase_intent dropped from 0.808 to 0.713 (-0.095), label-free since ground truth is not yet available for the current window. The drift localizes to PageValues, which shows a KS statistic of 0.239 (adjusted p-value 0.0) and a collapse in range from [0, 270.78] to a constant 0.0, with cardinality falling from 353 unique values to 1. This pattern, all values pinned to zero with no nulls, is consistent with a null or default-value regression: an upstream job likely started coalescing nulls or missing joins to 0 instead of passing through actual page-value scores. Lineage traces PageValues to ecommerce.web_sessions in Snowflake, owned by data-engineering, so the likely point of failure is a recent change to that table's ETL. Since PageValues is a top signal for purchase intent, zeroing it out removes most of its discriminative power, which lines up with the observed AUC drop. Recommended fix: have data-engineering check recent deploys on ecommerce.web_sessions for default-fill logic touching PageValues, confirm the source page-view aggregation job is still running, and backfill the affected window once fixed. This is a lineage-guided correlation based on timing and feature ownership, not a proven causal link, so confirm the upstream commit history before rolling back.
