from __future__ import annotations

import pytest

from pawsible.text.normalize import normalize

# Idempotence is the property every stored offset depends on. If normalize is not a
# fixpoint, re-running the pipeline silently shifts spans that verified yesterday.
IDEMPOTENCE_CASES = [
    "",
    "plain text",
    "Buddy &amp;amp; friends &#39;love&#39; cats",  # Petfinder double-escapes
    "<p>Line one</p><p>Line two</p>",
    "<div><br/><br/>spaced</div>",
    "loves you <3 so much",  # not a tag; must survive
    "a  b   c\r\n\r\n\r\n\r\nd  ",
    "café dog \U0001f436 here",  # combining accent -> NFC
    "trailing   \n\n\n   leading",
    "zero​width﻿joiners",
]


@pytest.mark.parametrize("raw", IDEMPOTENCE_CASES)
def test_normalize_is_idempotent(raw: str) -> None:
    once = normalize(raw)
    assert normalize(once) == once


def test_unescapes_double_escaped_entities() -> None:
    assert normalize("Buddy &amp;amp; Max") == "Buddy & Max"


def test_block_tags_become_line_breaks() -> None:
    assert normalize("<p>one</p><p>two</p>") == "one\n\ntwo"


def test_heart_emoticon_is_not_a_tag() -> None:
    assert normalize("loves you <3 and more") == "loves you <3 and more"


def test_nbsp_collapses_to_plain_space() -> None:
    assert normalize("a  b") == "a b"


def test_blank_runs_collapse_to_one_blank_line() -> None:
    assert normalize("a\n\n\n\n\nb") == "a\n\nb"


def test_combining_marks_are_composed() -> None:
    # Five code points in, four out: the accent composes onto the "e".
    assert len(normalize("café")) == 4
