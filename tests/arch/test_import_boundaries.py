"""The layering rule, enforced rather than documented.

    layer 0: pawsible.schema, pawsible.text, pawsible.config   import nothing else from pawsible
    layer 1: pawsible.db
    layer 2: pawsible.extraction, pawsible.sources, pawsible.sync, pawsible.query
    layer 3: pawsible.web, pawsible.jobs, pawsible.notify

Layer 0 importing nothing is the load-bearing part. `pawsible.schema` and `pawsible.text`
carry the invariants, so `evals/` must be able to import them without dragging in a
database driver or an HTTP client -- and `mypy --strict` over them stays fast and free
of third-party stub gaps.

`evals/` additionally may not import `pawsible.web` or `pawsible.db`: an eval that can reach
the database is an eval that can accidentally grade against production rows.

Thirty lines of `ast` beats adding import-linter as a dependency, and it fails in the
same pytest run as everything else.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

LAYER = {
    "pawsible.config": 0,
    "pawsible.schema": 0,
    "pawsible.text": 0,
    "pawsible.db": 1,
    "pawsible.extraction": 2,
    "pawsible.sources": 2,
    "pawsible.sync": 2,
    "pawsible.query": 2,
    "pawsible.web": 3,
    "pawsible.jobs": 3,
    "pawsible.notify": 3,
}

EVALS_FORBIDDEN = ("pawsible.web", "pawsible.db")


def _package_of(module: str) -> str | None:
    parts = module.split(".")
    for depth in (2, 1):
        candidate = ".".join(parts[:depth])
        if candidate in LAYER:
            return candidate
    return None


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module)
    return [m for m in found if m == "pawsible" or m.startswith("pawsible.")]


def _python_files(*relative: str) -> list[Path]:
    return sorted(p for r in relative for p in (ROOT / r).rglob("*.py"))


@pytest.mark.parametrize("path", _python_files("pawsible"), ids=lambda p: str(p.relative_to(ROOT)))
def test_module_only_imports_its_own_layer_or_below(path: Path) -> None:
    own = _package_of(path.relative_to(ROOT).with_suffix("").as_posix().replace("/", "."))
    if own is None:
        pytest.skip("module is not in a layered package")
    for imported in _imported_modules(path):
        target = _package_of(imported)
        if target is None or target == own:
            continue
        assert LAYER[target] <= LAYER[own], (
            f"{path.relative_to(ROOT)} (layer {LAYER[own]}) imports {imported} "
            f"(layer {LAYER[target]}); imports may only go downward"
        )


@pytest.mark.parametrize("path", _python_files("evals"), ids=lambda p: str(p.relative_to(ROOT)))
def test_evals_cannot_reach_the_database_or_the_web_layer(path: Path) -> None:
    for imported in _imported_modules(path):
        assert not imported.startswith(EVALS_FORBIDDEN), (
            f"{path.relative_to(ROOT)} imports {imported}; evals must not depend on "
            "the database or the web layer"
        )
