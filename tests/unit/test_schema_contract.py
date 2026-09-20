"""The `fields` contract. These tests are the enforcement of invariants #1 and #2."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pawsible.schema.enums import Compatibility, HomeRequirement
from pawsible.schema.fields import Extracted, ExtractedFields, Note, from_jsonb, to_jsonb

VALID = {"value": "YES", "confidence": 0.9, "evidence": "good with cats", "offsets": (10, 24)}


def test_a_populated_value_requires_an_evidence_span() -> None:
    for missing in ("evidence", "offsets"):
        payload = {k: v for k, v in VALID.items() if k != missing}
        with pytest.raises(ValidationError):
            Extracted[Compatibility](**payload)


def test_empty_evidence_is_not_a_span() -> None:
    with pytest.raises(ValidationError):
        Extracted[Compatibility](**{**VALID, "evidence": ""})


def test_unknown_is_not_a_constructible_value() -> None:
    """Invariant #2's structural guard.

    If UNKNOWN were an enum member it could be returned with empty evidence, which
    would force an "empty evidence is fine when UNKNOWN" carve-out -- and that carve-out
    is the only route by which NOT_TESTED could be rendered as a positive.
    """
    with pytest.raises(ValidationError):
        Extracted[Compatibility](**{**VALID, "value": "UNKNOWN"})


def test_not_tested_is_a_distinct_value_from_yes_and_from_absence() -> None:
    tested = ExtractedFields(
        good_with_cats=Extracted[Compatibility](
            value=Compatibility.NOT_TESTED,
            confidence=0.95,
            evidence="has not been cat tested",
            offsets=(0, 23),
        )
    )
    silent = ExtractedFields()
    assert tested.good_with_cats is not None
    assert tested.good_with_cats.value is Compatibility.NOT_TESTED
    assert silent.good_with_cats is None
    assert "good_with_cats" in to_jsonb(tested)
    assert "good_with_cats" not in to_jsonb(silent)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_is_bounded(confidence: float) -> None:
    with pytest.raises(ValidationError):
        Extracted[Compatibility](**{**VALID, "confidence": confidence})


def test_unexpected_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Extracted[Compatibility](**{**VALID, "vibes": "immaculate"})


def test_unknown_is_absence_of_key_for_collections_too() -> None:
    assert to_jsonb(ExtractedFields()) == {}


def test_jsonb_round_trips() -> None:
    fields = ExtractedFields(
        good_with_cats=Extracted[Compatibility](**VALID),
        home_requirements=(
            Extracted[HomeRequirement](
                value=HomeRequirement.ONLY_PET,
                confidence=0.8,
                evidence="only pet",
                offsets=(1, 9),
            ),
        ),
        medical_needs=(
            Note(
                summary="heartworm",
                verbatim="heartworm positive",
                offsets=(2, 20),
                ongoing_care=True,
            ),
        ),
    )
    assert from_jsonb(to_jsonb(fields)) == fields


def test_storage_shape_matches_the_specified_contract() -> None:
    fields = ExtractedFields(good_with_cats=Extracted[Compatibility](**VALID))
    assert to_jsonb(fields) == {
        "good_with_cats": {
            "value": "YES",
            "confidence": 0.9,
            "evidence": "good with cats",
            "offsets": [10, 24],
        }
    }
