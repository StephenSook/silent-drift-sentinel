"""Metadata-aware code generation.

From the diagnosed drift (the change_type taxonomy + the EXACT column and upstream
table the agent traced, plus a data-quality fingerprint), emit the data-quality
guardrail that would have caught THIS regression: a dbt test block, a Great
Expectations expectation, and a plain SQL guard. Deterministic templates keyed on
the change_type, so no LLM is in the loop and the generated code is reproducible.
This is the Metadata-Aware Code-Gen surface: catalog metadata in, a paste-ready
pipeline guardrail out, written back onto the model.
"""
from __future__ import annotations

from typing import Any

# the change_type taxonomy (from ml/sentinel_ml/drift.py classify_change_type) maps
# 1:1 to a guardrail. Each entry is (summary, dbt, great_expectations, sql, needs).
_CHANGE_TYPES = {
    "null_default_regression",
    "null_regression",
    "default_value_regression",
    "unit_change",
    "distribution_shift",
}


def _short_table(urn: str) -> str:
    # urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)
    #   -> ecommerce.web_sessions
    try:
        return urn.split(",")[1]
    except IndexError:
        return urn or "the_source_table"


def _model_name(table: str) -> str:
    # dbt models are keyed by the last path segment
    return table.split(".")[-1] if table else "the_model"


def _bounds(drift_signal: dict[str, Any]) -> tuple[float, float]:
    """Expected [min, max] for the column, from the reference window if present."""
    ref = drift_signal.get("reference") or drift_signal.get("reference_stats") or {}
    dq = drift_signal.get("data_quality") or {}
    lo = ref.get("min", dq.get("ref_min", 0))
    hi = ref.get("max", dq.get("ref_max", 1))
    try:
        return float(lo), float(hi)
    except (TypeError, ValueError):
        return 0.0, 1.0


def generate_fix(causation: dict[str, Any], drift_signal: dict[str, Any] | None = None) -> dict[str, Any]:
    change_type = causation.get("change_type", "distribution_shift")
    if change_type not in _CHANGE_TYPES:
        change_type = "distribution_shift"
    col = causation.get("drifted_feature") or "the_column"
    table = _short_table(causation.get("root_cause_urn", ""))
    model = _model_name(table)
    lo, hi = _bounds(drift_signal or {})
    # a modest guard band around the reference max so a x100 rescale trips it
    hi_bound = round(hi * 1.5, 4) if hi else 1.0
    lo_bound = round(lo, 4)

    builders = {
        "null_default_regression": _null_default,
        "null_regression": _null,
        "default_value_regression": _default_value,
        "unit_change": _unit_change,
        "distribution_shift": _distribution_shift,
    }
    dbt, ge, sql, needs, note = builders[change_type](col, model, table, lo_bound, hi_bound)
    return {
        "change_type": change_type,
        "column": col,
        "table": table,
        "summary": note,
        "dbt": dbt,
        "great_expectations": ge,
        "sql": sql,
        "needs": needs,
    }


def _null_default(col, model, table, lo, hi):
    dbt = (
        f"# schema.yml\nmodels:\n  - name: {model}\n    columns:\n      - name: {col}\n"
        f"        tests:\n          - not_null\n"
        f"          - dbt_utils.not_constant   # nulls were being imputed to a constant\n"
    )
    ge = (
        f'expect_column_values_to_not_be_null(column="{col}")\n'
        f'expect_column_proportion_of_unique_values_to_be_between(column="{col}", min_value=0.02, max_value=1.0)'
    )
    sql = (
        f"-- fires (returns > 0) if {col} is null or has collapsed toward one value\n"
        f"select count(*) as violations\nfrom {table}\n"
        f"where {col} is null\n"
        f"   or {col} = (select mode({col}) from {table})"
    )
    return dbt, ge, sql, ["dbt_utils"], (
        f"not_null + not_constant on {col}: catches nulls being imputed to a default")


def _null(col, model, table, lo, hi):
    dbt = (
        f"# schema.yml\nmodels:\n  - name: {model}\n    columns:\n      - name: {col}\n"
        f"        tests:\n          - not_null\n"
    )
    ge = f'expect_column_values_to_not_be_null(column="{col}")'
    sql = (
        f"-- fires if any {col} became null\n"
        f"select count(*) as violations from {table} where {col} is null"
    )
    return dbt, ge, sql, [], f"not_null on {col}: catches nulls appearing"


def _default_value(col, model, table, lo, hi):
    dbt = (
        f"# schema.yml\nmodels:\n  - name: {model}\n    columns:\n      - name: {col}\n"
        f"        tests:\n          - dbt_utils.not_constant\n"
    )
    ge = f'expect_column_proportion_of_unique_values_to_be_between(column="{col}", min_value=0.02, max_value=1.0)'
    sql = (
        f"-- fires if one value dominates > 90% of rows\n"
        f"select count(*) as violations from (\n"
        f"  select {col}, count(*) as n, sum(count(*)) over () as total\n"
        f"  from {table} group by {col}\n"
        f") where n::float / total > 0.90"
    )
    return dbt, ge, sql, ["dbt_utils"], f"not_constant on {col}: catches a default value dominating"


def _unit_change(col, model, table, lo, hi):
    dbt = (
        f"# schema.yml\nmodels:\n  - name: {model}\n    columns:\n      - name: {col}\n"
        f"        tests:\n          - dbt_utils.accepted_range:\n"
        f"              min_value: {lo}\n              max_value: {hi}\n"
    )
    ge = f'expect_column_values_to_be_between(column="{col}", min_value={lo}, max_value={hi})'
    sql = (
        f"-- fires if {col} left its expected range (e.g. a x100 rescale)\n"
        f"select count(*) as violations from {table}\n"
        f"where {col} < {lo} or {col} > {hi}"
    )
    return dbt, ge, sql, ["dbt_utils"], (
        f"accepted_range [{lo}, {hi}] on {col}: catches a unit/scale change")


def _distribution_shift(col, model, table, lo, hi):
    mid = round((lo + hi) / 2, 4)
    dbt = (
        f"# schema.yml (dbt_expectations)\nmodels:\n  - name: {model}\n    columns:\n      - name: {col}\n"
        f"        tests:\n          - dbt_expectations.expect_column_mean_to_be_between:\n"
        f"              min_value: {lo}\n              max_value: {hi}\n"
    )
    ge = f'expect_column_mean_to_be_between(column="{col}", min_value={lo}, max_value={hi})'
    sql = (
        f"-- fires if the mean of {col} drifts outside the expected band\n"
        f"select count(*) as violations from (\n"
        f"  select avg({col}) as m from {table}\n"
        f") where m < {lo} or m > {hi}"
    )
    return dbt, ge, sql, ["dbt_expectations"], (
        f"expect_column_mean_to_be_between [{lo}, {hi}] on {col}: catches a distribution shift")
