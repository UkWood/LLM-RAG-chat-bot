"""Independent, deterministic Saturn answer scoring over a frozen canonical snapshot.

This module imports the public RESULT CONTRACT, not 5C verifier, 5D citation
builder, final gate or answer renderer. It does not trust provider labels,
verification flags, reason codes, evidence IDs or statuses as proof.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

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
    verified_need_ids: tuple[str, ...] = ()
    technical_failure: bool = False
    ranked_document_ids: tuple[str, ...] = ()
    snapshot_id: str | None = None
    bundle_id: str | None = None
    question_sha256: str | None = None
    needs: tuple = ()
    need_findings: tuple = ()
    retrieval_diagnostics_complete: bool = False
    policy_blocked_evidence_ids: tuple[str, ...] = ()
    policy_blocked_document_ids: tuple[str, ...] = ()
    policy_blocked_source_revision_ids: tuple[str, ...] = ()
    policy_blocked_entity_ids: tuple[str, ...] = ()


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
    source_unsupported_claim_count: int = 0
    off_question_claim_count: int = 0
    extra_answer_text_count: int = 0
    policy_restriction: bool = False
    evidence_conflict: bool = False
    answer_assertion_count: int = 0
    quote_requirement_count: int = 0
    verified_quote_count: int = 0


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
    if (type(s) is not SaturnAnswerStatement or type(s.text) is not str or
            type(s.citation_ids) is not tuple or len(s.citation_ids) != 1):
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
        prefix = "Цитата источника (не подтверждает характеристику): "
        unit = indexes["evidence"].get(citation.evidence_id)
        if (unit is None or unit.evidence_type not in ("site_passage", "pdf_passage") or
                s.evidence_id != unit.evidence_id or
                s.document_id is not None or
                not s.text.startswith(prefix)):
            return None
        quote = s.text[len(prefix):]
        # Python considers the empty string a substring of EVERY passage.
        # A quote is exact *and substantive*, never a whitespace-only token.
        if (not quote.strip() or len(quote) > 1000 or
                quote not in unit.text or
                (unit.evidence_type == "pdf_passage" and
                 citation.source_type != "pdf") or
                (unit.evidence_type == "site_passage" and
                 citation.source_type != "site")):
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


def _need_matches_requirement(need, req, indexes):
    """Gold provenance is authored independently; 5B needs are only observed
    runtime hypotheses, not a gold-definition mechanism.
    """
    if need.resolution_status != "resolved":
        return False
    if req.kind == "field":
        fact = indexes["facts"].get(req.canonical_id)
        return (fact is not None and need.kind == "field_value" and
                need.entity_id == fact.entity_id and
                need.field_path == fact.field_path)
    if req.kind == "relation":
        relation = indexes["relations"].get(req.canonical_id)
        return (relation is not None and need.kind == "relation" and
                need.entity_id == relation.subject_entity_id and
                need.object_entity_id == relation.object_entity_id and
                need.predicate == relation.predicate)
    if req.kind == "document":
        match = indexes["documents"].get(req.canonical_id)
        return (match is not None and need.kind == "document_lookup" and
                need.document_title == match.document.title and
                need.entity_id == req.owner_entity_id and
                (need.entity_id is None or
                 any(o.owner_entity_id == need.entity_id for o in match.occurrences)))
    return False  # PDF extractive quotes do not entail a technical fact.


# Independent lexical constraints for *observed* needs. These do not invoke
# Stage 5B parsing, look up source values, or use model-produced gold. Field
# tokens are taken literally from the authored question; punctuation, nested
# paths, indexed paths and JSON-quoted keys remain opaque exact substrings.
_FIELD_QUESTION_HEAD = re.compile(r"^\s*[^:\r\n?]{1,160}?\s*:\s*")
_RELATION_QUESTION = re.compile(
    r"^\s*relation\(\s*([^,()?]+?)\s*,\s*([^,()?]+?)\s*,"
    r"\s*([^,()?]+?)\s*\)\s*\?\s*$")
_DOCUMENT_QUESTION = re.compile(
    r"^\s*(?:Документ|Document)\s*:\s*([^|\r\n?]+?)"
    r"(?:\s*\|\s*owner=([^|\r\n?]+?))?\s*\?\s*$",
    re.IGNORECASE,
)


def _semantic_need_binding(question, needs):
    """Independently validate observed semantic slots and ordered field list.

    Only checks source-question wording, not which source facts exist. Commas
    inside source-declared field names are preserved within the literal span.
    """
    if all(n.kind == "field_value" for n in needs):
        header = _FIELD_QUESTION_HEAD.match(question)
        if header is None:
            return False
        ordered = sorted(needs, key=lambda n: n.question_span[0])
        cursor = header.end()
        for i, need in enumerate(ordered):
            left, right = need.question_span
            if left < cursor or need.field_path != question[left:right] or not need.field_path.strip():
                return False
            gap = question[cursor:left]
            if i == 0:
                if gap.strip():
                    return False
            elif not (re.fullmatch(r"\s*,\s*", gap) or
                      re.fullmatch(r"\s+(?:and|и)\s+", gap, re.IGNORECASE)):
                return False
            cursor = right
        return re.fullmatch(r"\s*\?\s*", question[cursor:]) is not None
    if len(needs) != 1:
        return False
    need = needs[0]
    if need.kind == "relation":
        match = _RELATION_QUESTION.fullmatch(question)
        return (match is not None and
                need.predicate == match.group(2).strip() and
                need.question_span == (0, len(question)))
    if need.kind == "document_lookup":
        match = _DOCUMENT_QUESTION.fullmatch(question)
        return (match is not None and
                need.document_title == match.group(1).strip() and
                ((need.entity_id is None) if match.group(2) is None
                 else need.entity_id is not None or
                 need.resolution_status in ("missing_entity", "ambiguous")) and
                need.question_span == (0, len(question)))
    if need.kind == "unresolved":
        return (need.field_path is None and need.predicate is None and
                need.document_title is None)
    return False


def _need_bindings(case, snapshot, trace, indexes):
    """Validate need identity, spans, source meaning, and matched gold scopes.

    Does not call production parse_saturn_question_needs. Every need ID is
    independently reconstructed from the Stage 5B public ID contract.
    """
    if (trace is None or not trace.needs or
            len(trace.needs) != len(trace.need_findings) or
            len(trace.needs) > 6):
        return {}, True
    needs = {}
    sha = sha256(case.question.encode("utf-8")).hexdigest()
    for need, finding in zip(trace.needs, trace.need_findings):
        span = getattr(need, "question_span", None)
        if (not isinstance(span, tuple) or len(span) != 2 or
                not all(type(i) is int for i in span) or
                not 0 <= span[0] < span[1] <= len(case.question) or
                need.original_text != case.question[span[0]:span[1]] or
                need.need_id != stable_id(
                    "saturn-question-need-v1", sha, span[0], span[1],
                    need.kind, need.entity_id, need.field_path,
                    need.predicate, need.object_entity_id,
                    need.resolution_status, need.document_title) or
                need.need_id in needs or finding.need_id != need.need_id):
            return {}, True
        needs[need.need_id] = (need, finding)
    if not _semantic_need_binding(case.question, tuple(n for n, _ in needs.values())):
        return needs, True
    # Every positive source requirement must map to exactly ONE observed need.
    for req in case.required:
        if req.kind == "pdf_quote":
            continue
        matched = [need_id for need_id, (need, _) in needs.items()
                   if _need_matches_requirement(need, req, indexes)]
        if len(matched) != 1:
            return needs, True
    # A source-backed need for a *different* requirement must never be
    # accepted as though the expected gold requirement were asked.
    return needs, False


def _statement_binds(s, match, needs, indexes):
    if s.need_id not in needs:
        return False
    need, finding = needs[s.need_id]
    if (type(s.citation_ids) is not tuple or len(s.citation_ids) != 1 or
            s.statement_id != stable_id(
                "saturn-answer-statement-v1", s.need_id, s.evidence_id,
                s.document_id, s.statement_kind, s.citation_ids[0])):
        return False
    if match is None:
        return False
    kind, identity, revision, evidence_id = match
    if kind in ("field", "relation"):
        if (finding.status != "covered_structured" or
                evidence_id not in finding.evidence_ids):
            return False
        fake = SaturnGoldRequirement("observed", kind, identity,
                                     revision, evidence_id)
        return _need_matches_requirement(need, fake, indexes)
    if kind == "document":
        if (finding.status != "document_found" or
                identity not in finding.document_ids or
                need.kind != "document_lookup"):
            return False
        doc = indexes["documents"].get(identity)
        if doc is None or need.document_title != doc.document.title:
            return False
        return need.entity_id is None or any(
            o.owner_entity_id == need.entity_id for o in doc.occurrences)
    if kind == "quote":
        unit = indexes["evidence"].get(identity)
        return (finding.status == "text_candidate" and
                identity in finding.evidence_ids and
                need.kind in ("field_value", "relation") and
                need.entity_id is not None and unit is not None and
                (unit.entity_id == need.entity_id or
                 (unit.evidence_type == "pdf_passage" and
                  any(m.pdf_revision_id == revision and
                      need.entity_id in m.document.owner_entity_ids
                      for m in indexes["documents"].values()))))
    return False


def _attribution(case, trace, missing, result, indexes=None):
    """Explain each missing gold requirement using *its own* observed need.

    Cross-need evidence (another covered_structured finding) cannot establish
    that this requirement reached verification. Never infer a retrieval miss
    from an unavailable or pre-retrieval technical trace.
    """
    if not missing:
        return ()
    if trace is None:
        return ("undetermined",)
    if trace.technical_failure:
        return ("technical_failure",)
    codes = []
    for req in missing:
        if (req.evidence_id in trace.policy_blocked_evidence_ids or
                req.canonical_id in trace.policy_blocked_document_ids or
                req.source_revision_id in trace.policy_blocked_source_revision_ids or
                (req.owner_entity_id is not None and
                 req.owner_entity_id in trace.policy_blocked_entity_ids)):
            codes.append("policy_restriction")
            continue
        if not trace.retrieval_diagnostics_complete:
            codes.append("undetermined")
            continue
        ranked = (trace.ranked_document_ids if req.kind == "document"
                  else trace.ranked_evidence_ids)
        selected = (trace.selected_document_ids if req.kind == "document"
                    else trace.selected_evidence_ids)
        target = req.canonical_id if req.kind == "document" else req.evidence_id
        if target not in ranked:
            codes.append("retrieval_miss")
            continue
        if target not in selected:
            codes.append("document_not_selected" if req.kind == "document"
                         else "evidence_not_selected")
            continue
        if req.kind == "pdf_quote":
            # Extraction and quotation are not verified technical facts.
            codes.append("quote_requirement_not_satisfied")
            continue
        observed = [
            (need, finding) for need, finding in
            zip(trace.needs, trace.need_findings)
            if indexes is not None and _need_matches_requirement(
                need, req, indexes)
        ]
        if len(observed) != 1:
            codes.append("question_parse_failure" if trace.needs
                         else "undetermined")
            continue
        need, finding = observed[0]
        if finding.status in ("potential_conflict", "ambiguous"):
            codes.append("evidence_conflict")
        elif req.kind == "document":
            if (finding.status != "document_found" or
                    target not in finding.document_ids):
                codes.append("document_requirement_not_satisfied")
            else:
                codes.append("answer_assembly_missing")
        elif finding.status != "covered_structured":
            codes.append("sufficiency_false_negative")
        elif target not in finding.evidence_ids:
            codes.append("sufficiency_false_negative")
        elif target not in trace.verified_evidence_ids:
            codes.append("claim_generation_missing")
        else:
            codes.append("answer_assembly_missing")
    return tuple(sorted(set(codes))) or ("undetermined",)


def _gold_source_channel(case):
    channels = {"site" if r.kind in ("field", "relation") else
                "document_metadata" if r.kind == "document" else "pdf"
                for r in case.required}
    return next(iter(channels)) if len(channels) == 1 else ("mixed" if channels else "none")


def score_answer(case: SaturnEvaluationCase, result: SaturnAnswerResult,
                 snapshot, trace: SaturnStageTrace | None = None) -> SaturnEvaluationOutcome:
    """Independently inspect a returned result against source-authored gold.

    The Stage 5B parser is *never* an oracle for gold requirements. Its
    emitted needs are validated as observations before being matched to
    independent canonical gold IDs/owner scopes.
    """
    indexes = _indexes(snapshot)
    codes = set()
    expected = case.expected_status
    question_sha = sha256(case.question.encode("utf-8")).hexdigest()
    if (type(result) is not SaturnAnswerResult or
            result.snapshot_id != snapshot.snapshot_id or
            result.question_sha256 != question_sha or
            (trace is not None and (
                trace.snapshot_id not in (None, snapshot.snapshot_id) or
                trace.question_sha256 not in (None, question_sha) or
                trace.bundle_id not in (None, result.bundle_id)))):
        codes.add("technical_failure")
        return SaturnEvaluationOutcome(
            case.case_id, case.category, case.split, expected, "error",
            expected == "error", False, len(case.required), 0, 0, 0,
            len(case.required), None, 0, 0, None, None, 0,
            len(case.required), tuple(sorted(codes)), _gold_source_channel(case))

    actual = result.status
    status_correct = actual == expected and actual in ANSWER_STATUSES
    if not status_correct:
        codes.add("incorrect_status")
    if actual == "error" or (trace is not None and trace.technical_failure):
        codes.add("technical_failure")
    try:
        need_map, need_error = _need_bindings(case, snapshot, trace, indexes)
    except (TypeError, AttributeError, ValueError, IndexError):
        need_map, need_error = {}, True
    if need_error:
        codes.add("need_binding_failure")
    if (len({c.citation_id for c in result.citations}) != len(result.citations) or
            len({s.statement_id for s in result.statements}) != len(result.statements)):
        codes.add("citation_error")
    citation_map = {c.citation_id: c for c in result.citations}
    valid_citations = set()
    for citation in result.citations:
        try:
            if _citation_ok(citation, snapshot, indexes):
                valid_citations.add(citation.citation_id)
        except (TypeError, ValueError, KeyError, AttributeError, IndexError):
            pass
    citation_valid = (len(valid_citations) == len(result.citations)
                      if result.citations else None)
    if citation_valid is False:
        codes.add("citation_error")

    try:
        extra_text = int(result.answer_text != _expected_answer_text(
            actual, result.statements))
    except (TypeError, AttributeError, ValueError):
        extra_text = 1
    if extra_text:
        codes.add("extra_unsupported_answer_text")
        codes.add("unsafe_claim")

    seen_needs = set()
    emitted_evidence = set()
    emitted_requirements = set()
    technical_assertions = 0
    source_unsupported = 0
    off_question_ids = set()
    answer_assertions = 0
    verified_quotes = set()
    for s in result.statements:
        technical = s.statement_kind in _TECH
        assertion = s.statement_kind in _SATISFY
        technical_assertions += int(technical)
        answer_assertions += int(assertion)
        if s.need_id in seen_needs or s.need_id not in need_map:
            codes.add("need_binding_failure")
        seen_needs.add(s.need_id)
        referenced_valid = (type(s.citation_ids) is tuple and
                            bool(s.citation_ids) and
                            all(cid in valid_citations for cid in s.citation_ids))
        match = (_evaluate_statement(s, citation_map, indexes)
                 if referenced_valid else None)
        if not referenced_valid:
            codes.add("citation_error")
        if match is None:
            if technical:
                source_unsupported += 1
            if assertion or s.statement_kind == "source_quote":
                codes.add("unsafe_claim")
            continue
        if not _statement_binds(s, match, need_map, indexes):
            codes.add("need_binding_failure")
            # This may be a valid fact from a different question, not
            # necessarily source-unsupported. Count it as off-question.
            if assertion:
                off_question_ids.add(s.statement_id)
        if match[0] == "quote" and _statement_binds(s, match, need_map, indexes):
            citation = citation_map.get(s.citation_ids[0])
            unit = indexes["evidence"].get(match[1])
            quote = s.text[len("Цитата источника (не подтверждает характеристику): "):]
            for req in case.required:
                if (req.kind == "pdf_quote" and
                        citation is not None and citation.source_type == "pdf" and
                        unit is not None and unit.evidence_type == "pdf_passage" and
                        req.canonical_id == citation.document_id and
                        req.source_revision_id == citation.pdf_revision_id and
                        req.evidence_id == match[1] and
                        req.physical_page == citation.physical_page and
                        req.exact_quote == quote):
                    verified_quotes.add(req.requirement_id)
                    emitted_requirements.add(req.requirement_id)
        if match[0] in ("field", "relation", "document"):
            if match in emitted_evidence:
                codes.add("need_binding_failure")
                off_question_ids.add(s.statement_id)
            emitted_evidence.add(match)
            matching_gold = [r for r in case.required
                             if (r.kind, r.canonical_id, r.source_revision_id,
                                 r.evidence_id) == match]
            if not matching_gold:
                off_question_ids.add(s.statement_id)
                codes.add("unexpected_claim")
            elif not _statement_binds(s, match, need_map, indexes):
                codes.add("need_binding_failure")
            else:
                for req in matching_gold:
                    if req.owner_entity_id is not None:
                        citation = citation_map.get(s.citation_ids[0])
                        if (citation is None or
                                citation.source_type != "document_metadata" or
                                citation.owner_entity_ids != (req.owner_entity_id,) or
                                not citation.occurrences or
                                any(o.owner_entity_id != req.owner_entity_id
                                    for o in citation.occurrences)):
                            codes.add("owner_scope_mismatch")
                            continue
                    # The current runtime need must match the authored
                    # source requirement; source ID alone is insufficient.
                    if s.need_id not in need_map or not _need_matches_requirement(
                            need_map[s.need_id][0], req, indexes):
                        codes.add("need_binding_failure")
                        continue
                    emitted_requirements.add(req.requirement_id)

    off_question = len(off_question_ids)
    cited_ids = {ref for s in result.statements for ref in s.citation_ids}
    if any(c.citation_id not in cited_ids for c in result.citations):
        codes.add("citation_error")
    missing = tuple(r for r in case.required
                    if r.requirement_id not in emitted_requirements)
    if missing:
        codes.update(_attribution(case, trace, missing, result, indexes))
    if source_unsupported:
        codes.add("unsafe_claim")
    if off_question:
        codes.add("unexpected_claim")
    if expected == "answered" and actual in ("needs_support", "clarification", "partial"):
        codes.add("false_refusal")
    if expected != "answered" and actual == "answered":
        codes.add("sufficiency_false_positive")

    unresolved = result.unresolved_need_ids
    known_ids = set(need_map)
    if (type(unresolved) is not tuple or
            len(unresolved) != len(set(unresolved)) or
            not set(unresolved) <= known_ids):
        codes.add("unresolved_need_mismatch")
    if actual in ("answered", "partial", "needs_support", "clarification"):
        resolved_needs = {s.need_id for s in result.statements
                          if s.statement_kind in _SATISFY and
                          s.need_id in known_ids}
        expected_unresolved = known_ids - resolved_needs
        if (actual == "answered" and
                (unresolved or expected_unresolved or not resolved_needs)):
            codes.add("unresolved_need_mismatch")
        elif actual == "partial" and (
                not resolved_needs or not expected_unresolved or
                set(unresolved) != expected_unresolved):
            codes.add("unresolved_need_mismatch")
        if actual == "partial":
            # An unresolved need with an already verified structured claim,
            # or an exact found document requiring no provider, is an assembly
            # omission, not a genuinely unsupported partial requirement.
            if any(uid in trace.verified_need_ids or
                   (uid in need_map and need_map[uid][1].status == "document_found")
                   for uid in unresolved) if trace is not None else False:
                codes.add("unresolved_need_mismatch")
        if actual == "needs_support" and (
                resolved_needs or set(unresolved) != known_ids):
            codes.add("unresolved_need_mismatch")
        elif actual == "clarification" and (
                result.statements or set(unresolved) != known_ids):
            codes.add("unresolved_need_mismatch")

    if citation_valid is None and case.required and actual == "answered":
        codes.add("citation_error")
    if result.statements and any(
            s.statement_kind in _SATISFY and not s.citation_ids
            for s in result.statements):
        codes.add("citation_error")

    # Explicit source-backed conflicts are neither ordinary retrieval misses
    # nor a safe arbitrary choice of one conflicting claim.
    conflict = (trace is not None and any(
        f.status == "potential_conflict" for f in trace.need_findings))
    if conflict:
        codes.add("evidence_conflict")
    policy = "policy_restriction" in codes
    fully_correct = (status_correct and not missing and
                     source_unsupported == 0 and off_question == 0 and
                     extra_text == 0 and not any(code in codes for code in (
                         "technical_failure", "citation_error",
                         "need_binding_failure", "owner_scope_mismatch",
                         "unresolved_need_mismatch", "unexpected_claim",
                         "unsafe_claim", "evidence_conflict",
                         "policy_restriction", "sufficiency_false_positive",
                         "false_refusal")))
    if expected == "answered":
        fully_correct = fully_correct and citation_valid is True
    elif expected == "partial":
        fully_correct = (fully_correct and citation_valid is True and
                         bool(unresolved) and bool(emitted_requirements))
    else:
        fully_correct = fully_correct and technical_assertions == 0

    expected_evidence = {r.evidence_id for r in case.required if r.evidence_id}
    expected_documents = {r.canonical_id for r in case.required if r.kind == "document"}
    retrieval_measured = trace is not None and trace.retrieval_diagnostics_complete
    selected = set(trace.selected_evidence_ids) if retrieval_measured else set()
    ranked = set(trace.ranked_evidence_ids[:5]) if retrieval_measured else set()
    ranked_docs = set(trace.ranked_document_ids[:5]) if retrieval_measured else set()
    return SaturnEvaluationOutcome(
        case.case_id, case.category, case.split, expected, actual,
        status_correct, fully_correct, len(case.required),
        len(emitted_requirements), source_unsupported,
        technical_assertions, len(missing), citation_valid,
        len(result.citations), len(valid_citations),
        (expected_evidence <= ranked if expected_evidence and retrieval_measured else None),
        (expected_documents <= ranked_docs if expected_documents and retrieval_measured else None),
        len(expected_evidence & selected),
        len(expected_evidence) if retrieval_measured else 0,
        tuple(sorted(codes)), _gold_source_channel(case),
        source_unsupported, off_question, extra_text, policy, bool(conflict),
        answer_assertions,
        sum(req.kind == "pdf_quote" for req in case.required),
        len(verified_quotes),
    )
