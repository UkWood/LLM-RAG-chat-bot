import unittest
from dataclasses import replace

from saturn_ai.ingestion.saturn_contracts import SiteFileRevision
from saturn_ai.ingestion.schema_evolution import (
    build_schema_inventory,
    build_sync_manifest,
    compare_file_revisions,
    compare_schema,
    plan_sync,
)


COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
TREE_A = "c" * 40
TREE_B = "d" * 40
BLOB_A = "e" * 40
BLOB_B = "f" * 40
HASH_A = "1" * 64
HASH_B = "2" * 64


def inventory(records=None, schema=b"schema-v1", dictionaries=None):
    return build_schema_inventory(
        records or {"products": [{"title": "DEMO-300", "mass_kg": 1,
                                  "temperature_c": {"min": -20, "max": 60},
                                  "specs": [{"name": "Protocol", "value": "BACnet"}]}]},
        schema,
        dictionaries or {"src/data/industries.yaml": b"- heating\n- water\n"},
    )


def file(path, blob=BLOB_A, content=HASH_A, collection="products", slug="demo"):
    return SiteFileRevision(path, blob, content, collection, slug)


class SaturnSchemaEvolutionTests(unittest.TestCase):
    def test_inventory_discovers_collections_and_nested_fields(self):
        current = inventory()
        self.assertEqual(current.collections, ("products",))
        fields = {(item.collection, item.field_path): item.value_type for item in current.fields}
        self.assertEqual(fields[("products", "temperature_c")], "object")
        self.assertEqual(fields[("products", "temperature_c.min")], "integer")
        self.assertEqual(fields[("products", "specs[].name")], "string")
        self.assertEqual(fields[("products", "specs[].value")], "string")
        self.assertEqual(fields[("products", "mass_kg")], "integer")

    def test_inventory_recurses_through_nested_objects(self):
        current = inventory({"products": [{"outer": {"inner": {"leaf": "value"}}}]})
        paths = {item.field_path for item in current.fields}
        self.assertIn("outer.inner.leaf", paths)

    def test_inventory_type_inference_does_not_confuse_boolean_and_integer(self):
        current = inventory({"products": [{"enabled": True, "count": 1},
                                           {"enabled": False, "count": 2.5}]})
        fields = {(item.collection, item.field_path): item.value_type for item in current.fields}
        self.assertEqual(fields[("products", "enabled")], "boolean")
        self.assertEqual(fields[("products", "count")], "number")

    def test_nullable_and_mixed_fields_are_recorded(self):
        current = inventory({"products": [{"value": None}, {"value": "x"}]})
        field, = [item for item in current.fields if item.field_path == "value"]
        self.assertEqual(field.value_type, "string")
        self.assertTrue(field.nullable)

    def test_additive_fields_collections_and_dictionary_changes_are_reported(self):
        previous = inventory()
        current = inventory({
            "products": [{"title": "DEMO-300", "mass_kg": 1, "new_filter": ["A", "B"]}],
            "software": [{"title": "Tool", "version": "3.0"}],
        }, schema=b"schema-v2",
           dictionaries={"src/data/industries.yaml": b"- heating\n- water\n- gas\n",
                         "src/data/interfaces.yaml": b"- RS-485\n"})
        events = compare_schema(previous, current)
        kinds = {event.kind for event in events}
        self.assertIn("collection_added", kinds)
        self.assertIn("field_added", kinds)
        self.assertIn("dictionary_changed", kinds)
        self.assertIn("dictionary_added", kinds)
        self.assertIn("schema_definition_changed", kinds)

    def test_removed_fields_and_collections_are_reported(self):
        previous = inventory({"products": [{"title": "A", "obsolete_field": "x"}],
                              "systems": [{"title": "S"}]})
        current = inventory({"products": [{"title": "A"}]})
        events = compare_schema(previous, current)
        self.assertIn("field_removed", {event.kind for event in events})
        self.assertIn("collection_removed", {event.kind for event in events})

    def test_changed_field_type_is_breaking(self):
        previous = inventory({"products": [{"rating": "IP54"}]})
        current = inventory({"products": [{"rating": {"code": "IP54"}}]})
        event, = [item for item in compare_schema(previous, current)
                  if item.kind == "field_type_changed"]
        self.assertEqual(event.severity, "breaking")
        self.assertEqual(event.before, "string")
        self.assertEqual(event.after, "object")

    def test_unchanged_inventory_has_no_drift(self):
        current = inventory()
        self.assertEqual(compare_schema(current, current), ())

    def test_file_diff_reports_add_change_and_delete(self):
        previous = (file("src/content/products/a.md"),
                    file("src/content/products/b.md", BLOB_B, HASH_B))
        current = (file("src/content/products/a.md", BLOB_B, HASH_B),
                   file("src/content/products/c.md"))
        changes = compare_file_revisions(previous, current)
        self.assertEqual(changes.added, ("src/content/products/c.md",))
        self.assertEqual(changes.changed, ("src/content/products/a.md",))
        self.assertEqual(changes.deleted, ("src/content/products/b.md",))

    def test_manifest_and_snapshot_identity_are_deterministic(self):
        schema = inventory()
        files = (file("src/content/products/demo.md"),)
        first = build_sync_manifest(commit_sha=COMMIT_A, tree_sha=TREE_A,
                                    schema_inventory=schema, file_revisions=files,
                                    adapter_version="adapter/0.1", mapping_version="mapping/0.1")
        second = build_sync_manifest(commit_sha=COMMIT_A, tree_sha=TREE_A,
                                     schema_inventory=schema, file_revisions=files,
                                     adapter_version="adapter/0.1", mapping_version="mapping/0.1")
        changed = build_sync_manifest(commit_sha=COMMIT_B, tree_sha=TREE_B,
                                      schema_inventory=schema, file_revisions=files,
                                      adapter_version="adapter/0.1", mapping_version="mapping/0.1")
        self.assertEqual(first, second)
        self.assertNotEqual(first.snapshot_id, changed.snapshot_id)

    def test_manifest_rejects_snapshot_id_mismatch(self):
        manifest = build_sync_manifest(
            commit_sha=COMMIT_A, tree_sha=TREE_A, schema_inventory=inventory(),
            file_revisions=(file("src/content/products/a.md"),),
            adapter_version="adapter/0.1", mapping_version="mapping/0.1")
        forged = replace(manifest, tree_sha=TREE_B)
        with self.assertRaises(ValueError):
            forged.__post_init__()

    def test_sync_plan_initial_and_incremental(self):
        schema = inventory()
        first = build_sync_manifest(commit_sha=COMMIT_A, tree_sha=TREE_A,
                                    schema_inventory=schema,
                                    file_revisions=(file("src/content/products/a.md"),),
                                    adapter_version="adapter/0.1", mapping_version="mapping/0.1")
        second = build_sync_manifest(commit_sha=COMMIT_B, tree_sha=TREE_B,
                                     schema_inventory=schema,
                                     file_revisions=(file("src/content/products/b.md"),),
                                     adapter_version="adapter/0.1", mapping_version="mapping/0.1")
        initial = plan_sync(None, first)
        self.assertEqual(initial.file_changes.added, ("src/content/products/a.md",))
        delta = plan_sync(first, second)
        self.assertEqual(delta.file_changes.added, ("src/content/products/b.md",))
        self.assertEqual(delta.file_changes.deleted, ("src/content/products/a.md",))


if __name__ == "__main__":
    unittest.main()
