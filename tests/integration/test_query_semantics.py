"""The query semantics that "UNKNOWN is the absence of a key" buys.

This is the payoff for the schema decision, and it is worth proving against a real
Postgres rather than asserting in prose: if `NOT (fields ? 'good_with_cats')` did not
cleanly separate "nobody said" from "said not tested", the whole argument for removing
UNKNOWN from the enums would collapse.

Marked `db`; skipped unless a Postgres is reachable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, insert, select, text

from pawsible.config import settings
from pawsible.db.tables import extractions, listings, metadata
from pawsible.schema.enums import Compatibility
from pawsible.schema.fields import Extracted, ExtractedFields, to_jsonb

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def engine():  # type: ignore[no-untyped-def]
    try:
        eng = create_engine(settings.database_url)
        with eng.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database reachable: {exc}")
    metadata.create_all(eng)
    return eng


def _span(value: Compatibility) -> Extracted[Compatibility]:
    return Extracted[Compatibility](
        value=value, confidence=0.9, evidence="quoted text", offsets=(0, 11)
    )


@pytest.fixture
def seeded(engine):  # type: ignore[no-untyped-def]
    """Three animals: one cat-safe, one explicitly untested, one nobody mentioned."""
    cases = {
        "yes": ExtractedFields(good_with_cats=_span(Compatibility.YES)),
        "not_tested": ExtractedFields(good_with_cats=_span(Compatibility.NOT_TESTED)),
        "silent": ExtractedFields(),
    }
    ids: dict[str, int] = {}
    with engine.begin() as conn:
        conn.execute(text("delete from extractions"))
        conn.execute(text("delete from listings"))
        for label, fields in cases.items():
            listing_id = conn.execute(
                insert(listings)
                .values(
                    source="rescuegroups",
                    source_id=f"test-{label}",
                    url=f"https://example.invalid/{label}",
                    description_raw="quoted text",
                )
                .returning(listings.c.id)
            ).scalar_one()
            conn.execute(
                insert(extractions).values(
                    listing_id=listing_id,
                    extraction_version=1,
                    model_used="test",
                    prompt_version="test",
                    fields=to_jsonb(fields),
                )
            )
            ids[label] = listing_id
    return ids


def _source_ids(engine, where: str) -> set[str]:  # type: ignore[no-untyped-def]
    stmt = (
        select(listings.c.source_id)
        .select_from(listings.join(extractions, listings.c.id == extractions.c.listing_id))
        .where(text(where))
    )
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(stmt)}


def test_containment_finds_only_the_positive(engine, seeded) -> None:  # type: ignore[no-untyped-def]
    """The query an adopter's "good with cats" filter compiles to.

    It must not return the untested animal. That is the single highest-cost failure in
    the product, and this is the assertion that pins it.
    """
    found = _source_ids(engine, """fields @> '{"good_with_cats":{"value":"YES"}}'""")
    assert found == {"test-yes"}


def test_absent_key_is_the_unknown_query(engine, seeded) -> None:  # type: ignore[no-untyped-def]
    found = _source_ids(engine, """NOT (fields ? 'good_with_cats')""")
    assert found == {"test-silent"}


def test_not_tested_is_addressable_as_its_own_state(engine, seeded) -> None:  # type: ignore[no-untyped-def]
    found = _source_ids(engine, """fields @> '{"good_with_cats":{"value":"NOT_TESTED"}}'""")
    assert found == {"test-not_tested"}


def test_the_three_states_partition_the_corpus(engine, seeded) -> None:  # type: ignore[no-untyped-def]
    """No animal is in two buckets, and none falls through the gaps."""
    yes = _source_ids(engine, """fields @> '{"good_with_cats":{"value":"YES"}}'""")
    untested = _source_ids(engine, """fields @> '{"good_with_cats":{"value":"NOT_TESTED"}}'""")
    unknown = _source_ids(engine, """NOT (fields ? 'good_with_cats')""")
    assert yes.isdisjoint(untested) and yes.isdisjoint(unknown) and untested.isdisjoint(unknown)
    assert yes | untested | unknown == {"test-yes", "test-not_tested", "test-silent"}
