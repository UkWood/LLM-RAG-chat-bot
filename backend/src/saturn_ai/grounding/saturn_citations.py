"""Stage 5D canonical citation construction from a *pinned* Saturn snapshot.

No URL, title, location or revision is obtained from a provider or guessed
from a retrieval score. Any incomplete binding aborts the whole assembly.
"""
from ..ingestion.saturn_contracts import stable_id
from .saturn_answer_contracts import SaturnCitation
from .saturn_contracts import SaturnContextError


def _reject(code):
    raise SaturnContextError(code) from None


def _exact(items, predicate, code="citation_identity_mismatch"):
    selected = [item for item in items if predicate(item)]
    if len(selected) != 1:
        _reject(code)
    return selected[0]


def _site_source(snapshot, revision_id):
    return _exact(snapshot.source_revisions,
                  lambda item: item.revision_id == revision_id)


def _site_citation(snapshot, evidence, *, field_path=None, relation_path=None):
    pointer = _exact(snapshot.evidence_pointers,
                     lambda p: p.evidence_id == evidence.evidence_id)
    unit = _exact(snapshot.answer_evidence,
                  lambda u: u.evidence_id == evidence.evidence_id)
    if (unit.evidence_type != evidence.evidence_type or
            unit.source_revision_id != evidence.source_revision_id or
            unit.entity_id != evidence.entity_id or
            unit.locator != evidence.locator or
            pointer.canonical_kind != evidence.canonical_kind or
            pointer.canonical_id != evidence.canonical_id or
            pointer.canonical_url != evidence.canonical_url):
        _reject("citation_identity_mismatch")
    entity = _exact(snapshot.entities, lambda e: e.entity_id == evidence.entity_id)
    source = _site_source(snapshot, evidence.source_revision_id)
    if (entity.source_revision_id != source.revision_id or entity.draft or
            not entity.canonical_url or
            pointer.canonical_url != entity.canonical_url):
        _reject("citation_provenance_missing")
    if field_path is not None:
        fact = _exact(snapshot.facts, lambda f: f.fact_id == evidence.fact_id)
        if (pointer.canonical_kind != "SiteFact" or
                evidence.canonical_id != fact.fact_id or
                fact.entity_id != entity.entity_id or
                fact.field_path != field_path or
                fact.field_path != evidence.field_path or
                fact.source_revision_id != source.revision_id):
            _reject("citation_identity_mismatch")
    elif relation_path is not None:
        relation = _exact(snapshot.relations,
                          lambda r: r.relation_id == evidence.relation_id)
        if (pointer.canonical_kind != "SiteRelation" or
                evidence.canonical_id != relation.relation_id or
                relation.subject_entity_id != entity.entity_id or
                relation.source_revision_id != source.revision_id or
                relation.source_field_path != relation_path or
                relation.source_field_path != evidence.source_field_path or
                relation.predicate != evidence.predicate or
                relation.object_entity_id != evidence.object_entity_id):
            _reject("citation_identity_mismatch")
    else:
        if (pointer.canonical_kind != "SiteEntity" or
                pointer.canonical_id != entity.entity_id or
                evidence.evidence_type != "site_passage"):
            _reject("citation_identity_mismatch")
    citation_id = stable_id("saturn-answer-citation-v1", "site",
                            evidence.evidence_id, source.revision_id,
                            unit.locator, field_path, relation_path)
    return SaturnCitation(
        citation_id=citation_id, source_type="site",
        source_revision_id=source.revision_id,
        title=entity.title, canonical_url=entity.canonical_url,
        locator=unit.locator, evidence_id=evidence.evidence_id,
        entity_id=entity.entity_id, source_repository=source.repository,
        source_branch=source.branch, source_path=source.path,
        source_commit_sha=source.commit_sha, source_blob_sha=source.blob_sha,
        source_content_sha256=source.content_sha256,
        field_path=field_path, relation_source_field_path=relation_path,
    )


def _pdf_revision(snapshot, revision_id):
    from ..ingestion.saturn_contracts import stable_id as sid
    return _exact(snapshot.pdf_revisions, lambda p: sid(
        "saturn-pdf-revision-v1", p.document_id, p.url,
        p.bytes_sha256, p.parser_version) == revision_id)


def _pdf_citation(snapshot, evidence):
    pointer = _exact(snapshot.evidence_pointers,
                     lambda p: p.evidence_id == evidence.evidence_id)
    unit = _exact(snapshot.answer_evidence,
                  lambda u: u.evidence_id == evidence.evidence_id)
    pdf = _pdf_revision(snapshot, evidence.source_revision_id)
    match = _exact(snapshot.document_matches,
                   lambda m: m.document.document_id == pdf.document_id)
    doc = match.document
    if (evidence.evidence_type != "pdf_passage" or
            unit.evidence_type != "pdf_passage" or
            unit.source_revision_id != evidence.source_revision_id or
            pointer.canonical_kind != "PdfRevision" or
            pointer.canonical_id != evidence.source_revision_id or
            pointer.canonical_url != pdf.url or
            evidence.pdf_revision_id != evidence.source_revision_id or
            evidence.pdf_document_id != pdf.document_id or
            evidence.original_url != pdf.url or
            evidence.bytes_sha256 != pdf.bytes_sha256 or
            evidence.parser_version != pdf.parser_version or
            unit.page_number != evidence.physical_page or
            type(unit.page_number) is not int or
            pdf.page_count is None or
            not 1 <= unit.page_number <= pdf.page_count or
            pdf.extraction_state != "extracted" or
            match.pdf_revision_id != evidence.source_revision_id or
            match.extraction_status != "extracted" or
            doc.url != pdf.url or
            tuple(sorted({o.owner_entity_id for o in match.occurrences})) !=
            doc.owner_entity_ids or
            tuple(sorted({o.source_locator for o in match.occurrences})) !=
            doc.source_locators or
            evidence.pdf_owner_entity_ids != doc.owner_entity_ids or
            evidence.pdf_source_locators != doc.source_locators or
            evidence.pdf_link_source_revision_ids !=
            tuple(sorted({o.source_revision_id for o in match.occurrences}))):
        _reject("citation_identity_mismatch")
    if not doc.url or not match.occurrences:
        _reject("citation_provenance_missing")
    for occ in match.occurrences:
        _validate_occurrence(snapshot, occ, doc.document_id, doc.url)
    citation_id = stable_id("saturn-answer-citation-v1", "pdf",
                            evidence.evidence_id, evidence.source_revision_id,
                            unit.page_number)
    return SaturnCitation(
        citation_id=citation_id, source_type="pdf",
        source_revision_id=evidence.source_revision_id,
        title=doc.title, canonical_url=doc.url,
        locator=unit.locator, evidence_id=evidence.evidence_id,
        document_id=doc.document_id,
        pdf_revision_id=evidence.source_revision_id,
        pdf_bytes_sha256=pdf.bytes_sha256,
        pdf_parser_version=pdf.parser_version,
        physical_page=unit.page_number,
        owner_entity_ids=doc.owner_entity_ids,
        source_revision_ids=evidence.pdf_link_source_revision_ids,
        source_locators=doc.source_locators,
        occurrences=match.occurrences,
        document_kind=doc.kind, document_version=doc.version,
        document_date=doc.date, extraction_status=match.extraction_status,
    )


def _validate_occurrence(snapshot, occ, document_id, url):
    if (occ.document_id != document_id or
            occ.resolved_url.split("#")[0] != url):
        _reject("citation_identity_mismatch")
    source = _site_source(snapshot, occ.source_revision_id)
    entity = _exact(snapshot.entities, lambda e: e.entity_id == occ.owner_entity_id)
    if (entity.source_revision_id != source.revision_id or
            entity.draft or not entity.canonical_url or
            not occ.source_locator):
        _reject("citation_provenance_missing")
    return entity


def _document_citation(snapshot, reference, need):
    match = _exact(snapshot.document_matches,
                   lambda m: m.document.document_id == reference.document_id)
    doc = match.document
    if (not doc.url or not match.occurrences or
            reference.title != doc.title or
            reference.kind != doc.kind or
            reference.original_url != doc.url or
            reference.version != doc.version or
            reference.date != doc.date or
            reference.occurrences != match.occurrences or
            reference.owner_entity_ids != doc.owner_entity_ids or
            reference.source_locators != doc.source_locators or
            reference.extraction_status != match.extraction_status or
            reference.pdf_revision_id != match.pdf_revision_id or
            need.document_title != doc.title):
        _reject("citation_identity_mismatch")
    occurrences = tuple(o for o in match.occurrences
                        if need.entity_id is None or
                        o.owner_entity_id == need.entity_id)
    if not occurrences:
        _reject("citation_identity_mismatch")
    for occ in occurrences:
        _validate_occurrence(snapshot, occ, doc.document_id, doc.url)
    owner_ids = tuple(sorted({o.owner_entity_id for o in occurrences}))
    locators = tuple(sorted({o.source_locator for o in occurrences}))
    revision_ids = tuple(sorted({o.source_revision_id for o in occurrences}))
    pdf = None
    if match.pdf_revision_id:
        pdf = _pdf_revision(snapshot, match.pdf_revision_id)
        if pdf.document_id != doc.document_id or pdf.url != doc.url:
            _reject("citation_identity_mismatch")
    citation_id = stable_id("saturn-answer-citation-v1", "document_metadata",
                            reference.document_id, match.pdf_revision_id,
                            tuple((o.owner_entity_id, o.source_locator,
                                   o.source_revision_id) for o in occurrences))
    return SaturnCitation(
        citation_id=citation_id, source_type="document_metadata",
        source_revision_id=match.pdf_revision_id,
        title=doc.title, canonical_url=doc.url,
        locator=None, document_id=doc.document_id,
        pdf_revision_id=match.pdf_revision_id,
        pdf_bytes_sha256=pdf.bytes_sha256 if pdf is not None else None,
        pdf_parser_version=pdf.parser_version if pdf is not None else None,
        owner_entity_ids=owner_ids, source_revision_ids=revision_ids,
        source_locators=locators, occurrences=occurrences,
        document_kind=doc.kind, document_version=doc.version,
        document_date=doc.date, extraction_status=match.extraction_status,
    )


def claim_citation(snapshot, evidence, claim, payload):
    if claim.source_revision_id != evidence.source_revision_id:
        _reject("citation_identity_mismatch")
    if claim.claim_kind == "field_value":
        return _site_citation(snapshot, evidence,
                              field_path=payload["field_path"])
    if claim.claim_kind == "relation":
        return _site_citation(snapshot, evidence,
                              relation_path=payload["source_field_path"])
    if claim.claim_kind == "passage_quote":
        if evidence.evidence_type == "site_passage":
            return _site_citation(snapshot, evidence)
        if evidence.evidence_type == "pdf_passage":
            return _pdf_citation(snapshot, evidence)
    _reject("citation_identity_mismatch")


def document_citation(snapshot, reference, need):
    return _document_citation(snapshot, reference, need)
