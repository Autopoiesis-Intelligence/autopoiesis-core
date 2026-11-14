"""Domain-neutral state and relation model.

The model is deliberately independent from persistence, execution, providers and
repository integrations. It stores a canonical JSON snapshot and returns fresh
copies to callers so mutations cannot silently alter an existing graph.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


class StateModelError(ValueError):
    """Raised when a state graph is malformed or internally inconsistent."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise StateModelError(
            f"State graph must contain finite JSON-compatible data: {exc}"
        ) from exc


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateModelError(f"{field} must be a non-empty string.")
    if value != value.strip():
        raise StateModelError(f"{field} must not contain surrounding whitespace.")
    return value


def _validate_object_keys(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise StateModelError(f"{field} keys must be strings.")
        for nested in value.values():
            _validate_object_keys(nested, field)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _validate_object_keys(nested, field)


def _attributes(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise StateModelError(f"{field} must be a JSON object.")
    _validate_object_keys(value, field)
    result = dict(value)
    # Validate and detach nested values through a JSON round-trip.
    try:
        return json.loads(_canonical_json(result))
    except StateModelError as exc:
        raise StateModelError(f"{field}: {exc}") from exc


def _normalize_element(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise StateModelError("Every state element must be an object.")
    unknown = set(value) - {"id", "kind", "attributes"}
    if unknown:
        raise StateModelError(
            f"Unknown state element fields: {', '.join(sorted(map(str, unknown)))}"
        )
    return {
        "id": _non_empty_string(value.get("id"), "element.id"),
        "kind": _non_empty_string(value.get("kind"), "element.kind"),
        "attributes": _attributes(value.get("attributes", {}), "element.attributes"),
    }


def _normalize_relation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise StateModelError("Every relation must be an object.")
    unknown = set(value) - {"id", "kind", "source", "target", "attributes"}
    if unknown:
        raise StateModelError(
            f"Unknown relation fields: {', '.join(sorted(map(str, unknown)))}"
        )
    return {
        "id": _non_empty_string(value.get("id"), "relation.id"),
        "kind": _non_empty_string(value.get("kind"), "relation.kind"),
        "source": _non_empty_string(value.get("source"), "relation.source"),
        "target": _non_empty_string(value.get("target"), "relation.target"),
        "attributes": _attributes(
            value.get("attributes", {}), "relation.attributes"
        ),
    }


def _records(value: Any, field: str) -> list[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise StateModelError(f"{field} must be an array.")
    return list(value)


class StateGraph:
    """Immutable canonical snapshot of domain elements X and relations R.

    Element and relation order does not affect the canonical representation.
    Accessors return detached dictionaries; mutating them cannot mutate this
    StateGraph instance.
    """

    __slots__ = ("_canonical",)

    def __init__(
        self,
        elements: Sequence[Mapping[str, Any]],
        relations: Sequence[Mapping[str, Any]],
    ) -> None:
        normalized_elements = [
            _normalize_element(item) for item in _records(elements, "elements")
        ]
        normalized_relations = [
            _normalize_relation(item) for item in _records(relations, "relations")
        ]

        element_ids = [item["id"] for item in normalized_elements]
        relation_ids = [item["id"] for item in normalized_relations]
        if len(element_ids) != len(set(element_ids)):
            raise StateModelError("State element IDs must be unique.")
        if len(relation_ids) != len(set(relation_ids)):
            raise StateModelError("Relation IDs must be unique.")

        known_elements = set(element_ids)
        for relation in normalized_relations:
            for endpoint in ("source", "target"):
                if relation[endpoint] not in known_elements:
                    raise StateModelError(
                        f"Relation {relation['id']!r} references unknown "
                        f"{endpoint} element {relation[endpoint]!r}."
                    )

        document = {
            "elements": sorted(normalized_elements, key=lambda item: item["id"]),
            "relations": sorted(normalized_relations, key=lambda item: item["id"]),
        }
        object.__setattr__(self, "_canonical", _canonical_json(document))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("StateGraph instances are immutable.")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StateGraph:
        """Build a graph from its canonical document shape."""
        if not isinstance(value, Mapping):
            raise StateModelError("State graph document must be an object.")
        unknown = set(value) - {"elements", "relations"}
        if unknown:
            raise StateModelError(
                f"Unknown state graph fields: {', '.join(sorted(map(str, unknown)))}"
            )
        if "elements" not in value or "relations" not in value:
            raise StateModelError("State graph requires elements and relations.")
        return cls(value["elements"], value["relations"])

    @property
    def elements(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(self._canonical)["elements"])

    @property
    def relations(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(self._canonical)["relations"])

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible state graph document."""
        return json.loads(self._canonical)

    def canonical_json(self) -> str:
        """Return the stable serialized representation of this graph."""
        return self._canonical

    @property
    def digest(self) -> str:
        """Return the SHA-256 identity of this canonical graph snapshot."""
        return hashlib.sha256(self._canonical.encode("utf-8")).hexdigest()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StateGraph):
            return NotImplemented
        return self._canonical == other._canonical

    def __hash__(self) -> int:
        return hash(self._canonical)

    def __repr__(self) -> str:
        return (
            f"StateGraph(elements={len(self.elements)}, "
            f"relations={len(self.relations)}, digest={self.digest[:12]!r})"
        )
