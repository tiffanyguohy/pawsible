"""Hand-written listings that deliberately hit every hard case in the codebook.

**These are not the golden set and must never become it.** Accuracy claims require
real listings written by real shelter staff; text composed by the same project that
grades it would make the eval circular and void the only claim that matters. These
exist for three narrower jobs, all of which are blocked without *some* text:

1. Writing and iterating on the extraction prompt.
2. Stress-testing `evals/CODEBOOK.md` — definitions that have never met a hard listing
   tend not to survive one, and it is much cheaper to find that out now than after
   100 listings have been labeled against them.
3. Deterministic pipeline tests that need realistic input.

Every entry names the specific failure mode it exists to provoke. If you add one,
say what it is for; a fixture that does not distinguish a right answer from a wrong
one is just more text to read.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["LISTINGS", "SyntheticListing", "source_flatten", "to_resource_object"]


@dataclass(frozen=True)
class SyntheticListing:
    id: str
    covers: str
    """The failure mode this fixture provokes. One line, specific."""

    description_html: str
    structured_attrs: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    """Field -> {"value": ..., "evidence_contains": ...}. A field absent from this
    mapping is expected to be absent from the extraction, i.e. UNKNOWN."""

    notes: str = ""
    expect_canary: bool = False
    """True when our normalization is *expected* to disagree with the source's own
    plain text about characters, not just formatting. Double-escaped HTML does this:
    a source unescaping once renders "&amp;amp;" as "&amp;" where we resolve to "&".
    Exactly the divergence the canary exists to report."""

    species: str = "Dog"
    org_name: str = "Example Rescue"


def source_flatten(description_html: str) -> str:
    """Approximate how a source renders its own `descriptionText` from its HTML.

    Deliberately *not* our normalizer: this collapses paragraph structure to single
    spaces, which ours preserves. That difference is what makes the two independent
    enough for `description_diverges` to be a meaningful canary rather than a tautology.
    """
    text = re.sub(r"<[^>]+>", " ", description_html)
    return " ".join(html.unescape(text).split())


def to_resource_object(listing: SyntheticListing) -> dict[str, Any]:
    """Shape a fixture as a RescueGroups v5 JSON:API resource object.

    Lets the same fixtures exercise the adapter, not just the extractor.
    """
    return {
        "id": listing.id,
        "type": "animals",
        "attributes": {
            "species": listing.species,
            "url": f"https://www.rescuegroups.org/animal/{listing.id}",
            "descriptionHtml": listing.description_html,
            "descriptionText": source_flatten(listing.description_html),
            **listing.structured_attrs,
        },
        "relationships": {"orgs": {"data": [{"type": "orgs", "id": "9001"}]}},
    }


LISTINGS: tuple[SyntheticListing, ...] = (
    # ---- the NOT_TESTED family: the highest-cost failure in the product ----
    SyntheticListing(
        id="syn-001",
        covers="Plain NOT_TESTED phrasing. Must not become YES or UNKNOWN.",
        description_html=(
            "<p>Rosie is a sweet four-year-old girl who came to us from a rural shelter. "
            "She walks nicely on leash and knows sit and paw.</p>"
            "<p>Rosie has not been cat tested. She lived with another dog at her previous "
            "home and did well.</p>"
        ),
        structured_attrs={"isCatsOk": None, "isDogsOk": True, "isKidsOk": None},
        expected={
            "good_with_cats": {
                "value": "NOT_TESTED",
                "evidence_contains": "has not been cat tested",
            },
            "good_with_dogs": {"value": "YES", "evidence_contains": "lived with another dog"},
        },
        notes="good_with_kids stays absent: the text never mentions children.",
    ),
    SyntheticListing(
        id="syn-002",
        covers="NOT_TESTED phrased as an absence of opportunity rather than the word 'tested'.",
        description_html=(
            "<p>Tucker is a big goofy boy who loves tennis balls more than food.</p>"
            "<p>We have not had the chance to see how he does around cats or small animals, "
            "so we cannot say either way.</p>"
        ),
        structured_attrs={"isCatsOk": None, "isFarmAnimalsOk": None},
        expected={
            "good_with_cats": {
                "value": "NOT_TESTED",
                "evidence_contains": "have not had the chance to see how he does around cats",
            }
        },
        notes=(
            "The phrase 'we cannot say either way' reads like uncertainty, but the sentence "
            "asserts a specific fact: no observation was made. That is NOT_TESTED."
        ),
    ),
    SyntheticListing(
        id="syn-003",
        covers="Genuine uncertainty, which is UNKNOWN and NOT NOT_TESTED. The mirror of syn-002.",
        description_html=(
            "<p>Maple came in as a stray so we do not know much about her history.</p>"
            "<p>We are not sure how she would be with cats. She has been friendly with "
            "everyone she has met here.</p>"
        ),
        structured_attrs={"isCatsOk": None},
        expected={},
        notes=(
            "The single most confusable pair in the codebook. 'We are not sure' is an "
            "absence of knowledge, not a statement that testing did not happen, so "
            "good_with_cats must be absent entirely. An extractor that returns "
            "NOT_TESTED here is over-reading; one that returns NO is badly wrong."
        ),
    ),
    SyntheticListing(
        id="syn-004",
        covers="Structured attribute contradicts the description. The headline conflict case.",
        description_html=(
            "<p>Biscuit is a mellow senior who would love a quiet retirement home.</p>"
            "<p>Please note that Biscuit has never been tested with cats, despite what you "
            "may see elsewhere on our site.</p>"
        ),
        structured_attrs={"isCatsOk": True, "isHousetrained": True},
        expected={
            "good_with_cats": {
                "value": "NOT_TESTED",
                "evidence_contains": "never been tested with cats",
            }
        },
        notes=(
            "isCatsOk is ticked true while the text says never tested. The description "
            "wins (invariant #3) and the disagreement is written to attribute_conflicts. "
            "This is the exact shape of the README's headline finding."
        ),
    ),
    # ---- CONDITIONAL: the second-worst failure is collapsing these ----
    SyntheticListing(
        id="syn-005",
        covers="CONDITIONAL on child age. Must not collapse to YES.",
        description_html=(
            "<p>Nala is an affectionate shepherd mix with a lot of energy.</p>"
            "<p>She is great with older children but can be knocked-over-boisterous, so we "
            "are looking for a home with kids aged ten and up.</p>"
        ),
        structured_attrs={"isKidsOk": True, "activityLevel": "High"},
        expected={
            "good_with_kids": {
                "value": "CONDITIONAL",
                "evidence_contains": "great with older children",
            },
            "energy_level": {"value": "HIGH", "evidence_contains": "a lot of energy"},
        },
        notes=(
            "isKidsOk=true is not wrong exactly, it is just incapable of carrying 'ten and "
            "up'. A family with a toddler filters on kid-friendly and gets Nala."
        ),
    ),
    SyntheticListing(
        id="syn-006",
        covers="CONDITIONAL on a slow introduction. The condition must be inside the span.",
        description_html=(
            "<p>Pepper is a curious tabby who supervises all household activity.</p>"
            "<p>She could live with a calm dog with a slow, careful introduction over a "
            "few weeks. She would not do well with a boisterous puppy.</p>"
        ),
        species="Cat",
        structured_attrs={"isDogsOk": True},
        expected={
            "good_with_dogs": {
                "value": "CONDITIONAL",
                "evidence_contains": "with a slow, careful introduction",
            }
        },
        notes="A span reading only 'could live with a calm dog' fails rule 3 in the codebook.",
    ),
    SyntheticListing(
        id="syn-007",
        covers="Positive tone wrapping a hard condition. Tone must not drive the value.",
        description_html=(
            "<p>Otis is a wonderful, loving boy and honestly one of our favourites. "
            "Everybody here adores him.</p>"
            "<p>He would do best as the only pet in the home, though he did share space "
            "with a very calm senior dog in his foster home without issue.</p>"
        ),
        structured_attrs={"isDogsOk": False, "isNeedingFoster": False},
        expected={
            "good_with_dogs": {
                "value": "CONDITIONAL",
                "evidence_contains": "did share space with a very calm senior dog",
            },
            "home_requirements": {
                "value": ["ONLY_PET"],
                "evidence_contains": "would do best as the only pet",
            },
            "placement": {"value": "FOSTER", "evidence_contains": "foster home"},
        },
        notes=(
            "isDogsOk=false flattens a real nuance: Otis is adoptable into a home with a "
            "calm senior dog, and a hard NO removes that home from consideration."
        ),
    ),
    # ---- negation, and the NO that is genuinely NO ----
    SyntheticListing(
        id="syn-008",
        covers="Flat negation. NO, not CONDITIONAL and not NOT_TESTED.",
        description_html=(
            "<p>Duke is a confident rottweiler mix who knows his own mind.</p>"
            "<p>He is not good with cats and has a strong prey drive around small animals. "
            "He must go to a home with no other pets and a securely fenced yard.</p>"
        ),
        structured_attrs={"isCatsOk": False, "isFarmAnimalsOk": False, "isYardRequired": True},
        expected={
            "good_with_cats": {"value": "NO", "evidence_contains": "not good with cats"},
            "home_requirements": {
                "value": ["ONLY_PET", "FENCED_YARD", "NO_SMALL_ANIMALS"],
                "evidence_contains": "securely fenced yard",
            },
        },
        notes=(
            "The one case where the checkbox and the description agree. Worth having: an "
            "extractor that turns every NO into CONDITIONAL would pass the other fixtures."
        ),
    ),
    # ---- span mechanics ----
    SyntheticListing(
        id="syn-009",
        covers="The same phrase appears twice about different subjects. Offsets must disambiguate.",
        description_html=(
            "<p>Juno does great with the resident cats at her foster home.</p>"
            "<p>She also does great when left alone and settles on her bed for the workday.</p>"
        ),
        structured_attrs={"isCatsOk": True},
        expected={
            "good_with_cats": {
                "value": "YES",
                "evidence_contains": "does great with the resident cats",
            },
            "separation_tolerance": {
                "value": "GOOD",
                "evidence_contains": "does great when left alone",
            },
            "placement": {"value": "FOSTER", "evidence_contains": "foster home"},
        },
        notes=(
            "A substring search for 'does great' matches both. Only the offset check "
            "catches a span pointing at the wrong clause, which is why verify_spans "
            "compares at position rather than searching."
        ),
    ),
    SyntheticListing(
        id="syn-010",
        covers="Emoji before the evidence. Code-point vs UTF-16 offsets.",
        description_html=(
            "<p>\U0001f436 \U0001f49b Meet Clover! \U0001f49b \U0001f436</p>"
            "<p>Clover is house trained and crate trained, and she has not been tested "
            "with children.</p>"
        ),
        structured_attrs={"isHousetrained": True, "isKidsOk": None},
        expected={
            "good_with_kids": {
                "value": "NOT_TESTED",
                "evidence_contains": "has not been tested with children",
            },
            "house_trained": {"value": "YES", "evidence_contains": "house trained"},
            "crate_trained": {"value": "YES", "evidence_contains": "crate trained"},
        },
        notes=(
            "Four astral-plane characters before every span. A browser reports offsets "
            "eight code units higher than Python counts. crate_trained has no structured "
            "counterpart at any source, so it is free-text-only by construction."
        ),
    ),
    SyntheticListing(
        id="syn-011",
        covers="Double-escaped entities, nbsp, inline tags. Normalization before offsets.",
        description_html=(
            "<p>Sadie &amp;amp; her sister came in together.</p>"
            "<p>Sadie is <b>great</b> with kids&nbsp;&nbsp;aged 6&#43;, and she&#39;s "
            "been described as a &quot;velcro dog&quot; by her foster.</p>"
        ),
        structured_attrs={"isKidsOk": True},
        expected={
            "good_with_kids": {"value": "CONDITIONAL", "evidence_contains": "aged 6"},
            "placement": {"value": "FOSTER", "evidence_contains": "foster"},
        },
        expect_canary=True,
        notes=(
            "If offsets were computed against the raw HTML rather than the canonical "
            "text, every span here would be wrong by a different amount. This is also "
            "the one fixture where the canary should fire: a source unescaping once "
            "leaves '&amp;' where we resolve through to '&'."
        ),
    ),
    # ---- the negative case ----
    SyntheticListing(
        id="syn-012",
        covers="Boilerplate only. Everything must come back UNKNOWN.",
        description_html=(
            "<p>All of our dogs are spayed or neutered, microchipped, and up to date on "
            "age-appropriate vaccinations before adoption.</p>"
            "<p>Adoption fee is $250. Applications are reviewed in the order received. "
            "We adopt within a two-hour radius of our location.</p>"
        ),
        structured_attrs={"isAltered": True, "isMicrochipped": True, "isCatsOk": True},
        expected={},
        notes=(
            "The most important fixture in the file. Text identical across an "
            "organization's whole roster asserts nothing about this animal. An extractor "
            "that invents fields here will invent them everywhere, and isCatsOk=true "
            "makes the temptation concrete. Everything absent is the only passing result."
        ),
    ),
    # ---- medical and behavioural notes ----
    SyntheticListing(
        id="syn-013",
        covers="ongoing_care true vs false in one listing. Verbatim, never paraphrased.",
        description_html=(
            "<p>Gus tested heartworm positive on intake and is partway through treatment. "
            "He will need his final dose and a follow-up test in March, and must stay on "
            "monthly preventative for life.</p>"
            "<p>He also broke a leg as a puppy, which healed completely and causes him no "
            "trouble now.</p>"
        ),
        structured_attrs={"isSpecialNeeds": True},
        expected={
            "medical_needs": {
                "value": [
                    {"ongoing_care": True, "verbatim_contains": "heartworm positive"},
                    {"ongoing_care": False, "verbatim_contains": "healed completely"},
                ]
            }
        },
        notes=(
            "Two conditions, opposite ongoing_care. The healed fracture must not scare an "
            "adopter off, and the heartworm treatment must not be softened. Both are "
            "displayed as the shelter's own words."
        ),
    ),
    SyntheticListing(
        id="syn-014",
        covers="Separation anxiety and a regressed house-training. STRUGGLES and PARTIAL.",
        description_html=(
            "<p>Ziggy is a velcro boy who wants to be wherever you are.</p>"
            "<p>He becomes distressed when left alone and has damaged a door frame trying "
            "to follow his foster out of the house. He is working on it with a trainer.</p>"
            "<p>He was house trained in his previous home but has had accidents since "
            "coming into the kennel, so he is not fully reliable yet.</p>"
        ),
        structured_attrs={"isHousetrained": True, "isNeedingFoster": True},
        expected={
            "separation_tolerance": {
                "value": "STRUGGLES",
                "evidence_contains": "becomes distressed when left alone",
            },
            "house_trained": {"value": "PARTIAL", "evidence_contains": "not fully reliable"},
            "behavioral_notes": {
                "value": [{"verbatim_contains": "damaged a door frame"}],
            },
        },
        notes=(
            "isHousetrained=true is flatly contradicted. Two conflicting placement signals "
            "appear (a foster is mentioned, and so is the kennel) which is the kind of "
            "thing that should come back UNKNOWN rather than guessed."
        ),
    ),
    # ---- structural hard cases ----
    SyntheticListing(
        id="syn-015",
        covers="Bonded pair with differing attributes. Label only this animal.",
        description_html=(
            "<p>Luna and her brother Milo are a bonded pair and must be adopted together.</p>"
            "<p>Luna is cat friendly and lived happily with two cats in her foster home. "
            "Milo has not been cat tested and would likely chase.</p>"
            "<p>This listing is for Luna.</p>"
        ),
        structured_attrs={"isCatsOk": True},
        expected={
            "good_with_cats": {
                "value": "YES",
                "evidence_contains": "lived happily with two cats",
            },
            "placement": {"value": "FOSTER", "evidence_contains": "foster home"},
        },
        notes=(
            "Both YES and NOT_TESTED appear in the text for the same field, attached to "
            "different animals. Picking Milo's clause would be a span that verifies "
            "perfectly and is still wrong -- the failure mode span checking cannot catch, "
            "and therefore one the prompt has to handle."
        ),
    ),
    SyntheticListing(
        id="syn-016",
        covers="Long first-person foster write-up. Density without over-reading.",
        description_html=(
            "<p>Hi, I'm Winnie's foster mum and I've had her for eleven weeks now, so I "
            "can tell you a lot about her!</p>"
            "<p>Winnie sleeps through the night in her crate without a peep and is fully "
            "house trained -- not one accident since week two. She is happy alone for a "
            "normal work day; I've left her up to six hours with no trouble.</p>"
            "<p>She is a moderate energy girl. A good walk in the morning and a bit of "
            "garden time in the evening and she is content to nap.</p>"
            "<p>My two cats completely ignore her and she ignores them right back. I don't "
            "have children so I genuinely can't tell you how she'd be with them.</p>"
            "<p>She does find stairs difficult with her hip, so a single-level home or one "
            "with a ramp would suit her best.</p>"
        ),
        structured_attrs={
            "isHousetrained": True,
            "isCatsOk": True,
            "isKidsOk": None,
            "activityLevel": "Moderate",
        },
        expected={
            "crate_trained": {"value": "YES", "evidence_contains": "sleeps through the night"},
            "house_trained": {"value": "YES", "evidence_contains": "fully house trained"},
            "separation_tolerance": {"value": "GOOD", "evidence_contains": "happy alone"},
            "energy_level": {"value": "MODERATE", "evidence_contains": "moderate energy"},
            "good_with_cats": {
                "value": "YES",
                "evidence_contains": "My two cats completely ignore her",
            },
            "home_requirements": {
                "value": ["NO_STAIRS"],
                "evidence_contains": "find stairs difficult",
            },
            "placement": {"value": "FOSTER", "evidence_contains": "foster mum"},
        },
        notes=(
            "Eight recoverable fields, which is why placement matters: a foster who has "
            "had the dog eleven weeks can speak to separation and house-training, and a "
            "kennel attendant cannot. good_with_kids must stay absent -- 'I genuinely "
            "can't tell you' is uncertainty, not a statement that testing did not happen. "
            "Compare syn-003."
        ),
    ),
)
