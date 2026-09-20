"""The wire schema is consumer (a) of the single source of truth, and it feeds the
prompt-cache prefix and the derived prompt_version -- so determinism is a requirement,
not a nicety.
"""

from __future__ import annotations

import json

import pytest

from pawsible.schema.fields import ExtractedFields
from pawsible.schema.wire import to_wire_schema

UNSUPPORTED = ["minimum", "maximum", "minLength", "maxItems", "minItems", "prefixItems", "default"]


@pytest.mark.parametrize("keyword", UNSUPPORTED)
def test_unsupported_validation_keywords_are_stripped(keyword: str) -> None:
    assert keyword not in json.dumps(to_wire_schema())


def test_schema_is_total_so_the_model_must_emit_null_rather_than_omit() -> None:
    schema = to_wire_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert set(schema["properties"]) == set(ExtractedFields.model_fields)


def test_optional_fields_permit_null_exactly_once() -> None:
    """Pydantic already renders `X | None` as anyOf[X, null]; wrapping again nests."""
    prop = to_wire_schema()["properties"]["good_with_cats"]
    assert [branch.get("type") for branch in prop["anyOf"]].count("null") == 1
    assert all("anyOf" not in branch for branch in prop["anyOf"])


def test_objects_forbid_additional_properties() -> None:
    schema = to_wire_schema()
    for name, definition in schema["$defs"].items():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False, name


def test_unknown_is_not_offered_to_the_model_as_a_value() -> None:
    """It may appear in a description -- the model should be told absence means
    UNKNOWN -- but it must never be selectable as an enum member."""
    schema = to_wire_schema()
    for name, definition in schema["$defs"].items():
        assert "UNKNOWN" not in definition.get("enum", []), name


def test_evidence_and_offsets_are_required_on_every_extracted_value() -> None:
    definition = to_wire_schema()["$defs"]["Extracted_Compatibility_"]
    assert {"evidence", "offsets", "value", "confidence"} == set(definition["required"])


def test_schema_is_deterministic() -> None:
    assert json.dumps(to_wire_schema()) == json.dumps(to_wire_schema())
