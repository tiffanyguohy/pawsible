"""The canonical-text value type: one text, one hash, one offset space.

Invariant #1 requires that every extracted value carry a verbatim evidence span that
verifies against the description at its stated offsets. That check is only meaningful
if every part of the system agrees on *which string* the offsets index into.

`CanonicalText` makes disagreement unrepresentable. An instance cannot hold
un-normalized text, cannot hold a hash that disagrees with its text, and cannot be
rebuilt from the database against the wrong row without raising. Every downstream
signature takes `CanonicalText` rather than `str`, so under `mypy --strict` passing a
bare string is a type error at CI time rather than a garbage span in production.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import final

from pawsible.text.normalize import NORMALIZATION_VERSION, normalize

__all__ = [
    "NORMALIZATION_VERSION",
    "CanonicalText",
    "CanonicalTextError",
    "HashMismatchError",
    "NotCanonicalError",
    "utf16_to_codepoint",
]


class CanonicalTextError(Exception):
    """Base class for canonical-text construction failures."""


class NotCanonicalError(CanonicalTextError):
    """The supplied text is not in normalized form."""


class HashMismatchError(CanonicalTextError):
    """The supplied text and hash disagree."""


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@final
@dataclass(frozen=True, slots=True)
class CanonicalText:
    """Normalized description text plus the hash that identifies it."""

    text: str
    sha256: str

    def __post_init__(self) -> None:
        # Checked unconditionally rather than only in the factories: a direct
        # constructor call, a dataclasses.replace, or an unpickle all go through here.
        if normalize(self.text) != self.text:
            raise NotCanonicalError("text is not in normalized form")
        if sha256_of(self.text) != self.sha256:
            raise HashMismatchError("text and sha256 disagree")

    @staticmethod
    def of(raw: str) -> CanonicalText:
        """Normalize raw source text and wrap it. The only ingest path."""
        text = normalize(raw)
        return CanonicalText(text=text, sha256=sha256_of(text))

    @staticmethod
    def from_db(text: str, expected_hash: str) -> CanonicalText:
        """Rebuild from a stored row, re-checking the hash.

        This closes the failure mode that is easiest to miss and hardest to spot in
        output: verifying one listing's spans against a different listing's text. A
        row mixup raises here instead of producing plausible-looking garbage.
        """
        return CanonicalText(text=text, sha256=expected_hash)

    def __len__(self) -> int:
        return len(self.text)

    def slice(self, offsets: tuple[int, int]) -> str:
        start, end = offsets
        if start < 0 or end < start or end > len(self.text):
            raise IndexError(
                f"offsets {offsets!r} out of range for text of length {len(self.text)}"
            )
        return self.text[start:end]

    def split_around(self, offsets: tuple[int, int]) -> tuple[str, str, str]:
        """Return (before, evidence, after).

        The UI is served this, never bare offsets: Python indexes by code point while
        JavaScript indexes by UTF-16 code unit, so a single emoji earlier in a
        description silently shifts every highlight. Splitting server-side means the
        frontend does no offset arithmetic at all.
        """
        start, end = offsets
        evidence = self.slice(offsets)
        return self.text[:start], evidence, self.text[end:]


def utf16_to_codepoint(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 code-unit offset (what a browser reports) to a code-point offset.

    `window.getSelection()` and `String.prototype.slice` count UTF-16 code units, so
    any character outside the BMP -- every emoji -- counts as two. The labeler converts
    before saving; this is the reference implementation and the thing its tests check.
    """
    if utf16_offset < 0:
        raise ValueError("utf16_offset must be non-negative")
    units = 0
    for cp_index, ch in enumerate(text):
        if units == utf16_offset:
            return cp_index
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > utf16_offset:
            raise ValueError(f"utf16 offset {utf16_offset} falls inside a surrogate pair")
    if units == utf16_offset:
        return len(text)
    raise ValueError(f"utf16 offset {utf16_offset} is past the end of the text")
