"""The metadata-aware code-gen is deterministic, so it unit-tests with no network."""
import pytest

from sentinel_agent import fixgen

CAUSATION = {
    "drifted_feature": "PageValues",
    "root_cause_urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,ecommerce.web_sessions,PROD)",
}


@pytest.mark.parametrize(
    "change_type,dep",
    [
        ("null_default_regression", "dbt_utils"),
        ("null_regression", None),
        ("default_value_regression", "dbt_utils"),
        ("unit_change", "dbt_utils"),
        ("distribution_shift", "dbt_expectations"),
    ],
)
def test_generate_fix_per_change_type(change_type, dep):
    fix = fixgen.generate_fix(
        {**CAUSATION, "change_type": change_type}, {"reference": {"min": 0, "max": 361}}
    )
    assert fix["change_type"] == change_type
    assert fix["column"] == "PageValues"
    assert fix["table"] == "ecommerce.web_sessions"
    # every format is produced and references the exact column
    for fmt in ("dbt", "great_expectations", "sql"):
        assert fix[fmt] and "PageValues" in fix[fmt]
    if dep:
        assert dep in fix["needs"]


def test_null_regression_is_native_dbt():
    fix = fixgen.generate_fix({**CAUSATION, "change_type": "null_regression"}, {})
    assert "not_null" in fix["dbt"]
    assert fix["needs"] == []  # dbt native, no package dependency


def test_unit_change_bounds_the_range():
    fix = fixgen.generate_fix(
        {**CAUSATION, "change_type": "unit_change"}, {"reference": {"min": 0, "max": 361}}
    )
    # a x100 rescale must fall outside the accepted range, so the guard fires
    assert "accepted_range" in fix["dbt"]
    assert "between" in fix["great_expectations"]


def test_unknown_change_type_falls_back():
    fix = fixgen.generate_fix({**CAUSATION, "change_type": "nonsense"}, {})
    assert fix["change_type"] == "distribution_shift"
