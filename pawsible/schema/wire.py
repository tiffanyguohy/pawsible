"""Consumer (a): the JSON Schema handed to the Anthropic structured-output API.

Derived from `ExtractedFields` so the model is constrained by the same definition that
validates the database write and generates the codebook. Two transforms separate what
Pydantic emits from what the API accepts:

**Unsupported keywords are stripped.** Structured outputs honor a subset of JSON
Schema; `minimum`, `maxItems`, `minLength` and friends are not in it. They are still
enforced -- by `model_validate` on the way in, client-side, which is where we want the
authority anyway.

**The schema is made total.** Every field is `required`, and an optional one becomes
`anyOf: [<value>, null]`. Forcing the model to emit an explicit `null` rather than
silently omitting a key is a better extraction signal: an omission is ambiguous between
"nothing was asserted" and "I ran out of attention", while a null is a statement.
"""

from __future__ import annotations

import copy
from typing import Any

from pawsible.schema.fields import ExtractedFields

__all__ = ["to_wire_schema"]

# Everything the structured-output API reads. Anything else is dropped.
_KEEP = frozenset(
    {
        "type",
        "enum",
        "const",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "anyOf",
        "$ref",
        "$defs",
        "description",
    }
)


# Keys whose values are name -> schema maps. Their own keys are field names, not
# schema keywords, so they must be recursed into without being filtered.
_SCHEMA_MAPS = frozenset({"properties", "$defs"})


def _strip(node: Any) -> Any:
    if isinstance(node, list):
        return [_strip(item) for item in node]
    if not isinstance(node, dict):
        return node

    # `offsets` is a fixed-length tuple, which Pydantic expresses with prefixItems.
    # Collapse it to a homogeneous array; the length check lives in model_validate.
    prefix = node.get("prefixItems")
    if prefix and "items" not in node:
        node = {**node, "items": prefix[0]}

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key not in _KEEP:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _strip(sub) for name, sub in value.items()}
        else:
            out[key] = _strip(value)
    if out.get("type") == "object":
        out.setdefault("additionalProperties", False)
    return out


def _permits_null(prop: dict[str, Any]) -> bool:
    return any(branch.get("type") == "null" for branch in prop.get("anyOf", []))


def _make_total(schema: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = schema.get("properties", {})
    required: list[str] = list(schema.get("required", []))
    for name, prop in properties.items():
        # Pydantic already renders `X | None` as anyOf[X, null]; wrapping that again
        # would nest a second, meaningless anyOf around it.
        if name in required or _permits_null(prop):
            continue
        description = prop.get("description")
        wrapped: dict[str, Any] = {"anyOf": [prop, {"type": "null"}]}
        if description:
            wrapped["description"] = description
        properties[name] = wrapped
    schema["required"] = list(properties)
    return schema


def to_wire_schema() -> dict[str, Any]:
    """The schema sent to the model. Deterministic: same input bytes every call.

    Determinism matters twice over -- it goes into the prompt cache prefix, and it goes
    into the hash that derives `prompt_version`.
    """
    raw = copy.deepcopy(ExtractedFields.model_json_schema())
    return _make_total(_strip(raw))
