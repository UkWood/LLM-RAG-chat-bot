"""Explicit, source-pinned experimental Saturn corpus (Stage 5F).

This is an adapter composition over the existing 3A-5E implementation, not an
alternative ingestion or answer pipeline. It is intentionally opt-in: fetching
the real site and executing a development-only PDF worker require CLI flags.
The pinned, read-only GitHub provider still verifies every fetched Git blob.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from ..evaluation.saturn_grounding import SaturnEvaluationProfile, _run_question
from ..grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from ..grounding.saturn_claim_provider import SaturnFakeClaimProvider
from ..grounding.saturn_local_provider import SaturnLocalClaimProvider, SaturnLocalModelConfig
from ..grounding.saturn_generation import SaturnClaimVerificationService
from ..grounding.saturn_sufficiency_gate import SaturnQuestionGate
from ..ingestion.external_document_adapter import adapt_external_documents
from ..ingestion.external_document_extractor import SubprocessPdfExtractor
from ..ingestion.external_document_transport import DocumentFetchPolicy
from ..ingestion.github_snapshot_provider import GitHubSnapshotProvider
from ..ingestion.saturn_site_adapter import PinnedSiteSnapshot, adapt_snapshot
from ..ingestion.schema_evolution import is_route_source_path
from ..ingestion.support_catalog_adapter import SupportCatalogResult, adapt_support_catalog
from ..retrieval.saturn_channel import SaturnRetrievalService, build_saturn_retrieval_bundle
from ..saturn_knowledge_snapshot import build_saturn_knowledge_snapshot


STAND_VERSION = "saturn-real-integration-stand/0.1.0"
SOURCE_COMMIT = "084d759487bfab6e111549c9b5469711ac5fc13e"
SOURCE_REPOSITORY = "UkWood/Saturn-Main-Site"

# 10 source records + 4 linked PDFs: selected by engineering coverage,
# not by an evaluation dataset or model performance.
CONTENT_PATHS = (
    "src/content/groups/easdkiu.md",
    "src/content/groups/newel.md",
    "src/content/groups/programmnoe-obespechenie.md",
    "src/content/products/bkd-pk-rf-2.md",
    "src/content/products/bkd-ups.md",
    "src/content/products/server-lanmon.md",
    "src/content/systems/informatsionno-izmeritelnaya-sistema-easdkiu.md",
    "src/content/systems/newel.md",
    "src/content/systems/programmnoe-obespechenie.md",
    "src/content/systems/sistema-liftovogo-dispetcherskogo-kontrolya-sldks-1.md",
)
PDF_PATHS = (
    "/ftp/public/doc/bkd-pk-rf2/re%20BKD-PK-RF2.pdf",
    "/ftp/public/doc/bkd-ups/re%20bkd-UPS3.pdf",
    "/ftp/public/doc/sldks/re%20SLDKS-1%20p1(3).pdf",
    "/ftp/public/soft/lmserver/user%20manual%20%20LMS.pdf",
)
ESSENTIAL_FILES = frozenset(("astro.config.mjs", "src/content.config.ts"))


class RealCorpusIntegrityError(RuntimeError):
    """A missing, changed or incomplete real-source experiment is not PASS."""


def select_site_snapshot(
    verified: PinnedSiteSnapshot, *,
    expected_commit: str = SOURCE_COMMIT,
    content_paths: tuple[str, ...] = CONTENT_PATHS,
) -> PinnedSiteSnapshot:
    """Retain exact verified Git files. Never synthesize Git object identities."""
    if not isinstance(verified, PinnedSiteSnapshot):
        raise TypeError("A provider-verified PinnedSiteSnapshot is required")
    if verified.commit_sha != expected_commit:
        raise RealCorpusIntegrityError("source_commit_mismatch")
    if not content_paths or len(set(content_paths)) != len(content_paths):
        raise RealCorpusIntegrityError("invalid_sample_selection")
    if any(not p.startswith("src/content/") or not p.endswith(".md")
           for p in content_paths):
        raise RealCorpusIntegrityError("unsafe_sample_path")
    by_path = {item.path: item for item in verified.files}
    missing = sorted((set(content_paths) | ESSENTIAL_FILES) - set(by_path))
    if missing:
        raise RealCorpusIntegrityError("missing_verified_source_paths:" + ",".join(missing))
    selected = [
        item for item in verified.files
        if item.path in content_paths or item.path in ESSENTIAL_FILES
        or is_route_source_path(item.path)
        or (item.path.startswith("src/data/") and
            item.path.lower().endswith((".yaml", ".yml")))
    ]
    return PinnedSiteSnapshot(
        repository=verified.repository, branch=verified.branch,
        commit_sha=verified.commit_sha, tree_sha=verified.tree_sha,
        files=tuple(sorted(selected, key=lambda file: file.path)),
    )


def select_pdf_catalog(
    catalog: SupportCatalogResult, *,
    pdf_paths: tuple[str, ...] = PDF_PATHS,
) -> SupportCatalogResult:
    """Restrict external downloads to exact declared PDF paths in this sample.

    Unselected documents are NOT silently represented as extracted PDF
    evidence: this is an explicitly bounded experiment, not a full sync.
    """
    if not isinstance(catalog, SupportCatalogResult) or not catalog.ready_for_promotion:
        raise RealCorpusIntegrityError("source_support_catalog_not_ready")
    if not pdf_paths or len(set(pdf_paths)) != len(pdf_paths):
        raise RealCorpusIntegrityError("invalid_pdf_selection")
    if any(not path.startswith("/ftp/") or not path.endswith(".pdf")
           for path in pdf_paths):
        raise RealCorpusIntegrityError("unsafe_pdf_sample_path")
    selected = tuple(candidate for candidate in catalog.pdf_candidates
                     if urlsplit(candidate.resolved_url).path in pdf_paths)
    found_paths = [urlsplit(candidate.resolved_url).path for candidate in selected]
    if set(found_paths) != set(pdf_paths) or len(found_paths) != len(pdf_paths):
        raise RealCorpusIntegrityError("missing_or_ambiguous_source_pdf")
    ids = {candidate.document_id for candidate in selected}
    return SupportCatalogResult(
        documents=tuple(doc for doc in catalog.documents if doc.document_id in ids),
        pdf_candidates=selected,
        occurrences=tuple(item for item in catalog.occurrences if item.document_id in ids),
        issues=catalog.issues, upstream_ready=catalog.upstream_ready,
        catalog_version=catalog.catalog_version,
    )


def real_pdf_policy() -> DocumentFetchPolicy:
    """Network allowlist, SSRF protection and hard limits are enforced by 3B."""
    return DocumentFetchPolicy(
        allowed_hosts=("www.mnppsaturn.ru",),
        allowed_path_prefixes=("/ftp",),
        max_requests=len(PDF_PATHS), max_attempts=1,
        max_pdf_bytes=16 * 1024 * 1024, max_pages=200,
        worker_wall_seconds=60, worker_cpu_seconds=20,
    )


@dataclass(frozen=True)
class RealStand:
    snapshot: object
    bundle: object
    manifest: dict


def prepare_real_stand(*, provider: GitHubSnapshotProvider,
                       enable_development_pdf_worker: bool) -> RealStand:
    """Real fetch + real extraction + exact production snapshot/index builders."""
    if type(enable_development_pdf_worker) is not bool or not enable_development_pdf_worker:
        raise RealCorpusIntegrityError("development_pdf_worker_opt_in_required")
    pinned = select_site_snapshot(provider.fetch_snapshot())
    site = adapt_snapshot(pinned)
    if not site.ready_for_promotion:
        raise RealCorpusIntegrityError("site_adapter_not_ready")
    catalog = select_pdf_catalog(adapt_support_catalog(site))
    external = adapt_external_documents(
        catalog, real_pdf_policy(),
        extractor=SubprocessPdfExtractor(enable_development_worker=True),
    )
    # No fabricated empty PDFs. Even a single failed download/parse aborts
    # publication; diagnostic status remains explicit to the CLI caller.
    if not external.ready_for_promotion:
        diagnostics = sorted({item.code for item in external.diagnostics})
        raise RealCorpusIntegrityError(
            "real_pdf_ingestion_incomplete:" + ",".join(diagnostics))
    snapshot = build_saturn_knowledge_snapshot(site, catalog, external)
    bundle = build_saturn_retrieval_bundle(snapshot)
    bundle.validate()
    pdf_by_document = {rev.document_id: rev for rev in external.revisions}
    manifest = {
        "stand_version": STAND_VERSION,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": pinned.commit_sha,
        "source_tree": pinned.tree_sha,
        "selected_content_paths": list(CONTENT_PATHS),
        "selected_pdf_paths": list(PDF_PATHS),
        "selected_files": [
            {"path": file.path, "git_blob_sha1": file.blob_sha,
             "content_sha256": file.content_sha256}
            for file in pinned.files
        ],
        "pdf_revisions": [
            {"document_id": rev.document_id, "url": rev.url,
             "bytes_sha256": rev.bytes_sha256,
             "parser_version": rev.parser_version,
             "page_count": rev.page_count,
             "extraction_state": rev.extraction_state}
            for rev in sorted(pdf_by_document.values(), key=lambda r: r.document_id)
        ],
        "site_parser_version": site.parser_version,
        "site_adapter_version": site.manifest.adapter_version,
        "mapping_version": site.manifest.mapping_version,
        "catalog_version": catalog.catalog_version,
        "pdf_parser_version": external.parser_version,
        "corpus_hash": snapshot.manifest.corpus_hash,
        "snapshot_id": snapshot.snapshot_id,
        "retrieval_bundle_id": bundle.manifest.bundle_id,
        "counts": dict(snapshot.manifest.counts),
        "pdf_statuses": [
            {"document_id": s.document_id, "status": s.status}
            for s in external.statuses
        ],
        "independent_blind_evaluation": "NOT_RUN",
        "model_status": "NOT_CONNECTED",
    }
    return RealStand(snapshot, bundle, manifest)


def run_question(stand: RealStand, question: str, *,
                 draft_provider=None) -> dict:
    """Run the existing Stage 4B-5D path, never passing gold to the provider."""
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("invalid_question")
    service = SaturnRetrievalService()
    service.publish(stand.bundle)
    provider = draft_provider if draft_provider is not None else SaturnFakeClaimProvider()
    if type(provider) not in (SaturnFakeClaimProvider, SaturnLocalClaimProvider):
        raise ValueError("unapproved_draft_provider")
    verifier = SaturnClaimVerificationService(provider=provider)
    assembly = SaturnAnswerAssemblyService(verifier=verifier)
    answer, trace = _run_question(
        service, assembly, SaturnQuestionGate(), verifier,
        question, SaturnEvaluationProfile("real_sample"),
    )
    if type(provider) is SaturnLocalClaimProvider:
        profile = "real_source_local_llm"
        local = {
            "model_id": provider.config.model_id,
            "declared_model_sha256": provider.config.declared_model_sha256,
            "model_digest_server_verified": False,
            "successful_inference_requests": provider.successful_requests,
            "latencies_ms": list(provider.latencies_ms),
            "token_usage": provider.last_usage,
            "actual_inference_status": (
                "INVOKED" if provider.successful_requests else "NOT_CONFIRMED"),
        }
    else:
        profile, local = "real_source_fake_baseline", None
    return {
        "profile": profile,
        "provider": type(provider).__name__,
        "local_inference": local,
        "answer": asdict(answer),
        "stage_trace": asdict(trace),
        "independent_blind_evaluation": "NOT_RUN",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in real Saturn integration experiment")
    parser.add_argument("--allow-real-network", action="store_true")
    parser.add_argument("--allow-development-pdf-worker", action="store_true")
    parser.add_argument("--provider", choices=("fake", "local_llm"), default="fake")
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--local-endpoint")
    parser.add_argument("--local-model-id")
    parser.add_argument("--local-model-sha256")
    parser.add_argument("--question", help="One question (no gold or expected answer)")
    parser.add_argument("--report", type=Path, help="Exclusive local JSON report")
    args = parser.parse_args(argv)
    if not (args.allow_real_network and args.allow_development_pdf_worker):
        parser.error("Real source fetch and development PDF worker both require explicit opt-in")
    if args.provider == "local_llm" and (
            not args.allow_local_inference or not args.question
            or not args.local_endpoint or not args.local_model_id
            or not args.local_model_sha256):
        parser.error("Local inference requires opt-in, a question, exact loopback endpoint, model ID and declared weight SHA-256")
    try:
        if args.provider == "local_llm":
            draft_provider = SaturnLocalClaimProvider(SaturnLocalModelConfig(
                endpoint=args.local_endpoint, model_id=args.local_model_id,
                declared_model_sha256=args.local_model_sha256,
            ))
        else:
            draft_provider = SaturnFakeClaimProvider()
        stand = prepare_real_stand(
            provider=GitHubSnapshotProvider.from_env(),
            enable_development_pdf_worker=True,
        )
        result = {"manifest": stand.manifest}
        if args.question is not None:
            result["question_run"] = run_question(
                stand, args.question, draft_provider=draft_provider)
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")) + "\n"
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            # No silent overwrite of prior observations.
            with args.report.open("x", encoding="utf-8") as output:
                output.write(serialized)
        print(serialized, end="")
        return 0
    except (RealCorpusIntegrityError, ValueError) as exc:
        print("REAL_STAND_NOT_READY: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
