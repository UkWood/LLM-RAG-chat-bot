"""Stage 5A: pinned bundle sessions and canonical Saturn evidence materialization.

No planning, semantic sufficiency, generation, citations or source approval.
All lookups use the exact published immutable snapshot and index bindings.
"""
from dataclasses import replace
from hashlib import sha256
from threading import RLock

from ..ingestion.saturn_contracts import stable_id
from ..saturn_knowledge_snapshot import (
    _field_projection, _relation_projection, site_passages,
)
from ..retrieval.saturn_channel import (
    SaturnOperationalPolicy, SaturnRetrievalResult, _allowed_doc,
    _allowed_record, _candidate, _valid_query,
)
from .saturn_contracts import (
    MAX_CONTEXT_DOCUMENTS, MAX_CONTEXT_EVIDENCE, MAX_CONTEXT_TEXT_CHARS,
    MAX_SESSION_CONTEXTS, SaturnContextError, SaturnDocumentReference,
    SaturnEvidenceContext, SaturnTypedEvidence,
)


def _reject(code):
    raise SaturnContextError(code)


def _safe_policy(provider):
    try:
        policy = provider.capture()
        if not isinstance(policy, SaturnOperationalPolicy):
            _reject("policy_unavailable")
        # Also reject a policy mutated by nonstandard reflective assignment.
        policy.__post_init__()
        return policy
    except SaturnContextError:
        raise
    except Exception:
        _reject("policy_unavailable")


class SaturnAnswerSession:
    """A single pinned retrieval bundle and, if present, its Qdrant lease.

    Created by SaturnRetrievalService.open_answer_session under the publication
    lock. Session lock serializes operations and release: close cannot retire an
    index while an in-session retrieval still uses it.
    """
    __slots__ = ("_service", "_bundle", "_lock", "_closed", "_issued")

    def __init__(self, service, bundle):
        self._service = service
        self._bundle = bundle
        self._lock = RLock()
        self._closed = False
        self._issued = []

    def __enter__(self):
        with self._lock:
            self._assert_open()
            return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def _assert_open(self):
        if self._closed:
            _reject("session_closed")

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._issued.clear()
            dense = self._bundle.dense
            if dense is not None:
                dense._release()

    def _validate_result(self, result, question, mode):
        bundle = self._bundle
        if (not isinstance(result, SaturnRetrievalResult) or
                result.snapshot_id != bundle.snapshot.snapshot_id or
                result.bundle_id != bundle.manifest.bundle_id or
                result.index_manifest != bundle.manifest or
                result.query != question or result.mode != mode or
                result.status != "ok"):
            _reject("context_identity_mismatch")
        if (type(result.answer_evidence) is not tuple or
                type(result.document_matches) is not tuple):
            _reject("evidence_integrity_failure")
        if (len(result.answer_evidence) > MAX_CONTEXT_EVIDENCE or
                len(result.document_matches) > MAX_CONTEXT_DOCUMENTS):
            _reject("resource_budget_exceeded")

    def _typed_evidence(self, candidates):
        snapshot = self._bundle.snapshot
        records = {r.evidence_id: r for r in self._bundle.records}
        units = {e.evidence_id: e for e in snapshot.answer_evidence}
        pointers = {p.evidence_id: p for p in snapshot.evidence_pointers}
        entities = {e.entity_id: e for e in snapshot.entities}
        facts = {f.fact_id: f for f in snapshot.facts}
        relations = {r.relation_id: r for r in snapshot.relations}
        source_revisions = {r.revision_id for r in snapshot.source_revisions}
        pdfs = {
            stable_id("saturn-pdf-revision-v1", p.document_id, p.url,
                      p.bytes_sha256, p.parser_version): p
            for p in snapshot.pdf_revisions
        }
        documents = {m.document.document_id: m for m in snapshot.document_matches}
        passages_by_owner = {}
        result = []
        seen = set()

        for rank, candidate in enumerate(candidates, 1):
            eid = getattr(candidate, "evidence_id", None)
            if eid in seen or eid not in records or eid not in units or eid not in pointers:
                _reject("evidence_integrity_failure")
            seen.add(eid)
            record = records[eid]
            unit = units[eid]
            ptr = pointers[eid]
            if (candidate.rank != rank or candidate.channel not in ("lexical", "dense", "rrf") or
                    candidate != _candidate(record, candidate.score, rank, candidate.channel) or
                    unit.evidence_id != record.evidence_id or
                    unit.evidence_type != record.evidence_type or
                    unit.source_revision_id != record.source_revision_id or
                    unit.entity_id != record.entity_id or
                    unit.locator != record.locator or
                    ptr.evidence_id != eid or ptr.canonical_url != record.url or
                    unit.evidence_type not in ("site_field", "relation", "site_passage", "pdf_passage")):
                _reject("evidence_integrity_failure")

            details = {}
            if unit.evidence_type == "site_field":
                fact = facts.get(ptr.canonical_id)
                entity = entities.get(unit.entity_id)
                if (ptr.canonical_kind != "SiteFact" or fact is None or entity is None or
                        fact.entity_id != entity.entity_id or
                        fact.source_revision_id != entity.source_revision_id or
                        fact.source_revision_id != unit.source_revision_id or
                        fact.source_revision_id not in source_revisions):
                    _reject("evidence_integrity_failure")
                projection = _field_projection(fact, entity)
                if projection is None or projection != (unit, ptr):
                    _reject("evidence_integrity_failure")
                details = dict(
                    fact_id=fact.fact_id, field_path=fact.field_path,
                    raw_value_json=fact.raw_value_json,
                    normalized_value_json=fact.normalized_value_json,
                    unit=fact.unit, qualifiers_json=fact.qualifiers_json,
                )
            elif unit.evidence_type == "relation":
                rel = relations.get(ptr.canonical_id)
                entity = entities.get(unit.entity_id)
                if (ptr.canonical_kind != "SiteRelation" or rel is None or entity is None or
                        rel.subject_entity_id != entity.entity_id or
                        rel.object_entity_id not in entities or
                        rel.source_revision_id != entity.source_revision_id or
                        rel.source_revision_id != unit.source_revision_id or
                        rel.source_revision_id not in source_revisions or
                        _relation_projection(rel, entity) != (unit, ptr)):
                    _reject("evidence_integrity_failure")
                details = dict(
                    relation_id=rel.relation_id,
                    subject_entity_id=rel.subject_entity_id,
                    predicate=rel.predicate, object_entity_id=rel.object_entity_id,
                    source_field_path=rel.source_field_path,
                )
            elif unit.evidence_type == "site_passage":
                entity = entities.get(unit.entity_id)
                if (ptr.canonical_kind != "SiteEntity" or entity is None or
                        ptr.canonical_id != entity.entity_id or
                        unit.source_revision_id != entity.source_revision_id or
                        unit.source_revision_id not in source_revisions or
                        ptr.canonical_url != entity.canonical_url):
                    _reject("evidence_integrity_failure")
                if entity.entity_id not in passages_by_owner:
                    passages_by_owner[entity.entity_id] = {
                        x.evidence_id: x for x in site_passages(entity)
                    }
                if passages_by_owner[entity.entity_id].get(eid) != unit:
                    _reject("evidence_integrity_failure")
            else:
                pdf = pdfs.get(unit.source_revision_id)
                if (ptr.canonical_kind != "PdfRevision" or
                        ptr.canonical_id != unit.source_revision_id or
                        pdf is None or pdf.extraction_state != "extracted" or
                        type(unit.page_number) is not int or
                        not 1 <= unit.page_number <= pdf.page_count or
                        unit.entity_id is not None or
                        unit.locator != pdf.url + "#page=" + str(unit.page_number) or
                        ptr.canonical_url != pdf.url or
                        unit.evidence_id != stable_id(
                            "saturn-pdf-passage-v1", unit.source_revision_id,
                            unit.page_number, sha256(unit.text.encode("utf-8")).hexdigest()
                        )):
                    _reject("evidence_integrity_failure")
                match = documents.get(pdf.document_id)
                if (match is None or match.document.url != pdf.url or
                        match.pdf_revision_id != unit.source_revision_id or
                        match.extraction_status != "extracted" or
                        not match.occurrences or
                        tuple(sorted({x.owner_entity_id for x in match.occurrences}))
                        != match.document.owner_entity_ids or
                        tuple(sorted({x.source_locator for x in match.occurrences}))
                        != match.document.source_locators):
                    _reject("evidence_integrity_failure")
                link_revisions = tuple(sorted({x.source_revision_id for x in match.occurrences}))
                if (record.pdf_document_id != pdf.document_id or
                        record.pdf_bytes_sha256 != pdf.bytes_sha256 or
                        record.pdf_parser_version != pdf.parser_version or
                        record.physical_page != unit.page_number or
                        record.pdf_owner_entity_ids != match.document.owner_entity_ids or
                        record.pdf_link_source_revisions != link_revisions):
                    _reject("evidence_integrity_failure")
                details = dict(
                    pdf_document_id=pdf.document_id, original_url=pdf.url,
                    pdf_revision_id=unit.source_revision_id,
                    bytes_sha256=pdf.bytes_sha256,
                    parser_version=pdf.parser_version,
                    physical_page=unit.page_number,
                    pdf_owner_entity_ids=match.document.owner_entity_ids,
                    pdf_source_locators=match.document.source_locators,
                    pdf_link_source_revision_ids=link_revisions,
                )
            result.append(SaturnTypedEvidence(
                eid, unit.evidence_type, snapshot.snapshot_id, unit.source_revision_id,
                unit.entity_id, unit.locator, ptr.canonical_url, unit.text,
                ptr.canonical_kind, ptr.canonical_id, **details,
            ))
        return tuple(result)

    def _document_references(self, ranked):
        snapshot = self._bundle.snapshot
        matches = {m.document.document_id: m for m in snapshot.document_matches}
        result = []
        seen = set()
        for rank, item in enumerate(ranked, 1):
            doc_id = getattr(getattr(getattr(item, "match", None), "document", None),
                             "document_id", None)
            match = matches.get(doc_id)
            if (doc_id in seen or match is None or item.match != match or
                    item.snapshot_id != snapshot.snapshot_id or item.rank != rank):
                _reject("evidence_integrity_failure")
            seen.add(doc_id)
            doc = match.document
            if (not match.occurrences or
                    tuple(sorted({o.owner_entity_id for o in match.occurrences}))
                    != doc.owner_entity_ids or
                    tuple(sorted({o.source_locator for o in match.occurrences}))
                    != doc.source_locators or
                    any(o.document_id != doc_id or o.resolved_url.split("#")[0] != doc.url
                        for o in match.occurrences)):
                _reject("evidence_integrity_failure")
            result.append(SaturnDocumentReference(
                doc_id, doc.title, doc.kind, doc.version, doc.date, doc.url,
                doc.owner_entity_ids, doc.source_locators, match.occurrences,
                match.extraction_status, match.pdf_revision_id,
            ))
        return tuple(result)

    def _check_policy(self, context, policy):
        record_map = {r.evidence_id: r for r in self._bundle.records}
        document_map = {r.match.document.document_id: r for r in self._bundle.documents}
        entities = {e.entity_id: e for e in self._bundle.snapshot.entities}
        for ev in context.answer_evidence:
            record = record_map.get(ev.evidence_id)
            if record is None or not _allowed_record(record, policy):
                _reject("policy_blocked")
        for ref in context.document_references:
            record = document_map.get(ref.document_id)
            if record is None or not _allowed_doc(record, policy, entities):
                _reject("policy_blocked")

    def build_context(self, question: str, *, mode="lexical", top_k=5):
        with self._lock:
            self._assert_open()
            try:
                _valid_query(question, top_k, mode)
            except (TypeError, ValueError):
                _reject("invalid_request")
            if top_k > MAX_CONTEXT_EVIDENCE:
                _reject("resource_budget_exceeded")
            try:
                retrieval = self._service._search_captured(
                    self._bundle, question, mode, top_k)
            except RuntimeError as exc:
                if "policy" in str(exc).casefold():
                    _reject("policy_unavailable")
                _reject("retrieval_unavailable")
            except (ValueError, LookupError, AttributeError, TypeError):
                _reject("retrieval_unavailable")
            self._validate_result(retrieval, question, mode)
            evidence = self._typed_evidence(retrieval.answer_evidence)
            documents = self._document_references(retrieval.document_matches)
            if sum(len(item.source_text) for item in evidence) > MAX_CONTEXT_TEXT_CHARS:
                _reject("resource_budget_exceeded")
            policy = _safe_policy(self._service.policy_provider)
            context = SaturnEvidenceContext(
                question=question,
                question_sha256=sha256(question.encode("utf-8")).hexdigest(),
                snapshot_id=self._bundle.snapshot.snapshot_id,
                bundle_id=self._bundle.manifest.bundle_id, mode=mode,
                policy_revision=policy.revision, answer_evidence=evidence,
                document_references=documents,
                diagnostics=(("answer_evidence_count", len(evidence)),
                             ("document_reference_count", len(documents)),
                             ("source_text_chars", sum(len(e.source_text) for e in evidence))),
            )
            self._check_policy(context, policy)
            if len(self._issued) >= MAX_SESSION_CONTEXTS:
                _reject("resource_budget_exceeded")
            self._issued.append(context)
            return context

    def recheck_policy(self, context: SaturnEvidenceContext):
        with self._lock:
            self._assert_open()
            if (not isinstance(context, SaturnEvidenceContext) or
                    not any(context is issued for issued in self._issued) or
                    context.snapshot_id != self._bundle.snapshot.snapshot_id or
                    context.bundle_id != self._bundle.manifest.bundle_id or
                    context.question_sha256 != sha256(context.question.encode("utf-8")).hexdigest()):
                _reject("context_identity_mismatch")
            policy = _safe_policy(self._service.policy_provider)
            self._check_policy(context, policy)
            # This is an eligibility check at capture time, not a permanent
            # permission. Stage 5B-5D must recheck before consuming evidence.
            return policy.revision
