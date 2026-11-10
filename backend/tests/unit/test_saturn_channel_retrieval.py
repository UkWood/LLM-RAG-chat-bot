"""Stage 4B: Saturn-only functional/identity/policy/index regression tests.

Controlled vectors test Qdrant integration, not real semantic quality.
"""
from collections import Counter
from math import log
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
from threading import Event
from tempfile import TemporaryDirectory
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
    _check_channel, _candidate, SaturnBM25Index, SearchRecord,
    TOKENIZER_VERSION, _make_manifest,
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


def baseline_reference_bm25(query, texts):
    """Independent pre-CR BM25 formula over eligible raw records."""
    words = [(key, tokenize(text)) for key, text in texts]
    if not words:
        return ()
    n = len(words)
    avg = sum(len(items) for _, items in words) / n
    if not avg:
        return ()
    df = Counter(term for _, toks in words for term in set(toks))
    result = []
    for key, toks in words:
        tf = Counter(toks)
        score = sum(
            log(1 + (n - df[t] + .5) / (df[t] + .5)) *
            tf[t] * 2.2 / (tf[t] + 1.2 * (.25 + .75 * len(toks) / avg))
            for t in sorted(set(tokenize(query))) if tf[t]
        )
        if score > 0:
            result.append((key, score))
    return tuple(sorted(result, key=lambda item: (-item[1], item[0]))[:40])


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
            PRODUCT: source("Instrument", fields="protocol: RS-485\n"),
            "src/data/interfaces.yaml": (
                "- code: RS-485\n"
                "  aliases: [RS485]\n"
                "- code: БКД-ПК-РФ.2\n"
                "  label: Example\n"
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
        object.__setattr__(other.lexical, 'tokens', ())
        with self.assertRaises(ValueError):
            service.publish(other)
        self.assertIs(service.capture(), bundle)
        other2 = build_saturn_retrieval_bundle(self.snap)
        object.__setattr__(other2.metadata, 'tokens', ())
        with self.assertRaises(ValueError):
            service.publish(other2)
        other3 = build_saturn_retrieval_bundle(self.snap)
        object.__setattr__(other3, 'manifest', replace(other3.manifest, evidence_count=0))
        with self.assertRaises(ValueError):
            service.publish(other3)
        self.assertIs(service.capture(), bundle)

    def test_tampered_source_or_unpromotable_snapshot_fails_closed(self):
        forged = replace(self.snap, answer_evidence=self.snap.answer_evidence[:-1])
        with self.assertRaises(ValueError):
            build_saturn_retrieval_bundle(forged)
        failed = build_saturn_retrieval_bundle(self.snap)
        object.__setattr__(failed, 'records', failed.records[:-1])
        with self.assertRaises(ValueError):
            SaturnRetrievalService().publish(failed)

    def test_qdrant_local_path_reopens_with_identical_snapshot_identity(self):
        with TemporaryDirectory() as directory:
            first = build_saturn_retrieval_bundle(
                self.snap, encoder=ControlledEncoder(), qdrant_path=directory)
            expected = first.manifest
            first.dense.close()
            restored = build_saturn_retrieval_bundle(
                self.snap, encoder=ControlledEncoder(), qdrant_path=directory)
            self.assertEqual(restored.manifest, expected)
            service = SaturnRetrievalService()
            service.publish(restored)
            self.assertTrue(service.search_saturn("BACnet", mode="dense").answer_evidence)
            # Published Qdrant close is deferred until retirement, including
            # Windows local-path locks; a lexical successor retires it.
            restored.dense.close()
            self.assertFalse(restored.dense._lifetime.closed)
            service.publish(build_saturn_retrieval_bundle(self.snap))
            self.assertTrue(restored.dense._lifetime.closed)

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

    def test_dense_cached_payload_and_point_identity_cannot_be_resealed(self):
        bundle = build_saturn_retrieval_bundle(self.snap, encoder=ControlledEncoder())
        dense = bundle.dense
        original = dense._payloads
        object.__setattr__(dense, "_payloads", (
            tuple(sorted(dict(original[0], source_revision_id="forged").items())),
            *original[1:]))
        with self.assertRaisesRegex(ValueError, "canonical evidence"):
            bundle.validate()
        object.__setattr__(dense, '_payloads', original)
        object.__setattr__(dense, "point_ids",
            ("00000000-0000-4000-8000-000000000000", *dense.point_ids[1:]))
        with self.assertRaisesRegex(ValueError, "point IDs"):
            bundle.validate()
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

    def test_document_block_alone_revokes_linked_pdf_answer_evidence(self):
        did = self.snap.document_matches[0].document.document_id
        policy = SaturnOperationalPolicy("doc-only", blocked_document_ids=frozenset((did,)))
        service = SaturnRetrievalService(SaturnPolicyProvider(policy))
        service.publish(build_saturn_retrieval_bundle(self.snap))
        result = service.search_saturn("Alpha guide", top_k=40)
        self.assertFalse(result.document_matches)
        self.assertFalse(any(c.evidence_type == "pdf_passage"
                             for c in result.answer_evidence))
        self.assertTrue(any(c.evidence_type != "pdf_passage"
                            for c in result.answer_evidence)
                        or result.answer_evidence == ())

    def test_revoked_site_origin_or_owner_blocks_linked_pdf_evidence(self):
        match = self.snap.document_matches[0]
        source_id = match.occurrences[0].source_revision_id
        owner_id = match.document.owner_entity_ids[0]
        for policy in (
            SaturnOperationalPolicy(
                "source-revoked", blocked_source_revision_ids=frozenset((source_id,))),
            SaturnOperationalPolicy(
                "owner-blocked", blocked_entity_ids=frozenset((owner_id,))),
        ):
            with self.subTest(policy=policy.revision):
                service = SaturnRetrievalService(SaturnPolicyProvider(policy))
                service.publish(build_saturn_retrieval_bundle(self.snap))
                result = service.search_saturn("Alpha", top_k=40)
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
        object.__setattr__(second.lexical, 'tokens', ())
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

    def test_cr01_published_bundle_and_nested_bindings_reject_assignment(self):
        bundle = build_saturn_retrieval_bundle(self.snap, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(bundle)
        for attr, replacement in (
            ("snapshot", fixture_snapshot(commit="b"*40)),
            ("records", ()),
            ("documents", ()),
            ("lexical", SaturnBM25Index(bundle.records)),
            ("metadata", None),
            ("dense", None),
            ("manifest", replace(bundle.manifest, evidence_count=0)),
            ("aliases", {}),
        ):
            with self.subTest(attr=attr), self.assertRaises(FrozenInstanceError):
                setattr(bundle, attr, replacement)
        for attr, replacement in (
            ("tokens", ()),
            ("_prepared", ()),
            ("coverage_hash", "tampered"),
        ):
            with self.subTest(index_attr=attr), self.assertRaises(FrozenInstanceError):
                setattr(bundle.lexical, attr, replacement)
                setattr(bundle.metadata, attr, replacement)
        with self.assertRaises(TypeError):
            bundle.aliases["rs485"] = ("tampered",)
        for attr in ("snapshot_id", "_payloads", "point_ids", "_client", "collection"):
            with self.subTest(dense_attr=attr), self.assertRaises(FrozenInstanceError):
                setattr(bundle.dense, attr, None)
        self.assertIs(service.capture(), bundle)
        with self.assertRaises(AttributeError):
            service._active = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        with self.assertRaises(AttributeError):
            service._lock = None
        with self.assertRaises(AttributeError):
            service.policy_provider = SaturnPolicyProvider()
        self.assertEqual(service.search_saturn("BACnet", mode="hybrid").snapshot_id,
                         bundle.snapshot.snapshot_id)
        service.publish(build_saturn_retrieval_bundle(self.snap))
        self.assertTrue(bundle.dense._lifetime.closed)

    def test_cr01_close_active_dense_is_deferred_until_retirement(self):
        old = build_saturn_retrieval_bundle(self.snap, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(old)
        old.dense.close()
        self.assertFalse(old.dense._lifetime.closed)
        self.assertTrue(service.search_saturn("BACnet", mode="dense").answer_evidence)
        service.publish(build_saturn_retrieval_bundle(self.snap))
        self.assertTrue(old.dense._lifetime.closed)

    def test_cr01_old_inflight_dense_query_finishes_after_new_publication(self):
        old = build_saturn_retrieval_bundle(self.snap, encoder=ControlledEncoder())
        new = build_saturn_retrieval_bundle(
            fixture_snapshot(commit="b"*40), encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(old)
        entered, resume = Event(), Event()
        method = type(old.dense).search
        def delayed(index, query, allowed):
            if index is old.dense:
                entered.set()
                if not resume.wait(timeout=15):
                    raise AssertionError("Timed out waiting for publication")
            return method(index, query, allowed)
        try:
            with patch.object(type(old.dense), "search", delayed), \
                 ThreadPoolExecutor(max_workers=2) as pool:
                future = pool.submit(service.search_saturn, "BACnet",
                                     mode="hybrid", top_k=10)
                self.assertTrue(entered.wait(timeout=10))
                service.publish(new)
                self.assertFalse(old.dense._lifetime.closed)
                self.assertIs(service.capture(), new)
                fresh = service.search_saturn("BACnet", mode="hybrid", top_k=10)
                self.assertEqual(fresh.snapshot_id, new.snapshot.snapshot_id)
                resume.set()
                in_flight = future.result(timeout=20)
            self.assertEqual(in_flight.snapshot_id, old.snapshot.snapshot_id)
            self.assertEqual(in_flight.bundle_id, old.manifest.bundle_id)
            self.assertTrue(all(x.snapshot_id == in_flight.snapshot_id
                                for x in in_flight.answer_evidence))
            self.assertTrue(old.dense._lifetime.closed)
            self.assertFalse(new.dense._lifetime.closed)
        finally:
            resume.set()
            service.publish(build_saturn_retrieval_bundle(self.snap))

    def test_cr01_concurrent_mutation_attempts_and_publication(self):
        old = build_saturn_retrieval_bundle(self.snap)
        revisions = [build_saturn_retrieval_bundle(fixture_snapshot(commit=x*40))
                     for x in "bcd"]
        service = SaturnRetrievalService()
        service.publish(old)
        def reader(_):
            result = service.search_saturn("BACnet", top_k=30)
            with self.assertRaises(FrozenInstanceError):
                service.capture().manifest = old.manifest
            return result
        with ThreadPoolExecutor(max_workers=7) as pool:
            futures = [pool.submit(reader, i) for i in range(35)]
            publishes = [pool.submit(service.publish, item) for item in revisions]
            results = [f.result(timeout=25) for f in futures]
            published = [f.result(timeout=25) for f in publishes]
        known = {x.manifest.bundle_id: x.snapshot.snapshot_id for x in [old, *revisions]}
        self.assertEqual(set(published), set(known) - {old.manifest.bundle_id})
        for result in results:
            self.assertEqual(result.snapshot_id, known[result.bundle_id])
            self.assertEqual(result.index_manifest.snapshot_id, result.snapshot_id)
            self.assertTrue(all(x.snapshot_id == result.snapshot_id
                                for x in result.answer_evidence))
        self.assertIn(service.capture(), revisions)

    def test_cr02_prepared_bm25_never_retokenizes_record_text_on_search(self):
        service = SaturnRetrievalService()
        bundle = build_saturn_retrieval_bundle(self.snap)
        service.publish(bundle)
        with patch("saturn_ai.retrieval.saturn_channel.tokenize", wraps=tokenize) as spy:
            for _ in range(3):
                self.assertTrue(service.search_saturn("RS-485").answer_evidence)
            self.assertEqual(spy.call_count, 6)  # 3 queries x 2 separate channels
            self.assertTrue(all(call.args == ("RS-485",) for call in spy.call_args_list))
        self.assertEqual(bundle.lexical.coverage_hash, bundle.lexical.coverage_hash)
        with patch("builtins.open", side_effect=AssertionError("No file/label reads")):
            self.assertTrue(service.search_saturn("RS-485").answer_evidence)

    def test_cr02_prepared_policy_filtered_scoring_matches_reference(self):
        sample = [
            SearchRecord(key, "site_passage", "snap", "rev", None,
                         "body:line=1-1", None, text, sha256(text.encode()).hexdigest())
            for key, text in (
                ("a", "alpha alpha beta"), ("b", "alpha beta"),
                ("c", "alpha gamma gamma"), ("d", "beta beta"),
            )
        ]
        index = SaturnBM25Index(sample)
        for allowed in (set(x.evidence_id for x in sample), {"a", "c"}, {"b"},
                        {"d"}, set()):
            for query in ("alpha", "beta gamma", "none"):
                with self.subTest(allowed=allowed, query=query):
                    reference = _bm25(query, [(r.evidence_id, r.text) for r in sample
                                              if r.evidence_id in allowed], 40)
                    self.assertEqual(index.search(query, sample, allowed), reference)
                    independent = baseline_reference_bm25(
                        query, [(r.evidence_id, r.text) for r in sample
                                if r.evidence_id in allowed])
                    self.assertEqual(len(reference), len(independent))
                    for (rid, score), (other_id, old_score) in zip(reference, independent):
                        self.assertEqual(rid, other_id)
                        self.assertAlmostEqual(score, old_score, places=12)
        self.assertEqual(index.search("none", sample, {"a", "b"}), ())
        self.assertEqual(index.search("", sample, {"a", "b"}), ())
        tied = [SearchRecord(key, "site_passage", "snap", "rev", None,
                "line", None, "equal equal", "h"*64) for key in ("z", "a")]
        tied_index = SaturnBM25Index(tied)
        self.assertEqual([cid for cid, _ in tied_index.search(
            "equal", tied, {"z", "a"})], ["a", "z"])

    def test_cr02_add_remove_evidence_rebuilds_prepared_index(self):
        small = build_saturn_knowledge_snapshot(*make_inputs({
            PRODUCT: source("Instrument", body="## Note\nOne\n")
        }))
        large = build_saturn_knowledge_snapshot(*make_inputs({
            PRODUCT: source("Instrument", fields="novel_field: 37\n",
                            body="## Note\nOne\nTwo new passages\n"),
            SECOND: source("Extra", body="New evidence")
        }))
        initial = build_saturn_retrieval_bundle(small)
        updated = build_saturn_retrieval_bundle(large)
        self.assertNotEqual(initial.manifest.bundle_id, updated.manifest.bundle_id)
        self.assertNotEqual(initial.lexical.coverage_hash, updated.lexical.coverage_hash)
        self.assertNotEqual(initial.lexical._prepared, updated.lexical._prepared)
        service = SaturnRetrievalService()
        service.publish(initial)
        old = service.search_saturn("novel_field")
        self.assertFalse(old.answer_evidence)
        service.publish(updated)
        self.assertTrue(service.search_saturn("novel_field").answer_evidence)
        service.publish(initial)
        self.assertFalse(service.search_saturn("novel_field").answer_evidence)

    def test_cr02_corrupted_prepared_counts_or_tokens_fail_publication(self):
        service = SaturnRetrievalService()
        good = build_saturn_retrieval_bundle(self.snap)
        service.publish(good)
        for component, attribute, value in (
            ("lexical", "tokens", ()),
            ("lexical", "_prepared", ()),
            ("metadata", "tokens", ()),
            ("metadata", "_prepared", ()),
        ):
            with self.subTest(component=component, attribute=attribute):
                candidate = build_saturn_retrieval_bundle(self.snap)
                object.__setattr__(getattr(candidate, component), attribute, value)
                with self.assertRaises(ValueError):
                    service.publish(candidate)
                self.assertIs(service.capture(), good)

    def test_cr03_signed_decimal_range_and_identifiers_tokens(self):
        self.assertEqual(tokenize("-20 +20 20 −20"), ("-20", "+20", "20", "-20"))
        self.assertNotEqual(tokenize("-20"), tokenize("+20"))
        self.assertNotEqual(tokenize("-20"), tokenize("20"))
        self.assertEqual(tokenize("0,5 0.5 0 5"), ("0,5", "0.5", "0", "5"))
        self.assertEqual(tokenize("-20..+20 10-20 5–7"),
                         ("-20..+20", "10-20", "5–7"))
        self.assertEqual(tokenize("RS-485 БКД-ПК-РФ.2 БКД-ПК-RF.2"),
                         ("rs-485", "бкд-пк-рф.2", "бкд-пк-rf.2"))

    def test_cr03_numeric_ranking_preserves_sign_and_decimal(self):
        values = ("-20", "+20", "20", "−20", "0,5", "0.5", "-20..+20")
        records = tuple(SearchRecord(str(i), "site_passage", "snap", "rev",
                        None, "body:line=1-1", None, "температура "+value+" °C",
                        sha256(value.encode()).hexdigest())
                        for i, value in enumerate(values))
        index = SaturnBM25Index(records)
        allowed = {r.evidence_id for r in records}
        expected = {
            "-20": {"0", "3"},
            "+20": {"1"},
            "20": {"2"},
            "0,5": {"4"},
            "0.5": {"5"},
            "-20..+20": {"6"},
        }
        for query, ids in expected.items():
            with self.subTest(query=query):
                result = index.search(query, records, allowed)
                self.assertEqual({cid for cid, _ in result}, ids)
                self.assertEqual(result, index.search(query, records, allowed))
        self.assertEqual(index.search("−20", records, allowed),
                         index.search("-20", records, allowed))

    def test_cr03_tokenizer_version_changes_lexical_identity(self):
        bundle = build_saturn_retrieval_bundle(self.snap)
        self.assertEqual(bundle.manifest.tokenizer_version, TOKENIZER_VERSION)
        with patch("saturn_ai.retrieval.saturn_channel.TOKENIZER_VERSION",
                   "saturn-technical-tokenizer/next"):
            updated = _make_manifest(bundle.snapshot, bundle.records, bundle.documents,
                                     bundle.lexical, bundle.metadata, bundle.dense)
        self.assertNotEqual(updated.lexical_config_hash,
                            bundle.manifest.lexical_config_hash)
        self.assertNotEqual(updated.bundle_id, bundle.manifest.bundle_id)
        self.assertEqual(bundle.manifest,
                         build_saturn_retrieval_bundle(self.snap).manifest)

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
