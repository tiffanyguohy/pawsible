"""Stage 4: span verification.

Every `evidence` string must appear at its stated offsets in the canonical text. A
mismatch is a hard failure, not a warning.

This is the mechanism that makes invariant #1 real. It catches fabricated evidence
*mechanically*, with no model in the loop -- a second model asked "is this quote
real?" would be one more thing that can be wrong, whereas string equality cannot.

Pure function. No database, no network, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pawsible.schema.fields import ExtractedFields, iter_spans
from pawsible.text.canonical import CanonicalText

__all__ = ["SpanViolation", "ViolationKind", "verify_spans"]


class ViolationKind(StrEnum):
    OUT_OF_RANGE = "OUT_OF_RANGE"
    """Offsets fall outside the text, or end precedes start."""

    TEXT_MISMATCH = "TEXT_MISMATCH"
    """The text at those offsets is not the quoted evidence. Fabrication, a stale
    offset space, or an off-by-one -- indistinguishable here, and all disqualifying."""


@dataclass(frozen=True, slots=True)
class SpanViolation:
    path: str
    """Dotted path to the offending node, e.g. "medical_needs[2]"."""

    kind: ViolationKind
    offsets: tuple[int, int]
    claimed: str
    """What the extraction said the text says."""

    actual: str | None
    """What the text actually says there, or None when the offsets are unusable."""


def verify_spans(fields: ExtractedFields, doc: CanonicalText) -> tuple[SpanViolation, ...]:
    """Return every span in `fields` that does not verify against `doc`. Empty is a pass.

    Walks for span-bearing nodes rather than consulting a list of fields, so a field
    added to `ExtractedFields` is covered here the moment it exists.
    """
    violations: list[SpanViolation] = []
    for path, span in iter_spans(fields):
        start, end = span.offsets
        claimed = span.evidence_text
        if start < 0 or end < start or end > len(doc):
            violations.append(
                SpanViolation(path, ViolationKind.OUT_OF_RANGE, span.offsets, claimed, None)
            )
            continue
        actual = doc.text[start:end]
        if actual != claimed:
            violations.append(
                SpanViolation(path, ViolationKind.TEXT_MISMATCH, span.offsets, claimed, actual)
            )
    return tuple(violations)
