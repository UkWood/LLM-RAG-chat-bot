import json
import unittest

from saturn_ai.ingestion.saturn_contracts import (
    DictionaryFingerprint,
    EvidenceUnit,
    PdfRevision,
    SchemaDriftEvent,
    SchemaField,
    SchemaInventory,
    SiteEntity,
    SiteFact,
    SiteFileRevision,
    SiteRelation,
    SiteSourceRevision,
    SupportDocument,
    canonical_json,
    stable_id,
)


COMMIT = "a" * 40
TREE = "b" * 40
BLOB = "c" * 40
CONTENT = "d" * 64
TEXT_HASH = "e" * 64


def source_revision(path="src/content/products/demo-300.md"):
    return SiteSourceRevision("UkWood/Saturn-Main-Site", "main", COMMIT,
                              path, BLOB, CONTENT)


class SaturnCanonicalContractTests(unittest.TestCase):
    def test_source_revision_is_exact_and_deterministic(self):
        first = source_revision()
        self.assertEqual(first.revision_id, source_revision().revision_id)
        self.assertEqual(len(first.revision_id), 64)
        changed = SiteSourceRevision("UkWood/Saturn-Main-Site", "main", COMMIT,
                                     "src/content/products/other.md", BLOB, CONTENT)
        self.assertNotEqual(first.revision_id, changed.revision_id)

    def test_source_revision_rejects_wrong_trust_root_and_unsafe_path(self):
        with self.assertRaises(ValueError):
            SiteSourceRevision("someone/else", "main", COMMIT,
                               "src/content/products/demo.md", BLOB, CONTENT)
        with self.assertRaises(ValueError):
            SiteSourceRevision("UkWood/Saturn-Main-Site", "feature", COMMIT,
                               "src/content/products/demo.md", BLOB, CONTENT)
        with self.assertRaises(ValueError):
            SiteSourceRevision("UkWood/Saturn-Main-Site", "main", COMMIT,
                               "src/content/../secret.md", BLOB, CONTENT)

    def test_entity_preserves_unknown_frontmatter_fields(self):
        raw = {"title": "DEMO-300", "new_filter_parameter": {"min": 1, "max": 9},
               "custom_flag": True}
        entity = SiteEntity("saturn:products:demo-300", "products", "demo-300", "Device",
                            "DEMO-300", "/products/demo-300/", False,
                            source_revision().revision_id, canonical_json(raw),
                            "Описание изделия.")
        self.assertEqual(json.loads(entity.raw_frontmatter_json), raw)
        self.assertIn("new_filter_parameter", entity.raw_frontmatter_json)
        self.assertIn("custom_flag", entity.raw_frontmatter_json)

    def test_entity_requires_canonical_raw_json_and_boolean_draft(self):
        with self.assertRaises(ValueError):
            SiteEntity("e", "products", "demo", "Device", "Demo", None, False,
                       source_revision().revision_id, '{"title": "Demo"}', "")
        with self.assertRaises(ValueError):
            SiteEntity("e", "products", "demo", "Device", "Demo", None, 0,
                       source_revision().revision_id, canonical_json({"title": "Demo"}), "")

    def test_fact_preserves_raw_and_normalized_values_separately(self):
        fact = SiteFact("fact-1", "saturn:products:demo-300", "specs[0].value",
                        canonical_json("10...30 V"), source_revision().revision_id,
                        canonical_json({"min": 10, "max": 30}), "V",
                        canonical_json({"condition": "nominal"}))
        self.assertEqual(json.loads(fact.raw_value_json), "10...30 V")
        self.assertEqual(json.loads(fact.normalized_value_json), {"min": 10, "max": 30})
        self.assertEqual(json.loads(fact.qualifiers_json), {"condition": "nominal"})

    def test_relation_keeps_source_field_semantics(self):
        relation = SiteRelation("r1", "saturn:products:demo", "software",
                                "saturn:products:demo-tool",
                                source_revision().revision_id, "software[0]")
        self.assertEqual(relation.predicate, "software")
        self.assertEqual(relation.source_field_path, "software[0]")

    def test_support_document_retains_all_owners_and_locators(self):
        doc = SupportDocument("doc-1", "Manual", "manual",
                              "https://www.mnppsaturn.ru/files/manual.pdf",
                              ("saturn:products:a", "saturn:products:b"),
                              ("products/a.documents[0]", "products/b.documents[1]"),
                              "2.1", "2026-01-01")
        self.assertEqual(len(doc.owner_entity_ids), 2)
        self.assertEqual(len(doc.source_locators), 2)
        with self.assertRaises(ValueError):
            SupportDocument("doc-2", "Manual", "manual", "https://example.org/a.pdf",
                            ("saturn:products:a", "saturn:products:a"),
                            ("products/a.documents[0]",))

    def test_pdf_revision_has_no_approval_gate(self):
        revision = PdfRevision("doc-1", "https://www.mnppsaturn.ru/files/manual.pdf",
                               CONTENT, "pdf-parser/0.1", "extracted", 12, TEXT_HASH)
        self.assertEqual(revision.extraction_state, "extracted")
        self.assertFalse(hasattr(revision, "approval_state"))
        with self.assertRaises(ValueError):
            PdfRevision("doc-1", "https://www.mnppsaturn.ru/files/manual.pdf",
                        CONTENT, "pdf-parser/0.1", "extracted", None, TEXT_HASH)

    def test_pdf_evidence_requires_physical_page(self):
        evidence = EvidenceUnit("ev-1", "pdf_passage", "rev-1", "page:3",
                                "Technical passage", "saturn:products:a", 3)
        self.assertEqual(evidence.page_number, 3)
        with self.assertRaises(ValueError):
            EvidenceUnit("ev-2", "pdf_passage", "rev-1", "page:0",
                         "Passage", page_number=0)
        with self.assertRaises(ValueError):
            EvidenceUnit("ev-3", "site_passage", "rev-1", "heading:intro",
                         "Passage", page_number=2)

    def test_inventory_requires_sorted_unique_entries(self):
        inventory = SchemaInventory(CONTENT, ("products", "systems"),
                                    (SchemaField("products", "title", "string"),
                                     SchemaField("systems", "title", "string")),
                                    (DictionaryFingerprint("src/data/industries.yaml", CONTENT),))
        self.assertEqual(inventory.collections, ("products", "systems"))
        with self.assertRaises(ValueError):
            SchemaInventory(CONTENT, ("systems", "products"), (), ())

    def test_schema_drift_event_has_explicit_severity(self):
        event = SchemaDriftEvent("field_type_changed", "breaking",
                                 "products.temperature_c", "object", "string")
        self.assertEqual(event.severity, "breaking")
        with self.assertRaises(ValueError):
            SchemaDriftEvent("field_type_changed", "approved", "products.value")

    def test_file_revision_and_change_set_are_immutable_and_sorted(self):
        file = SiteFileRevision("src/content/products/demo.md", BLOB, CONTENT,
                                 "products", "demo")
        self.assertEqual(file.collection, "products")
        with self.assertRaises(ValueError):
            SiteFileRevision("src/content/../secret.md", BLOB, CONTENT)


if __name__ == '__main__':
    unittest.main()
