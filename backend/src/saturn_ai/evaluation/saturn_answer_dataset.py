"""Strict source-backed gold contract for Saturn Stage 5E (not the legacy evaluator).

The evaluator reads labels only after the application has returned its answer.
No user-supplied expected answer is passed to retrieval, parser or provider.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from ..grounding.saturn_answer_contracts import ANSWER_STATUSES
from ..ingestion.saturn_contracts import canonical_json, stable_id

SCHEMA_VERSION = 1
MAX_CASES = 300
MAX_QUESTION_CHARS = 4000
MAX_REQUIREMENTS = 6
_SPLITS = frozenset(("synthetic_calibration", "synthetic_blind", "real_sample"))
_KINDS = frozenset(("field", "relation", "document", "pdf_quote"))
_HEX = set("0123456789abcdef")


class GoldValidationError(ValueError):
    """Safe error code; never echo source/gold text or private file paths."""
    def __init__(self, code):
        self.code = code
        super().__init__("Invalid Saturn gold dataset: " + code)


def _fail(code):
    raise GoldValidationError(code) from None


def _keys(value, keys, required=None):
    if type(value) is not dict or not set(value).issubset(keys) or not set(required or keys).issubset(value):
        _fail("schema")


def _sha(value):
    return type(value) is str and len(value) == 64 and all(x in _HEX for x in value)


def _text(value, maximum=256):
    return type(value) is str and 0 < len(value) <= maximum and value.strip() and "\x00" not in value


@dataclass(frozen=True)
class SaturnGoldRequirement:
    requirement_id: str
    kind: str
    canonical_id: str
    source_revision_id: str
    # Exact source identity, not an expected model-produced rendering.
    evidence_id: str | None = None
    physical_page: int | None = None
    exact_quote: str | None = None


@dataclass(frozen=True)
class SaturnEvaluationCase:
    case_id: str
    question: str
    category: str
    split: str
    expected_status: str
    required: tuple[SaturnGoldRequirement, ...]
    negative_reason: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SaturnGoldDataset:
    schema_version: int
    dataset_id: str
    snapshot_id: str
    corpus_hash: str
    split: str
    author: str
    reviewer: str
    cases: tuple[SaturnEvaluationCase, ...]
    sha256: str


def _index(snapshot):
    return {
        "facts": {x.fact_id: x for x in snapshot.facts},
        "relations": {x.relation_id: x for x in snapshot.relations},
        "documents": {x.document.document_id: x for x in snapshot.document_matches},
        "evidence": {x.evidence_id: x for x in snapshot.answer_evidence},
        "pointers": {x.evidence_id: x for x in snapshot.evidence_pointers},
        "revisions": {x.revision_id: x for x in snapshot.source_revisions},
        "pdf": {stable_id("saturn-pdf-revision-v1", p.document_id, p.url,
                          p.bytes_sha256, p.parser_version): p
                for p in snapshot.pdf_revisions},
    }


def _requirement(raw, idx):
    keys = {"requirement_id", "kind", "canonical_id", "source_revision_id",
            "evidence_id", "physical_page", "exact_quote"}
    _keys(raw, keys, {"requirement_id", "kind", "canonical_id", "source_revision_id"})
    if any(not _text(raw.get(k), 256) for k in ("requirement_id", "canonical_id",
                                                 "source_revision_id")):
        _fail("requirement_identity")
    if raw.get("kind") not in _KINDS:
        _fail("requirement_kind")
    if raw.get("evidence_id") is not None and not _text(raw["evidence_id"]):
        _fail("evidence_id")
    if raw.get("physical_page") is not None and (
            type(raw["physical_page"]) is not int or raw["physical_page"] < 1):
        _fail("physical_page")
    if raw.get("exact_quote") is not None and not _text(raw["exact_quote"], 2000):
        _fail("exact_quote")
    return SaturnGoldRequirement(**raw)


def _check_reference(req, index):
    pointer = index["pointers"].get(req.evidence_id)
    unit = index["evidence"].get(req.evidence_id)
    if req.kind == "field":
        f = index["facts"].get(req.canonical_id)
        if (f is None or f.source_revision_id != req.source_revision_id or
                req.source_revision_id not in index["revisions"] or
                pointer is None or unit is None or
                pointer.canonical_kind != "SiteFact" or pointer.canonical_id != f.fact_id or
                unit.evidence_type != "site_field" or
                unit.source_revision_id != req.source_revision_id or
                unit.entity_id != f.entity_id or
                req.physical_page is not None or req.exact_quote is not None):
            _fail("field_gold_mismatch")
    elif req.kind == "relation":
        r = index["relations"].get(req.canonical_id)
        if (r is None or r.source_revision_id != req.source_revision_id or
                req.source_revision_id not in index["revisions"] or
                pointer is None or unit is None or
                pointer.canonical_kind != "SiteRelation" or
                pointer.canonical_id != r.relation_id or
                unit.evidence_type != "relation" or
                unit.source_revision_id != req.source_revision_id or
                req.physical_page is not None or req.exact_quote is not None):
            _fail("relation_gold_mismatch")
    elif req.kind == "document":
        m = index["documents"].get(req.canonical_id)
        if (m is None or req.source_revision_id !=
                (m.pdf_revision_id or "metadata-only") or
                req.evidence_id is not None or req.physical_page is not None or
                req.exact_quote is not None or not m.occurrences):
            _fail("document_gold_mismatch")
    else:
        pdf = index["pdf"].get(req.source_revision_id)
        if (pdf is None or pdf.document_id != req.canonical_id or
                pdf.extraction_state != "extracted" or
                type(req.physical_page) is not int or
                req.physical_page > pdf.page_count or
                unit is None or pointer is None or
                unit.evidence_type != "pdf_passage" or
                unit.source_revision_id != req.source_revision_id or
                unit.page_number != req.physical_page or
                pointer.canonical_kind != "PdfRevision" or
                pointer.canonical_id != req.source_revision_id or
                not req.exact_quote or req.exact_quote not in unit.text):
            _fail("pdf_gold_mismatch")


def validate_gold(raw_bytes: bytes, snapshot, *, split=None):
    """Validate raw frozen bytes against one pinned canonical Saturn snapshot."""
    if type(raw_bytes) is not bytes or len(raw_bytes) > 1_000_000:
        _fail("dataset_bytes")
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeError, ValueError):
        _fail("json")
    _keys(raw, {"schema_version", "dataset_id", "snapshot_id", "corpus_hash",
                "split", "author", "reviewer", "cases"})
    if raw["schema_version"] != SCHEMA_VERSION or type(raw["schema_version"]) is not int:
        _fail("schema_version")
    if not _text(raw["dataset_id"]) or not _text(raw["author"]) or not _text(raw["reviewer"]):
        _fail("identity")
    if (raw["split"] not in _SPLITS or (split is not None and split != raw["split"]) or
            raw["snapshot_id"] != snapshot.snapshot_id or
            raw["corpus_hash"] != snapshot.manifest.corpus_hash or
            not _sha(raw["snapshot_id"]) or not _sha(raw["corpus_hash"])):
        _fail("snapshot_binding")
    cases = raw["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        _fail("case_count")
    seen_ids, seen_questions = set(), set()
    index = _index(snapshot)
    parsed = []
    for item in cases:
        _keys(item, {"case_id", "question", "category", "split", "expected_status",
                     "required", "negative_reason", "tags"},
              {"case_id", "question", "category", "split", "expected_status",
               "required", "tags"})
        if (not _text(item["case_id"]) or
                not _text(item["question"], MAX_QUESTION_CHARS) or
                not _text(item["category"]) or
                item["split"] != raw["split"] or
                item["expected_status"] not in ANSWER_STATUSES or
                type(item["required"]) is not list or
                len(item["required"]) > MAX_REQUIREMENTS or
                type(item["tags"]) is not list or
                len(item["tags"]) > 20 or
                any(not _text(t, 80) for t in item["tags"]) or
                len(set(item["tags"])) != len(item["tags"])):
            _fail("case_schema")
        if item["case_id"] in seen_ids or item["question"] in seen_questions:
            _fail("duplicate_case")
        seen_ids.add(item["case_id"])
        seen_questions.add(item["question"])
        requirements = tuple(_requirement(x, index) for x in item["required"])
        ids = [r.requirement_id for r in requirements]
        refs = [(r.kind, r.canonical_id, r.source_revision_id) for r in requirements]
        if len(set(ids)) != len(ids) or len(set(refs)) != len(refs):
            _fail("duplicate_requirement")
        for req in requirements:
            _check_reference(req, index)
        negative = item.get("negative_reason")
        if (item["expected_status"] == "answered" and
                (not requirements or negative is not None or
                 any(r.kind == "pdf_quote" for r in requirements))):
            _fail("positive_gold")
        if (item["expected_status"] != "answered" and not _text(negative)):
            _fail("negative_justification")
        parsed.append(SaturnEvaluationCase(
            item["case_id"], item["question"], item["category"], item["split"],
            item["expected_status"], requirements, negative, tuple(item["tags"])))
    return SaturnGoldDataset(
        SCHEMA_VERSION, raw["dataset_id"], raw["snapshot_id"], raw["corpus_hash"],
        raw["split"], raw["author"], raw["reviewer"], tuple(parsed),
        sha256(raw_bytes).hexdigest(),
    )


def serialize_gold(payload):
    """Canonical deterministic authored-data serialization; no model outputs."""
    return (canonical_json(payload) + "\n").encode("utf-8")
