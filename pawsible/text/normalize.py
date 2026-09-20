"""Canonical normalization of shelter description text.

This module is the *only* place raw source bytes become canonical text. Everything
downstream -- extraction prompts, evidence spans, golden labels, UI highlighting --
indexes into the string this function produces.

`normalize` MUST be idempotent: `normalize(normalize(s)) == normalize(s)` for every
input. That property is what makes an offset stable, and it is property-tested.

Changing any rule here shifts every offset already stored in the database and
invalidates every hand-labeled golden span. That is why `NORMALIZATION_VERSION`
exists and is written to `listings` -- bump it, and the re-extraction gate correctly
treats the whole corpus as stale.
"""

from __future__ import annotations

import html
import re
import unicodedata

NORMALIZATION_VERSION = 1

_MAX_UNESCAPE_PASSES = 3

# Tags that carry line structure in shelter HTML. Replaced with a newline rather
# than removed, so paragraph breaks in the original survive into the canonical text.
_BLOCK_TAG = re.compile(r"</?(?:br|p|div|li|tr|h[1-6])\b[^>]*>", re.IGNORECASE)

# Any remaining tag. The leading letter requirement is deliberate: it stops this from
# eating "loves you <3 and cuddles" -- shelter descriptions really do contain "<3".
_ANY_TAG = re.compile(r"</?[a-zA-Z][^>]*>")

_ZERO_WIDTH = re.compile(r"[​‌‍﻿]")

# Horizontal whitespace, including the nbsp that "&nbsp;" unescapes into.
_H_SPACE = re.compile(r"[ \t   -   　]+")

_BLANK_RUN = re.compile(r"\n{3,}")


def _unescape_to_fixpoint(raw: str) -> str:
    """Unescape HTML entities repeatedly. Petfinder double-escapes ("&amp;#39;")."""
    for _ in range(_MAX_UNESCAPE_PASSES):
        out = html.unescape(raw)
        if out == raw:
            return out
        raw = out
    return raw


def normalize(raw: str) -> str:
    """Return the canonical form of a description. Idempotent."""
    s = _unescape_to_fixpoint(raw)
    s = _BLOCK_TAG.sub("\n", s)
    s = _ANY_TAG.sub("", s)
    s = _ZERO_WIDTH.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = unicodedata.normalize("NFC", s)
    s = "\n".join(_H_SPACE.sub(" ", line).strip() for line in s.split("\n"))
    s = _BLANK_RUN.sub("\n\n", s)
    return s.strip()
