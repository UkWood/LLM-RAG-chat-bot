"""CR-08: independent, source-backed scoped Stage 5F snapshot contract tests.

The source is a synthetic but genuine PinnedSiteSnapshot -> site adapter ->
support catalog chain. Test cases are NOT real-corpus acceptance evidence.
"""
from dataclasses import asdict, replace
from unittest.mock import patch
import unittest

from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot, adapt_snapshot,
)
from saturn_ai.ingestion.support_catalog_adapter import (
    adapt_support_catalog,
)
from saturn_ai.ingestion.external_document_adapter import (
    adapt_external_documents,
)
from saturn_ai.ingestion.external_document_extractor import SubprocessPdfExtractor
from saturn_ai.ingestion.external_document_transport import DocumentFetchPolicy
from saturn_ai.ingestion.saturn_contracts import stable_id
from saturn_ai.real_corpus_stand import (
    select_pdf_catalog, prepare_real_stand,
)
from saturn_ai.saturn_knowledge_contracts import (
    SaturnScopedExperiment, SaturnSnapshotManager, SnapshotBuildError,
    define_scoped_experiment, snapshot_content, verify_snapshot_seal,
)
from saturn_ai.saturn_knowledge_snapshot import (
    build_saturn_knowledge_snapshot, build_scoped_saturn_knowledge_snapshot,
)
from saturn_ai.retrieval.saturn_channel import build_saturn_retrieval_bundle
from unit.test_saturn_knowledge_snapshot import OfflineExtractor, OfflineTransport, PDF
from unit.test_support_catalog_adapter import (
    PRODUCT, SECOND, doc, files, put, source,
)


def source_fixture():
    """Two PDFs, one chosen PDF with two owner usages, all verified source bytes."""
    mapping = files()
    put(mapping, PRODUCT, source(fields=(
        'documents:\n - ' + doc(title='Guide one', url='/ftp/guide.pdf') + '\n'
        ' - ' + doc(title='Guide two', url='/ftp/other.pdf') + '\n'),
        body='\n# Manual\n[Guide](/ftp/guide.pdf)\n'))
    put(mapping, SECOND, source('Second', fields=(
        'documents:\n - ' + doc(title='Guide one', url='/ftp/guide.pdf') + '\n')))
    pinned = PinnedSiteSnapshot.from_mapping(
        commit_sha='a'*40, tree_sha='c'*40, files=mapping)
    site = adapt_snapshot(pinned)
    full = adapt_support_catalog(site)
    assert site.ready_for_promotion and full.ready_for_promotion
    assert len(full.pdf_candidates) == 2
    chosen = select_pdf_catalog(full, pdf_paths=('/ftp/guide.pdf',))
    scope = define_scoped_experiment(site, chosen.pdf_candidates)
    return pinned, site, full, chosen, scope


def policy():
    return DocumentFetchPolicy(allowed_hosts=('www.mnppsaturn.ru',),
                               allowed_path_prefixes=('/ftp',), max_requests=4)


def extraction(catalog, *, pages=None, real_worker=False):
    extractor = (SubprocessPdfExtractor(enable_development_worker=True)
                 if real_worker else OfflineExtractor(
                     pages=pages if pages is not None else ((1, 'Alpha'), (2, 'Beta'))))
    return adapt_external_documents(catalog, policy(),
                                    transport=OfflineTransport(PDF), extractor=extractor)


def scoped_snapshot(site, catalog, scope, *, pages=None, real_worker=False):
    return build_scoped_saturn_knowledge_snapshot(
        site, catalog, extraction(catalog, pages=pages, real_worker=real_worker),
        scope=scope)


def reseal_scoped(snapshot):
    """Attacker-like *self-consistent* hash recomputation: not a source proof."""
    scope = snapshot.scope
    corpus_hash = stable_id('saturn-scoped-corpus-v1', {
        'mode': scope.mode, 'scope_digest': scope.scope_digest,
        'content': snapshot_content(snapshot),
    })
    manifest = replace(snapshot.manifest, corpus_hash=corpus_hash, snapshot_id='')
    unsigned = {key: value for key, value in asdict(manifest).items()
                if key != 'snapshot_id'}
    manifest = replace(manifest, snapshot_id=stable_id('saturn-scoped-snapshot-v1', {
        'scope': asdict(scope), 'manifest': unsigned,
    }))
    return replace(snapshot, manifest=manifest)


class CR08ScopedSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pinned, cls.site, cls.full, cls.chosen, cls.scope = source_fixture()

    def test_CR08_T01_two_source_pdfs_one_scoped_pdf_real_subprocess(self):
        snap = scoped_snapshot(self.site, self.chosen, self.scope, real_worker=True)
        self.assertTrue(snap.ready_for_promotion)
        self.assertEqual(len(snap.pdf_revisions), 1)
        self.assertTrue(any(x.evidence_type == 'pdf_passage' for x in snap.answer_evidence))
        self.assertEqual(snap.manifest.pdf_parser_version,
                         'saturn-pdf-pypdf-6.10.0/0.3.0')

    def test_CR08_T02_additional_documents_outside_scope_are_not_falsified(self):
        self.assertEqual(len(self.full.documents), 2)
        self.assertEqual(len(self.chosen.documents), 1)
        snap = scoped_snapshot(self.site, self.chosen, self.scope)
        self.assertEqual(len(snap.document_matches), 1)
        excluded_id = next(d.document_id for d in self.full.documents
                           if d.document_id not in self.scope.selected_document_ids)
        self.assertNotIn(excluded_id, {d.document.document_id for d in snap.document_matches})

    def test_CR08_T03_every_occurrence_and_owner_of_selected_document(self):
        chosen_id = self.scope.selected_document_ids[0]
        expected = tuple(x for x in self.full.occurrences if x.document_id == chosen_id)
        self.assertEqual(set(expected), set(self.chosen.occurrences))
        self.assertEqual(len({o.owner_entity_id for o in expected}), 2)
        self.assertEqual(len(expected), 3)
        snap = scoped_snapshot(self.site, self.chosen, self.scope)
        self.assertEqual(set(snap.document_occurrences), set(expected))
        self.assertEqual(set(snap.document_matches[0].occurrences), set(expected),
                         'Source-verified occurrences must remain attached')

    def test_CR08_T04_scoped_snapshot_survives_structural_activation_replay(self):
        snap = scoped_snapshot(self.site, self.chosen, self.scope)
        self.assertTrue(verify_snapshot_seal(snap))
        manager = SaturnSnapshotManager()
        self.assertEqual(manager.activate(snap), snap.snapshot_id)
        self.assertIs(manager.capture(), snap)
        self.assertEqual(snap.validation_sources.scope, self.scope)

    def test_CR08_T05_stage4b_retrieval_bundle_has_scoped_identity(self):
        snap = scoped_snapshot(self.site, self.chosen, self.scope)
        bundle = build_saturn_retrieval_bundle(snap)
        bundle.validate()
        self.assertEqual(bundle.scope_mode, 'scoped_experiment')
        self.assertEqual(bundle.scope_digest, self.scope.scope_digest)
        self.assertEqual(bundle.manifest.snapshot_id, snap.snapshot_id)

    def test_CR08_T06_deterministic_scope_and_snapshot_identity(self):
        another = define_scoped_experiment(self.site, reversed(self.chosen.pdf_candidates))
        self.assertEqual(another.scope_digest, self.scope.scope_digest)
        a = scoped_snapshot(self.site, self.chosen, self.scope)
        b = scoped_snapshot(self.site, self.chosen, another)
        self.assertEqual(a.snapshot_id, b.snapshot_id)
        self.assertEqual(a.manifest.corpus_hash, b.manifest.corpus_hash)

    def test_CR08_T07_standard_full_corpus_builder_and_activation_still_strict(self):
        external = extraction(self.full)
        snap = build_saturn_knowledge_snapshot(self.site, self.full, external)
        self.assertIsNone(snap.scope)
        self.assertIsNone(build_saturn_retrieval_bundle(snap).scope_mode)
        self.assertEqual(SaturnSnapshotManager().activate(snap), snap.snapshot_id)

    def test_CR08_T08_missing_selected_occurrence_is_rejected(self):
        reduced = replace(self.chosen, occurrences=self.chosen.occurrences[:-1])
        with self.assertRaises(SnapshotBuildError):
            scoped_snapshot(self.site, reduced, self.scope)

    def test_CR08_T09_changed_owner_is_rejected(self):
        occ = self.chosen.occurrences[0]
        forged = replace(occ, owner_entity_id='saturn-owner-forged')
        reduced = replace(self.chosen, occurrences=(forged, *self.chosen.occurrences[1:]))
        with self.assertRaises(SnapshotBuildError):
            scoped_snapshot(self.site, reduced, self.scope)

    def test_CR08_T10_changed_source_revision_is_rejected(self):
        occ = self.chosen.occurrences[0]
        forged = replace(occ, source_revision_id='f'*64)
        changed = replace(self.chosen, occurrences=(forged, *self.chosen.occurrences[1:]))
        with self.assertRaises(SnapshotBuildError):
            scoped_snapshot(self.site, changed, self.scope)

    def test_CR08_T11_changed_document_id_or_url_is_rejected(self):
        cand = self.chosen.pdf_candidates[0]
        for forged in (replace(cand, document_id='saturn-doc:invented'),
                       replace(cand, resolved_url='https://www.mnppsaturn.ru/ftp/forged.pdf')):
            with self.subTest(forged=forged):
                modified = replace(self.chosen, pdf_candidates=(forged,))
                with self.assertRaises(SnapshotBuildError):
                    scoped_snapshot(self.site, modified, self.scope)

    def test_CR08_T12_scope_source_nonmember_is_rejected(self):
        forged = replace(self.chosen.pdf_candidates[0], document_id='saturn-doc:invented')
        claimed = define_scoped_experiment(self.site, (forged,))
        with self.assertRaises(SnapshotBuildError):
            scoped_snapshot(self.site, self.chosen, claimed)

    def test_CR08_T13_modified_scope_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.scope, scope_digest='0'*64)
        damaged = replace(self.scope)
        object.__setattr__(damaged, 'scope_digest', '0'*64)
        with self.assertRaises(SnapshotBuildError):
            scoped_snapshot(self.site, self.chosen, damaged)

    def test_CR08_T14_scope_swap_after_seal_is_rejected_even_if_resealed(self):
        snap = scoped_snapshot(self.site, self.chosen, self.scope)
        other = next(c for c in self.full.pdf_candidates
                     if c.document_id not in self.scope.selected_document_ids)
        different = define_scoped_experiment(self.site, (other,))
        tampered = reseal_scoped(replace(snap, scope=different))
        self.assertTrue(verify_snapshot_seal(tampered))
        with self.assertRaises(SnapshotBuildError):
            SaturnSnapshotManager().activate(tampered)

    def test_CR08_T15_partial_selected_pdf_blocks_readiness(self):
        external = extraction(self.chosen, pages=((1, 'Alpha'), (2, '')))
        self.assertFalse(external.ready_for_promotion)
        with self.assertRaises(SnapshotBuildError):
            build_scoped_saturn_knowledge_snapshot(self.site, self.chosen,
                                                   external, scope=self.scope)

    def test_CR08_T16_standard_validator_rejects_partial_catalog_without_scope(self):
        with self.assertRaises(SnapshotBuildError):
            build_saturn_knowledge_snapshot(self.site, self.chosen,
                                            extraction(self.chosen))

    def test_CR08_T17_resealed_tampered_evidence_fails_structural_replay(self):
        snap = scoped_snapshot(self.site, self.chosen, self.scope)
        self.assertGreater(len(snap.document_occurrences), 1)
        tampered = reseal_scoped(replace(snap, document_occurrences=()))
        self.assertTrue(verify_snapshot_seal(tampered))
        with self.assertRaises(SnapshotBuildError):
            SaturnSnapshotManager().activate(tampered)
        with self.assertRaises(ValueError):
            build_saturn_retrieval_bundle(tampered)

    def test_CR08_T18_four_pdf_subset_cannot_claim_full_corpus_ready(self):
        # This tests prepare_real_stand's manifest, not just a static literal.
        class Provider:
            def fetch_snapshot(inner):
                return self.pinned
        with patch('saturn_ai.real_corpus_stand.select_site_snapshot',
                   side_effect=lambda p: p), \
             patch('saturn_ai.real_corpus_stand.select_pdf_catalog',
                   side_effect=lambda cat: select_pdf_catalog(cat, pdf_paths=('/ftp/guide.pdf',))), \
             patch('saturn_ai.real_corpus_stand.SubprocessPdfExtractor',
                   side_effect=lambda **kwargs: OfflineExtractor()), \
             patch('saturn_ai.real_corpus_stand.real_pdf_policy', side_effect=policy), \
             patch('saturn_ai.real_corpus_stand.PDF_PATHS', ('/ftp/guide.pdf',)):
            stand = prepare_real_stand(provider=Provider(), enable_development_pdf_worker=True)
        self.assertTrue(stand.manifest['scoped_extraction_ready'])
        self.assertFalse(stand.manifest['full_corpus_extraction_ready'])
        self.assertEqual(stand.manifest['full_source_catalog_pdf_candidate_count'], 2)
        self.assertEqual(stand.manifest['selected_pdf_count'], 1)
        self.assertEqual(stand.manifest['excluded_pdf_count'], 1)
        self.assertEqual(stand.manifest['scope_mode'], 'scoped_experiment')
        self.assertEqual(stand.manifest['source_tree'], 'c'*40)


if __name__ == '__main__':
    unittest.main()