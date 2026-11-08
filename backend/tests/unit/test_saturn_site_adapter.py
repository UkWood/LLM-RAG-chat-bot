import json
import unittest
from pathlib import Path

from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot,
    SnapshotFile,
    SnapshotValidationError,
    adapt_snapshot,
    git_blob_sha1,
)


COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
TREE_A = "c" * 40
TREE_B = "d" * 40


def fixture_file_map():
    root = Path(__file__).resolve().parents[1] / "fixtures" / "saturn_site"
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            content = path.read_bytes()
            result[relative] = (git_blob_sha1(content), content)
    return result


def make_snapshot(files=None, commit=COMMIT_A, tree=TREE_A):
    return PinnedSiteSnapshot.from_mapping(
        commit_sha=commit,
        tree_sha=tree,
        files=fixture_file_map() if files is None else files,
    )


def replace_file(files, path, content):
    files[path] = (git_blob_sha1(content), content)


class SaturnSiteContentAdapterTests(unittest.TestCase):
    def test_discovers_all_current_collections_and_maps_entity_subtypes(self):
        package = adapt_snapshot(make_snapshot())
        entities = {(item.collection, item.slug): item for item in package.entities}
        expected_collections = {"products", "systems", "groups", "articles", "news", "pages", "labs"}
        self.assertTrue(expected_collections.issubset(set(package.manifest.schema_inventory.collections)))
        self.assertEqual(entities[("products", "device-x")].entity_type, "Device")
        self.assertEqual(entities[("products", "software-x")].entity_type, "Software")
        self.assertEqual(entities[("systems", "heating-system")].entity_type, "System")
        self.assertEqual(entities[("systems", "controllers")].entity_type, "Category")
        self.assertEqual(entities[("systems", "implicit-system")].entity_type, "System")
        self.assertEqual(entities[("systems", "unknown-kind")].entity_type, "SiteContent")
        self.assertTrue(any(item.code == "unknown_entity_discriminator"
                            and item.path.endswith("/unknown-kind.md") for item in package.issues))
        self.assertEqual(entities[("groups", "controllers")].entity_type, "Group")
        self.assertEqual(entities[("articles", "article-x")].entity_type, "Article")
        self.assertEqual(entities[("news", "news-x")].entity_type, "News")
        self.assertEqual(entities[("pages", "solution-x")].entity_type, "Solution")
        self.assertEqual(entities[("pages", "section-x")].entity_type, "SectionPage")
        self.assertEqual(entities[("labs", "unknown-x")].entity_type, "SiteContent")
        self.assertNotIn(("products", "draft-x"), entities)
        self.assertIn(("products", "draft-string"), entities)
        self.assertTrue(package.ready_for_promotion)

    def test_preserves_exact_frontmatter_body_unknown_fields_arrays_units_and_qualifiers(self):
        package = adapt_snapshot(make_snapshot())
        device = next(item for item in package.entities
                      if item.collection == "products" and item.slug == "device-x")
        raw = json.loads(device.raw_frontmatter_json)
        self.assertEqual(raw["new_filter_parameter"]["unit"], "kPa")
        self.assertEqual(raw["new_filter_parameter"]["values"], [1, 2, 3])
        self.assertEqual(raw["features"], ["first", "second"])
        self.assertEqual(device.body, "# Device X\n\nBody text.\n")
        raw_record = next(item for item in package.raw_records if item.path.endswith("/device-x.md"))
        self.assertIn("# keep this source comment", raw_record.raw_frontmatter_text)
        self.assertEqual(raw_record.content, fixture_file_map()["src/content/products/device-x.md"][1])
        facts = {item.field_path: item for item in package.facts if item.entity_id == device.entity_id}
        self.assertEqual(json.loads(facts["features"].raw_value_json), ["first", "second"])
        self.assertEqual(facts["mass_kg"].unit, "kg")
        self.assertEqual(facts["temperature_c"].unit, "°C")
        self.assertEqual(json.loads(facts["specs[0].condition"].raw_value_json), "isolated")
        self.assertEqual(json.loads(facts["new_filter_parameter.qualifiers.condition"].raw_value_json), "nominal")
        self.assertIsNone(device.canonical_url)

    def test_relations_follow_only_explicit_source_fields(self):
        package = adapt_snapshot(make_snapshot())
        entities = {(item.collection, item.slug): item for item in package.entities}
        relations = package.relations

        def for_entity(collection, slug):
            entity = entities[(collection, slug)]
            return [item for item in relations if item.subject_entity_id == entity.entity_id]

        device_relations = for_entity("products", "device-x")
        by_predicate = {item.predicate: item for item in device_relations}
        self.assertEqual(set(by_predicate), {
            "group", "systems", "related", "variant_of", "software", "articles", "solutions"
        })
        self.assertEqual(by_predicate["software"].predicate, "software")
        self.assertEqual(by_predicate["software"].object_entity_id, entities[("products", "software-x")].entity_id)
        self.assertEqual(by_predicate["group"].object_entity_id, entities[("groups", "controllers")].entity_id)
        self.assertEqual(by_predicate["systems"].source_field_path, "systems[0]")
        self.assertEqual({item.predicate for item in for_entity("systems", "heating-system")}, {"articles", "solutions"})
        self.assertEqual({item.predicate for item in for_entity("groups", "controllers")}, {"system"})
        self.assertEqual({item.predicate for item in for_entity("articles", "article-x")}, {"products", "systems"})
        self.assertEqual({item.predicate for item in for_entity("news", "news-x")}, {"products"})
        self.assertEqual({item.predicate for item in for_entity("pages", "solution-x")}, {"systems", "products"})
        self.assertNotIn("groups", {item.predicate for item in relations})
        self.assertTrue(any(item.field_path == "groups[0].items[0]" for item in package.facts))

    def test_only_boolean_true_marks_a_record_as_draft(self):
        package = adapt_snapshot(make_snapshot())
        entities = {(item.collection, item.slug): item for item in package.entities}
        self.assertNotIn(("products", "draft-x"), entities)
        self.assertIn(("products", "device-x"), entities)
        self.assertIn(("products", "software-x"), entities)
        self.assertIn(("products", "draft-string"), entities)
        draft_record = next(item for item in package.raw_records if item.path.endswith("/draft-x.md"))
        self.assertIs(draft_record.draft, True)
        self.assertIn("src/content/products/draft-x.md", {item.path for item in package.manifest.file_revisions})

    def test_yaml_dates_remain_strings_and_dictionaries_are_safely_parsed(self):
        package = adapt_snapshot(make_snapshot())
        news = next(item for item in package.entities if item.collection == "news")
        date_fact = next(item for item in package.facts
                         if item.entity_id == news.entity_id and item.field_path == "date")
        self.assertEqual(json.loads(date_fact.raw_value_json), "2026-11-09")
        dictionary = next(item for item in package.dictionaries if item.path.endswith("interfaces.yaml"))
        self.assertIn("RS-485", dictionary.raw_yaml_text)
        self.assertIsInstance(json.loads(dictionary.raw_value_json), list)
        self.assertTrue(any(item.path == "src/data/interfaces.yaml" for item in package.manifest.file_revisions))

    def test_same_pinned_snapshot_is_deterministic(self):
        snapshot = make_snapshot()
        first = adapt_snapshot(snapshot)
        second = adapt_snapshot(snapshot)
        self.assertEqual(first, second)
        self.assertEqual(first.manifest.snapshot_id, second.manifest.snapshot_id)
        self.assertEqual(first.entities, second.entities)
        self.assertEqual(first.facts, second.facts)
        self.assertEqual(first.relations, second.relations)

    def test_add_update_delete_and_schema_drift_are_reported(self):
        previous = adapt_snapshot(make_snapshot())
        files = fixture_file_map()
        old_device = files["src/content/products/device-x.md"][1]
        changed_device = old_device.replace(b"mass_kg: 1.25", b'mass_kg: "1.25 kg"')
        changed_device = changed_device.replace(
            b"new_filter_parameter:",
            b"new_filter_parameter:\n  extra_filter: true\n  ",
        )
        replace_file(files, "src/content/products/device-x.md", changed_device)
        del files["src/content/news/news-x.md"]
        replace_file(files, "src/content/experiments/experiment-x.md",
                     b"---\ntitle: Experiment X\nnew_parameter: [one, two]\n---\nExperiment body.\n")
        replace_file(files, "src/data/interfaces.yaml",
                     b"- code: RS-485\n  label: RS-485\n- code: Ethernet\n  label: Ethernet\n- code: CAN\n  label: CAN\n")
        current = adapt_snapshot(make_snapshot(files, commit=COMMIT_B, tree=TREE_B),
                                 previous_manifest=previous.manifest)
        changes = current.sync_plan.file_changes
        self.assertEqual(changes.added, ("src/content/experiments/experiment-x.md",))
        self.assertEqual(changes.changed, ("src/content/products/device-x.md", "src/data/interfaces.yaml"))
        self.assertEqual(changes.deleted, ("src/content/news/news-x.md",))
        drift = current.sync_plan.schema_drift
        pairs = {(item.kind, item.subject) for item in drift}
        self.assertIn(("collection_added", "experiments"), pairs)
        self.assertIn(("field_added", "experiments.new_parameter"), pairs)
        self.assertIn(("field_type_changed", "products.mass_kg"), pairs)
        self.assertIn(("dictionary_changed", "src/data/interfaces.yaml"), pairs)
        self.assertTrue(current.ready_for_promotion)

    def test_invalid_record_is_diagnosed_without_losing_its_raw_bytes(self):
        files = fixture_file_map()
        bad = b"---\ntitle: Broken\nvalue: [unterminated\n---\nOriginal body.\n"
        replace_file(files, "src/content/products/broken.md", bad)
        package = adapt_snapshot(make_snapshot(files))
        self.assertFalse(package.ready_for_promotion)
        self.assertGreater(package.error_count, 0)
        issue = next(item for item in package.issues if item.path == "src/content/products/broken.md")
        self.assertEqual(issue.code, "content_parse_error")
        raw = next(item for item in package.raw_records if item.path.endswith("/broken.md"))
        self.assertEqual(raw.content, bad)
        self.assertIn("src/content/products/broken.md", {item.path for item in package.manifest.file_revisions})
        self.assertTrue(any(item.slug == "device-x" for item in package.entities))

    def test_aliases_anchors_tags_duplicate_and_non_string_keys_are_rejected(self):
        bad_payloads = {
            "alias": b"---\ntitle: Bad\nvalue: &v [one]\ncopy: *v\n---\nBody\n",
            "tag": b"---\ntitle: Bad\nvalue: !!python/object/apply:os.system ['echo unsafe']\n---\nBody\n",
            "duplicate": b"---\ntitle: Bad\ntitle: Duplicate\n---\nBody\n",
            "non-string": b"---\ntitle: Bad\n1: value\n---\nBody\n",
        }
        for name, payload in bad_payloads.items():
            with self.subTest(name=name):
                files = fixture_file_map()
                path = f"src/content/labs/bad-{name}.md"
                replace_file(files, path, payload)
                package = adapt_snapshot(make_snapshot(files))
                self.assertFalse(package.ready_for_promotion)
                self.assertTrue(any(item.path == path and item.code == "content_parse_error"
                                    for item in package.issues))
                raw = next(item for item in package.raw_records if item.path == path)
                self.assertEqual(raw.content, payload)

    def test_crlf_body_is_preserved_exactly(self):
        files = fixture_file_map()
        payload = b"---\r\ntitle: CRLF\r\n---\r\n# Heading\r\n\r\nBody\r\n"
        replace_file(files, "src/content/labs/crlf.md", payload)
        package = adapt_snapshot(make_snapshot(files))
        entity = next(item for item in package.entities if item.collection == "labs" and item.slug == "crlf")
        self.assertEqual(entity.body, "# Heading\r\n\r\nBody\r\n")
        raw = next(item for item in package.raw_records if item.path.endswith("/crlf.md"))
        self.assertEqual(raw.content, payload)

    def test_snapshot_rejects_unpinned_or_mutated_inputs(self):
        content = b"---\ntitle: x\n---\n"
        with self.assertRaises(SnapshotValidationError):
            SnapshotFile("src/content/products/x.md", "0" * 40, content)
        with self.assertRaises(SnapshotValidationError):
            PinnedSiteSnapshot("someone/else", "main", COMMIT_A, TREE_A, ())
        files = fixture_file_map()
        del files["src/content.config.ts"]
        with self.assertRaises(SnapshotValidationError):
            adapt_snapshot(make_snapshot(files))


    def test_dictionary_size_limit_is_independent_from_frontmatter_limit(self):
        files = fixture_file_map()
        large_dictionary = b"payload: " + (b"x" * 300_000) + b"\n"
        replace_file(files, "src/data/large.yaml", large_dictionary)
        package = adapt_snapshot(make_snapshot(files))
        dictionary = next(item for item in package.dictionaries if item.path == "src/data/large.yaml")
        self.assertIsNotNone(dictionary.raw_value_json)
        self.assertEqual(len(json.loads(dictionary.raw_value_json)["payload"]), 300_000)
        self.assertTrue(package.ready_for_promotion)


if __name__ == "__main__":
    unittest.main()
