from __future__ import annotations

import pytest

from pawsible.text.canonical import (
    CanonicalText,
    HashMismatchError,
    NotCanonicalError,
    sha256_of,
    utf16_to_codepoint,
)


def test_of_normalizes_and_hashes() -> None:
    doc = CanonicalText.of("Buddy &#39;does great&#39;  with  cats")
    assert doc.text == "Buddy 'does great' with cats"
    assert doc.sha256 == sha256_of(doc.text)


def test_direct_construction_rejects_unnormalized_text() -> None:
    with pytest.raises(NotCanonicalError):
        CanonicalText(text="not  normalized  ", sha256=sha256_of("not  normalized  "))


def test_construction_rejects_disagreeing_hash() -> None:
    with pytest.raises(HashMismatchError):
        CanonicalText(text="fine", sha256="deadbeef")


def test_from_db_rejects_the_wrong_rows_hash() -> None:
    """The failure mode this exists for: verifying listing A's spans against B's text."""
    a = CanonicalText.of("dog A is good with cats")
    b = CanonicalText.of("dog B has not been cat tested")
    with pytest.raises(HashMismatchError):
        CanonicalText.from_db(a.text, b.sha256)


def test_split_around_returns_three_parts() -> None:
    doc = CanonicalText.of("Buddy does great with cats")
    i = doc.text.index("does great")
    assert doc.split_around((i, i + 10)) == ("Buddy ", "does great", " with cats")


def test_slice_rejects_out_of_range() -> None:
    doc = CanonicalText.of("short")
    with pytest.raises(IndexError):
        doc.slice((0, 99))


@pytest.mark.parametrize(
    ("utf16", "expected"),
    [(0, 0), (1, 1), (3, 2), (4, 3), (5, 4)],
)
def test_utf16_offsets_convert_across_an_emoji(utf16: int, expected: int) -> None:
    # "a\U0001f436bc": the dog occupies two UTF-16 units but one code point.
    assert utf16_to_codepoint("a\U0001f436bc", utf16) == expected


def test_utf16_offset_inside_a_surrogate_pair_is_an_error() -> None:
    with pytest.raises(ValueError, match="surrogate"):
        utf16_to_codepoint("a\U0001f436bc", 2)
