"""The source-agnostic ingest boundary.

Scout's thesis is about what shelters write, not about who hosts it. Petfinder's
retirement on 2025-12-02 proved the point the hard way: the API vanished, and the only
thing that needed replacing was an adapter. Everything above this boundary --
the schema, the canonical text, span verification, the evals -- is untouched by it.

An adapter's whole job is to produce `RawListing`s. It does not normalize, does not
hash, and does not touch the database. Normalization happens once, above, so that a
source changing its own text-stripping rules cannot silently shift every stored offset.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = ["ListingSource", "RawListing", "SourceFetchError"]


class SourceFetchError(Exception):
    """A page could not be fetched.

    Raised rather than swallowed: a partial sync must never be mistaken for a complete
    one, because the soft-delete that follows a complete sync would wipe everything the
    failed pages would have contained.
    """


@dataclass(frozen=True, slots=True)
class RawListing:
    """One animal as a source describes it, before any Scout processing."""

    source: str
    source_id: str
    url: str

    org_id: str | None = None
    org_name: str | None = None
    species: str | None = None
    breed_primary: str | None = None
    breed_mixed: bool | None = None
    sex: str | None = None
    age_bucket: str | None = None
    size_bucket: str | None = None
    weight_lb_listed: float | None = None
    photos: tuple[str, ...] = ()

    description_html: str | None = None
    """The source's rich description. This is what gets normalized -- see the module
    docstring for why we do not take a source's pre-stripped plain text."""

    description_text: str | None = None
    """The source's own plain-text rendering, kept only as a cross-check. A divergence
    from our normalization of `description_html` is a useful canary that a source
    changed its stripping rules."""

    structured_attrs: dict[str, Any] = field(default_factory=dict)
    """The source's own checkbox answers, verbatim. These are what `attribute_conflicts`
    diffs the recovered fields against, so they are stored exactly as received -- including
    nulls, which are themselves the finding: a boolean cannot express CONDITIONAL or
    NOT_TESTED at all."""


@runtime_checkable
class ListingSource(Protocol):
    """Every ingest source implements this and nothing more."""

    name: str
    """Stored in `listings.source`; half of the `(source, source_id)` upsert key."""

    def fetch_all(self) -> Iterator[RawListing]:
        """Yield every currently-available listing in scope.

        Must raise `SourceFetchError` rather than return short on a partial failure.
        """
        ...
