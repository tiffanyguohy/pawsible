"""Field value vocabularies.

Every docstring here is load-bearing: `pawsible.schema.codebook` renders these into the
generated half of `evals/CODEBOOK.md`, and CI fails if the committed codebook drifts
from them. One written definition per value, as the labeling discipline requires.

UNKNOWN is deliberately absent from every enum in this module. See
`pawsible.schema.fields` for why -- it is the decision that keeps NOT_TESTED from ever
collapsing into a positive.
"""

from __future__ import annotations

from enum import StrEnum


class Compatibility(StrEnum):
    """How the shelter describes the animal living with cats, dogs, or children."""

    YES = "YES"
    """Stated to be good with them, without qualification."""

    NO = "NO"
    """Stated to be unsuitable for a home with them."""

    CONDITIONAL = "CONDITIONAL"
    """Suitable only under a stated condition -- "fine with older kids", "cats with a
    slow introduction", "dogs after a meet-and-greet". Collapsing these into YES or NO
    is the second-worst failure in the product, so the condition itself must be in the
    evidence span."""

    NOT_TESTED = "NOT_TESTED"
    """The shelter states the animal has not been tested or observed with them. This
    is a positive assertion found in the text, not an absence of information -- it is
    what distinguishes an untested dog from one nobody wrote about."""


class EnergyLevel(StrEnum):
    """Activity level as the shelter describes it, not as inferred from breed or age."""

    LOW = "LOW"
    """Described as calm, low-key, a couch companion, content with short walks."""

    MODERATE = "MODERATE"
    """Described as enjoying daily walks and play without needing a working outlet."""

    HIGH = "HIGH"
    """Described as needing substantial daily exercise, a running partner, a job."""


class TrainingState(StrEnum):
    """House-training or crate-training status as stated."""

    YES = "YES"
    """Stated to be reliably trained."""

    PARTIAL = "PARTIAL"
    """Stated to be in progress, mostly reliable, or reliable under conditions."""

    NO = "NO"
    """Stated not to be trained."""


class Placement(StrEnum):
    """Where the animal currently lives.

    This changes what the description can even know: a foster who has lived with the
    dog for a month can speak to separation anxiety and house-training; a kennel
    attendant usually cannot.
    """

    FOSTER = "FOSTER"
    """In a foster home."""

    SHELTER = "SHELTER"
    """In a shelter, kennel, or boarding facility."""


class SeparationTolerance(StrEnum):
    """How the animal is described as handling being left alone."""

    GOOD = "GOOD"
    """Stated to settle when left alone."""

    STRUGGLES = "STRUGGLES"
    """Stated to show distress when left alone -- vocalizing, destruction, escape
    attempts, or an explicit separation-anxiety diagnosis."""


class HomeRequirement(StrEnum):
    """Multi-label requirements the shelter states about the adoptive home."""

    FENCED_YARD = "FENCED_YARD"
    """A fenced yard is stated as required."""

    NO_STAIRS = "NO_STAIRS"
    """Stairs are stated to be a problem, or a single-level home is required."""

    QUIET_HOME = "QUIET_HOME"
    """A calm or low-traffic household is stated as required."""

    EXPERIENCED_OWNER = "EXPERIENCED_OWNER"
    """Prior experience with the species, breed, or behavior issue is stated as
    required."""

    APARTMENT_OK = "APARTMENT_OK"
    """Explicitly stated to do well in an apartment or condo."""

    ONLY_PET = "ONLY_PET"
    """Stated to need to be the only animal in the home."""

    NO_SMALL_ANIMALS = "NO_SMALL_ANIMALS"
    """Stated to be unsafe with small animals -- rabbits, rodents, birds, poultry."""
