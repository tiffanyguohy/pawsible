"""The `fields` JSONB contract -- the single source of truth for the whole project.

One definition here drives three consumers:

  (a) the Anthropic structured-output schema  (`pawsible.schema.wire`)
  (b) database write validation               (`model_validate` / `model_dump`)
  (c) the generated half of the codebook      (`pawsible.schema.codebook`)

Two invariants are enforced structurally rather than by rule:

**No value without an evidence span (invariant #1).** `evidence`/`verbatim` and
`offsets` have no defaults, so there is no code path that constructs a populated field
without a span. Omitting one is a `ValidationError`, not a convention a prompt might
forget.

**UNKNOWN is the absence of a key, not a value (invariant #2).** NOT_TESTED is a
positive assertion found in the text ("has not been cat tested"), so it has a span.
UNKNOWN is the absence of any assertion, so it has none. Were UNKNOWN an enum member,
`{"value": "UNKNOWN", "confidence": 0.5, "evidence": "", "offsets": [0, 0]}` would be
schema-valid and evidence-free -- which forces a validator special case reading
"empty evidence is allowed iff the value is UNKNOWN". That special case is exactly the
hole through which NOT_TESTED collapses into a positive, which CLAUDE.md names the
highest-cost failure in the product. Deleting the member closes the hole.

This deviates from the literal enum lists in CLAUDE.md section 5. It is a deliberate,
documented choice, not drift.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from pawsible.schema.enums import (
    Compatibility,
    EnergyLevel,
    HomeRequirement,
    Placement,
    SeparationTolerance,
    TrainingState,
)

__all__ = [
    "Extracted",
    "ExtractedFields",
    "Note",
    "Offsets",
    "SpanBearing",
    "iter_spans",
]

Offsets = Annotated[tuple[int, int], Field(description="[start, end) into the canonical text")]


class SpanBearing(BaseModel):
    """Anything carrying a verbatim quote and its offsets into the canonical text.

    `pawsible.extraction.verify` walks for instances of this class rather than iterating a
    hardcoded field registry, so adding a new field to `ExtractedFields` gets span
    verification automatically. There is no list to forget to update.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    offsets: Offsets

    @property
    def evidence_text(self) -> str:
        raise NotImplementedError


class Extracted[V](SpanBearing, frozen=True):
    """A single recovered field value, with the shelter's own words behind it."""

    value: V
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1)

    @property
    def evidence_text(self) -> str:
        return self.evidence


class Note(SpanBearing, frozen=True):
    """A medical need or behavioral note.

    `verbatim` is what gets displayed; `summary` exists only so the value is
    filterable and is never shown to an adopter as the claim. Invariant #3: never
    paraphrase a medical or behavioral claim -- quote it.
    """

    summary: str = Field(min_length=1)
    verbatim: str = Field(min_length=1)
    ongoing_care: bool

    @property
    def evidence_text(self) -> str:
        return self.verbatim


class ExtractedFields(BaseModel):
    """Everything recovered from one listing's description.

    A field set to `None`, or an empty collection, means UNKNOWN: the description made
    no assertion either way. It is stored via `model_dump(exclude_none=True)`, so an
    absent JSONB key is the on-disk representation of UNKNOWN.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    good_with_cats: Extracted[Compatibility] | None = None
    good_with_dogs: Extracted[Compatibility] | None = None
    good_with_kids: Extracted[Compatibility] | None = None
    energy_level: Extracted[EnergyLevel] | None = None
    house_trained: Extracted[TrainingState] | None = None
    crate_trained: Extracted[TrainingState] | None = None
    placement: Extracted[Placement] | None = None
    separation_tolerance: Extracted[SeparationTolerance] | None = None
    home_requirements: tuple[Extracted[HomeRequirement], ...] = ()
    medical_needs: tuple[Note, ...] = ()
    behavioral_notes: tuple[Note, ...] = ()


def iter_spans(fields: ExtractedFields) -> Iterator[tuple[str, SpanBearing]]:
    """Yield every span-bearing node with a dotted path naming where it came from.

    The path is what makes a span violation actionable -- "medical_needs[2]" rather
    than "one of the notes".
    """
    for name in type(fields).model_fields:
        value = getattr(fields, name)
        if value is None:
            continue
        if isinstance(value, SpanBearing):
            yield name, value
        elif isinstance(value, tuple):
            for i, item in enumerate(value):
                if isinstance(item, SpanBearing):
                    yield f"{name}[{i}]", item


def to_jsonb(fields: ExtractedFields) -> dict[str, object]:
    """Serialize for the `extractions.fields` column.

    Absent key means UNKNOWN, so `None` *and* empty collections are both dropped --
    an empty `home_requirements` means the description asserted no requirement, which
    is the same statement as an absent `good_with_cats`. This is what makes
    `NOT (fields ? 'home_requirements')` the correct query for unknown.
    """
    dumped = fields.model_dump(mode="json", exclude_none=True)
    return {k: v for k, v in dumped.items() if v != []}


def from_jsonb(raw: dict[str, object]) -> ExtractedFields:
    """Rebuild from a stored row. Round-trips with `to_jsonb`."""
    return ExtractedFields.model_validate(raw)
