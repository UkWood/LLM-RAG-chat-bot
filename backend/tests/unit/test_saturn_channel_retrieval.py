"""Stage 4B: Saturn-only functional/identity/policy/index regression tests.

Controlled vectors test Qdrant integration, not real semantic quality.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from qdrant_client import models
import unittest

from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot, adapt_snapshot, git_blob_sha1,
)
from saturn_ai.ingestion.support_catalog_adapter import adapt_support_catalog
from saturn_ai.ingestion.external_document_adapter import adapt_external_documents
from saturn_ai.ingestion.external_document_transport import DocumentFetchPolicy
from saturn_ai.retrieval.saturn_channel import (
    SaturnOperationalPolicy, SaturnPolicyProvider, SaturnRetrievalService,
    build_saturn_retrieval_bundle, search_saturn, tokenize, _bm25,
    _check_channel, _candidate,
)
from saturn_ai.saturn_knowledge_snapshot import build_saturn_knowledge_snapshot
from unit.test_saturn_knowledge_snapshot import (
    make_inputs, OfflineTransport, OfflineExtractor, ROOT,
)
from unit.test_support_catalog_adapter import PRODUCT, SECOND, doc, source


def fixture_snapshot(commit="a"*40):
    block = "documents:\n - " + doc(version="v2") + "\n"
    site, catalog, external = make_inputs({
        PRODUCT: source("БКД-ПК-РФ.2", fields=block +
                        "interface: RS-485\nprotocol: BACnet\nfuture_name: 12\n",
                        body="## Протоколы\nОбмен по RS-485.\n"),
        SECOND: source("Second", fields=block,
                       body="## Overview\nSome technical features.\n"),
    }, commit=commit)
    return build_saturn_knowledge_snapshot(site, catalog, external)


class ControlledEncoder:
    dimensions = 4
    identity = {"kind": "controlled-test", "revision": "1", "dimensions": 4}

    @staticmethod
    def vector(text):
        data = sha256(text.encode("utf-8")).digest()
        return [float(x + 1) for x in data[:4]]

    def encode_documents(self, texts):
        return [self.vector(text) for text in texts]

    def encode_query(self, text):
        return self.vector(text)


class CountingEncoder(ControlledEncoder):
    def __init__(self):
        self.batch_lengths = []

    def encode_documents(self, texts):
        self.batch_lengths.append(len(texts))
        return super().encode_documents(texts)


class ChangingPolicyProvider:
    def __init__(self, first, later):
        self.first, self.later, self.calls = first, later, 0

    def capture(self):
        self.calls += 1
        return self.first if self.calls == 1 else self.later


class SaturnRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = fixture_snapshot()

    def test_tokenizer_preserves_engineering_identity(self):
        self.assertEqual(tokenize("RS-485 BACnet БКД-ПК-РФ.2 0.25 kPa"),
                         ("rs-485", "bacnet", "бкд-пк-рф.2", "0.25", "kpa"))
        self.assertNotEqual(tokenize("БКД-ПК-РФ.2"), tokenize("БКД-ПК-RF.2"))

    def test_exact_full_evidence_pointer_coverage(self):
        bundle = build_saturn_retrieval_bundle(self.snap)
        ids = {x.evidence_id for x in self.snap.answer_evidence}
        self.assertEqual(ids, {x.evidence_id for x in bundle.records})
        self.assertEqual(ids, {x.evidence_id for x in self.snap.evidence_pointers})
        self.assertEqual(bundle.manifest.evidence_count, len(ids))
        self.assertEqual(bundle.manifest.document_count, len(self.snap.document_matches))
        self.assertEqual({x.snapshot_id for x in bundle.records}, {self.snap.snapshot_id})
        self.assertEqual(bundle.records, tuple(sorted(bundle.records, key=lambda x: x.evidence_id)))
        self.assertTrue(all(len(x.text_hash) == 64 for x in bundle.records))

    def test_source_backed_field_unit_relation_unknown_and_pdf(self):
        bundle = build_saturn_retrieval_bundle(self.snap)
        fields = [r for r in bundle.records if r.evidence_type == "site_field"]
        self.assertTrue(any("interface" in r.text and "RS-485" in r.text for r in fields))
        self.assertTrue(any("future_name" in r.text for r in fields))
        self.assertTrue(any(r.evidence_type == "relation" for r in bundle.records))
        self.assertTrue(any(r.evidence_type == "site_passage" and "body:line=" in r.locator
                            for r in bundle.records))
        pdfs = [r for r in bundle.records if r.evidence_type == "pdf_passage"]
        self.assertTrue(pdfs)
        self.assertTrue(all(r.pdf_bytes_sha256 and r.pdf_parser_version and
                            r.physical_page in (1, 2) and r.url.endswith(".pdf")
                            for r in pdfs))

    def test_lexical_offline_exact_tokens_ranks_and_empty(self):
        bundle = build_saturn_retrieval_bundle(self.snap)
        service = SaturnRetrievalService()
        service.publish(bundle)
        result = service.search_saturn("RS-485")
        self.assertTrue(result.answer_evidence)
        self.assertEqual(result.query, "RS-485")
        self.assertEqual(result.mode, "lexical")
        self.assertEqual(tuple(c.rank for c in result.answer_evidence),
                         tuple(range(1, len(result.answer_evidence)+1)))
        self.assertEqual(result, service.search_saturn("RS-485"))
        self.assertFalse(service.search_saturn("xyz-nonexistent-123456").answer_evidence)
        self.assertFalse(service.search_saturn("БКД-ПК-RF.2").answer_evidence)
        self.assertEqual(result.snapshot_id, self.snap.snapshot_id)

    def test_metadata_is_a_separate_channel_with_owners_and_status(self):
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(self.snap))
        result = service.search_saturn("guide")
        self.assertTrue(result.document_matches)
        docmatch = result.document_matches[0].match
        self.assertEqual(docmatch.document.title, "A guide")
        self.assertEqual(len(docmatch.document.owner_entity_ids), 2)
        self.assertEqual(docmatch.extraction_status, "extracted")
        self.assertEqual(len(docmatch.occurrences), 2)
        self.assertTrue(docmatch.document.source_locators)
        self.assertTrue(docmatch.document.url.endswith(".pdf"))
        self.assertFalse(any(c.evidence_type == "document_metadata"
                             for c in result.answer_evidence))
        self.assertFalse(result.answer_evidence)  # metadata search cannot masquerade as facts

    def test_metadata_kind_version_and_owner_search(self):
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(self.snap))
        for query in ("manual", "v2", "БКД-ПК-РФ.2"):
            with self.subTest(query=query):
                self.assertTrue(service.search_saturn(query).document_matches)

    def test_bounded_dictionary_alias_requires_explicit_source_declaration(self):
        additions = {
            PRODUCT: source("Instrument", fields="protocol: RS-485\\n"),
            "src/data/interfaces.yaml": (
                "- code: RS-485\\n"
                "  aliases: [RS485]\\n"
                "- code: БКД-ПК-РФ.2\\n"
                "  label: Example\\n"
            ),
        }
        snapshot = build_saturn_knowledge_snapshot(*make_inputs(additions))
        service = SaturnRetrievalService()
        bundle = build_saturn_retrieval_bundle(snapshot)
        service.publish(bundle)
        self.assertTrue(service.search_saturn("RS485").answer_evidence)
        self.assertFalse(service.search_saturn("БКД-ПК-RF.2").answer_evidence)
        self.assertEqual(bundle.aliases.get("rs485"), ("rs-485",))

    def test_manifest_determinism_and_snapshot_change(self):
        one = build_saturn_retrieval_bundle(self.snap)
        two = build_saturn_retrieval_bundle(self.snap)
        self.assertEqual(one.manifest, two.manifest)
        other = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        self.assertNotEqual(one.manifest.bundle_id, other.manifest.bundle_id)
        self.assertNotEqual(one.manifest.corpus_hash, other.manifest.corpus_hash)
        self.assertIsNone(one.manifest.dense_encoder_hash)

    def test_bm25_math_basic(self):
        scores = _bm25("alpha", [("b", "alpha alpha"), ("a", "alpha")], 40)
        self.assertEqual(len(scores), 2)
        self.assertGreater(scores[0][1], 0)
        self.assertEqual(_bm25("not_found", [("a", "alpha")], 40), ())
        self.assertEqual(_bm25("alpha", [], 40), ())

    def test_dense_requires_encoder_and_reports_error(self):
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(self.snap))
        for mode in ("dense", "hybrid"):
            with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, "Dense"):
                service.search_saturn("BACnet", mode=mode)

    def test_qdrant_real_memory_ops_and_hybrid_rrf(self):
        encoder = CountingEncoder()
        bundle = build_saturn_retrieval_bundle(self.snap, encoder=encoder)
        self.assertTrue(all(1 <= k <= 16 for k in encoder.batch_lengths))
        self.assertEqual(sum(encoder.batch_lengths), len(bundle.records))
        self.assertEqual(len(bundle.dense.point_ids), len(bundle.records))
        service = SaturnRetrievalService()
        service.publish(bundle)
        dense = service.search_saturn("BACnet", mode="dense")
        hybrid = service.search_saturn("BACnet", mode="hybrid")
        self.assertTrue(dense.dense_trace)
        self.assertTrue(hybrid.lexical_trace)
        self.assertTrue(hybrid.dense_trace)
        self.assertTrue(hybrid.fusion_trace)
        self.assertEqual(hybrid.answer_evidence, hybrid.fusion_trace)
        self.assertEqual(hybrid, service.search_saturn("BACnet", mode="hybrid"))
        self.assertEqual(len({c.evidence_id for c in hybrid.answer_evidence}),
                         len(hybrid.answer_evidence))
        actual = {c.evidence_id: c for c in hybrid.fusion_trace}
        for item in hybrid.answer_evidence:
            lex_rank = next((c.rank for c in hybrid.lexical_trace
                             if c.evidence_id == item.evidence_id), None)
            den_rank = next((c.rank for c in hybrid.dense_trace
                             if c.evidence_id == item.evidence_id), None)
            target = sum(1/(60 + r) for r in (lex_rank, den_rank) if r is not None)
            self.assertAlmostEqual(actual[item.evidence_id].score, target)
        bundle.dense.close()

    def test_tampered_bm25_document_and_manifest_fail_publication(self):
        bundle = build_saturn_retrieval_bundle(self.snap)
        service = SaturnRetrievalService()
        service.publish(bundle)
        other = build_saturn_retrieval_bundle(self.snap)
        other.lexical.tokens = ()
        with self.assertRaises(ValueError):
            service.publish(other)
        self.assertIs(service.capture(), bundle)
        other2 = build_saturn_retrieval_bundle(self.snap)
        other2.metadata.tokens = ()
        with self.assertRaises(ValueError):
            service.publish(other2)
        other3 = build_saturn_retrieval_bundle(self.snap)
        other3.manifest = replace(other3.manifest, evidence_count=0)
        with self.assertRaises(ValueError):
            service.publish(other3)
        self.assertIs(service.capture(), bundle)

    def test_tampered_source_or_unpromotable_snapshot_fails_closed(self):
        forged = replace(self.snap, answer_evidence=self.snap.answer_evidence[:-1])
        with self.assertRaises(ValueError):
            build_saturn_retrieval_bundle(forged)
        failed = build_saturn_retrieval_bundle(self.snap)
        failed.records = failed.records[:-1]
        with self.assertRaises(ValueError):
            SaturnRetrievalService().publish(failed)

    def test_tampered_qdrant_payload_and_points_fail_closed(self):
        bundle = build_saturn_retrieval_bundle(self.snap, encoder=ControlledEncoder())
        client, dense = bundle.dense._client, bundle.dense
        client.set_payload(dense.collection, payload={"text_hash": "tampered"},
                           points=[dense.point_ids[0]])
        with self.assertRaises(ValueError):
            dense.validate()
        with self.assertRaises(ValueError):
            SaturnRetrievalService().publish(bundle)
        dense.close()

    def test_missing_qdrant_point_fails_closed(self):
        bundle = build_saturn_retrieval_bundle(self.snap, encoder=ControlledEncoder())
        dense = bundle.dense
        dense._client.delete(dense.collection, points_selector=models.PointIdsList(
            points=[dense.point_ids[0]]), wait=True)
        with self.assertRaises(ValueError):
            dense.validate()
        dense.close()

    def test_encoder_identity_dimensions_and_vector_failures(self):
        class Bad(ControlledEncoder):
            def encode_documents(self, texts):
                return [[0., 0., 0., 0.] for _ in texts]
        with self.assertRaises(ValueError):
            build_saturn_retrieval_bundle(self.snap, encoder=Bad())
        class Broken(ControlledEncoder):
            dimensions = 3
        with self.assertRaises(ValueError):
            build_saturn_retrieval_bundle(self.snap, encoder=Broken())
        class Invalid(ControlledEncoder):
            identity = {"checkpoint": float("nan")}
        with self.assertRaises(ValueError):
            build_saturn_retrieval_bundle(self.snap, encoder=Invalid())

    def test_policy_blocks_document_and_pdf_revision_without_approvals(self):
        pdf = next(r for r in self.snap.answer_evidence if r.evidence_type == "pdf_passage")
        did = self.snap.document_matches[0].document.document_id
        policy = SaturnOperationalPolicy(
            "rev-2", blocked_document_ids=frozenset((did,)),
            blocked_pdf_revision_ids=frozenset((pdf.source_revision_id,)))
        service = SaturnRetrievalService(SaturnPolicyProvider(policy))
        service.publish(build_saturn_retrieval_bundle(self.snap))
        result = service.search_saturn("Alpha guide")
        self.assertFalse(result.document_matches)
        self.assertFalse(any(c.evidence_type == "pdf_passage"
                             for c in result.answer_evidence))

    def test_policy_update_during_search_rechecks_post_query(self):
        match = self.snap.document_matches[0]
        pdf = next(e for e in self.snap.answer_evidence if e.evidence_type == "pdf_passage")
        later = SaturnOperationalPolicy(
            "rev-2", blocked_pdf_revision_ids=frozenset((pdf.source_revision_id,)),
            blocked_document_ids=frozenset((match.document.document_id,)))
        provider = ChangingPolicyProvider(SaturnOperationalPolicy("rev-1"), later)
        service = SaturnRetrievalService(provider)
        service.publish(build_saturn_retrieval_bundle(self.snap))
        result = service.search_saturn("Alpha guide", top_k=20)
        self.assertEqual(provider.calls, 2)
        self.assertFalse(result.document_matches)
        self.assertFalse(any(c.evidence_type == "pdf_passage"
                             for c in result.answer_evidence))
        self.assertEqual([c.rank for c in result.lexical_trace],
                         list(range(1, len(result.lexical_trace)+1)))

    def test_policy_capture_failure_is_not_silently_ignored(self):
        class Failed:
            def capture(self):
                raise RuntimeError("Policy backend unavailable")
        service = SaturnRetrievalService(Failed())
        service.publish(build_saturn_retrieval_bundle(self.snap))
        with self.assertRaisesRegex(RuntimeError, "Policy"):
            service.search_saturn("RS-485")

    def test_resource_limits_and_query_security(self):
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(self.snap))
        for query in ("", " ", "\x00", "X"*4001, None):
            with self.subTest(query=str(query)[:10]), self.assertRaises(ValueError):
                service.search_saturn(query)
        for top_k in (0, -1, 41, 1.5, True):
            with self.subTest(top_k=top_k), self.assertRaises(ValueError):
                service.search_saturn("RS-485", top_k=top_k)
        with self.assertRaises(ValueError):
            service.search_saturn("RS-485", mode="unknown")
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("URL fetch forbidden")):
            service.search_saturn("https://example.org/not-a-source")
            self.assertTrue(service.search_saturn("RS-485").answer_evidence)

    def test_atomic_failed_next_bundle_retains_old(self):
        first = build_saturn_retrieval_bundle(self.snap)
        second = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        service = SaturnRetrievalService()
        service.publish(first)
        second.lexical.tokens = ()
        with self.assertRaises(ValueError):
            service.publish(second)
        self.assertIs(service.capture(), first)
        second = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        service.publish(second)
        self.assertIs(service.capture(), second)

    def test_concurrent_queries_never_mix_bundle_revisions(self):
        old = build_saturn_retrieval_bundle(self.snap)
        new = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        service = SaturnRetrievalService()
        service.publish(old)
        def reader(_):
            return search_saturn(service, "BACnet", top_k=10)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(reader, i) for i in range(35)]
            service.publish(new)
            results = [f.result() for f in futures]
        for result in results:
            self.assertIn(result.bundle_id, (old.manifest.bundle_id, new.manifest.bundle_id))
            self.assertTrue(all(c.snapshot_id == result.snapshot_id
                                for c in result.answer_evidence))
            self.assertTrue(all(d.snapshot_id == result.snapshot_id
                                for d in result.document_matches))

    def test_source_derived_saturn_fixture_integration_offline(self):
        paths = {}
        for file in ROOT.rglob("*"):
            if file.is_file() and file.name != "README.md":
                raw = file.read_bytes()
                paths[file.relative_to(ROOT).as_posix()] = (git_blob_sha1(raw), raw)
        pinned = PinnedSiteSnapshot.from_mapping(
            commit_sha="084d759487bfab6e111549c9b5469711ac5fc13e",
            tree_sha="a5297822bf3a5e071b10cc1dca553481c1b84d47",
            files=paths,
        )
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            site = adapt_snapshot(pinned)
            catalog = adapt_support_catalog(site)
            external = adapt_external_documents(
                catalog, DocumentFetchPolicy(
                    allowed_hosts=("www.mnppsaturn.ru",),
                    allowed_path_prefixes=("/ftp", "/public", "/photos")),
                transport=OfflineTransport(), extractor=OfflineExtractor())
            snapshot = build_saturn_knowledge_snapshot(site, catalog, external)
            service = SaturnRetrievalService()
            service.publish(build_saturn_retrieval_bundle(snapshot))
            result = service.search_saturn("архитектура", top_k=10)
        self.assertEqual(len(snapshot.document_matches), 10)
        self.assertEqual(len(snapshot.pdf_revisions), 8)
        self.assertEqual(result.snapshot_id, snapshot.snapshot_id)
        self.assertEqual(service.capture().manifest.document_count, 10)


if __name__ == "__main__":
    unittest.main()
