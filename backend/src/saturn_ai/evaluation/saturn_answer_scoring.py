"""Independent, deterministic Saturn answer scoring over a frozen canonical snapshot.

This module imports the public RESULT CONTRACT, not 5C verifier, 5D citation
builder, final gate or answer renderer. It does not trust provider labels,
verification flags, reason codes, evidence IDs or statuses as proof.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from ..grounding.saturn_answer_contracts import (
    ANSWER_STATUSES, SaturnAnswerResult, SaturnAnswerStatement, SaturnCitation,
)
from ..ingestion.saturn_contracts import stable_id
from .saturn_answer_dataset import SaturnEvaluationCase, SaturnGoldRequirement

_TECH = frozenset(("structured_field", "structured_relation"))
_SATISFY = frozenset((*_TECH, "document_reference"))


@dataclass(frozen=True)
class SaturnStageTrace:
    ranked_evidence_ids: tuple[str, ...] = ()
    selected_evidence_ids: tuple[str, ...] = ()
    selected_document_ids: tuple[str, ...] = ()
    parsed_need_kinds: tuple[str, ...] = ()
    finding_statuses: tuple[str, ...] = ()
    verified_evidence_ids: tuple[str, ...] = ()
    technical_failure: bool = False
    ranked_document_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SaturnEvaluationOutcome:
    case_id: str
    category: str
    split: str
    expected_status: str
    actual_status: str
    status_correct: bool
    fully_correct: bool
    required_fact_count: int
    supported_fact_count: int
    unsupported_claim_count: int
    technical_assertion_count: int
    missing_requirement_count: int
    citation_valid: bool | None
    citation_count: int
    valid_citation_count: int
    source_hit_at_5: bool | None
    document_hit_at_5: bool | None
    evidence_recall_numerator: int
    evidence_recall_denominator: int
    failure_codes: tuple[str, ...]
    source_channel: str = "none"


def _expected_field(fact, entities):
    entity = entities[fact.entity_id]
    value = json.loads(fact.raw_value_json)
    shown = value if isinstance(value, str) else fact.raw_value_json
    out = entity.title + " — " + fact.field_path + ": " + shown
    if fact.unit is not None:
        out += " [unit: " + fact.unit + "]"
    if fact.qualifiers_json not in (None, "{}"):
        out += " [qualifiers: " + fact.qualifiers_json + "]"
    return out + "."


def _expected_document(doc, match):
    out = doc.title + " [" + doc.kind + "] — " + doc.url
    if doc.version is not None:
        out += " [version: " + doc.version + "]"
    if doc.date is not None:
        out += " [date: " + doc.date + "]"
    return out + " [extraction: " + (match.extraction_status or "not_extracted") + "]."


def _expected_answer_text(status, statements):
    lines = [s.text for s in statements if s.statement_kind != "source_quote"]
    if status == "partial":
        lines.append("Ответ неполный. Для остальных требований недостаточно подтверждений.")
    elif status == "needs_support":
        lines.append("В доступных для текущего ответа материалах не найдено достаточного подтверждения.")
    elif status == "clarification":
        lines = ["Необходимо уточнить вопрос: неоднозначность или противоречивые сведения."]
    elif status == "error":
        lines = ["Не удалось выполнить проверку."]
    return "\n".join(lines)


def _pdf_revisions(snapshot):
    return {stable_id("saturn-pdf-revision-v1", p.document_id, p.url,
                      p.bytes_sha256, p.parser_version): p
            for p in snapshot.pdf_revisions}


def _citation_ok(c, snapshot, indexes):
    """Full canonical binding for all three source channels, including owners."""
    if type(c) is not SaturnCitation:
        return False
    revs, entities, units, pointers, pdfs, matches = (
        indexes[k] for k in ("revisions", "entities", "evidence", "pointers",
                              "pdfs", "documents"))
    if c.source_type == "site":
        e = units.get(c.evidence_id)
        p = pointers.get(c.evidence_id)
        rev = revs.get(c.source_revision_id)
        ent = entities.get(c.entity_id)
        if (not e or not p or not rev or not ent or ent.draft or
                not ent.canonical_url or e.entity_id != ent.entity_id or
                ent.source_revision_id != rev.revision_id or
                e.source_revision_id != rev.revision_id or
                p.canonical_url != ent.canonical_url or
                c.canonical_url != ent.canonical_url or
                c.title != ent.title or c.locator != e.locator or
                c.source_repository != rev.repository or
                c.source_branch != rev.branch or c.source_path != rev.path or
                c.source_commit_sha != rev.commit_sha or
                c.source_blob_sha != rev.blob_sha or
                c.source_content_sha256 != rev.content_sha256 or
                c.document_id is not None or c.physical_page is not None):
            return False
        if c.field_path is not None:
            f = indexes["facts"].get(p.canonical_id)
            if (not f or p.canonical_kind != "SiteFact" or
                    f.entity_id != ent.entity_id or f.source_revision_id != rev.revision_id or
                    f.field_path != c.field_path or e.evidence_type != "site_field" or
                    e.evidence_id != c.evidence_id):
                return False
        elif c.relation_source_field_path is not None:
            r = indexes["relations"].get(p.canonical_id)
            if (not r or p.canonical_kind != "SiteRelation" or
                    r.subject_entity_id != ent.entity_id or
                    r.source_revision_id != rev.revision_id or
                    r.source_field_path != c.relation_source_field_path or
                    e.evidence_type != "relation"):
                return False
        elif p.canonical_kind != "SiteEntity" or p.canonical_id != ent.entity_id or e.evidence_type != "site_passage":
            return False
        return c.citation_id == stable_id(
            "saturn-answer-citation-v1", "site", c.evidence_id,
            rev.revision_id, e.locator, c.field_path, c.relation_source_field_path)

    if c.source_type == "document_metadata":
        match = matches.get(c.document_id)
        if not match or not match.occurrences:
            return False
        doc = match.document
        occ = c.occurrences
        if (not occ or any(x not in match.occurrences for x in occ) or
                c.canonical_url != doc.url or c.title != doc.title or
                c.source_revision_id != match.pdf_revision_id or
                c.pdf_revision_id != match.pdf_revision_id or
                c.evidence_id is not None or
                c.document_kind != doc.kind or c.document_version != doc.version or
                c.document_date != doc.date or
                c.extraction_status != match.extraction_status or
                c.owner_entity_ids != tuple(sorted({o.owner_entity_id for o in occ})) or
                c.source_locators != tuple(sorted({o.source_locator for o in occ})) or
                c.source_revision_ids != tuple(sorted({o.source_revision_id for o in occ}))):
            return False
        pdf = pdfs.get(match.pdf_revision_id)
        if (c.pdf_bytes_sha256 != (pdf.bytes_sha256 if pdf else None) or
                c.pdf_parser_version != (pdf.parser_version if pdf else None)):
            return False
        for o in occ:
            owner, revision = entities.get(o.owner_entity_id), revs.get(o.source_revision_id)
            if (owner is None or revision is None or owner.draft or
                    owner.source_revision_id != revision.revision_id or
                    not o.source_locator or o.resolved_url.split("#")[0] != doc.url):
                return False
        return c.citation_id == stable_id(
            "saturn-answer-citation-v1", "document_metadata", doc.document_id,
            match.pdf_revision_id, tuple((o.owner_entity_id, o.source_locator,
                                           o.source_revision_id) for o in occ))

    if c.source_type == "pdf":
        pdf = pdfs.get(c.pdf_revision_id)
        unit = units.get(c.evidence_id)
        pointer = pointers.get(c.evidence_id)
        match = matches.get(c.document_id)
        if (not pdf or not unit or not pointer or not match or
                not match.occurrences or match.pdf_revision_id != c.pdf_revision_id or
                unit.evidence_type != "pdf_passage" or
                unit.source_revision_id != c.pdf_revision_id or
                pointer.canonical_kind != "PdfRevision" or
                pointer.canonical_id != c.pdf_revision_id or
                c.source_revision_id != c.pdf_revision_id or
                c.document_id != pdf.document_id or
                pdf.extraction_state != "extracted" or
                c.pdf_bytes_sha256 != pdf.bytes_sha256 or
                c.pdf_parser_version != pdf.parser_version or
                c.physical_page != unit.page_number or
                type(c.physical_page) is not int or
                not 1 <= c.physical_page <= pdf.page_count or
                c.canonical_url != pdf.url or pointer.canonical_url != pdf.url or
                c.locator != unit.locator or c.title != match.document.title or
                c.owner_entity_ids != match.document.owner_entity_ids or
                c.source_locators != match.document.source_locators or
                c.occurrences != match.occurrences or
                c.source_revision_ids != tuple(sorted({o.source_revision_id
                                                         for o in match.occurrences}))):
            return False
        return c.citation_id == stable_id(
            "saturn-answer-citation-v1", "pdf", c.evidence_id,
            c.pdf_revision_id, c.physical_page)
    return False


def _evaluate_statement(s, citations, indexes):
    """Return canonical kind/id/revision/evidence if an assertion is exact."""
    if type(s) is not SaturnAnswerStatement or len(s.citation_ids) != 1:
        return None
    citation = citations.get(s.citation_ids[0])
    if (citation is None or (s.evidence_id is not None and
                             citation.evidence_id != s.evidence_id) or
            (s.document_id is not None and citation.document_id != s.document_id)):
        return None
    if s.statement_kind == "structured_field" and citation.source_type == "site":
        p = indexes["pointers"].get(citation.evidence_id)
        f = indexes["facts"].get(p.canonical_id) if p else None
        if (not f or citation.field_path != f.field_path or
                s.text != _expected_field(f, indexes["entities"]) or
                s.document_id is not None or
                s.evidence_id != citation.evidence_id):
            return None
        return ("field", f.fact_id, f.source_revision_id, citation.evidence_id)
    if s.statement_kind == "structured_relation" and citation.source_type == "site":
        p = indexes["pointers"].get(citation.evidence_id)
        r = indexes["relations"].get(p.canonical_id) if p else None
        subj = indexes["entities"].get(r.subject_entity_id) if r else None
        obj = indexes["entities"].get(r.object_entity_id) if r else None
        if (not r or not subj or not obj or
                citation.relation_source_field_path != r.source_field_path or
                s.object_entity_id != r.object_entity_id or
                s.text != subj.title + " — " + r.predicate + " — " + obj.title + "." or
                s.evidence_id != citation.evidence_id):
            return None
        return ("relation", r.relation_id, r.source_revision_id, citation.evidence_id)
    if s.statement_kind == "document_reference" and citation.source_type == "document_metadata":
        m = indexes["documents"].get(citation.document_id)
        if (m is None or s.document_id != citation.document_id or
                s.evidence_id is not None or
                s.text != _expected_document(m.document, m)):
            return None
        return ("document", m.document.document_id,
                m.pdf_revision_id or "metadata-only", None)
    if s.statement_kind == "source_quote":
        unit = indexes["evidence"].get(citation.evidence_id)
        if (unit is None or unit.evidence_type not in ("site_passage", "pdf_passage") or
                s.evidence_id != unit.evidence_id or
                not s.text.startswith("Цитата источника (не подтверждает характеристику): ") or
                not unit.text.startswith(s.text.split(": ", 1)[1]) or
                len(s.text) > 1200):
            return None
        return ("quote", unit.evidence_id, unit.source_revision_id, unit.evidence_id)
    return None


def _indexes(snapshot):
    return {
        "facts": {x.fact_id: x for x in snapshot.facts},
        "relations": {x.relation_id: x for x in snapshot.relations},
        "documents": {x.document.document_id: x for x in snapshot.document_matches},
        "entities": {x.entity_id: x for x in snapshot.entities},
        "revisions": {x.revision_id: x for x in snapshot.source_revisions},
        "evidence": {x.evidence_id: x for x in snapshot.answer_evidence},
        "pointers": {x.evidence_id: x for x in snapshot.evidence_pointers},
        "pdfs": _pdf_revisions(snapshot),
    }


def _attribution(case, trace, missing, result):
    codes = []
    if trace is None:
        return ("undetermined",) if missing else ()
    if trace.technical_failure:
        return ("technical_failure",)
    for req in missing:
        if req.kind == "document":
            if req.canonical_id not in trace.selected_document_ids:
                codes.append("retrieval_miss")
        elif req.evidence_id not in trace.ranked_evidence_ids:
            codes.append("retrieval_miss")
        elif req.evidence_id not in trace.selected_evidence_ids:
            codes.append("evidence_not_selected")
        elif req.kind != "pdf_quote":
            if (not trace.parsed_need_kinds or
                    req.kind == "field" and "field_value" not in trace.parsed_need_kinds or
                    req.kind == "relation" and "relation" not in trace.parsed_need_kinds):
                codes.append("question_parse_failure")
            elif "covered_structured" not in trace.finding_statuses and req.kind != "document":
                codes.append("sufficiency_false_negative")
            elif req.evidence_id not in trace.verified_evidence_ids and req.kind != "document":
                codes.append("claim_generation_missing")
            else:
                codes.append("answer_assembly_missing")
    return tuple(sorted(set(codes))) or (("undetermined",) if missing else ())


def _gold_source_channel(case):
    channels = {"site" if r.kind in ("field", "relation") else
                "document_metadata" if r.kind == "document" else "pdf"
                for r in case.required}
    return next(iter(channels)) if len(channels) == 1 else ("mixed" if channels else "none")


def score_answer(case: SaturnEvaluationCase, result: SaturnAnswerResult,
                 snapshot, trace: SaturnStageTrace | None = None) -> SaturnEvaluationOutcome:
    """Score AFTER the sealed runtime returned; gold not passed to application."""
    indexes = _indexes(snapshot)
    codes = set()
    expected = case.expected_status
    if type(result) is not SaturnAnswerResult or result.snapshot_id != snapshot.snapshot_id:
        codes.add("technical_failure")
        actual = "error"
        return SaturnEvaluationOutcome(
            case.case_id, case.category, case.split, expected, actual,
            expected == actual, False, len(case.required), 0, 0, 0,
            len(case.required), None, 0, 0, None, None, 0,
            len(case.required), tuple(sorted(codes)), _gold_source_channel(case))
    actual = result.status
    status_correct = actual == expected and actual in ANSWER_STATUSES
    if not status_correct:
        codes.add("incorrect_status")
    if actual == "error":
        codes.add("technical_failure")
    if (len({c.citation_id for c in result.citations}) != len(result.citations) or
            len({s.statement_id for s in result.statements}) != len(result.statements)):
        codes.add("citation_error")
    citation_map = {c.citation_id: c for c in result.citations}
    valid_citations = {c.citation_id for c in result.citations
                       if _citation_ok(c, snapshot, indexes)}
    citation_valid = (len(valid_citations) == len(result.citations)
                      if result.citations else None)
    if citation_valid is False:
        codes.add("citation_error")
    text_integrity_failure = result.answer_text != _expected_answer_text(actual, result.statements)
    if text_integrity_failure:
        codes.add("unsafe_claim")
    supported = set()
    assertions = 0
    unsupported = int(text_integrity_failure)
    emitted_evidence = set()
    for s in result.statements:
        is_technical = s.statement_kind in _TECH
        is_assertion = s.statement_kind in _SATISFY
        assertions += int(is_technical)
        referenced_valid = all(cid in valid_citations for cid in s.citation_ids)
        match = _evaluate_statement(s, citation_map, indexes) if referenced_valid else None
        if match is None:
            unsupported += int(is_assertion)
            codes.add("citation_error" if not referenced_valid else "unsafe_claim")
        elif match[0] in _SATISFY or match[0] in ("field", "relation", "document"):
            if match in emitted_evidence:
                unsupported += 1
                codes.add("unsafe_claim")
            emitted_evidence.add(match)
        # A correct source quote does not satisfy an engineering gold fact.
    for req in case.required:
        candidate = (req.kind, req.canonical_id,
                     req.source_revision_id, req.evidence_id)
        if candidate in emitted_evidence and req.kind != "pdf_quote":
            supported.add(req.requirement_id)
    missing = tuple(r for r in case.required if r.requirement_id not in supported)
    permitted = {(r.kind, r.canonical_id, r.source_revision_id, r.evidence_id)
                 for r in case.required}
    unexpected = {m for m in emitted_evidence if m not in permitted}
    if unexpected:
        codes.add("unexpected_claim")
    cited_ids = {ref for statement in result.statements for ref in statement.citation_ids}
    if any(c.citation_id not in cited_ids for c in result.citations):
        codes.add("citation_error")
    if missing:
        codes.update(_attribution(case, trace, missing, result))
    if unsupported:
        codes.add("unsafe_claim")
    if expected == "answered" and actual in ("needs_support", "clarification", "partial"):
        codes.add("false_refusal")
    if expected != "answered" and actual == "answered":
        codes.add("sufficiency_false_positive")
    if citation_valid is None and case.required and actual == "answered":
        codes.add("citation_error")
    if (result.statements and any(s.statement_kind in _SATISFY and
            not s.citation_ids for s in result.statements)):
        codes.add("citation_error")
    if expected == "answered":
        full = (status_correct and not missing and unsupported == 0 and
                citation_valid is True and not codes)
    elif expected == "partial":
        # A legitimate partial answer must retain at least one unresolved need.
        full = (status_correct and bool(result.unresolved_need_ids) and
                bool(case.required) and unsupported == 0 and not missing and
                citation_valid is True and not codes)
    else:
        full = (status_correct and assertions == 0 and unsupported == 0 and
                not any(x in codes for x in
                        ("technical_failure", "unsafe_claim", "citation_error")))
    expected_evidence = {r.evidence_id for r in case.required if r.evidence_id}
    expected_documents = {r.canonical_id for r in case.required if r.kind == "document"}
    selected = set(trace.selected_evidence_ids) if trace else set()
    ranked = set(trace.ranked_evidence_ids[:5]) if trace else set()
    ranked_docs = set(trace.ranked_document_ids[:5]) if trace else set()
    return SaturnEvaluationOutcome(
        case.case_id, case.category, case.split, expected, actual,
        status_correct, full, len(case.required), len(supported),
        unsupported, assertions, len(missing), citation_valid, len(result.citations),
        len(valid_citations), (expected_evidence <= ranked if expected_evidence and trace else None),
        (expected_documents <= ranked_docs if expected_documents and trace else None),
        len(expected_evidence & selected), len(expected_evidence),
        tuple(sorted(codes)), _gold_source_channel(case),
    )
