import unittest

from autopoesis.domain import StateGraph, StateModelError


class StateGraphTests(unittest.TestCase):
    def setUp(self):
        self.elements = [
            {"id": "account", "kind": "entity", "attributes": {"balance": 12}},
            {"id": "ledger", "kind": "collection", "attributes": {"currency": "EUR"}},
        ]
        self.relations = [
            {
                "id": "owns-ledger",
                "kind": "owns",
                "source": "account",
                "target": "ledger",
                "attributes": {"since": 2025},
            }
        ]

    def test_builds_state_and_relation_model(self):
        graph = StateGraph(self.elements, self.relations)
        self.assertEqual(len(graph.elements), 2)
        self.assertEqual(len(graph.relations), 1)
        self.assertEqual(graph.to_dict()["elements"][0]["id"], "account")

    def test_digest_is_deterministic_and_order_independent(self):
        first = StateGraph(self.elements, self.relations)
        second = StateGraph(
            list(reversed(self.elements)),
            list(reversed(self.relations)),
        )
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.digest, second.digest)

    def test_attribute_key_order_does_not_change_digest(self):
        first = StateGraph(
            [{"id": "a", "kind": "node", "attributes": {"x": 1, "y": 2}}],
            [],
        )
        second = StateGraph(
            [{"id": "a", "kind": "node", "attributes": {"y": 2, "x": 1}}],
            [],
        )
        self.assertEqual(first.digest, second.digest)

    def test_attribute_value_change_changes_digest(self):
        first = StateGraph([{"id": "a", "kind": "node", "attributes": {"x": 1}}], [])
        second = StateGraph([{"id": "a", "kind": "node", "attributes": {"x": 2}}], [])
        self.assertNotEqual(first.digest, second.digest)

    def test_rejects_duplicate_element_ids(self):
        with self.assertRaisesRegex(StateModelError, "element IDs must be unique"):
            StateGraph(
                [{"id": "a", "kind": "node"}, {"id": "a", "kind": "node"}],
                [],
            )

    def test_rejects_duplicate_relation_ids(self):
        relation = {
            "id": "r",
            "kind": "links",
            "source": "a",
            "target": "b",
        }
        with self.assertRaisesRegex(StateModelError, "Relation IDs must be unique"):
            StateGraph(
                [{"id": "a", "kind": "node"}, {"id": "b", "kind": "node"}],
                [relation, relation],
            )

    def test_rejects_unknown_relation_source(self):
        with self.assertRaisesRegex(StateModelError, "unknown source element"):
            StateGraph(
                [{"id": "a", "kind": "node"}],
                [{"id": "r", "kind": "links", "source": "missing", "target": "a"}],
            )

    def test_rejects_unknown_relation_target(self):
        with self.assertRaisesRegex(StateModelError, "unknown target element"):
            StateGraph(
                [{"id": "a", "kind": "node"}],
                [{"id": "r", "kind": "links", "source": "a", "target": "missing"}],
            )

    def test_rejects_missing_required_graph_sections(self):
        with self.assertRaisesRegex(StateModelError, "requires elements and relations"):
            StateGraph.from_dict({"elements": []})

    def test_rejects_unknown_graph_fields(self):
        with self.assertRaisesRegex(StateModelError, "Unknown state graph fields"):
            StateGraph.from_dict({"elements": [], "relations": [], "permissions": []})

    def test_rejects_unknown_element_fields(self):
        with self.assertRaisesRegex(StateModelError, "Unknown state element fields"):
            StateGraph([{"id": "a", "kind": "node", "owner": "agent"}], [])

    def test_rejects_non_object_attributes(self):
        with self.assertRaisesRegex(StateModelError, "attributes must be a JSON object"):
            StateGraph([{"id": "a", "kind": "node", "attributes": ["bad"]}], [])

    def test_rejects_non_string_attribute_keys(self):
        with self.assertRaisesRegex(StateModelError, "keys must be strings"):
            StateGraph([{"id": "a", "kind": "node", "attributes": {1: "bad"}}], [])

    def test_rejects_non_string_nested_attribute_keys(self):
        with self.assertRaisesRegex(StateModelError, "keys must be strings"):
            StateGraph(
                [{"id": "a", "kind": "node", "attributes": {"nested": {1: "bad"}}}],
                [],
            )

    def test_snapshot_cannot_be_reassigned(self):
        graph = StateGraph(self.elements, self.relations)
        with self.assertRaisesRegex(AttributeError, "immutable"):
            graph._canonical = "{}"

    def test_rejects_non_finite_numbers(self):
        with self.assertRaisesRegex(StateModelError, "finite JSON-compatible"):
            StateGraph(
                [{"id": "a", "kind": "node", "attributes": {"score": float("nan")}}],
                [],
            )

    def test_rejects_null_attributes(self):
        with self.assertRaisesRegex(StateModelError, "attributes must be a JSON object"):
            StateGraph([{"id": "a", "kind": "node", "attributes": None}], [])

    def test_rejects_circular_attributes(self):
        attributes = {}
        attributes["self"] = attributes
        with self.assertRaisesRegex(StateModelError, "circular references"):
            StateGraph([{"id": "a", "kind": "node", "attributes": attributes}], [])

    def test_rejects_blank_identifiers_and_kinds(self):
        with self.assertRaisesRegex(StateModelError, "element.id"):
            StateGraph([{"id": " ", "kind": "node"}], [])
        with self.assertRaisesRegex(StateModelError, "relation.kind"):
            StateGraph(
                [{"id": "a", "kind": "node"}, {"id": "b", "kind": "node"}],
                [{"id": "r", "kind": "", "source": "a", "target": "b"}],
            )

    def test_accessors_return_detached_data(self):
        graph = StateGraph(self.elements, self.relations)
        exposed = graph.to_dict()
        exposed["elements"][0]["attributes"]["balance"] = 999
        exposed["relations"].clear()
        self.assertEqual(graph.elements[0]["attributes"]["balance"], 12)
        self.assertEqual(len(graph.relations), 1)

    def test_from_dict_round_trip(self):
        graph = StateGraph(self.elements, self.relations)
        restored = StateGraph.from_dict(graph.to_dict())
        self.assertEqual(graph, restored)
        self.assertEqual(graph.digest, restored.digest)

    def test_empty_graph_is_valid(self):
        graph = StateGraph([], [])
        self.assertEqual(graph.to_dict(), {"elements": [], "relations": []})
        self.assertEqual(len(graph.digest), 64)


if __name__ == "__main__":
    unittest.main()
