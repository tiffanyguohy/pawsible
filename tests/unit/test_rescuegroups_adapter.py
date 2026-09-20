"""The RescueGroups adapter, tested against a recorded resource object.

Pure mapping, so no key and no network -- which is the point of putting the network
behind the `ListingSource` protocol rather than inside the mapping.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pawsible.sources.base import ListingSource, RawListing
from pawsible.sources.rescuegroups import (
    CONFLICT_MAP,
    SOURCE_NAME,
    description_diverges,
    to_raw_listing,
)
from pawsible.text.canonical import CanonicalText

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "rescuegroups_animal.json").read_text()
)


@pytest.fixture
def listing() -> RawListing:
    return to_raw_listing(FIXTURE, org_names={"4412": "Steel City Rescue"})


def test_identity_fields_map(listing: RawListing) -> None:
    assert (listing.source, listing.source_id) == (SOURCE_NAME, "18234567")
    assert listing.org_id == "4412"
    assert listing.org_name == "Steel City Rescue"
    assert listing.url.endswith("/18234567")


def test_descriptive_fields_are_normalized_to_lowercase_buckets(listing: RawListing) -> None:
    assert listing.species == "dog"
    assert listing.age_bucket == "adult"
    assert listing.size_bucket == "large"
    assert listing.weight_lb_listed == 68.0
    assert listing.breed_mixed is True


def test_html_is_the_ingest_path_and_their_text_is_only_a_canary(listing: RawListing) -> None:
    assert listing.description_html is not None
    assert "<p>" in listing.description_html
    assert listing.description_text is not None


def test_canonical_text_comes_from_the_html(listing: RawListing) -> None:
    assert listing.description_html is not None
    doc = CanonicalText.of(listing.description_html)
    assert "&nbsp;" not in doc.text
    assert "<b>" not in doc.text
    # Paragraph structure we keep and their flattened text discards.
    assert "\n\n" in doc.text
    assert doc.text.startswith("Buddy does great with the resident cats")


def test_canary_ignores_formatting_but_would_catch_character_divergence() -> None:
    assert description_diverges("a b\n\nc", "a b c") is False
    assert description_diverges("Buddy & Max", "Buddy &amp; Max") is True
    assert description_diverges("anything", None) is False


def test_structured_attrs_preserve_nulls(listing: RawListing) -> None:
    """The nulls are the finding, so they must survive ingest.

    `isKidsOk` is null here while the description says the dog "has not been tested
    with small children" -- the checkbox cannot distinguish NOT_TESTED from nobody
    having filled it in, which is exactly what `attribute_conflicts` is built to count.
    """
    assert "isKidsOk" in listing.structured_attrs
    assert listing.structured_attrs["isKidsOk"] is None
    assert listing.structured_attrs["isCatsOk"] is True
    assert listing.structured_attrs["isDogsOk"] is False


def test_conflict_map_only_names_real_schema_fields() -> None:
    from pawsible.schema.fields import ExtractedFields

    assert set(CONFLICT_MAP.values()) <= set(ExtractedFields.model_fields)


def test_fields_with_no_checkbox_anywhere_are_deliberately_unmapped() -> None:
    """crate_trained and separation_tolerance are recoverable only from free text.

    They are the cleanest demonstration of the product: there is no checkbox to
    disagree with, so a structured filter cannot express them at all.
    """
    assert "crate_trained" not in CONFLICT_MAP.values()
    assert "separation_tolerance" not in CONFLICT_MAP.values()


def test_missing_optional_attributes_do_not_raise() -> None:
    minimal = to_raw_listing({"id": "1", "type": "animals", "attributes": {}})
    assert minimal.source_id == "1"
    assert minimal.description_html is None
    assert minimal.structured_attrs == {}
    assert minimal.photos == ()


def test_adapter_module_satisfies_the_source_protocol_shape() -> None:
    class _Fake:
        name = SOURCE_NAME

        def fetch_all(self):  # type: ignore[no-untyped-def]
            yield to_raw_listing(FIXTURE)

    assert isinstance(_Fake(), ListingSource)
