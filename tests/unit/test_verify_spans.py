"""Span verification is the mechanism behind invariant #1, so it gets the most
adversarial test in the repo. Each case is a way a span can be wrong in production.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pawsible.extraction.verify import ViolationKind, verify_spans
from pawsible.schema.enums import Compatibility
from pawsible.schema.fields import Extracted, ExtractedFields, Note
from pawsible.text.canonical import CanonicalText

TEXT = "Buddy does great with the resident cats but does great alone too."
DOC = CanonicalText.of(TEXT)
START = TEXT.index("does great")
END = START + len("does great")


def _fields(evidence: str, offsets: tuple[int, int]) -> ExtractedFields:
    return ExtractedFields(
        good_with_cats=Extracted[Compatibility](
            value=Compatibility.YES, confidence=0.9, evidence=evidence, offsets=offsets
        )
    )


def test_exact_match_passes() -> None:
    assert verify_spans(_fields("does great", (START, END)), DOC) == ()


@pytest.mark.parametrize("shift", [-1, 1])
def test_off_by_one_in_either_direction_fails(shift: int) -> None:
    (violation,) = verify_spans(_fields("does great", (START + shift, END + shift)), DOC)
    assert violation.kind is ViolationKind.TEXT_MISMATCH
    assert violation.path == "good_with_cats"


def test_offsets_past_end_of_text_fail() -> None:
    (violation,) = verify_spans(_fields("does great", (len(TEXT) - 2, len(TEXT) + 50)), DOC)
    assert violation.kind is ViolationKind.OUT_OF_RANGE


def test_negative_offsets_fail() -> None:
    (violation,) = verify_spans(_fields("does great", (-5, 5)), DOC)
    assert violation.kind is ViolationKind.OUT_OF_RANGE


def test_reversed_offsets_fail() -> None:
    (violation,) = verify_spans(_fields("does great", (END, START)), DOC)
    assert violation.kind is ViolationKind.OUT_OF_RANGE


def test_evidence_occurring_twice_is_checked_at_its_stated_position() -> None:
    """A substring search would pass this; only an offset check catches it.

    "does great" appears twice. Pointing at the second occurrence while quoting the
    first is exactly the kind of near-miss that makes a highlight land on the wrong
    clause -- here, on the dog being fine *alone* rather than fine *with cats*.
    """
    second = TEXT.index("does great", START + 1)
    assert verify_spans(_fields("does great", (second, second + 10)), DOC) == ()
    assert verify_spans(_fields("does great with the resident cats", (second, second + 33)), DOC)


def test_whitespace_near_match_fails() -> None:
    (violation,) = verify_spans(_fields("does  great", (START, START + 11)), DOC)
    assert violation.kind is ViolationKind.TEXT_MISMATCH


def test_empty_evidence_is_rejected_before_verification() -> None:
    """Stronger than a span violation: the value cannot be constructed at all."""
    with pytest.raises(ValidationError):
        _fields("", (START, START))


def test_evidence_longer_than_the_document_fails() -> None:
    (violation,) = verify_spans(_fields(TEXT + " and more", (0, len(TEXT) + 9)), DOC)
    assert violation.kind is ViolationKind.OUT_OF_RANGE


def test_emoji_before_the_span_does_not_shift_code_point_offsets() -> None:
    """The UTF-16 trap: a browser would report these offsets two higher."""
    doc = CanonicalText.of("\U0001f436 Rex does great with cats")
    start = doc.text.index("does great")
    assert verify_spans(_fields("does great", (start, start + 10)), doc) == ()


def test_violations_are_reported_per_node_with_a_usable_path() -> None:
    fields = ExtractedFields(
        medical_needs=(
            Note(summary="ok", verbatim="Buddy", offsets=(0, 5), ongoing_care=False),
            Note(summary="bad", verbatim="invented text", offsets=(0, 13), ongoing_care=True),
        )
    )
    (violation,) = verify_spans(fields, DOC)
    assert violation.path == "medical_needs[1]"
