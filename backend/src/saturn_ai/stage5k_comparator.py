"""Isolated Stage 5K-A-R A/B/C/D research comparator, not a final answerer.

Never changes Stage 4B/5B/5C/5D or Stage 5J storage. Gold labels and
expected answers are deliberately absent from runtime inputs.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path
from time import perf_counter

from .stage5k_contract import (
    BASELINE_BUNDLE_ID, COMPARATOR_REVISION, CORPUS_HASH, DATASET_SHA256,
    D_PREREQUISITE_REVISION, ENDPOINT, ExperimentError, FUSION_REVISION,
    MAX_PROMPT_BYTES, MAX_QUERY_EXPANSIONS, MAX_QUERY_CHARS, MAX_RESPONSE_BYTES,
    MAX_NEEDS,
    MAX_TOKENS, MODEL_ID, MODEL_SHA256, MODEL_TIMEOUT_SECONDS, PLAN_KEYS,
    PROMPT_REVISION, PROMPT_SYSTEM, ROUTER_REVISION, RRF_K, SNAPSHOT_ID,
    SOURCE_COMMIT, TOP_K, canonical, design_freeze, literal_identifiers,
    question_parts, sha_text, strict_json, validate_plan,
)
from .grounding.saturn_local_provider import (
    SaturnLocalModelConfig, _post_loopback, LocalModelError,
)
from .grounding.saturn_question_needs import parse_saturn_question_needs
from .retrieval.saturn_channel import (
    SaturnOperationalPolicy, SaturnPolicyProvider, SaturnRetrievalService,
    _allowed_record, _allowed_doc,
)
from .real_corpus_stand import (
    CONTENT_PATHS, PDF_PATHS, PINNED_PDF_REVISIONS,
)

VARIANTS = ("A", "B", "C", "D")
D_NOT_RUN = "D_NOT_RUN_PREREQUISITES_MISSING"
NOT_MEASURED = "NOT_MEASURED"


def verify_stand(stand) -> None:
    """Live Stage 5F pins must match before any real comparison can run."""
    m = stand.manifest
    if not isinstance(m, dict):
        raise ExperimentError("invalid_stand")
    if (m.get("source_commit") != SOURCE_COMMIT or
            m.get("snapshot_id") != SNAPSHOT_ID or
            m.get("corpus_hash") != CORPUS_HASH or
            m.get("retrieval_bundle_id") != BASELINE_BUNDLE_ID or
            m.get("selected_content_paths") != list(CONTENT_PATHS) or
            m.get("selected_pdf_paths") != list(PDF_PATHS) or
            m.get("selected_pdf_count") != 4 or
            m.get("scope_mode") != "scoped_experiment" or
            m.get("full_corpus_extraction_ready") is not False or
            m.get("scoped_extraction_ready") is not True):
        raise ExperimentError("real_stand_identity_mismatch")
    originals = m.get("pdf_revisions")
    if (type(originals) is not list or len(originals) != 4 or
            sum(item.get("page_count", -1000) for item in originals) != 256):
        raise ExperimentError("real_stand_pdf_mismatch")
    from urllib.parse import urlsplit
    actual = {
        urlsplit(item["url"]).path: (item["bytes_sha256"], item["page_count"])
        for item in originals
    }
    if actual != PINNED_PDF_REVISIONS:
        raise ExperimentError("real_stand_pdf_mismatch")
    files = m.get("selected_files")
    if (type(files) is not list or
            any(type(item) is not dict or
                not isinstance(item.get("content_sha256"), str) or
                len(item["content_sha256"]) != 64 for item in files) or
            not set(CONTENT_PATHS).issubset({
                item["path"] for item in files
            })):
        raise ExperimentError("real_stand_content_mismatch")
    if (stand.snapshot.snapshot_id != SNAPSHOT_ID or
            stand.snapshot.manifest.corpus_hash != CORPUS_HASH or
            stand.bundle.manifest.bundle_id != BASELINE_BUNDLE_ID or
            stand.bundle.dense is not None):
        raise ExperimentError("retrieval_baseline_identity_mismatch")
    stand.bundle.validate()


class LocalIntentPlanner:
    """One bounded direct loopback request; never a tool-using agent."""

    def __init__(self):
        self.config = SaturnLocalModelConfig(
            ENDPOINT, MODEL_ID, MODEL_SHA256,
            timeout_seconds=MODEL_TIMEOUT_SECONDS,
            max_completion_tokens=MAX_TOKENS,
        )
        self.calls = 0
        self.last_usage = None
        self.last_prompt_ms = None
        self.last_inference_ms = None
        self.last_outcome = None

    def plan(self, question: str) -> dict:
        self.last_usage = None
        self.last_prompt_ms = None
        self.last_inference_ms = None
        self.last_outcome = "pre_transport"
        start = perf_counter()
        body = {
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": canonical({
                    "question": question,
                    "question_parts": question_parts(question),
                    "question_sha256": sha_text(question),
                    "model_id": MODEL_ID,
                    "declared_model_sha256": MODEL_SHA256,
                })},
            ],
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        serialized = canonical(body).encode("utf-8")
        if len(serialized) > MAX_PROMPT_BYTES:
            raise ExperimentError("prompt_bytes_limit")
        self.last_prompt_ms = round((perf_counter() - start) * 1000, 3)
        # Count only attempts actually sent to the loopback transport.
        self.calls += 1
        self.last_outcome = "provider_failure"
        started = perf_counter()
        try:
            received = _post_loopback(self.config, serialized)
        except LocalModelError as exc:
            raise ExperimentError("planner_provider_" + exc.code) from None
        finally:
            self.last_inference_ms = round((perf_counter() - started) * 1000, 3)
        # From here on response/schema errors count as rejected plans,
        # not transport failures (no validated plan was returned).
        self.last_outcome = "plan_rejected"
        if len(received) > MAX_RESPONSE_BYTES:
            raise ExperimentError("planner_response_limit")
        response = strict_json(received)
        if (type(response) is not dict or response.get("model") != MODEL_ID
                or type(response.get("choices")) is not list
                or len(response["choices"]) != 1):
            raise ExperimentError("planner_model_identity")
        option = response["choices"][0]
        if (type(option) is not dict or option.get("finish_reason") != "stop"
                or type(option.get("message")) is not dict
                or type(option["message"].get("content")) is not str):
            raise ExperimentError("planner_response_contract")
        content = option["message"]["content"].encode("utf-8")
        if len(content) > MAX_RESPONSE_BYTES:
            raise ExperimentError("planner_response_limit")
        plan = validate_plan(content, question)
        usage = response.get("usage")
        if (type(usage) is dict and usage
                and all(key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                        and type(value) is int and value >= 0
                        for key, value in usage.items())):
            self.last_usage = dict(usage)
        self.last_outcome = "validated"
        return plan


def _candidate_info(candidate, record) -> dict:
    """Never construct new evidence IDs or URLs from model-provided text."""
    if (candidate.evidence_id != record.evidence_id or
            candidate.source_revision_id != record.source_revision_id or
            candidate.snapshot_id != record.snapshot_id or
            candidate.entity_id != record.entity_id or
            candidate.canonical_url != record.url or
            candidate.evidence_type != record.evidence_type):
        raise ExperimentError("candidate_provenance_mismatch")
    return {
        "evidence_id": record.evidence_id,
        "evidence_type": record.evidence_type,
        "entity_id": record.entity_id,
        "source_revision_id": record.source_revision_id,
        "canonical_url": record.url,
        "locator": record.locator,
        "content_sha256": record.text_hash,
        "pdf_document_id": record.pdf_document_id,
        "pdf_bytes_sha256": record.pdf_bytes_sha256,
        "physical_page": record.physical_page,
        "channel": candidate.channel,
        "rank": candidate.rank,
    }


def fuse_ranked(groups: list[list[dict]], *, budget: int = TOP_K) -> tuple[list[dict], list[dict]]:
    """Stable rank-only reciprocal rank fusion, never BM25+cosine raw mixing."""
    if type(groups) is not list or not 1 <= budget <= TOP_K:
        raise ExperimentError("invalid_fusion_input")
    sums: dict[str, float] = {}
    first: dict[str, dict] = {}
    traces: dict[str, list[dict]] = {}
    for query_index, group in enumerate(groups):
        if len(group) > TOP_K or len({c["evidence_id"] for c in group}) != len(group):
            raise ExperimentError("invalid_fusion_input")
        for rank, candidate in enumerate(group, 1):
            evidence_id = candidate["evidence_id"]
            if type(evidence_id) is not str or candidate["rank"] != rank:
                raise ExperimentError("invalid_fusion_input")
            if evidence_id in first and (
                    candidate["source_revision_id"] != first[evidence_id]["source_revision_id"]
                    or candidate["content_sha256"] != first[evidence_id]["content_sha256"]):
                raise ExperimentError("fusion_source_identity_drift")
            first.setdefault(evidence_id, candidate)
            sums[evidence_id] = sums.get(evidence_id, 0) + 1 / (RRF_K + rank)
            traces.setdefault(evidence_id, []).append({
                "query_index": query_index, "source_rank": rank,
                "channel": candidate["channel"],
            })
    ordered = sorted(sums, key=lambda eid: (-sums[eid], eid))
    result = []
    for new_rank, eid in enumerate(ordered[:budget], 1):
        item = dict(first[eid])
        item["rank"] = new_rank
        item["rrf_score"] = round(sums[eid], 12)
        item["query_provenance"] = traces[eid]
        result.append(item)
    omitted = [
        {"evidence_id": eid, "reason": "top_k_budget", "query_provenance": traces[eid]}
        for eid in ordered[budget:]
    ]
    return result, omitted


def fuse_documents(groups: list[list[dict]], *, budget: int = TOP_K):
    """Independent metadata RRF, never technical-answer evidence.

    A later expanded query can discover a document absent in original search.
    Do not blend document and answer-evidence budgets.
    """
    if type(groups) is not list or not 1 <= budget <= TOP_K:
        raise ExperimentError("invalid_document_fusion")
    scores = {}
    originals = {}
    traces = {}
    for query_index, group in enumerate(groups):
        if type(group) is not list or len(group) > TOP_K:
            raise ExperimentError("invalid_document_fusion")
        seen = set()
        for rank, document in enumerate(group, 1):
            if (type(document) is not dict or
                    type(document.get("document_id")) is not str or
                    not document["document_id"] or document.get("rank") != rank or
                    document["document_id"] in seen):
                raise ExperimentError("invalid_document_fusion")
            document_id = document["document_id"]
            seen.add(document_id)
            identity = {k: document.get(k) for k in (
                "document_id", "source_url", "content_sha256", "pdf_revision_id")}
            if document_id in originals and identity != originals[document_id]:
                raise ExperimentError("document_fusion_source_drift")
            originals.setdefault(document_id, identity)
            scores[document_id] = scores.get(document_id, 0.0) + 1.0 / (RRF_K + rank)
            traces.setdefault(document_id, []).append({
                "query_index": query_index, "source_rank": rank,
                "channel": "document_metadata",
            })
    ordered = sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))
    output = [{
        **originals[doc_id], "rank": new_rank,
        "rrf_score": round(scores[doc_id], 12),
        "query_provenance": traces[doc_id],
        "evidence_role": "document_metadata_only",
    } for new_rank, doc_id in enumerate(ordered[:budget], 1)]
    omitted = [{
        "document_id": doc_id, "reason": "document_top_k_budget",
        "query_provenance": traces[doc_id],
    } for doc_id in ordered[budget:]]
    return output, omitted


def resolve_entity_mentions(mentions: list[str], snapshot, policy) -> list[dict]:
    """Source-declared exact names only; unknown in 5F != absent globally.

    Never promote LLM-proposed IDs, fuzzy similarity or a blocked entity.
    Stage 5F is deliberately limited and cannot prove site-wide absence.
    """
    if type(mentions) is not list or len(mentions) > MAX_NEEDS:
        raise ExperimentError("entity_mentions_budget")
    names = {}
    for entity in snapshot.entities:
        declared = {entity.entity_id, entity.title, entity.slug}
        try:
            front = json.loads(getattr(entity, "raw_frontmatter_json", "{}"))
        except (ValueError, TypeError):
            front = {}
        if type(front) is dict:
            for key in ("designation", "model", "alias", "aliases"):
                item = front.get(key)
                if type(item) is str:
                    declared.add(item)
                elif type(item) is list and len(item) <= 64:
                    declared.update(v for v in item if type(v) is str)
        for name in declared:
            if type(name) is str and 0 < len(name) <= 256:
                names.setdefault(name.strip().casefold(), set()).add(entity.entity_id)
    entities = {item.entity_id: item for item in snapshot.entities}
    result = []
    for mention in mentions:
        if type(mention) is not str or not mention.strip() or len(mention) > 500:
            raise ExperimentError("invalid_entity_mention")
        all_ids = sorted(names.get(mention.strip().casefold(), ()))
        eligible = [
            entity_id for entity_id in all_ids
            if entity_id not in policy.blocked_entity_ids
            and getattr(entities[entity_id], "source_revision_id", None)
            not in policy.blocked_source_revision_ids
        ]
        if len(eligible) > 1:
            status, reason, entity_id = "ambiguous", "multiple_exact_source_identifiers", None
        elif len(eligible) == 1:
            status, reason, entity_id = "resolved", "unique_exact_source_identity", eligible[0]
        elif all_ids:
            status, reason, entity_id = "not_in_scope", "source_identity_blocked_by_policy", None
        elif literal_identifiers(mention) or any(ch.isdigit() for ch in mention):
            status, reason, entity_id = "not_in_scope", "no_exact_identity_in_pinned_scope", None
        else:
            status, reason, entity_id = "unresolved", "unresolved_textual_mention", None
        result.append({
            "mention": mention, "status": status, "reason": reason,
            "entity_id": entity_id, "eligible_exact_candidate_count": len(eligible),
            "scope": "bounded_stage5f_snapshot_not_full_site",
        })
    return result


def select_fast_path(question: str, lexical_candidates: list[dict], snapshot) -> dict:
    """ONLY a source-verified Stage 5B structured-field exact hit is fast."""
    if not lexical_candidates:
        return {"route": "plan", "reason": "no_eligible_exact_structured_hit",
                "formal_needs": []}
    try:
        needs = parse_saturn_question_needs(question, snapshot)
    except Exception:
        return {"route": "plan", "reason": "structured_parser_cannot_resolve",
                "formal_needs": []}
    if (not needs or any(
            n.kind != "field_value" or n.resolution_status != "resolved"
            for n in needs)):
        return {"route": "plan", "reason": "natural_or_unresolved_question",
                "formal_needs": []}
    source = {candidate["evidence_id"] for candidate in lexical_candidates}
    pointers = {p.canonical_id: p.evidence_id for p in snapshot.evidence_pointers
                if p.canonical_kind == "SiteFact"}
    formal = []
    for need in needs:
        match = next((
            f for f in snapshot.facts
            if f.entity_id == need.entity_id and
            f.field_path == need.field_path and
            pointers.get(f.fact_id) in source
        ), None)
        if match is None:
            return {"route": "plan", "reason": "no_eligible_exact_structured_hit",
                    "formal_needs": []}
        formal.append({
            "entity_id": need.entity_id, "field_path": need.field_path,
            "kind": need.kind, "evidence_id": pointers[match.fact_id],
            "question_span": list(need.question_span),
        })
    return {"route": "fast", "reason": "all_structured_needs_source_bound",
            "formal_needs": formal}


def _normalize(vector: list[float] | tuple, dimensions: int) -> tuple[float, ...]:
    if len(vector) != dimensions or dimensions > 8192 or dimensions < 1:
        raise ExperimentError("embedding_dimensions")
    try:
        nums = tuple(float(x) for x in vector)
    except (ValueError, TypeError):
        raise ExperimentError("embedding_values") from None
    if not all(isfinite(x) for x in nums):
        raise ExperimentError("embedding_values")
    norm = sqrt(sum(x * x for x in nums))
    if not norm or not isfinite(norm):
        raise ExperimentError("embedding_values")
    return tuple(x / norm for x in nums)


class EphemeralDIndex:
    """Real local ONNX only, no database, no synthetic embeddings/auto-download."""

    def __init__(self, stand, encoder, license_record: dict):
        from .retrieval.embeddings import LocalONNXEncoder
        if type(encoder) is not LocalONNXEncoder:
            raise ExperimentError("d_requires_real_local_onnx")
        identity = encoder.identity
        if (type(license_record) is not dict
                or license_record.get("approval_status") != "APPROVED"
                or type(license_record.get("reviewer")) is not str
                or not license_record["reviewer"].strip()
                or license_record.get("model_sha256") != identity.get("model_sha256")
                or license_record.get("tokenizer_sha256") != identity.get("tokenizer_sha256")
                or type(license_record.get("license")) is not str
                or not license_record["license"].strip()
                or type(license_record.get("source_url")) is not str
                or not license_record["source_url"].startswith("https://")):
            raise ExperimentError("d_license_review_missing")
        records = stand.bundle.records
        if not records or len(records) > 3000:
            raise ExperimentError("d_index_record_budget")
        raw = encoder.encode_documents([r.text for r in records])
        if len(raw) != len(records):
            raise ExperimentError("d_index_coverage")
        self.records = records
        self.encoder = encoder
        self.vectors = tuple(_normalize(v, encoder.dimensions) for v in raw)
        review_digest = sha_text(canonical(license_record))
        self.index_id = sha_text(canonical({
            "revision": D_PREREQUISITE_REVISION,
            "snapshot_id": stand.snapshot.snapshot_id,
            "corpus_hash": stand.snapshot.manifest.corpus_hash,
            "encoder": identity,
            "license_review_sha256": review_digest,
            "record_ids": [r.evidence_id for r in records],
            "record_hashes": [r.text_hash for r in records],
        }))
        # Never publish arbitrary reviewer/license fields or source URLs
        # from the local file in exported research observations.
        self.identity = {"index_id": self.index_id, "encoder_identity": identity,
                         "license_review_sha256": review_digest,
                         "license_review_status": "APPROVED",
                         "backend": "process_memory_only_cpu_cosine"}

    def search(self, question: str, policy) -> list[dict]:
        query = _normalize(self.encoder.encode_query(question), self.encoder.dimensions)
        scored = []
        for record, vector in zip(self.records, self.vectors):
            if _allowed_record(record, policy):
                score = sum(a * b for a, b in zip(query, vector))
                if not isfinite(score):
                    raise ExperimentError("d_nonfinite_score")
                scored.append((record, score))
        ranked = sorted(scored, key=lambda x: (-x[1], x[0].evidence_id))[:TOP_K]
        return [
            {"evidence_id": r.evidence_id, "evidence_type": r.evidence_type,
             "entity_id": r.entity_id, "source_revision_id": r.source_revision_id,
             "canonical_url": r.url, "locator": r.locator,
             "content_sha256": r.text_hash, "pdf_document_id": r.pdf_document_id,
             "pdf_bytes_sha256": r.pdf_bytes_sha256,
             "physical_page": r.physical_page, "channel": "dense",
             "rank": i}
            for i, (r, _) in enumerate(ranked, 1)
        ]


class ResearchComparator:
    def __init__(self, stand, *, planner=None, policy_provider=None,
                 d_index=None, test_only_service=None,
                 d_preparation_reason="encoder_not_provided"):
        if test_only_service is None:
            verify_stand(stand)
            if planner is not None and type(planner) is not LocalIntentPlanner:
                raise ExperimentError("real_planner_type_required")
            if d_index is not None and type(d_index) is not EphemeralDIndex:
                raise ExperimentError("real_pinned_d_index_required")
        self.stand = stand
        self.policy_provider = policy_provider or SaturnPolicyProvider()
        self.frozen_policy = self.policy_provider.capture()
        if type(self.frozen_policy) is not SaturnOperationalPolicy:
            raise ExperimentError("policy_unavailable")
        self.service = test_only_service or SaturnRetrievalService(self.policy_provider)
        if test_only_service is None:
            self.service.publish(stand.bundle)
        self.records = {r.evidence_id: r for r in stand.bundle.records}
        self.planner = planner
        self.d_index = d_index
        self.d_preparation_reason = d_preparation_reason

    def _policy(self):
        p = self.policy_provider.capture()
        if type(p) is not SaturnOperationalPolicy:
            raise ExperimentError("policy_unavailable")
        if p != self.frozen_policy:
            raise ExperimentError("policy_revision_changed")
        return p

    def _search(self, question: str, policy) -> tuple[list[dict], list[dict]]:
        result = self.service.search_saturn(question, mode="lexical", top_k=TOP_K)
        if (result.query != question or result.snapshot_id != self.stand.snapshot.snapshot_id
                or result.bundle_id != self.stand.bundle.manifest.bundle_id):
            raise ExperimentError("retrieval_identity_drift")
        eligible = {r.evidence_id for r in self.records.values()
                    if _allowed_record(r, policy)}
        ranked = []
        for index, candidate in enumerate(result.answer_evidence, 1):
            record = self.records.get(candidate.evidence_id)
            if (record is None or candidate.evidence_id not in eligible
                    or candidate.rank != index):
                raise ExperimentError("policy_or_evidence_violation")
            ranked.append(_candidate_info(candidate, record))
        docs = []
        documents = {d.match.document.document_id: d
                     for d in self.stand.bundle.documents}
        entities = {e.entity_id: e for e in self.stand.snapshot.entities}
        for idx, candidate in enumerate(result.document_matches, 1):
            document = documents.get(candidate.match.document.document_id)
            if (document is None or candidate.match != document.match
                    or candidate.snapshot_id != self.stand.snapshot.snapshot_id
                    or candidate.rank != idx or
                    not _allowed_doc(document, policy, entities)):
                raise ExperimentError("policy_or_document_violation")
            docs.append({
                "document_id": document.match.document.document_id,
                "rank": idx, "source_url": document.match.document.url,
                "content_sha256": document.text_hash,
                "pdf_revision_id": document.match.pdf_revision_id,
            })
        return ranked, docs

    def _planned(self, question: str, report: dict) -> dict:
        if self.planner is None:
            raise ExperimentError("planner_not_available")
        report["planning_attempts"] += 1
        is_real = type(self.planner) is LocalIntentPlanner
        before_calls = self.planner.calls if is_real else None
        # Test-injected deterministic planners are not real HTTP requests.
        # Keep legacy model_calls for backwards-compatible test diagnostics.
        report["model_calls"] = 0 if is_real else 1
        try:
            proposed = self.planner.plan(question)
            verified = validate_plan(proposed, question)
            report["validated_plans"] += 1
            return verified
        except Exception:
            if is_real:
                kind = self.planner.last_outcome
                if kind == "provider_failure":
                    report["provider_failures"] += 1
                elif kind in ("plan_rejected", "validated"):
                    report["rejected_plans"] += 1
                else:
                    report["pre_transport_failures"] += 1
            else:
                report["rejected_plans"] += 1
            raise
        finally:
            if is_real:
                actual = self.planner.calls - before_calls
                report["model_requests_sent"] += actual
                report["model_calls"] = actual
            report["model_usage"] = getattr(self.planner, "last_usage", None)
            report["prompt_ms"] = getattr(self.planner, "last_prompt_ms", None)
            report["inference_ms"] = getattr(self.planner, "last_inference_ms", None)

    def run_arm(self, case: dict, variant: str, *, synthetic: bool = False) -> dict:
        if variant not in VARIANTS:
            raise ValueError("invalid_variant")
        question = case["question"]
        if (type(question) is not str or not question.strip()
                or len(question) > MAX_QUERY_CHARS):
            raise ExperimentError("invalid_question")
        started = perf_counter()
        policy = self._policy()
        report = {
            "case_id": case["case_id"], "question": question,
            "question_sha256": sha_text(question), "variant": variant,
            "comparator_revision": COMPARATOR_REVISION,
            "dataset_sha256": DATASET_SHA256,
            "source_commit": SOURCE_COMMIT,
            "snapshot_id": self.stand.snapshot.snapshot_id,
            "corpus_hash": self.stand.snapshot.manifest.corpus_hash,
            "baseline_bundle_id": self.stand.bundle.manifest.bundle_id,
            "policy_revision": policy.revision,
            "index_id": self.d_index.index_id if variant == "D" and self.d_index else None,
            "router_revision": ROUTER_REVISION,
            "prompt_revision": PROMPT_REVISION,
            "fusion_revision": FUSION_REVISION,
            "status": "NOT_RUN", "error_code": None, "route": None,
            "intent_plan": None, "intent_accuracy": NOT_MEASURED,
            "evidence_recall": NOT_MEASURED, "evidence_hit_at_5": NOT_MEASURED,
            "evidence_hit_at_10": NOT_MEASURED,
            "final_answer_accuracy": NOT_MEASURED,
            "original_question_preserved": True,
            "search_queries": [], "per_query": [], "candidates": [],
            "documents": [], "excluded": [], "excluded_documents": [],
            "entity_resolution": [],
            "model_calls": 0, "planning_attempts": 0,
            "model_requests_sent": 0, "validated_plans": 0,
            "rejected_plans": 0, "provider_failures": 0,
            "pre_transport_failures": 0, "model_usage": None,
            "prompt_ms": None, "inference_ms": None,
            "retrieval_ms": None, "end_to_end_ms": None,
            "inference_provenance": "OFFLINE_SYNTHETIC" if synthetic else "NO_LLM",
        }
        if variant == "D" and self.d_index is None:
            report["status"] = D_NOT_RUN
            report["d_prerequisite_reason"] = self.d_preparation_reason
            report["inference_provenance"] = "NO_EMBEDDING_RUN"
            report["end_to_end_ms"] = round((perf_counter() - started) * 1000, 3)
            return report
        elapsed_retrieval = 0.
        phase = "retrieval"
        try:
            preplanned = None
            if variant == "B":
                report["route"] = {
                    "route": "plan", "reason": "always_plan", "formal_needs": [],
                }
                # The B control arm MUST plan BEFORE retrieval; a failed
                # model does not silently trigger a lexical fallback.
                phase = "planning"
                preplanned = self._planned(question, report)
                report["intent_plan"] = preplanned
                report["entity_resolution"] = resolve_entity_mentions(
                    preplanned["entity_mentions"], self.stand.snapshot, policy)
                report["inference_provenance"] = (
                    ("LOCAL_QWEN_RESPONSE_VALIDATED"
                     if not synthetic and type(self.planner) is LocalIntentPlanner
                     else "OFFLINE_SYNTHETIC"))
            phase = "retrieval"
            t0 = perf_counter()
            original, original_docs = self._search(question, policy)
            original_ms = (perf_counter() - t0) * 1000
            elapsed_retrieval += original_ms
            report["search_queries"].append(question)
            report["per_query"].append({
                "query_index": 0, "query": question,
                "retrieval_ms": round(original_ms, 3),
                "candidates": original, "documents": original_docs,
            })
            report["documents"] = original_docs
            if variant == "D":
                t0 = perf_counter()
                dense = self.d_index.search(question, policy)
                dense_ms = (perf_counter() - t0) * 1000
                elapsed_retrieval += dense_ms
                if len(dense) > TOP_K or any(
                    d["evidence_id"] not in self.records or
                    not _allowed_record(self.records[d["evidence_id"]], policy)
                    for d in dense
                ):
                    raise ExperimentError("d_policy_violation")
                report["per_query"].append({
                    "query_index": 1, "query": question, "channel": "dense",
                    "retrieval_ms": round(dense_ms, 3), "candidates": dense,
                })
                report["candidates"], report["excluded"] = fuse_ranked([original, dense])
                report["status"] = "CANDIDATES_RETRIEVED" if report["candidates"] else "NO_ELIGIBLE_EVIDENCE"
                report["inference_provenance"] = "REAL_LOCAL_ONNX"
            elif variant == "A":
                report["candidates"] = original
                report["status"] = "CANDIDATES_RETRIEVED" if original else "NO_ELIGIBLE_EVIDENCE"
                report["inference_provenance"] = "NO_LLM"
            else:
                if variant == "C":
                    phase = "routing"
                    decision = select_fast_path(question, original, self.stand.snapshot)
                    report["route"] = decision
                    phase = "retrieval"
                if report["route"]["route"] == "fast":
                    report["candidates"] = original
                    report["status"] = "CANDIDATES_RETRIEVED"
                    report["inference_provenance"] = "NO_LLM_PROVEN_FAST_PATH"
                else:
                    if variant == "B":
                        plan = preplanned
                    else:
                        phase = "planning"
                        plan = self._planned(question, report)
                        report["intent_plan"] = plan
                        report["entity_resolution"] = resolve_entity_mentions(
                            plan["entity_mentions"], self.stand.snapshot, policy)
                        report["inference_provenance"] = (
                            ("LOCAL_QWEN_RESPONSE_VALIDATED"
                     if not synthetic and type(self.planner) is LocalIntentPlanner
                     else "OFFLINE_SYNTHETIC"))
                    phase = "retrieval"
                    groups = [original]
                    doc_groups = [original_docs]
                    for expansion in plan["suggested_search_queries"]:
                        t0 = perf_counter()
                        candidates, documents = self._search(expansion, policy)
                        expansion_ms = (perf_counter() - t0) * 1000
                        elapsed_retrieval += expansion_ms
                        report["search_queries"].append(expansion)
                        report["per_query"].append({
                            "query_index": len(groups), "query": expansion,
                            "retrieval_ms": round(expansion_ms, 3),
                            "candidates": candidates, "documents": documents,
                        })
                        groups.append(candidates)
                        doc_groups.append(documents)
                    report["candidates"], report["excluded"] = fuse_ranked(groups)
                    report["documents"], report["excluded_documents"] = (
                        fuse_documents(doc_groups))
                    report["status"] = (
                        "CANDIDATES_RETRIEVED" if report["candidates"]
                        else "NO_ELIGIBLE_EVIDENCE")
            after = self._policy()
            if after != policy:
                raise ExperimentError("policy_revision_changed")
            report["retrieval_ms"] = round(elapsed_retrieval, 3)
        except Exception as exc:
            # A technical search/policy failure after successful planning is
            # NOT a planning failure. Never publish partial/policy-drifted hits.
            report["status"] = ("PLANNING_FAILED" if phase == "planning"
                                else "EXPERIMENT_FAILED")
            report["error_code"] = (
                str(exc)[:120] if type(exc) is ExperimentError
                else "experiment_runtime_" + type(exc).__name__
            )
            report["candidates"] = []
            report["documents"] = []
            report["per_query"] = []
            report["search_queries"] = []
            report["excluded"] = []
            report["excluded_documents"] = []
            report["retrieval_ms"] = round(elapsed_retrieval, 3)
        report["end_to_end_ms"] = round((perf_counter() - started) * 1000, 3)
        return report

    def iter_arms(self, cases: tuple[dict, ...],
                  variants=("A", "B", "C", "D"), *, synthetic: bool = False):
        """Yield each completed arm immediately; CLI must persist before next."""
        if len(cases) > 60 or len({c["case_id"] for c in cases}) != len(cases):
            raise ExperimentError("case_budget_or_identity")
        if not variants or len(set(variants)) != len(variants) or any(
                v not in VARIANTS for v in variants):
            raise ExperimentError("invalid_variants")
        for case in cases:
            for variant in variants:
                yield self.run_arm(case, variant, synthetic=synthetic)

    def summarize_results(self, cases, variants, results, *, synthetic=False):
        """No inference or retrieval; summarize only already durable rows."""
        results = tuple(results)
        expected = {(case["case_id"], variant)
                    for case in cases for variant in variants}
        actual = [(r["case_id"], r["variant"]) for r in results]
        if len(actual) != len(expected) or len(set(actual)) != len(actual) or (
                set(actual) != expected):
            raise ExperimentError("incomplete_paired_comparison")
        e4b = {
            "kind": "search_only",
            "A": "LEXICAL_BASELINE" if "A" in variants else "NOT_RUN",
            "D": (
                "SEMANTIC_HYBRID_MEASURED" if self.d_index and "D" in variants
                else D_NOT_RUN),
            "A_vs_D_hit_at_5": NOT_MEASURED,
            "A_vs_D_hit_at_10": NOT_MEASURED,
            "B_C_query_expansion_is_not_embedding_gain": True,
        }
        c_reports = [r for r in results if r["variant"] == "C"]
        e5b = {
            "kind": "intent_understanding",
            "A": NOT_MEASURED, "D": NOT_MEASURED,
            "intent_accuracy": NOT_MEASURED,
            "B_plan_attempts": sum(r["planning_attempts"] for r in results if r["variant"] == "B"),
            "C_plan_attempts": sum(r["planning_attempts"] for r in c_reports),
            "model_request_counts": {
                variant: {
                    key: sum(r[key] for r in results if r["variant"] == variant)
                    for key in (
                        "planning_attempts", "model_requests_sent", "validated_plans",
                        "rejected_plans", "provider_failures", "pre_transport_failures")
                } for variant in VARIANTS if variant in variants
            },
            "C_fast_path_count": sum(
                (r["route"] or {}).get("route") == "fast" for r in c_reports),
            "C_route_observation": (
                "C_ALWAYS_PLANNED_OBSERVED" if c_reports and all(
                    (r["route"] or {}).get("route") == "plan" for r in c_reports)
                else "MIXED_OR_NOT_MEASURED"),
            "all_intents_require_independent_human_labels": True,
        }
        return {
            "design_freeze": design_freeze(
                policy_revision=self.frozen_policy.revision),
            "stand_manifest": self.stand.manifest,
            "D_index_identity": self.d_index.identity if self.d_index else None,
            "quality_gate": "QUALITY_NOT_MEASURED_UNREVIEWED_DATASET",
            "real_model_inference": (
                not synthetic and any(
                    r["inference_provenance"] == "LOCAL_QWEN_RESPONSE_VALIDATED"
                    for r in results)),
            "model_inference_evidence": (
                "VALIDATED_LOCAL_QWEN_RESPONSE" if not synthetic and any(
                    r["inference_provenance"] == "LOCAL_QWEN_RESPONSE_VALIDATED"
                    for r in results) else "NOT_CONFIRMED"),
            "E4B": e4b, "E5B": e5b,
            "results": list(results),
        }

    def run(self, cases: tuple[dict, ...], variants=("A", "B", "C", "D"),
            *, synthetic: bool = False) -> dict:
        # Compatibility for offline unit tests. Live CLI uses iter_arms().
        return self.summarize_results(
            cases, variants, self.iter_arms(cases, variants, synthetic=synthetic),
            synthetic=synthetic,
        )
