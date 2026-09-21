"""Settings, from the environment only.

Model IDs live here rather than in the extraction code so the eval harness can sweep
them: which tier-1/tier-2 pair is correct is a question the golden set answers, not one
to settle by argument.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "settings"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pawsible:pawsible@localhost:5433/pawsible"

    rescuegroups_api_key: str = ""
    anthropic_api_key: str = ""

    tier1_model: str = Field(default="claude-haiku-4-5", alias="PAWSIBLE_TIER1_MODEL")
    tier2_model: str = Field(default="claude-sonnet-5", alias="PAWSIBLE_TIER2_MODEL")

    seed_location: str = Field(default="", alias="PAWSIBLE_SEED_LOCATION")
    """Postal code bounding the backfill. Empty means nationwide -- see CLAUDE.md §3."""

    seed_radius_mi: int = Field(default=100, alias="PAWSIBLE_SEED_RADIUS_MI")

    escalate_unknown_min_chars: int = 400
    escalate_mean_confidence_below: float = 0.7
    """The two numeric escalation thresholds, held as settings so tests can parametrize
    the boundaries rather than hardcode them alongside the comparison they check."""

    softdelete_min_seen_fraction: float = 0.70
    """A sync that sees less than this fraction of the previously-active count does not
    soft-delete. A source returning 200 with an empty body during an outage would
    otherwise remove the entire catalog while every request looked successful."""


settings = Settings()
