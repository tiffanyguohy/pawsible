"""The fixtures have to be correct before anything can be measured against them.

An expectation naming evidence that does not appear in the text is unsatisfiable: no
extractor could ever pass it, and the failure would look like a model problem rather
than a fixture problem. These checks run in CI so that stays impossible.
"""

from __future__ import annotations

import pytest

from pawsible.schema.enums import (
    Compatibility,
    EnergyLevel,
    HomeRequirement,
    Placement,
    SeparationTolerance,
    TrainingState,
)
from pawsible.schema.fields import ExtractedFields
from pawsible.sources.rescuegroups import description_diverges, to_raw_listing
from pawsible.text.canonical import CanonicalText
from tests.fixtures.synthetic import LISTINGS, to_resource_object

ENUM_FOR_FIELD = {
    "good_with_cats": Compatibility,
    "good_with_dogs": Compatibility,
    "good_with_kids": Compatibility,
    "energy_level": EnergyLevel,
    "house_trained": TrainingState,
    "crate_trained": TrainingState,
    "placement": Placement,
    "separation_tolerance": SeparationTolerance,
    "home_requirements": HomeRequirement,
}

IDS = [listing.id for listing in LISTINGS]


def _canonical(listing) -> CanonicalText:  # type: ignore[no-untyped-def]
    return CanonicalText.of(listing.description_html)


def test_ids_are_unique() -> None:
    assert len(IDS) == len(set(IDS))


@pytest.mark.parametrize("listing", LISTINGS, ids=IDS)
def test_every_fixture_says_what_it_is_for(listing) -> None:  # type: ignore[no-untyped-def]
    assert listing.covers.strip(), f"{listing.id} does not name a failure mode"


@pytest.mark.parametrize("listing", LISTINGS, ids=IDS)
def test_expected_evidence_actually_appears_in_the_canonical_text(listing) -> None:  # type: ignore[no-untyped-def]
    """The check that makes every expectation satisfiable."""
    text = _canonical(listing).text
    for field, spec in listing.expected.items():
        if isinstance(spec.get("value"), list):
            for entry in spec["value"]:
                if not isinstance(entry, dict):
                    continue  # multi-label enum values carry no verbatim of their own
                needle = entry.get("verbatim_contains")
                if needle:
                    assert needle in text, f"{listing.id}.{field}: {needle!r} not in text"
        needle = spec.get("evidence_contains")
        if needle:
            assert needle in text, f"{listing.id}.{field}: {needle!r} not in text"


@pytest.mark.parametrize("listing", LISTINGS, ids=IDS)
def test_expected_fields_and_values_exist_in_the_schema(listing) -> None:  # type: ignore[no-untyped-def]
    for field, spec in listing.expected.items():
        assert field in ExtractedFields.model_fields, f"{listing.id}: no such field {field}"
        enum_cls = ENUM_FOR_FIELD.get(field)
        if enum_cls is None:
            continue
        values = spec["value"] if isinstance(spec["value"], list) else [spec["value"]]
        for value in values:
            if isinstance(value, dict):
                continue
            assert value in {m.value for m in enum_cls}, f"{listing.id}.{field}: bad {value!r}"


@pytest.mark.parametrize("listing", LISTINGS, ids=IDS)
def test_fixtures_round_trip_through_the_adapter(listing) -> None:  # type: ignore[no-untyped-def]
    raw = to_raw_listing(to_resource_object(listing))
    assert raw.source_id == listing.id
    assert raw.description_html == listing.description_html
    assert raw.structured_attrs.keys() <= set(listing.structured_attrs)


@pytest.mark.parametrize("listing", LISTINGS, ids=IDS)
def test_canary_stays_quiet_on_formatting_differences(listing) -> None:  # type: ignore[no-untyped-def]
    """source_flatten drops paragraph breaks that our normalizer keeps.

    If the canary fired on that, it would fire on every real listing too and be
    useless for spotting the thing it exists to spot.
    """
    raw = to_raw_listing(to_resource_object(listing))
    assert raw.description_html is not None
    doc = CanonicalText.of(raw.description_html)
    diverged = description_diverges(doc.text, raw.description_text)
    assert diverged is listing.expect_canary, (
        f"{listing.id}: canary {'fired' if diverged else 'stayed quiet'}, "
        f"expected {'fire' if listing.expect_canary else 'quiet'}"
    )


def test_the_hard_pairs_are_both_present() -> None:
    """NOT_TESTED and genuine uncertainty must both exist, or neither is testable.

    An extractor can score well on one alone by always guessing that answer.
    """
    covered = " ".join(listing.covers for listing in LISTINGS)
    assert "NOT_TESTED" in covered and "UNKNOWN" in covered
    assert any(listing.expected == {} for listing in LISTINGS), "no all-UNKNOWN fixture"
    assert any("CONDITIONAL" in listing.covers for listing in LISTINGS)
    assert any("NO," in listing.covers for listing in LISTINGS)


def test_structured_attrs_contradict_the_text_somewhere() -> None:
    """attribute_conflicts needs a fixture that actually produces a conflict."""
    conflicted = [
        listing
        for listing in LISTINGS
        if listing.structured_attrs.get("isCatsOk") is True
        and listing.expected.get("good_with_cats", {}).get("value")
        in {"NOT_TESTED", "NO", "CONDITIONAL"}
    ]
    assert conflicted, "no fixture where a ticked checkbox disagrees with the description"
