"""SQLAlchemy Core table definitions. Alembic's `target_metadata`.

Core rather than ORM on purpose: the recovered fields are queried as real columns and
JSONB containment, and an ORM's identity map buys nothing for a pipeline that reads
rows, writes rows, and never mutates an object graph.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

metadata = MetaData()

JSONB_OR_JSON = JSONB().with_variant(JSON(), "sqlite")
TEXT_ARRAY = ARRAY(Text()).with_variant(JSON(), "sqlite")

listings = Table(
    "listings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source", String(32), nullable=False),
    Column("source_id", String(64), nullable=False),
    Column("org_id", String(64)),
    Column("org_name", Text),
    Column("species", String(16)),
    Column("breed_primary", Text),
    Column("breed_mixed", Boolean),
    Column("sex", String(16)),
    Column("age_bucket", String(16)),
    Column("size_bucket", String(16)),
    Column("weight_lb_listed", Float),
    Column("photos", TEXT_ARRAY),
    Column("url", Text, nullable=False),
    # The canonical normalized text. Every evidence-span offset in the system indexes
    # into this string and no other.
    Column("description_raw", Text),
    # The source's original bytes, kept for provenance. Nothing reads this except a
    # debugging view -- it exists so that a normalization bug is diagnosable.
    Column("description_source", Text),
    Column("description_hash", String(64)),
    # Part of the re-extraction staleness check alongside extraction_version and
    # prompt_version: changing a normalization rule shifts every stored offset, so the
    # whole corpus is correctly stale.
    Column("normalization_version", Integer, nullable=False, server_default="1"),
    Column("structured_attrs", JSONB_OR_JSON, nullable=False, server_default="{}"),
    Column("first_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Soft delete. Rows are never deleted: first_seen_at together with removed_at yields
    # length of stay and adoption timing, which is a dataset nobody else is keeping.
    Column("removed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("source", "source_id", name="uq_listings_source_source_id"),
    Index("ix_listings_active", "removed_at"),
    Index("ix_listings_species", "species"),
    Index("ix_listings_hash", "description_hash"),
)

extractions = Table(
    "extractions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("listing_id", Integer, ForeignKey("listings.id"), nullable=False),
    Column("extraction_version", Integer, nullable=False),
    Column("model_used", String(64), nullable=False),
    # Derived from the prompt bytes plus the wire schema, so an extraction is always
    # attributable to the exact prompt that produced it.
    Column("prompt_version", String(64), nullable=False),
    Column("fields", JSONB_OR_JSON, nullable=False),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("cost_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("latency_ms", Integer, nullable=False, server_default="0"),
    Column("escalated", Boolean, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Append-only: never overwrite an extraction, let the latest-per-listing view win.
    UniqueConstraint(
        "listing_id", "extraction_version", "prompt_version", name="uq_extractions_listing_version"
    ),
    Index("ix_extractions_listing", "listing_id"),
)

# GIN index over the recovered fields. `fields @> '{"good_with_cats":{"value":"YES"}}'`
# is the positive query; `NOT (fields ? 'good_with_cats')` is the unknown one, which is
# what "UNKNOWN is the absence of a key" buys at query time.
Index(
    "ix_extractions_fields_gin",
    extractions.c.fields,
    postgresql_using="gin",
    postgresql_ops={"fields": "jsonb_path_ops"},
)

attribute_conflicts = Table(
    "attribute_conflicts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("listing_id", Integer, ForeignKey("listings.id"), nullable=False),
    Column("field", String(64), nullable=False),
    Column("structured_value", Text),
    Column("extracted_value", String(32), nullable=False),
    Column("evidence", Text, nullable=False),
    Column("offsets", JSONB_OR_JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_conflicts_field", "field"),
)

# CLAUDE.md §6 requires every pipeline stage to write a trace row, but §5 defines no
# table for it. These two are that table.
pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("source", String(32)),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(16), nullable=False, server_default="running"),
    Column("seen_count", Integer),
    Column("previous_active_count", Integer),
    Column("soft_deleted_count", Integer),
    # Set when the soft-delete was skipped, naming which guard tripped. A sync that
    # declines to delete must say so loudly rather than look like a clean run.
    Column("softdelete_skipped_reason", Text),
    Column("error", Text),
    # A national sync is long enough to die partway through; the cursor is what makes
    # the next run resume rather than restart.
    Column("cursor", Text),
    Index("ix_runs_kind_started", "kind", "started_at"),
)

pipeline_stage_traces = Table(
    "pipeline_stage_traces",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("pipeline_runs.id"), nullable=False),
    Column("listing_id", Integer, ForeignKey("listings.id")),
    Column("stage", String(32), nullable=False),
    Column("ok", Boolean, nullable=False),
    Column("detail", JSONB_OR_JSON, nullable=False, server_default="{}"),
    Column("latency_ms", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_traces_run_stage", "run_id", "stage"),
)

saved_searches = Table(
    "saved_searches",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", Text, nullable=False),
    Column("filters", JSONB_OR_JSON, nullable=False),
    Column("radius_mi", Integer),
    Column("location", String(16)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_run_at", DateTime(timezone=True)),
    Column("active", Boolean, nullable=False, server_default="true"),
    Index("ix_saved_active", "active"),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("saved_search_id", Integer, ForeignKey("saved_searches.id"), nullable=False),
    Column("listing_id", Integer, ForeignKey("listings.id"), nullable=False),
    Column("sent_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("channel", String(16), nullable=False, server_default="email"),
    # Prevents telling the same person about the same animal twice.
    UniqueConstraint("saved_search_id", "listing_id", name="uq_notification_once"),
)
