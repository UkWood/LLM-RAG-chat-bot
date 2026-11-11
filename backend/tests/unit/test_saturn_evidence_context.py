"""Stage 5A: pinned session, canonical evidence, policy and adversarial tests.

Offline controlled Saturn source/PDF fixtures only. No cloud keys or live site.
"""
from dataclasses import FrozenInstanceError, replace
from threading import Event, RLock, Thread
from unittest.mock import patch
import unittest

from saturn_ai.grounding.saturn_contracts import (
    SaturnContextError, MAX_CONTEXT_EVIDENCE, MAX_CONTEXT_TEXT_CHARS,\n    MAX_SESSION_CONTEXTS,
)
from saturn_ai.grounding.saturn_context import SaturnAnswerSession\nfrom saturn_ai.retrieval.saturn_channel import (
    SaturnOperationalPolicy, SaturnRetrievalService,
    SaturnRetrievalResult, build_saturn_retrieval_bundle,
)
from saturn_ai.saturn_knowledge_snapshot import build_saturn_knowledge_snapshot
from unit.test_saturn_channel_retrieval import fixture_snapshot, ControlledEncoder
from unit.test_saturn_knowledge_snapshot import make_inputs
from unit.test_support_catalog_adapter import PRODUCT, SECOND, doc, source


def expect_code(case, code):
    assert isinstance(case.exception, SaturnContextError), type(case.exception).__name__
    assert case.exception.reason_code == code, case.exception.reason_code


class SaturnEvidenceContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = fixture_snapshot()

    def setUp(self):
        self.bundle = build_saturn_retrieval_bundle(self.snapshot)
        self.service = SaturnRetrievalService()
        self.service.publish(self.bundle)

    def test_field_raw_text_and_exact_canonical_pointer(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("RS-485", top_k=5)
            self.assertEqual(context.snapshot_id, self.snapshot.snapshot_id)
            self.assertEqual(context.bundle_id, self.bundle.manifest.bundle_id)
            self.assertTrue(context.answer_evidence)
            fields = [e for e in context.answer_evidence if e.evidence_type == "site_field"]
            self.assertTrue(fields)
            field = fields[0]
            fact = next(f for f in self.snapshot.facts if f.fact_id == field.fact_id)
            unit = next(e for e in self.snapshot.answer_evidence
                        if e.evidence_id == field.evidence_id)
            self.assertEqual(field.source_text, unit.text)
            self.assertEqual(field.raw_value_json, fact.raw_value_json)
            self.assertEqual(field.field_path, fact.field_path)
            self.assertEqual(field.source_revision_id, fact.source_revision_id)
            self.assertEqual(field.canonical_kind, "SiteFact")
            self.assertEqual(field.canonical_id, fact.fact_id)
            self.assertEqual(context.question_sha256,
                             __import__("hashlib").sha256(b"RS-485").hexdigest())
            self.assertEqual(session.recheck_policy(context), "initial")
            with self.assertRaises(FrozenInstanceError):
                context.answer_evidence = ()
            with self.assertRaises(FrozenInstanceError):
                field.source_text = "fabricated"

    def test_literal_signed_decimals_attached_units_and_explicit_source_unit(self):
        snapshot = build_saturn_knowledge_snapshot(*make_inputs({
            PRODUCT: source("Instrument", fields=(
                'temperature_c: "-0,5"\n'
                'mass_kg: "12.5V"\n'
                'pressure: "0,5МПа"\n'
            )),
        }))
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(snapshot))
        for name, value, unit in (
            ("temperature_c", '"-0,5"', "°C"),
            ("mass_kg", '"12.5V"', "kg"),
            ("pressure", '"0,5МПа"', None),
        ):
            with self.subTest(name=name), service.open_answer_session() as session:
                matches = session.build_context(name, top_k=10)
                selected = next(e for e in matches.answer_evidence
                                if e.field_path == name)
                fact = next(f for f in snapshot.facts if f.fact_id == selected.fact_id)
                self.assertEqual(selected.raw_value_json, value)
                self.assertEqual(selected.raw_value_json, fact.raw_value_json)
                self.assertEqual(selected.normalized_value_json, fact.normalized_value_json)
                self.assertEqual(selected.qualifiers_json, fact.qualifiers_json)
                self.assertEqual(selected.unit, unit)
                self.assertIn(value, selected.source_text)

    def test_relation_preserves_exact_direction_predicate_and_provenance(self):
        relation = self.snapshot.relations[0]
        with self.service.open_answer_session() as session:
            context = session.build_context(relation.predicate, top_k=10)
            found = next(e for e in context.answer_evidence
                         if e.relation_id == relation.relation_id)
            self.assertEqual((found.subject_entity_id, found.predicate, found.object_entity_id),
                             (relation.subject_entity_id, relation.predicate,
                              relation.object_entity_id))
            self.assertEqual(found.source_field_path, relation.source_field_path)
            self.assertEqual(found.canonical_kind, "SiteRelation")
            self.assertEqual(found.entity_id, relation.subject_entity_id)

    def test_site_passage_source_exact_body_locator(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("Обмен", top_k=10)
            found = next(e for e in context.answer_evidence
                         if e.evidence_type == "site_passage")
            self.assertIn("body:line=", found.locator)
            self.assertIn(":heading=", found.locator)
            unit = next(e for e in self.snapshot.answer_evidence
                        if e.evidence_id == found.evidence_id)
            self.assertEqual(found.source_text, unit.text)
            self.assertEqual(found.canonical_kind, "SiteEntity")

    def test_pdf_exact_physical_page_hash_parser_url_and_multiple_owners(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("Alpha", top_k=10)
            found = next(e for e in context.answer_evidence
                         if e.evidence_type == "pdf_passage")
            revision = next(p for p in self.snapshot.pdf_revisions
                            if p.document_id == found.pdf_document_id)
            self.assertEqual(found.original_url, revision.url)
            self.assertEqual(found.canonical_url, revision.url)
            self.assertEqual(found.pdf_revision_id, found.source_revision_id)
            self.assertEqual(found.bytes_sha256, revision.bytes_sha256)
            self.assertEqual(found.parser_version, revision.parser_version)
            self.assertEqual(found.physical_page, 1)
            self.assertEqual(len(found.pdf_owner_entity_ids), 2)
            self.assertTrue(found.pdf_source_locators)
            self.assertEqual(found.source_text, "Alpha")

    def test_document_lookup_is_separate_and_metadata_only(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("guide")
            self.assertFalse(context.answer_evidence)
            self.assertTrue(context.document_references)
            ref = context.document_references[0]
            self.assertEqual(ref.title, "A guide")
            self.assertEqual(len(ref.owner_entity_ids), 2)
            self.assertEqual(ref.extraction_status, "extracted")
            self.assertEqual(len(ref.occurrences), 2)
            self.assertTrue(ref.original_url.endswith(".pdf"))
            self.assertEqual(context.diagnostics[0][1], 0)

    def test_empty_context_and_deterministic_replay(self):
        with self.service.open_answer_session() as session:
            a = session.build_context("xyz-absent-123456")
            b = session.build_context("xyz-absent-123456")
            self.assertEqual(a, b)
            self.assertFalse(a.answer_evidence)
            self.assertFalse(a.document_references)
            self.assertEqual(session.recheck_policy(a), "initial")

    def test_policy_revision_change_without_block_is_allowed(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("RS-485")
            self.service.policy_provider.activate(SaturnOperationalPolicy("second"))
            self.assertEqual(session.recheck_policy(context), "second")

    def test_policy_recheck_all_block_types(self):
        cases = [
            ("evidence", "RS-485", lambda c: dict(blocked_evidence_ids=frozenset(
                {c.answer_evidence[0].evidence_id}))),
            ("source", "RS-485", lambda c: dict(blocked_source_revision_ids=frozenset(
                {c.answer_evidence[0].source_revision_id}))),
            ("entity", "RS-485", lambda c: dict(blocked_entity_ids=frozenset(
                {c.answer_evidence[0].entity_id}))),
            ("document", "guide", lambda c: dict(blocked_document_ids=frozenset(
                {c.document_references[0].document_id}))),
            ("pdf_revision", "Alpha", lambda c: dict(blocked_pdf_revision_ids=frozenset(
                {next(e.pdf_revision_id for e in c.answer_evidence
                       if e.pdf_revision_id)}))),
        ]
        for label, query, block in cases:
            with self.subTest(label=label):
                service = SaturnRetrievalService()
                service.publish(self.bundle)
                with service.open_answer_session() as session:
                    context = session.build_context(query, top_k=10)
                    service.policy_provider.activate(SaturnOperationalPolicy(label, **block(context)))
                    with self.assertRaises(SaturnContextError) as ex:
                        session.recheck_policy(context)
                    expect_code(ex, "policy_blocked")

    def test_policy_activated_during_materialization_denies_context(self):
        original = SaturnRetrievalService._search_captured
        service = self.service
        def activate_after_search(instance, bundle, question, mode, top_k):
            result = original(instance, bundle, question, mode, top_k)
            if result.answer_evidence:
                eid = result.answer_evidence[0].evidence_id
                service.policy_provider.activate(SaturnOperationalPolicy(
                    "blocked-during-build", blocked_evidence_ids=frozenset({eid})))
            return result
        with patch.object(SaturnRetrievalService, "_search_captured", activate_after_search):
            with self.service.open_answer_session() as session:
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context("RS-485")
                expect_code(ex, "policy_blocked")

    def test_policy_provider_unavailable_or_invalid_fails_closed(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("RS-485")
            object.__setattr__(self.service.policy_provider, "_active", None)
            for action in (lambda: session.recheck_policy(context),
                           lambda: session.build_context("RS-485")):
                with self.assertRaises(SaturnContextError) as ex:
                    action()
                expect_code(ex, "policy_unavailable")

    def _tampered_retrieval(self, question, edit):
        original = SaturnRetrievalService._search_captured
        def altered(service, bundle, query, mode, top_k):
            return edit(original(service, bundle, query, mode, top_k))
        with patch.object(SaturnRetrievalService, "_search_captured", altered):
            with self.service.open_answer_session() as session:
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context(question, top_k=10)
                return ex.exception.reason_code

    def test_unknown_foreign_evidence_and_provenance_tampering(self):
        for field, value in (
            ("evidence_id", "not-a-real-evidence"),
            ("snapshot_id", "other-snapshot"),
            ("entity_id", "wrong-entity"),
            ("source_revision_id", "wrong-source"),
            ("locator", "body:line=999-999"),
            ("canonical_url", "https://example.invalid/forged"),
        ):
            def edit(result, field=field, value=value):
                c = replace(result.answer_evidence[0], **{field: value})
                return replace(result, answer_evidence=(c, *result.answer_evidence[1:]))
            with self.subTest(field=field):
                self.assertEqual(self._tampered_retrieval("RS-485", edit),
                                 "evidence_integrity_failure")

    def test_snapshot_bundle_and_index_manifest_mismatch(self):
        for field, value in (
            ("snapshot_id", "other-snapshot"),
            ("bundle_id", "other-bundle"),
            ("index_manifest", replace(self.bundle.manifest,
                                       bundle_id="forged-manifest")),
        ):
            self.assertEqual(
                self._tampered_retrieval("RS-485",
                    lambda result, field=field, value=value:
                        replace(result, **{field: value})),
                "context_identity_mismatch")

    def test_malformed_retrieval_candidate_fails_with_safe_integrity_code(self):
        self.assertEqual(
            self._tampered_retrieval("RS-485",
                lambda result: replace(result, answer_evidence=("malformed",))),
            "evidence_integrity_failure")

    def test_metadata_cannot_be_promoted_to_answer_evidence(self):
        def edit(result):
            doc_id = result.document_matches[0].match.document.document_id
            from saturn_ai.retrieval.saturn_channel import SaturnCandidate
            counterfeit = SaturnCandidate(
                doc_id, "document_metadata", None, "fake", "fake", None,
                result.snapshot_id, 1.0, 1, "lexical")
            return replace(result, answer_evidence=(counterfeit,))
        self.assertEqual(self._tampered_retrieval("guide", edit),
                         "evidence_integrity_failure")

    def test_document_metadata_forgery_rejected(self):
        self.assertEqual(self._tampered_retrieval("guide",
            lambda result: replace(result, document_matches=(
                replace(result.document_matches[0],
                        snapshot_id="wrong-snapshot"),))),
            "evidence_integrity_failure")

    def test_context_is_scoped_to_issuing_session_even_for_same_bundle(self):
        with self.service.open_answer_session() as first, self.service.open_answer_session() as second:
            context = first.build_context("RS-485")
            with self.assertRaises(SaturnContextError) as ex:
                second.recheck_policy(context)
            expect_code(ex, "context_identity_mismatch")

    def test_issued_context_reflective_payload_corruption_is_rejected(self):
        with self.service.open_answer_session() as session:
            context = session.build_context("RS-485")
            self.assertTrue(context.answer_evidence)
            object.__setattr__(context, "answer_evidence", ())
            with self.assertRaises(SaturnContextError) as ex:
                session.recheck_policy(context)
            expect_code(ex, "context_identity_mismatch")

    def test_invalid_query_modes_and_missing_active_bundle(self):
        empty = SaturnRetrievalService()
        with self.assertRaises(SaturnContextError) as ex:
            empty.open_answer_session()
        expect_code(ex, "no_active_bundle")
        with self.service.open_answer_session() as session:
            for query, mode, k in (("", "lexical", 5), ("x", "other", 5),
                                   ("x", "lexical", 0)):
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context(query, mode=mode, top_k=k)
                expect_code(ex, "invalid_request")
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("x", top_k=MAX_CONTEXT_EVIDENCE + 1)
            expect_code(ex, "resource_budget_exceeded")
            for mode in ("dense", "hybrid"):
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context("RS-485", mode=mode)
                expect_code(ex, "retrieval_unavailable")

    def test_source_text_budget_never_silently_truncates(self):
        long_body = "".join("budgettoken " + "X"*2250 + "\n" for _ in range(12))
        snapshot = build_saturn_knowledge_snapshot(*make_inputs({
            PRODUCT: source("Budget test", body=long_body),
        }))
        service = SaturnRetrievalService()
        service.publish(build_saturn_retrieval_bundle(snapshot))
        with service.open_answer_session() as session:
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("budgettoken", top_k=10)
            expect_code(ex, "resource_budget_exceeded")

    def test_closed_session_and_idempotent_release(self):
        session = self.service.open_answer_session()
        ctx = session.build_context("RS-485")
        session.close()
        session.close()
        for fn in (lambda: session.build_context("RS-485"),
                   lambda: session.recheck_policy(ctx),
                   lambda: session.__enter__()):
            with self.assertRaises(SaturnContextError) as ex:
                fn()
            expect_code(ex, "session_closed")

    def test_pinned_snapshot_survives_concurrent_publication(self):
        newer = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        with self.service.open_answer_session() as session:
            before = session.build_context("RS-485")
            self.service.publish(newer)
            after = session.build_context("RS-485")
            self.assertEqual(before.snapshot_id, after.snapshot_id)
            self.assertEqual(before.bundle_id, after.bundle_id)
            self.assertEqual(before.answer_evidence, after.answer_evidence)
            self.assertNotEqual(self.service.search_saturn("RS-485").snapshot_id,
                                before.snapshot_id)

    def test_qdrant_reader_lease_survives_retirement_and_closes_after_release(self):
        old = build_saturn_retrieval_bundle(self.snapshot, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(old)
        newer = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        with service.open_answer_session() as session:
            service.publish(newer)
            self.assertFalse(old.dense._lifetime.closed)
            result = session.build_context("RS-485", mode="dense")
            self.assertEqual(result.snapshot_id, old.snapshot.snapshot_id)
        self.assertTrue(old.dense._lifetime.closed)

    def test_qdrant_release_on_exception_and_no_unbalanced_close(self):
        old = build_saturn_retrieval_bundle(self.snapshot, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(old)
        newer = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        session = None
        with self.assertRaisesRegex(ValueError, "injected"):
            with service.open_answer_session() as session:
                service.publish(newer)
                raise ValueError("injected")
        session.close()
        self.assertTrue(old.dense._lifetime.closed)

    def test_canonical_field_or_relation_mutation_rejected(self):
        # Adversarial reflective corruption AFTER publication. Normal frozen
        # assignment is already forbidden; runtime still verifies projections.
        for kind in ("field_path", "field_revision", "relation_predicate",
                     "relation_object"):
            with self.subTest(kind=kind):
                snapshot = fixture_snapshot()
                bundle = build_saturn_retrieval_bundle(snapshot)
                service = SaturnRetrievalService()
                service.publish(bundle)
                if kind.startswith("field"):
                    fact = next(f for f in snapshot.facts if f.field_path == "interface")
                    altered = replace(fact, **(
                        {"field_path": "invented_compatibility"}
                        if kind == "field_path" else
                        {"source_revision_id": "forged-revision"}
                    ))
                    object.__setattr__(snapshot, "facts", tuple(
                        altered if f.fact_id == fact.fact_id else f
                        for f in snapshot.facts))
                    query = "RS-485"
                else:
                    rel = snapshot.relations[0]
                    altered = replace(rel, **(
                        {"predicate": "compatible_with"}
                        if kind == "relation_predicate" else
                        {"object_entity_id": "saturn:fake-target"}
                    ))
                    object.__setattr__(snapshot, "relations", tuple(
                        altered if r.relation_id == rel.relation_id else r
                        for r in snapshot.relations))
                    query = rel.predicate
                with service.open_answer_session() as session:
                    with self.assertRaises(SaturnContextError) as ex:
                        session.build_context(query, top_k=10)
                    expect_code(ex, "evidence_integrity_failure")

    def test_pdf_hash_revision_parser_page_owner_corruption_rejected(self):
        # Canonical source objects remain frozen. A forced SearchRecord drift
        # cannot become an engineering PDF fact without exact PDF match.
        for field, forged in (
            ("pdf_bytes_sha256", "a"*64),
            ("pdf_parser_version", "untrusted-parser"),
            ("physical_page", 999),
            ("pdf_document_id", "forged-document"),
            ("pdf_owner_entity_ids", ("forged-owner",)),
            ("source_revision_id", "forged-pdf-revision"),
        ):
            with self.subTest(field=field):
                bundle = build_saturn_retrieval_bundle(self.snapshot)
                service = SaturnRetrievalService()
                service.publish(bundle)
                target = next(r for r in bundle.records
                              if r.evidence_type == "pdf_passage"
                              and r.physical_page == 1)
                forged_record = replace(target, **{field: forged})
                object.__setattr__(bundle, "records", tuple(
                    forged_record if r.evidence_id == target.evidence_id else r
                    for r in bundle.records))
                with service.open_answer_session() as session:
                    with self.assertRaises(SaturnContextError) as ex:
                        session.build_context("Alpha", top_k=10)
                    expect_code(ex, "evidence_integrity_failure")

    def test_pdf_link_source_and_owner_revocation(self):
        with self.service.open_answer_session() as session:
            pdf_ctx = session.build_context("Alpha", top_k=10)
            pdf_item = next(e for e in pdf_ctx.answer_evidence if e.pdf_document_id)
            link_revision = pdf_item.pdf_link_source_revision_ids[0]
            self.service.policy_provider.activate(SaturnOperationalPolicy(
                "link-revoked", blocked_source_revision_ids=frozenset({link_revision})))
            with self.assertRaises(SaturnContextError) as ex:
                session.recheck_policy(pdf_ctx)
            expect_code(ex, "policy_blocked")

    def test_broken_policy_provider_raises_policy_unavailable(self):
        class BrokenPolicy:
            def capture(self):
                raise ValueError("confidential provider diagnostic")
        service = SaturnRetrievalService(policy_provider=BrokenPolicy())
        service.publish(self.bundle)
        with service.open_answer_session() as session:
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("RS-485")
            expect_code(ex, "policy_unavailable")
            self.assertNotIn("confidential", str(ex.exception))

    def test_existing_stage4b_search_stays_unchanged(self):
        with self.service.open_answer_session() as session:
            original = self.service.search_saturn("RS-485")
            context = session.build_context("RS-485")
            self.assertEqual([e.evidence_id for e in context.answer_evidence],
                             [e.evidence_id for e in original.answer_evidence])
            self.assertEqual(original, self.service.search_saturn("RS-485"))


class Stage5AAcceptanceCorrectionTests(unittest.TestCase):
    """One consolidated CR-01 / CR-02 contract and adversarial regression set."""

    @classmethod
    def setUpClass(cls):
        cls.snapshot = fixture_snapshot()

    def setUp(self):
        self.old = build_saturn_retrieval_bundle(self.snapshot)
        self.service = SaturnRetrievalService()
        self.service.publish(self.old)

    def test_t01_immutable_pinned_bindings_preserve_original_bundle(self):
        alternate = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        other_service = SaturnRetrievalService()
        other_service.publish(alternate)
        with self.service.open_answer_session() as session:
            old = session.build_context("RS-485")
            for name, replacement in (
                ("_bundle", alternate),
                ("_service", other_service),
                ("_lock", RLock()),
                ("_issued", ()),
                ("_closed", True),
            ):
                with self.subTest(attribute=name):
                    with self.assertRaises(AttributeError):
                        setattr(session, name, replacement)
                    self.assertIs(session._bundle, self.old)
                    self.assertIs(session._service, self.service)
                    self.assertEqual(session.build_context("RS-485").answer_evidence,
                                     old.answer_evidence)
            self.service.publish(alternate)
            self.assertEqual(session.build_context("RS-485").snapshot_id,
                             self.old.snapshot.snapshot_id)
            self.assertNotEqual(self.service.search_saturn("RS-485").snapshot_id,
                                old.snapshot_id)

    def test_t02_direct_constructor_rejected_without_reader_release(self):
        dense_bundle = build_saturn_retrieval_bundle(
            self.snapshot, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(dense_bundle)
        refs_before = dense_bundle.dense._lifetime._refs
        with self.assertRaises(TypeError):
            SaturnAnswerSession(service, dense_bundle)
        self.assertEqual(dense_bundle.dense._lifetime._refs, refs_before)
        with service.open_answer_session() as session:
            self.assertEqual(dense_bundle.dense._lifetime._refs, refs_before + 1)
            self.assertIs(session._bundle, dense_bundle)
        self.assertEqual(dense_bundle.dense._lifetime._refs, refs_before)
        service.publish(self.old)
        self.assertTrue(dense_bundle.dense._lifetime.closed)

    def test_t03_issued_registry_cannot_be_mutated_or_bypass_bound(self):
        with self.service.open_answer_session() as session:
            first = session.build_context("RS-485")
            self.assertEqual(len(session._issued), 1)
            self.assertIsInstance(session._issued, tuple)
            for operation in (
                lambda: session._issued.append((first, "fake")),
                lambda: session._issued.clear(),
                lambda: setattr(session, "_issued", ()),
                lambda: setattr(session, "_issued", ((first, "fake"),)),
                lambda: setattr(session, "_issued", session._issued[:-1]),
                lambda: session._issued.__setitem__(0, (first, "fake")),
            ):
                with self.assertRaises((AttributeError, TypeError)):
                    operation()
            self.assertEqual(session.recheck_policy(first), "initial")
            self.assertEqual(len(session._issued), 1)
            for _ in range(MAX_SESSION_CONTEXTS - 1):
                session.build_context("xyz-no-result-1234")
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("xyz-no-result-1234")
            expect_code(ex, "resource_budget_exceeded")
            self.assertEqual(len(session._issued), MAX_SESSION_CONTEXTS)
        self.assertEqual(session._issued, ())

    def test_t04_true_threaded_publication_gives_whole_bundle_only(self):
        later = build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40))
        entered = Event()
        finished = Event()
        results = []
        errors = []

        def open_in_thread():
            entered.set()
            try:
                with self.service.open_answer_session() as session:
                    a = session.build_context("RS-485")
                    b = session.build_context("RS-485")
                    results.append((session._bundle, a.snapshot_id, b.snapshot_id))
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                finished.set()

        # The worker cannot capture a half-swapped pointer while the
        # publisher owns exactly the same publication lock.
        with self.service._lock:
            worker = Thread(target=open_in_thread)
            worker.start()
            self.assertTrue(entered.wait(5))
            self.service.publish(later)
        self.assertTrue(finished.wait(15))
        worker.join(15)
        self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        self.assertEqual(len(results), 1)
        bundle, first_id, second_id = results[0]
        self.assertIs(bundle, later)
        self.assertEqual((first_id, second_id),
                         (later.snapshot.snapshot_id, later.snapshot.snapshot_id))

    def test_t05_deferred_dense_close_until_last_session_release(self):
        dense = build_saturn_retrieval_bundle(
            self.snapshot, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(dense)
        a = service.open_answer_session()
        b = service.open_answer_session()
        service.publish(build_saturn_retrieval_bundle(fixture_snapshot(commit="b"*40)))
        self.assertFalse(dense.dense._lifetime.closed)
        a.close()
        self.assertFalse(dense.dense._lifetime.closed)
        self.assertEqual(b.build_context("RS-485", mode="dense").snapshot_id,
                         self.snapshot.snapshot_id)
        b.close()
        self.assertTrue(dense.dense._lifetime.closed)

    def test_t06_idempotent_close_releases_exactly_once(self):
        dense = build_saturn_retrieval_bundle(
            self.snapshot, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(dense)
        session = service.open_answer_session()
        self.assertEqual(dense.dense._lifetime._refs, 2)
        session.close()
        self.assertEqual(dense.dense._lifetime._refs, 1)
        session.close()
        self.assertEqual(dense.dense._lifetime._refs, 1)
        service.publish(self.old)
        self.assertTrue(dense.dense._lifetime.closed)

    def test_t07_with_exception_releases_once(self):
        dense = build_saturn_retrieval_bundle(
            self.snapshot, encoder=ControlledEncoder())
        service = SaturnRetrievalService()
        service.publish(dense)
        session = None
        with self.assertRaisesRegex(OSError, "test exception"):
            with service.open_answer_session() as session:
                self.assertEqual(dense.dense._lifetime._refs, 2)
                raise OSError("test exception")
        self.assertEqual(dense.dense._lifetime._refs, 1)
        session.close()
        self.assertEqual(dense.dense._lifetime._refs, 1)
        service.publish(self.old)
        self.assertTrue(dense.dense._lifetime.closed)

    def test_t08_invalid_unicode_surrogate_is_invalid_request(self):
        with self.service.open_answer_session() as session:
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("\ud800")
            expect_code(ex, "invalid_request")
            self.assertNotIn("surrogate", str(ex.exception))

    def test_t09_valid_russian_unicode_minus_and_decimal_query(self):
        query = "Обмен −0,5 МПа и RS-485"
        with self.service.open_answer_session() as session:
            context = session.build_context(query)
            self.assertEqual(context.question, query)
            self.assertEqual(context.question_sha256,
                             __import__("hashlib").sha256(query.encode("utf-8")).hexdigest())
            self.assertEqual(session.recheck_policy(context), "initial")

    def test_t10_corrupt_nested_context_fingerprint_fails_closed(self):
        with self.service.open_answer_session() as session:
            ctx = session.build_context("RS-485")
            object.__setattr__(ctx, "answer_evidence", (object(),))
            with self.assertRaises(SaturnContextError) as ex:
                session.recheck_policy(ctx)
            expect_code(ex, "context_identity_mismatch")
            ctx2 = session.build_context("RS-485")
            object.__setattr__(ctx2, "question", "\ud800")
            with self.assertRaises(SaturnContextError) as ex:
                session.recheck_policy(ctx2)
            expect_code(ex, "context_identity_mismatch")

    def test_t11_unexpected_retrieval_oserror_is_sanitized(self):
        with patch.object(SaturnRetrievalService, "_search_captured",
                          side_effect=OSError("/private/backend/path?token=secret")):
            with self.service.open_answer_session() as session:
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context("RS-485")
                expect_code(ex, "retrieval_unavailable")
                self.assertNotIn("/private/", str(ex.exception))
                self.assertNotIn("secret", str(ex.exception))

    def test_t12_policy_failure_before_and_inside_search_is_typed(self):
        class BrokenPolicy:
            def capture(self):
                raise OSError("internal policy credentials")
        service = SaturnRetrievalService(policy_provider=BrokenPolicy())
        service.publish(self.old)
        with service.open_answer_session() as session:
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("RS-485")
            expect_code(ex, "policy_unavailable")
            self.assertNotIn("credentials", str(ex.exception))

        class FailsDuringRetrievalPolicy:
            def __init__(self):
                self.calls = 0
            def capture(self):
                self.calls += 1
                if self.calls == 3:  # Stage5A pre, 4B before, 4B after
                    raise OSError("sensitive provider details")
                return SaturnOperationalPolicy("initial")
        provider = FailsDuringRetrievalPolicy()
        service = SaturnRetrievalService(policy_provider=provider)
        service.publish(self.old)
        with service.open_answer_session() as session:
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("RS-485")
            expect_code(ex, "policy_unavailable")
            self.assertNotIn("sensitive", str(ex.exception))
            self.assertEqual(provider.calls, 3)

    def test_t13_backend_runtimeerror_containing_policy_is_not_policy_error(self):
        with patch.object(SaturnRetrievalService, "_search_captured",
                          side_effect=RuntimeError("policy unrelated backend crash")):
            with self.service.open_answer_session() as session:
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context("RS-485")
                expect_code(ex, "retrieval_unavailable")

    def test_t14_legitimate_empty_result_is_not_infrastructure_error(self):
        with self.service.open_answer_session() as session:
            ctx = session.build_context("zzz-no-such-source-987654")
            self.assertEqual(ctx.answer_evidence, ())
            self.assertEqual(ctx.document_references, ())
            self.assertEqual(session.recheck_policy(ctx), "initial")

    def test_t15_existing_reason_codes_preserved(self):
        with self.service.open_answer_session() as session:
            ctx = session.build_context("RS-485")
            with self.assertRaises(SaturnContextError) as ex:
                session.build_context("RS-485", top_k=MAX_CONTEXT_EVIDENCE + 1)
            expect_code(ex, "resource_budget_exceeded")

            self.service.policy_provider.activate(SaturnOperationalPolicy(
                "block", blocked_evidence_ids=frozenset({
                    ctx.answer_evidence[0].evidence_id})))
            with self.assertRaises(SaturnContextError) as ex:
                session.recheck_policy(ctx)
            expect_code(ex, "policy_blocked")
            self.service.policy_provider.activate(SaturnOperationalPolicy("unblock"))
            self.assertEqual(session.recheck_policy(ctx), "unblock")
        with self.assertRaises(SaturnContextError) as ex:
            session.build_context("RS-485")
        expect_code(ex, "session_closed")

        from saturn_ai.retrieval.saturn_channel import SaturnCandidate
        original = SaturnRetrievalService._search_captured
        def forged(service, bundle, query, mode, top_k):
            answer = original(service, bundle, query, mode, top_k)
            counterfeit = replace(answer.answer_evidence[0],
                                  evidence_id="forged-id")
            return replace(answer, answer_evidence=(counterfeit,))
        with patch.object(SaturnRetrievalService, "_search_captured", forged):
            with self.service.open_answer_session() as session:
                with self.assertRaises(SaturnContextError) as ex:
                    session.build_context("RS-485")
                expect_code(ex, "evidence_integrity_failure")


if __name__ == "__main__":
    unittest.main()
