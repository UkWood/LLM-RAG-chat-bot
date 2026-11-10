"""Stage 4A: independent offline/contract/integration Saturn snapshot tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import unittest

from saturn_ai.ingestion.external_document_adapter import adapt_external_documents
from saturn_ai.ingestion.external_document_extractor import ExtractedPdf
from saturn_ai.ingestion.external_document_transport import (
    DocumentError, DocumentFetchPolicy,
)
from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot, adapt_snapshot, git_blob_sha1,
)
from saturn_ai.ingestion.support_catalog_adapter import adapt_support_catalog
from saturn_ai.saturn_knowledge_contracts import (
    SaturnSnapshotManager, SnapshotBuildError, verify_snapshot_seal,
)
from saturn_ai.saturn_knowledge_snapshot import (
    build_saturn_knowledge_snapshot, stage_saturn_knowledge_snapshot,
)
from unit.test_pdf import make_pdf
from unit.test_support_catalog_adapter import (
    PRODUCT, SECOND, doc, files, put, source,
)


PDF = make_pdf(("Page 1", "Page 2"))
ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "saturn_support_real"


class OfflineTransport:
    def __init__(self, data=PDF, failure=None):
        self.data = data
        self.failure = failure

    def fetch(self, url, policy):
        if self.failure:
            raise DocumentError(self.failure)
        return self.data


class OfflineExtractor:
    def __init__(self, pages=((1, "Alpha"), (2, "Beta")), failure=None):
        self.pages = pages
        self.failure = failure

    def extract(self, raw, policy):
        if self.failure:
            raise DocumentError(self.failure)
        return ExtractedPdf(len(self.pages), self.pages)


def make_inputs(additions=None, *, removed=(), commit="a"*40, pdf=PDF,
                failure=None, pages=((1, "Alpha"), (2, "Beta"))):
    paths = files()
    for path in removed:
        paths.pop(path, None)
    for path, text in (additions or {}).items():
        put(paths, path, text)
    pinned = PinnedSiteSnapshot.from_mapping(
        commit_sha=commit, tree_sha="c"*40, files=paths)
    site = adapt_snapshot(pinned)
    catalog = adapt_support_catalog(site)
    external = adapt_external_documents(
        catalog,
        DocumentFetchPolicy(
            allowed_hosts=("www.mnppsaturn.ru",),
            allowed_path_prefixes=("/ftp", "/public", "/photos"),
        ),
        transport=OfflineTransport(pdf, failure),
        extractor=OfflineExtractor(pages),
    )
    return site, catalog, external


class SaturnKnowledgeSnapshotTests(unittest.TestCase):
    def test_immutable_assembly_manifest_and_exact_provenance(self):
        site, catalog, external = make_inputs({
            PRODUCT: source(fields="documents:\n - " + doc() + "\n",
                            body="## Specification\nOne\nTwo\n\n## Notes\nThree\n"),
        })
        snapshot = build_saturn_knowledge_snapshot(site, catalog, external)
        self.assertTrue(snapshot.ready_for_promotion)
        self.assertTrue(verify_snapshot_seal(snapshot))
        self.assertEqual(snapshot.manifest.site_manifest, site.manifest)
        self.assertEqual(snapshot.manifest.pdf_parser_version, external.parser_version)
        self.assertEqual(len(snapshot.document_matches), len(catalog.documents))
        self.assertEqual(len(snapshot.document_occurrences), len(catalog.occurrences))
        self.assertEqual({x.evidence_type for x in snapshot.answer_evidence},
                         {"site_field", "site_passage", "pdf_passage"})
        self.assertEqual([e.page_number for e in snapshot.answer_evidence
                          if e.evidence_type == "pdf_passage"], [1, 2])
        for e in snapshot.answer_evidence:
            self.assertTrue(e.text)
            pointer = next(p for p in snapshot.evidence_pointers
                           if p.evidence_id == e.evidence_id)
            self.assertIn(pointer.canonical_kind,
                          ("SiteFact", "SiteEntity", "SiteRelation", "PdfRevision"))
        for match in snapshot.document_matches:
            self.assertIn(match.document.document_id,
                          {d.document_id for d in catalog.documents})
        with self.assertRaises(FrozenInstanceError):
            snapshot.entities = ()
        with self.assertRaises(FrozenInstanceError):
            snapshot.manifest.snapshot_id = "wrong"
        self.assertEqual(snapshot.snapshot_id,
                         build_saturn_knowledge_snapshot(site, catalog, external).snapshot_id)

    def test_metadata_is_not_pdf_answer_evidence(self):
        site, catalog, external = make_inputs({
            PRODUCT: source(fields="documents:\n - " + doc() + "\n")
        })
        snap = build_saturn_knowledge_snapshot(site, catalog, external)
        metadata_facts = [f for f in snap.facts
                          if f.field_path.startswith("documents")]
        self.assertTrue(metadata_facts)
        self.assertFalse(any(
            e.evidence_type == "document_metadata" or
            (e.evidence_type == "site_field" and
             "#documents" in e.locator)
            for e in snap.answer_evidence))
        self.assertEqual(snap.document_matches[0].extraction_status, "extracted")

    def test_unresolved_relation_has_diagnostic_but_no_dangling_evidence(self):
        site, catalog, external = make_inputs({
            PRODUCT: source(fields="related:\n - not-on-site\n")
        })
        snapshot = build_saturn_knowledge_snapshot(site, catalog, external)
        self.assertTrue(snapshot.unresolved_relations)
        self.assertTrue(any(x.code == "unresolved_relation"
                            for x in snapshot.diagnostics))
        self.assertFalse(any(x.evidence_type == "relation"
                             and x.canonical_id in {r.relation_id for r in snapshot.unresolved_relations}
                             for x in snapshot.evidence_pointers))
        self.assertTrue(snapshot.ready_for_promotion)

    def test_unknown_fields_collections_and_dictionaries_preserved(self):
        site, catalog, external = make_inputs({
            PRODUCT: source(fields="future_name: {x: [11, 22]}\n")
        })
        snap = build_saturn_knowledge_snapshot(site, catalog, external)
        self.assertTrue(any(f.field_path == "future_name.x[1]"
                            for f in snap.facts))
        self.assertTrue(any(f.field_path == "future_name.x[1]"
                            for f in site.facts))
        self.assertEqual(snap.dictionaries, site.dictionaries)
        self.assertTrue(any(x.entity_type == "SiteContent" for x in snap.entities))
        self.assertEqual(len(snap.manifest.site_manifest.schema_inventory.dictionaries),
                         len(snap.dictionaries))

    def test_markdown_passages_exact_and_stable(self):
        content = "## Header\n" + "A" * 2501 + "\nLine two\n\n|Col|Value|\n|---|---|\n|x|y|\n"
        site, catalog, external = make_inputs({PRODUCT: source(body=content)})
        snap = build_saturn_knowledge_snapshot(site, catalog, external)
        entity = next(e for e in snap.entities if e.collection == "products"
                      and e.slug == "catalog-a")
        passages = [e for e in snap.answer_evidence
                    if e.evidence_type == "site_passage"
                    and e.entity_id == entity.entity_id]
        self.assertTrue(passages)
        self.assertTrue(all(len(e.text) <= 2400 for e in passages))
        self.assertTrue(all(e.text in entity.body for e in passages))
        self.assertTrue(any("column=" in e.locator for e in passages))
        self.assertTrue(any("|x|y|" in e.text for e in passages))
        self.assertTrue(all("heading=" in e.locator for e in passages))

    def test_determinism_under_shuffled_adapter_collections(self):
        site, catalog, ext = make_inputs({
            PRODUCT: source(fields="documents:\n - " + doc() + "\n")
        })
        original = build_saturn_knowledge_snapshot(site, catalog, ext)
        alternate = build_saturn_knowledge_snapshot(
            replace(site, source_revisions=tuple(reversed(site.source_revisions)),
                    entities=tuple(reversed(site.entities)),
                    facts=tuple(reversed(site.facts)),
                    relations=tuple(reversed(site.relations))),
            replace(catalog, documents=tuple(reversed(catalog.documents)),
                    occurrences=tuple(reversed(catalog.occurrences)),
                    pdf_candidates=tuple(reversed(catalog.pdf_candidates))),
            replace(ext, statuses=tuple(reversed(ext.statuses)),
                    revisions=tuple(reversed(ext.revisions)),
                    evidence=tuple(reversed(ext.evidence)),
                    associations=tuple(reversed(ext.associations)),
                    cached_extractions=tuple(reversed(ext.cached_extractions))),
        )
        self.assertEqual(original, alternate)

    def test_revisions_and_content_changes_change_snapshot_identity(self):
        spec = {PRODUCT: source(fields="documents:\n - " + doc() + "\n")}
        first = build_saturn_knowledge_snapshot(*make_inputs(spec))
        changes = [
            make_inputs(spec, commit="b"*40),
            make_inputs({PRODUCT: source(fields="documents:\n - " + doc() + "\n",
                                        body="New body")}),
            make_inputs({PRODUCT: source(fields="documents:\n - " +
                             doc(title="Other title") + "\n")}),
            make_inputs(spec, pdf=PDF + b"\nupdated"),
            make_inputs(spec, pages=((1, "changed"), (2, "Beta"))),
            make_inputs({PRODUCT: source(body="No PDF")}),
        ]
        for args in changes:
            with self.subTest(version=args[0].manifest.snapshot_id):
                self.assertNotEqual(
                    first.snapshot_id,
                    build_saturn_knowledge_snapshot(*args).snapshot_id)

    def test_owner_changes_are_visible_but_pdf_revision_stable(self):
        block = "documents:\n - " + doc() + "\n"
        one = build_saturn_knowledge_snapshot(
            *make_inputs({PRODUCT: source(fields=block)}))
        two = build_saturn_knowledge_snapshot(
            *make_inputs({PRODUCT: source(fields=block),
                          SECOND: source("Second", fields=block)}))
        self.assertNotEqual(one.snapshot_id, two.snapshot_id)
        self.assertEqual(one.pdf_revisions[0], two.pdf_revisions[0])
        self.assertEqual(len(one.support_documents[0].owner_entity_ids), 1)
        self.assertEqual(len(two.support_documents[0].owner_entity_ids), 2)

    def test_pdf_failures_stage_real_metadata_without_promotion(self):
        spec = {PRODUCT: source(fields="documents:\n - " + doc() + "\n")}
        for failure, pages in [
            ("network_error", ((1, "Alpha"), (2, "Beta"))),
            ("parser_error", ((1, "Alpha"), (2, "Beta"))),
            (None, ((1, ""), (2, ""))),
            (None, ((1, "Alpha"), (2, ""))),
        ]:
            with self.subTest(failure=failure, pages=pages):
                inputs = make_inputs(spec, failure=failure, pages=pages)
                result = stage_saturn_knowledge_snapshot(*inputs)
                self.assertIsNotNone(result.candidate)
                self.assertFalse(result.ready_for_promotion)
                self.assertTrue(result.candidate.document_matches)
                self.assertTrue(result.candidate.pdf_diagnostics)
                self.assertEqual(
                    len([x for x in result.candidate.answer_evidence
                         if x.evidence_type == "pdf_passage"]),
                    sum(bool(text) for _, text in pages) if failure is None else 0)
                with self.assertRaises(SnapshotBuildError):
                    build_saturn_knowledge_snapshot(*inputs)

    def test_integrity_fail_closed_and_codes(self):
        site, catalog, ext = make_inputs({
            PRODUCT: source(fields="documents:\n - " + doc() + "\n")
        })
        cases = [
            (replace(site, facts=site.facts + site.facts[:1]), catalog, ext,
             "duplicate_fact"),
            (replace(site, source_revisions=(
                replace(site.source_revisions[0], content_sha256="f"*64),
                *site.source_revisions[1:])), catalog, ext,
             "source_revision_mismatch"),
            (site, replace(catalog, documents=(
                replace(catalog.documents[0], title="forged"),)), ext,
             "document_metadata_mismatch"),
            (site, catalog, replace(ext, associations=(
                replace(ext.associations[0], source_locators=("fake",)),)),
             "pdf_association_mismatch"),
            (site, catalog, replace(ext, evidence=ext.evidence + ext.evidence[:1]),
             "duplicate_pdf_evidence"),
            (site, catalog, replace(ext, evidence=(
                replace(ext.evidence[0], page_number=999), *ext.evidence[1:])),
             "pdf_evidence_mismatch"),
            (site, catalog, replace(ext, statuses=(
                replace(ext.statuses[0], revision_id="f"*64),)),
             "pdf_revision_mismatch"),
            (site, catalog, replace(ext, cached_extractions=(
                replace(ext.cached_extractions[0], extraction=ExtractedPdf(
                    2, ((1, "tampered"), (2, "Beta")))),)),
             "pdf_text_hash_mismatch"),
        ]
        for changed_site, changed_catalog, changed_ext, expected in cases:
            with self.subTest(expected=expected):
                result = stage_saturn_knowledge_snapshot(
                    changed_site, changed_catalog, changed_ext)
                self.assertIsNone(result.candidate)
                self.assertIn(expected, {x.code for x in result.issues})
                with self.assertRaises(SnapshotBuildError):
                    build_saturn_knowledge_snapshot(
                        changed_site, changed_catalog, changed_ext)

    def test_atomic_activation_rejects_tampering_and_retains_old(self):
        manager = SaturnSnapshotManager()
        with self.assertRaises(LookupError):
            manager.capture()
        spec = {PRODUCT: source(fields="documents:\n - " + doc() + "\n")}
        original = build_saturn_knowledge_snapshot(*make_inputs(spec))
        later = build_saturn_knowledge_snapshot(*make_inputs(spec, commit="b"*40))
        self.assertEqual(manager.activate(original), original.snapshot_id)
        failed = stage_saturn_knowledge_snapshot(
            *make_inputs(spec, failure="network_error")).candidate
        with self.assertRaises(SnapshotBuildError):
            manager.activate(failed)
        with self.assertRaises(SnapshotBuildError):
            manager.activate(replace(original, answer_evidence=()))
        self.assertIs(manager.capture(), original)
        self.assertEqual(manager.activate(later), later.snapshot_id)
        self.assertIs(manager.capture(), later)
        self.assertEqual(manager.activate(later), later.snapshot_id)

    def test_concurrent_capture_is_consistent_pointer(self):
        manager = SaturnSnapshotManager()
        snapshots = [
            build_saturn_knowledge_snapshot(*make_inputs(commit=sha*40))
            for sha in ("a", "b", "c")
        ]
        manager.activate(snapshots[0])

        def reader(_):
            return manager.capture()

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(reader, i) for i in range(80)]
            manager.activate(snapshots[1])
            manager.activate(snapshots[2])
            captured = [f.result() for f in futures]
        self.assertTrue(all(s is snapshots[0] or s is snapshots[1]
                            or s is snapshots[2] for s in captured))

    def test_exact_saturn_source_derived_integration_offline(self):
        paths = {}
        for file in ROOT.rglob("*"):
            if file.is_file() and file.name != "README.md":
                raw = file.read_bytes()
                paths[file.relative_to(ROOT).as_posix()] = (
                    git_blob_sha1(raw), raw)
        self.assertEqual(len(paths), 8)
        pinned = PinnedSiteSnapshot.from_mapping(
            commit_sha="084d759487bfab6e111549c9b5469711ac5fc13e",
            tree_sha="a5297822bf3a5e071b10cc1dca553481c1b84d47",
            files=paths,
        )
        with patch("socket.create_connection",
                   side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen",
                   side_effect=AssertionError("network forbidden")):
            site = adapt_snapshot(pinned)
            catalog = adapt_support_catalog(site)
            external = adapt_external_documents(
                catalog, DocumentFetchPolicy(
                    allowed_hosts=("www.mnppsaturn.ru",),
                    allowed_path_prefixes=("/ftp", "/public", "/photos")),
                transport=OfflineTransport(), extractor=OfflineExtractor(),
            )
            snapshot = build_saturn_knowledge_snapshot(site, catalog, external)
        self.assertEqual(len(snapshot.entities), 4)
        self.assertEqual(len(snapshot.support_documents), 10)
        self.assertEqual(len(snapshot.document_matches), 10)
        self.assertEqual(len(snapshot.pdf_revisions), 8)
        self.assertEqual(len(snapshot.pdf_statuses), 8)
        self.assertEqual(len([x for x in snapshot.answer_evidence
                              if x.evidence_type == "pdf_passage"]), 16)
        self.assertEqual(snapshot.manifest.site_manifest.commit_sha,
                         pinned.commit_sha)
        self.assertTrue(snapshot.ready_for_promotion)
        self.assertEqual(len(snapshot.document_occurrences), 10)
        for occurrence in snapshot.document_occurrences:
            self.assertTrue(occurrence.source_path.startswith("src/content/"))
            self.assertTrue(occurrence.source_locator.startswith(
                occurrence.source_revision_id + "#"))
        self.assertTrue(verify_snapshot_seal(snapshot))


if __name__ == "__main__":
    unittest.main()
