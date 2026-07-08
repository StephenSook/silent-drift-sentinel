# Proposed fix: null_default_regression on PageValues in ecommerce.web_sessions

The agent generated this data-quality guardrail from the diagnosis (metadata-aware
code-gen, deterministic templates keyed on the change type). not_null + not_constant on PageValues: catches nulls being imputed to a default.

## dbt (schema.yml)
```yaml
# schema.yml
models:
  - name: web_sessions
    columns:
      - name: PageValues
        tests:
          - not_null
          - dbt_utils.not_constant   # nulls were being imputed to a constant
```

## Great Expectations
```python
expect_column_values_to_not_be_null(column="PageValues")
expect_column_proportion_of_unique_values_to_be_between(column="PageValues", min_value=0.02, max_value=1.0)
```

## Plain SQL guard
```sql
-- fires (returns > 0) if PageValues is null or has collapsed toward one value
select count(*) as violations
from ecommerce.web_sessions
where PageValues is null
   or PageValues = (select mode(PageValues) from ecommerce.web_sessions)
```

Requires: dbt_utils
