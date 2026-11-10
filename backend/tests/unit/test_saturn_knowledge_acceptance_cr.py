"""PR #25 consolidated CR-01..CR-04 offline negative regression tests."""
from dataclasses import asdict, replace
import json
import unittest

from saturn_ai.ingestion.saturn_contracts import canonical_json, stable_id
from saturn_ai.ingestion.saturn_site_adapter import _facts_for_entity
from saturn_ai.saturn_knowledge_contracts import (
    SaturnSnapshotManager, SnapshotBuildError, snapshot_content,
    verify_snapshot_seal,
)
from saturn_ai.saturn_knowledge_snapshot import (
    stage_saturn_knowledge_snapshot, build_saturn_knowledge_snapshot,
)
from unit.test_saturn_knowledge_snapshot import (
    PRODUCT, SECOND, doc, make_inputs, source,
)


def entity_for(site):
    return next(x for x in site.entities if x.collection == "products"
                and x.slug == "catalog-a")


def replace_entity(site, new):
    return replace(site, entities=tuple(new if e.entity_id == new.entity_id
                                       else e for e in site.entities))


def check(*inputs):
    result = stage_saturn_knowledge_snapshot(*inputs)
    return {e.code for e in result.issues}, result


def reseal(snapshot):
    unsigned_manifest = replace(snapshot.manifest, corpus_hash=stable_id(
        "saturn-unified-corpus-v1", snapshot_content(snapshot)))
    unsigned = asdict(unsigned_manifest)
    unsigned.pop("snapshot_id")
    return replace(snapshot, manifest=replace(
        unsigned_manifest, snapshot_id=stable_id(
            "saturn-unified-snapshot-v1", unsigned)))


class CR01SourceProjection(unittest.TestCase):
    def test_title_type_url_and_changed_host(self):
        site, cat, pdf = make_inputs({PRODUCT: source(fields="temperature_c: -20\n")})
        entity = entity_for(site)
        changes = [
            ("entity_title_mismatch", replace(entity, title="Invented")),
            ("entity_type_mismatch", replace(entity, entity_type="Software")),
            ("entity_canonical_url_mismatch", replace(
                entity, canonical_url=entity.canonical_url.replace(
                    "/catalog-a/", "/not-original/"))),
            ("canonical_origin_mismatch", replace(
                entity, canonical_url=entity.canonical_url.replace(
                    "https://www.mnppsaturn.ru", "https://forged.example.org"))),
        ]
        for code, forged in changes:
            with self.subTest(code=code):
                errors, result = check(replace_entity(site, forged), cat, pdf)
                self.assertIn(code, errors)
                self.assertIsNone(result.candidate)

    def test_forged_frontmatter_with_consistent_facts(self):
        site, cat, pdf = make_inputs({PRODUCT: source(fields="temperature_c: -20\n")})
        e = entity_for(site)
        metadata = json.loads(e.raw_frontmatter_json)
        metadata["temperature_c"] = 9000
        forged = replace_entity(site, replace(
            e, raw_frontmatter_json=canonical_json(metadata)))
        facts = tuple(f for f in site.facts if f.entity_id != e.entity_id)
        facts += tuple(_facts_for_entity(
            e.entity_id, metadata, e.source_revision_id))
        errors, result = check(replace(forged, facts=facts), cat, pdf)
        self.assertIn("entity_frontmatter_mismatch", errors)
        self.assertIsNone(result.candidate)

    def test_unit_normalization_and_qualifiers_cannot_be_invented(self):
        site, cat, pdf = make_inputs({PRODUCT: source(fields="temperature_c: -20\n")})
        fact = next(f for f in site.facts if f.field_path == "temperature_c"
                    and f.entity_id == entity_for(site).entity_id)
        bad = [replace(fact, unit="K"),
               replace(fact, normalized_value_json="253.15"),
               replace(fact, qualifiers_json=canonical_json({"verified": True}))]
        for altered in bad:
            with self.subTest(altered=altered):
                source_facts = tuple(altered if f.fact_id == fact.fact_id
                                     else f for f in site.facts)
                errors, result = check(replace(site, facts=source_facts), cat, pdf)
                self.assertIn("fact_projection_mismatch", errors)
                self.assertIsNone(result.candidate)

    def test_dictionary_is_reparsed_from_original_yaml_bytes(self):
        site, cat, pdf = make_inputs()
        dictionary = site.dictionaries[0]
        fake = replace(dictionary, raw_value_json=canonical_json(
            {"plausible": ["but", "forged"]}))
        errors, result = check(replace(
            site, dictionaries=(fake,) + site.dictionaries[1:]), cat, pdf)
        self.assertIn("dictionary_projection_mismatch", errors)
        self.assertIsNone(result.candidate)

    def test_source_raw_frontmatter_body_and_draft_are_exact(self):
        site, cat, pdf = make_inputs({PRODUCT: source()})
        record = next(r for r in site.raw_records if r.path == PRODUCT)
        for forged in (replace(record, body="forged"),
                       replace(record, raw_frontmatter_text="title: Forged\n"),
                       replace(record, draft=True)):
            with self.subTest(forged=forged):
                records = tuple(forged if r.path == record.path else r
                                for r in site.raw_records)
                errors, result = check(replace(site, raw_records=records), cat, pdf)
                self.assertIn("source_record_projection_mismatch", errors)
                self.assertIsNone(result.candidate)

    def test_rejection_keeps_previous_active(self):
        inputs = make_inputs({PRODUCT: source()})
        previous = build_saturn_knowledge_snapshot(*inputs)
        manager = SaturnSnapshotManager()
        manager.activate(previous)
        forged = replace_entity(inputs[0], replace(
            entity_for(inputs[0]), title="Fake"))
        result = stage_saturn_knowledge_snapshot(
            forged, inputs[1], inputs[2])
        with self.assertRaises(SnapshotBuildError):
            manager.activate(result.candidate)
        self.assertIs(manager.capture(), previous)


class CR02RelationCoverage(unittest.TestCase):
    def inputs(self):
        return make_inputs({
            PRODUCT: source(fields="related:\n - catalog-b\n - absent\n"),
            SECOND: source("Second"),
        })

    def test_missing_single_and_all(self):
        site, cat, pdf = self.inputs()
        source_relations = tuple(
            r for r in site.relations if r.predicate == "related"
            and r.subject_entity_id == entity_for(site).entity_id)
        self.assertEqual(len(source_relations), 2)
        for sub in (tuple(r for r in site.relations
                          if r != source_relations[0]), ()):
            with self.subTest(length=len(sub)):
                errors, result = check(replace(site, relations=sub), cat, pdf)
                self.assertIn("relation_projection_coverage_mismatch", errors)
                self.assertIsNone(result.candidate)

    def test_extra_changed_predicate_object_and_field_path(self):
        site, cat, pdf = self.inputs()
        rel = next(r for r in site.relations if r.predicate == "related")
        for forged in (replace(rel, predicate="compatible_with"),
                       replace(rel, object_entity_id="saturn:invented"),
                       replace(rel, source_field_path="related[99]")):
            with self.subTest(forged=forged):
                changed = tuple(forged if r.relation_id == rel.relation_id else r
                                for r in site.relations)
                errors, result = check(replace(site, relations=changed), cat, pdf)
                self.assertIn("relation_projection_mismatch", errors)
                self.assertIsNone(result.candidate)
        fabricated = replace(rel, relation_id=stable_id("extra", rel.relation_id))
        errors, result = check(
            replace(site, relations=site.relations + (fabricated,)), cat, pdf)
        self.assertIn("relation_projection_coverage_mismatch", errors)
        self.assertIsNone(result.candidate)

    def test_array_cardinality_draft_and_missing_target(self):
        site, cat, pdf = self.inputs()
        snap = build_saturn_knowledge_snapshot(site, cat, pdf)
        related = [r for r in snap.relations + snap.unresolved_relations
                   if r.predicate == "related"]
        self.assertEqual({r.source_field_path for r in related},
                         {"related[0]", "related[1]"})
        self.assertTrue(any(x.code == "unresolved_relation"
                            for x in snap.diagnostics))
        draft = make_inputs({
            PRODUCT: source(fields="related:\n - catalog-b\n"),
            SECOND: source("Second", draft=True),
        })
        self.assertFalse(any(
            r.predicate == "related" and
            r.subject_entity_id == entity_for(draft[0]).entity_id
            for r in draft[0].relations))
        self.assertTrue(build_saturn_knowledge_snapshot(*draft).ready_for_promotion)
        wrong_site = replace(draft[0], relations=(site.relations[0],))
        self.assertIn("relation_projection_coverage_mismatch",
                      check(wrong_site, draft[1], draft[2])[0])


class CR03SourceLinkProvenance(unittest.TestCase):
    def inputs(self, body):
        data = make_inputs({PRODUCT: source(body=body)})
        self.assertTrue(data[1].ready_for_promotion)
        return data

    def test_rewritten_raw_url_with_rewritten_pdf_candidate(self):
        site, cat, pdf = self.inputs("[guide](/ftp/guide.pdf)")
        changed = replace(
            cat, occurrences=(replace(cat.occurrences[0],
                                      raw_url="/ftp/invented.pdf"),),
            pdf_candidates=(replace(cat.pdf_candidates[0],
                                    raw_urls=("/ftp/invented.pdf",)),))
        errors, result = check(site, changed, pdf)
        self.assertIn("source_occurrence_mismatch", errors)
        self.assertIsNone(result.candidate)

    def test_same_line_other_link_and_invalid_ordinal(self):
        site, cat, pdf = self.inputs(
            "[first](/ftp/a.pdf) [second](/ftp/b.pdf)")
        first, second = sorted(cat.occurrences, key=lambda o: o.field_path)
        wrong = replace(first, field_path=second.field_path,
                        source_locator=first.source_revision_id + "#" + second.field_path)
        changed = replace(cat, occurrences=tuple(
            wrong if o.document_id == first.document_id else o
            for o in cat.occurrences))
        self.assertIn("source_occurrence_mismatch", check(site, changed, pdf)[0])
        invalid_path = first.field_path.replace("occurrence=1", "occurrence=99")
        self.assertNotEqual(first.field_path, invalid_path)
        wrong = replace(first, field_path=invalid_path,
                        source_locator=first.source_revision_id + "#" + invalid_path)
        changed = replace(cat, occurrences=tuple(
            wrong if o.document_id == first.document_id else o
            for o in cat.occurrences))
        self.assertIn("source_occurrence_mismatch", check(site, changed, pdf)[0])

    def test_resolved_url_document_id_and_candidate_coforged(self):
        site, cat, pdf = self.inputs("[guide](/ftp/guide.pdf)")
        url = "https://www.mnppsaturn.ru/ftp/other.pdf"
        identity = "saturn-doc:" + stable_id("saturn-support-document-url-v1", url)
        changed = replace(cat,
            documents=(replace(cat.documents[0], document_id=identity, url=url),),
            occurrences=(replace(cat.occurrences[0],
                                 document_id=identity, resolved_url=url),),
            pdf_candidates=(replace(cat.pdf_candidates[0],
                                    document_id=identity, resolved_url=url),))
        errors, result = check(site, changed, pdf)
        self.assertIn("source_occurrence_mismatch", errors)
        self.assertIn("source_document_mismatch", errors)
        self.assertIsNone(result.candidate)

    def test_supported_inline_reference_autolink_html_multiple_owner(self):
        text = (
            "[inline](/ftp/inline.pdf)\n"
            "[ref][manual]\n"
            "[manual]: /ftp/ref.pdf\n"
            "<https://www.mnppsaturn.ru/ftp/absolute.pdf>\n"
            '<a href="/ftp/html%20file.pdf?x=1&amp;y=2">HTML</a>\n'
            "[last](/ftp/last.pdf)\n"
        )
        args = self.inputs(text)
        self.assertEqual(len(args[1].occurrences), 5)
        snap = build_saturn_knowledge_snapshot(*args)
        self.assertEqual(len(snap.document_matches), 5)
        self.assertEqual(len(snap.document_occurrences), 5)

    def test_code_fences_comments_inline_code_are_not_links(self):
        text = (
            "[valid](/ftp/valid.pdf)\n"
            "~~~\n"
            "[hidden](/ftp/hidden.pdf)\n"
            "~~~\n"
            "<!-- [comment](/ftp/comment.pdf) -->\n"
            "Inline " + chr(96) + "[code](/ftp/code.pdf)" + chr(96) + "\n"
        )
        site, cat, pdf = self.inputs(text)
        self.assertEqual(len(cat.occurrences), 1)
        occurrence = cat.occurrences[0]
        field = "body:line=5:column=6:heading=null:occurrence=2"
        fake = replace(occurrence, field_path=field, raw_url="/ftp/comment.pdf",
                       source_locator=occurrence.source_revision_id + "#" + field)
        changed = replace(cat, occurrences=(occurrence, fake))
        self.assertIn("source_occurrence_mismatch", check(site, changed, pdf)[0])


class CR04StructuralActivation(unittest.TestCase):
    def setUp(self):
        self.args = make_inputs({
            PRODUCT: source(fields="documents:\n - " + doc() + "\n")})
        self.snapshot = build_saturn_knowledge_snapshot(*self.args)
        self.manager = SaturnSnapshotManager()
        self.manager.activate(self.snapshot)

    def assert_invalid_reseal(self, changed):
        forged = reseal(changed)
        self.assertTrue(verify_snapshot_seal(forged))
        with self.assertRaises(SnapshotBuildError):
            self.manager.activate(forged)
        self.assertIs(self.manager.capture(), self.snapshot)

    def test_counts_and_dangling_pointer_after_reseal(self):
        changed_counts = replace(self.snapshot.manifest, counts=tuple(
            (key, value + 1 if key == "answer_evidence" else value)
            for key, value in self.snapshot.manifest.counts))
        self.assert_invalid_reseal(replace(self.snapshot, manifest=changed_counts))
        self.assert_invalid_reseal(replace(
            self.snapshot, answer_evidence=self.snapshot.answer_evidence[:-1]))

    def test_nonexistent_pointer_and_pdf_page_revision_after_reseal(self):
        pointer = self.snapshot.evidence_pointers[0]
        self.assert_invalid_reseal(replace(
            self.snapshot, evidence_pointers=(replace(
                pointer, canonical_id="saturn:not-present"),) +
                self.snapshot.evidence_pointers[1:]))
        passage = next(x for x in self.snapshot.answer_evidence
                       if x.evidence_type == "pdf_passage")
        self.assert_invalid_reseal(replace(
            self.snapshot, answer_evidence=tuple(
                replace(e, source_revision_id="f" * 64)
                if e.evidence_id == passage.evidence_id else e
                for e in self.snapshot.answer_evidence)))
        rev = self.snapshot.pdf_revisions[0]
        self.assert_invalid_reseal(replace(
            self.snapshot, pdf_revisions=(replace(rev, bytes_sha256="f"*64),)))

    def test_ready_gate_forgery_cannot_promote_failed_pdf(self):
        broken = stage_saturn_knowledge_snapshot(
            *make_inputs({PRODUCT: source(fields="documents:\n - " + doc() + "\n")},
                         failure="network_error")).candidate
        self.assertIsNotNone(broken)
        self.assert_invalid_reseal(replace(
            broken, readiness_gates=(True, True, True), diagnostics=()))

    def test_repeat_good_activation_and_edited_source_receipt(self):
        self.assertEqual(self.manager.activate(self.snapshot),
                         self.snapshot.snapshot_id)
        inputs = self.snapshot.validation_sources
        other = make_inputs({
            PRODUCT: source(fields="documents:\n - " + doc() + "\n",
                            body="different source evidence")})
        self.assert_invalid_reseal(replace(
            self.snapshot, validation_sources=replace(
                inputs, site=other[0], catalog=other[1], external=other[2])))


if __name__ == "__main__":
    unittest.main()
