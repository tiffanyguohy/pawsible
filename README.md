# Pawsible

Adoptable-pet matching that actually reads the profile.

**Status: in development.** The extraction schema, the canonical-text layer and the
evaluation harness are built and tested. Not yet deployed, no public instance.

---

## The problem

Shelter and rescue staff put the facts adopters actually decide on into the
description, not the structured checkboxes. Here is one real listing's data, unedited:

```
isCatsOk        = true
isDogsOk        = false
isKidsOk        = null

"Buddy does great with the resident cats but would prefer to be the only dog.
 He has not been tested with small children."
```

Two of those three checkboxes are wrong in ways that matter:

- `isDogsOk = false` flattens *"would prefer to be the only dog"* into a hard no. That
  is a conditional, and a home with no other dogs is a perfectly good home for Buddy.
  A filter for dog-friendly dogs excludes him; so does a filter for dog-free homes,
  because nobody searches that way.
- `isKidsOk = null` is indistinguishable from nobody having filled the field in. But
  the description says something much more specific: he *has not been tested*. A
  filter treats "untested" and "unknown" identically. They are not the same, and the
  difference is the one that gets an animal returned — or a child bitten.

A boolean has three states. The sentence a person wrote has five. **`CONDITIONAL` and
`NOT_TESTED` are not merely missing from the structured data — they are inexpressible
in it.**

## The approach

Pawsible runs an extraction pass over every listing **once at ingest**, recovering those
attributes into a typed schema, and serves search as a plain database filter over the
recovered fields.

That ordering is the whole design. Query time touches no language model, so search is
fast, cheap, reproducible, and identical for every user. It is also what separates this
from pasting listings into a chatbot: the corpus is exhaustively processed in advance,
so a search can assert what is *not* there, and saved searches can run nightly across
the whole corpus.

Scope is national. Adopters filter by location and radius; the corpus itself is not
geographically bounded. Rollout is region-seeded — the first backfill covers a bounded
area so the accuracy numbers and the realized cost per 1k listings can be confirmed
before widening.

## What it guarantees

These are enforced in code, not by asking a model nicely.

**Every value carries its evidence.** A recovered field without a verbatim quote and
its character offsets into the source text fails validation and the record is rejected.
The quote is then checked against the text at those exact offsets — so a fabricated or
misplaced quote is caught by string comparison, with no second model in the loop.

**`UNKNOWN` is the absence of a field, not a value.** `NOT_TESTED` is an assertion
somebody wrote, so it carries a span. `UNKNOWN` is the absence of any assertion, so it
has none. Making `UNKNOWN` a value would mean allowing a value with empty evidence —
and that exception is the only route by which `NOT_TESTED` could ever reach an adopter
rendered as a positive.

**One canonical text.** Source HTML is normalized exactly once, at ingest, and every
offset everywhere indexes into that one string. Normalization is versioned, and the
normalizer is property-tested for idempotence, because a rule change shifts every
stored offset.

**The organization is authoritative.** Pawsible never contradicts, overrides or
paraphrases what a shelter wrote. Medical and behavioral claims are quoted, never
summarized. Every result links back to the original listing. Where a checkbox and a
description disagree, the description is what is shown — and the disagreement is
recorded, because counting those is a finding in itself.

## What it will not do

**No breed identification.** Shelter breed labels are already frequently wrong, and
"correcting" them means an algorithm assigning pit-type identity to a dog — which feeds
euthanasia decisions, housing denials and insurance refusals. Refusing this visibly is
a better signal than building it well.

**No adoptability or appeal scoring**, and **no temperament or health inferred from a
photo**. Pawsible recovers what a person wrote about an animal. It does not generate new
judgments about the animal.

## Evaluation

`evals/` is the most important directory here. Accuracy is reported per field and per
enum value — never as an aggregate, because an aggregate hides exactly the fields that
matter. The rate at which `NOT_TESTED` is misread as a positive is tracked as its own
headline number, and CI blocks any change that regresses it.

Labels are produced against a written codebook (`evals/CODEBOOK.md`) fixed before
labeling begins, and each golden record stores the exact text it was labeled against so
a label cannot silently rot when a normalization rule changes. Human self-agreement is
reported alongside model accuracy, since it is the ceiling on any claim made about the
latter.

## Data sources

RescueGroups.org, plus per-shelter PetPoint/Petango feeds where an organization is
willing to share one. Sources sit behind a single adapter interface; nothing above that
boundary knows where a listing came from.

That boundary earned itself early. The Petfinder API — the original source — was retired
on 2025-12-02 and its hostname no longer resolves. Replacing it touched one adapter and
a field mapping. The schema, the text layer, the validation and the evaluation harness
were untouched.

## Development

Requires Python 3.12 and Docker.

```sh
make dev        # install dependencies
make db-up      # local Postgres 16 + pgvector
make check      # lint, type check, full test suite
```

The test suite bans network access outright via an autouse fixture, so no test can
reach a data source or a model API by accident; extraction is tested against recorded
fixtures. Type checking is strict on the modules that carry the guarantees above.

## Licence

Not yet licensed. Listing data belongs to the organizations that wrote it.
