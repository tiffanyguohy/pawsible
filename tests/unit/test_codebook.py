from __future__ import annotations

from pawsible.schema.codebook import member_docs, render
from pawsible.schema.enums import Compatibility


def test_every_enum_member_has_a_written_definition() -> None:
    """One definition per value, before labeling starts -- the codebook's whole point."""
    for enum_name in (
        "Compatibility",
        "EnergyLevel",
        "TrainingState",
        "Placement",
        "SeparationTolerance",
        "HomeRequirement",
    ):
        docs = member_docs(enum_name)
        missing = [m for m in docs.values() if not m.strip()]
        assert not missing, f"{enum_name} has members with empty definitions"


def test_definitions_cover_all_members() -> None:
    docs = member_docs("Compatibility")
    assert set(docs) == {m.name for m in Compatibility}


def test_render_is_deterministic() -> None:
    assert render() == render()


def test_render_explains_that_unknown_is_absence() -> None:
    assert "UNKNOWN is not a value" in render()


def test_splice_is_idempotent() -> None:
    """`make codebook` must be safe to run repeatedly; CI diffs its output."""
    from pawsible.schema.codebook import splice

    document = "prose\n\n<!-- BEGIN GENERATED -->\n<!-- END GENERATED -->\n"
    once = splice(document)
    assert splice(once) == once
    assert once.startswith("prose")


def test_committed_codebook_is_in_sync_with_the_enums() -> None:
    """The same check CI runs, so it fails locally before it fails in a PR."""
    from pathlib import Path

    from pawsible.schema.codebook import splice

    path = Path(__file__).resolve().parents[2] / "evals" / "CODEBOOK.md"
    current = path.read_text(encoding="utf-8")
    assert splice(current) == current, "evals/CODEBOOK.md is stale; run `make codebook`"
