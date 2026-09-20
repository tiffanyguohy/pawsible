"""RescueGroups.org v5 adapter.

JSON:API over HTTPS, apikey in the `Authorization` header, free key on request, no
stated request ceiling and no attribution requirement -- better terms than the retired
Petfinder API offered.

The mapping below is the part worth reading. RescueGroups exposes *more* checkbox
attributes than Petfinder did, and every one of them is a boolean or null. That is the
thesis in miniature: `isCatsOk` has three possible states and the shelter's sentence has
five, so CONDITIONAL and NOT_TESTED are not merely missing from the structured data --
they are inexpressible in it.
"""

from __future__ import annotations

from typing import Any, Final

from pawsible.sources.base import RawListing

__all__ = ["CONFLICT_MAP", "SOURCE_NAME", "STRUCTURED_KEYS", "to_raw_listing"]

SOURCE_NAME: Final = "rescuegroups"

# Source attribute -> the Scout field it should be diffed against in
# `attribute_conflicts`. Only fields with a genuine structured counterpart appear;
# `crate_trained` and `separation_tolerance` are deliberately absent, because no source
# has a checkbox for them and they are recoverable only from the description.
CONFLICT_MAP: Final[dict[str, str]] = {
    "isCatsOk": "good_with_cats",
    "isDogsOk": "good_with_dogs",
    "isKidsOk": "good_with_kids",
    "isHousetrained": "house_trained",
    "activityLevel": "energy_level",
}

# Everything preserved verbatim in `listings.structured_attrs`. Broader than
# CONFLICT_MAP: these also feed home_requirements and medical_needs comparisons, and a
# field that is always null is itself a reportable finding about the source.
STRUCTURED_KEYS: Final[tuple[str, ...]] = (
    "isCatsOk",
    "isDogsOk",
    "isKidsOk",
    "isFarmAnimalsOk",
    "isSeniorsOk",
    "isHousetrained",
    "isYardRequired",
    "isSpecialNeeds",
    "isCurrentVaccinations",
    "isAltered",
    "isMicrochipped",
    "isDeclawed",
    "isNeedingFoster",
    "isAdoptionPending",
    "activityLevel",
    "energyLevel",
    "exerciseNeeds",
)


def _relationship_id(item: dict[str, Any], name: str) -> str | None:
    data = item.get("relationships", {}).get(name, {}).get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    if isinstance(data, dict):
        identifier = data.get("id")
        return str(identifier) if identifier is not None else None
    return None


def to_raw_listing(item: dict[str, Any], *, org_names: dict[str, str] | None = None) -> RawListing:
    """Map one JSON:API `animals` resource object to a `RawListing`.

    Pure: no network, no clock, no database. That is what lets the sync be tested
    against recorded fixtures rather than a live key.
    """
    attrs: dict[str, Any] = item.get("attributes", {})
    org_id = _relationship_id(item, "orgs")

    pictures = attrs.get("pictureThumbnailUrl") or attrs.get("pictureUrl")
    photos: tuple[str, ...] = (str(pictures),) if isinstance(pictures, str) else ()

    return RawListing(
        source=SOURCE_NAME,
        source_id=str(item["id"]),
        url=str(attrs.get("url") or f"https://www.rescuegroups.org/animal/{item['id']}"),
        org_id=org_id,
        org_name=(org_names or {}).get(org_id or ""),
        species=_lower(attrs.get("species")),
        breed_primary=attrs.get("breedPrimary"),
        breed_mixed=attrs.get("isBreedMixed"),
        sex=_lower(attrs.get("sex")),
        age_bucket=_lower(attrs.get("ageGroup")),
        size_bucket=_lower(attrs.get("sizeGroup")),
        weight_lb_listed=_float(attrs.get("sizeCurrent")),
        photos=photos,
        # The HTML is the ingest path; their plain text is only a canary.
        description_html=attrs.get("descriptionHtml"),
        description_text=attrs.get("descriptionText"),
        structured_attrs={k: attrs[k] for k in STRUCTURED_KEYS if k in attrs},
    )


def _lower(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) and value else None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def description_diverges(canonical_text: str, source_text: str | None) -> bool:
    """True when our normalization of the HTML disagrees with the source's own plain text.

    Compared with all whitespace collapsed, because a disagreement about *formatting* is
    expected and uninteresting -- we deliberately preserve paragraph breaks that their
    flattened text discards. What this is watching for is a disagreement about
    *characters*: an entity we unescape and they do not, a tag we strip and they keep.
    That is the signal that a source changed its stripping rules, which is the event that
    would otherwise shift every stored offset without anyone noticing.
    """
    if source_text is None:
        return False
    return " ".join(canonical_text.split()) != " ".join(source_text.split())
