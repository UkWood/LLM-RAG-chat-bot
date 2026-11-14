"""Immutable Saturn Knowledge Snapshot v0.1 contracts.

The trusted source and three adapters have independent contracts. This module
does not change them or legacy synthetic snapshots.
"""
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from threading import RLock

from .ingestion.saturn_contracts import (
    EvidenceUnit, PdfRevision, SiteEntity, SiteFact, SiteRelation,
    SiteSourceRevision, SiteSyncManifest, SupportDocument, stable_id,
    canonical_json,
)
from .ingestion.saturn_site_adapter import (
    RawSiteRecord, SiteDictionary, SiteContentPackage,
)
from .ingestion.support_catalog_adapter import CatalogOccurrence, SupportCatalogResult
from .ingestion.external_document_adapter import (
    DocumentAssociation, DocumentDiagnostic, DocumentStatus,
    ExternalDocumentResult,
)

BUILDER_VERSION = "saturn-unified-snapshot/0.1.0"


@dataclass(frozen=True)
class SnapshotIssue:
    code: str
    subject: str
    severity: str = "error"


class SnapshotBuildError(ValueError):
    def __init__(self, issues: tuple[SnapshotIssue, ...]):
        self.issues = issues
        super().__init__("Saturn knowledge snapshot rejected: " +
                         ", ".join(sorted({x.code for x in issues})))


@dataclass(frozen=True)
class EvidencePointer:
    evidence_id: str
    canonical_kind: str
    canonical_id: str
    canonical_url: str | None


@dataclass(frozen=True)
class DocumentMatch:
    """Document metadata lookup; not an engineering answer evidence unit."""
    document: SupportDocument
    occurrences: tuple[CatalogOccurrence, ...]
    extraction_status: str | None
    pdf_revision_id: str | None


@dataclass(frozen=True)
class SaturnSnapshotManifest:
    site_manifest: SiteSyncManifest
    site_parser_version: str
    catalog_version: str
    pdf_parser_version: str
    builder_version: str
    source_revision_ids: tuple[str, ...]
    pdf_revision_states: tuple[tuple[str, str, str], ...]
    counts: tuple[tuple[str, int], ...]
    corpus_hash: str
    snapshot_id: str


SCOPED_SELECTION_VERSION = "saturn-scoped-selection/0.1.0"


@dataclass(frozen=True)
class SaturnScopedExperiment:
    """Immutable opt-in scope sourced from one pinned Site Content Package.

    The digest is a selection identity, NOT a proof that the documents belong
    to the source. Independent full-catalog reconstruction supplies that proof.
    """
    mode: str
    source_commit: str
    source_tree: str
    selected_document_ids: tuple[str, ...]
    selected_pdf_urls: tuple[str, ...]
    selection_version: str
    scope_digest: str

    def __post_init__(self):
        from re import fullmatch
        if (self.mode != "scoped_experiment" or
                self.selection_version != SCOPED_SELECTION_VERSION or
                type(self.source_commit) is not str or
                not fullmatch(r"[0-9a-f]{40}", self.source_commit) or
                type(self.source_tree) is not str or
                not fullmatch(r"[0-9a-f]{40}", self.source_tree)):
            raise ValueError("Invalid scoped experiment identity")
        for values in (self.selected_document_ids, self.selected_pdf_urls):
            if (type(values) is not tuple or not values or
                    any(type(v) is not str or not v for v in values) or
                    tuple(sorted(set(values))) != values):
                raise ValueError("Scope entries must be nonempty, unique, sorted strings")
        if len(self.selected_document_ids) != len(self.selected_pdf_urls):
            raise ValueError("Scope document IDs / URL cardinality mismatch")
        if self.scope_digest != stable_id("saturn-scoped-selection-v1", self.payload()):
            raise ValueError("Scoped selection digest mismatch")

    def payload(self):
        return {
            "mode": self.mode,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "selected_document_ids": list(self.selected_document_ids),
            "selected_pdf_urls": list(self.selected_pdf_urls),
            "selection_version": self.selection_version,
        }


def define_scoped_experiment(site: SiteContentPackage, candidates) -> SaturnScopedExperiment:
    """Declare an experimental PDF subset; source membership is checked later."""
    if not isinstance(site, SiteContentPackage):
        raise TypeError("Pinned site package required")
    entries = tuple(candidates)
    ids = tuple(sorted(x.document_id for x in entries))
    urls = tuple(sorted(x.resolved_url for x in entries))
    payload = {
        "mode": "scoped_experiment",
        "source_commit": site.manifest.commit_sha,
        "source_tree": site.manifest.tree_sha,
        "selected_document_ids": list(ids),
        "selected_pdf_urls": list(urls),
        "selection_version": SCOPED_SELECTION_VERSION,
    }
    return SaturnScopedExperiment(
        payload["mode"], payload["source_commit"], payload["source_tree"],
        ids, urls, SCOPED_SELECTION_VERSION,
        stable_id("saturn-scoped-selection-v1", payload),
    )


@dataclass(frozen=True)
class SnapshotValidationSources:
    """Immutable builder inputs retained for structural activation replay.

    The content hash alone cannot authenticate fields or a forged re-seal;
    activation independently reconstructs the entire candidate from the same
    frozen inputs and compares all projections, pointers and manifest fields.
    """
    site: SiteContentPackage
    catalog: SupportCatalogResult
    external: ExternalDocumentResult
    scope: SaturnScopedExperiment | None = None


@dataclass(frozen=True)
class SaturnKnowledgeSnapshot:
    source_revisions: tuple[SiteSourceRevision, ...]
    source_records: tuple[RawSiteRecord, ...]
    entities: tuple[SiteEntity, ...]
    facts: tuple[SiteFact, ...]
    relations: tuple[SiteRelation, ...]
    unresolved_relations: tuple[SiteRelation, ...]
    dictionaries: tuple[SiteDictionary, ...]
    support_documents: tuple[SupportDocument, ...]
    document_occurrences: tuple[CatalogOccurrence, ...]
    document_associations: tuple[DocumentAssociation, ...]
    pdf_revisions: tuple[PdfRevision, ...]
    pdf_statuses: tuple[DocumentStatus, ...]
    pdf_diagnostics: tuple[DocumentDiagnostic, ...]
    answer_evidence: tuple[EvidenceUnit, ...]
    evidence_pointers: tuple[EvidencePointer, ...]
    document_matches: tuple[DocumentMatch, ...]
    diagnostics: tuple[SnapshotIssue, ...]
    readiness_gates: tuple[bool, bool, bool]
    manifest: SaturnSnapshotManifest
    validation_sources: SnapshotValidationSources = field(compare=False, repr=False)
    scope: SaturnScopedExperiment | None = None

    @property
    def snapshot_id(self) -> str:
        return self.manifest.snapshot_id

    @property
    def ready_for_promotion(self) -> bool:
        return all(self.readiness_gates) and not any(
            issue.severity == "error" for issue in self.diagnostics
        )


@dataclass(frozen=True)
class SaturnSnapshotBuildResult:
    candidate: SaturnKnowledgeSnapshot | None
    issues: tuple[SnapshotIssue, ...]

    @property
    def ready_for_promotion(self) -> bool:
        return self.candidate is not None and self.candidate.ready_for_promotion


def sorted_canonical(items):
    return tuple(sorted(items, key=lambda item: canonical_json(asdict(item))))


def dictionary_payload(dictionary: SiteDictionary):
    return {
        "path": dictionary.path,
        "source_revision_id": dictionary.source_revision_id,
        "sha256": sha256(dictionary.content).hexdigest(),
        "raw_yaml_text": dictionary.raw_yaml_text,
        "raw_value_json": dictionary.raw_value_json,
    }


def source_record_payload(record: RawSiteRecord):
    return {
        "path": record.path, "source_revision_id": record.source_revision_id,
        "collection": record.collection, "slug": record.slug,
        "content_sha256": sha256(record.content).hexdigest(),
        "raw_frontmatter_text": record.raw_frontmatter_text,
        "body": record.body, "draft": record.draft,
    }


def snapshot_content(snapshot: SaturnKnowledgeSnapshot):
    groups = (
        "source_revisions", "entities", "facts", "relations",
        "unresolved_relations", "support_documents", "document_occurrences",
        "document_associations", "pdf_revisions", "pdf_statuses",
        "pdf_diagnostics", "answer_evidence", "evidence_pointers",
        "document_matches", "diagnostics",
    )
    data = {name: [asdict(item) for item in getattr(snapshot, name)]
            for name in groups}
    data["source_records"] = [source_record_payload(x) for x in snapshot.source_records]
    data["dictionaries"] = [dictionary_payload(x) for x in snapshot.dictionaries]
    data["readiness_gates"] = list(snapshot.readiness_gates)
    return data


def verify_snapshot_seal(snapshot: SaturnKnowledgeSnapshot) -> bool:
    """Recheck full content identity when a candidate is activated."""
    try:
        manifest = snapshot.manifest
        if not isinstance(manifest, SaturnSnapshotManifest):
            return False
        if snapshot.scope is None:
            corpus = stable_id("saturn-unified-corpus-v1", snapshot_content(snapshot))
        elif isinstance(snapshot.scope, SaturnScopedExperiment):
            snapshot.scope.__post_init__()
            corpus = stable_id("saturn-scoped-corpus-v1", {
                "mode": snapshot.scope.mode, "scope_digest": snapshot.scope.scope_digest,
                "content": snapshot_content(snapshot),
            })
        else:
            return False
        if corpus != manifest.corpus_hash:
            return False
        unsigned = {key: value for key, value in asdict(manifest).items()
                    if key != "snapshot_id"}
        if snapshot.scope is None:
            identity = stable_id("saturn-unified-snapshot-v1", unsigned)
        else:
            identity = stable_id("saturn-scoped-snapshot-v1", {
                "scope": asdict(snapshot.scope), "manifest": unsigned,
            })
        return manifest.snapshot_id == identity
    except (TypeError, ValueError, AttributeError):
        return False


class SaturnSnapshotManager:
    """Thread-safe in-memory atomic pointer; never mutates the active snapshot."""

    def __init__(self):
        self._lock = RLock()
        self._active: SaturnKnowledgeSnapshot | None = None

    def capture(self) -> SaturnKnowledgeSnapshot:
        with self._lock:
            if self._active is None:
                raise LookupError("No active Saturn Knowledge Snapshot")
            return self._active

    def activate(self, candidate: SaturnKnowledgeSnapshot) -> str:
        if (not isinstance(candidate, SaturnKnowledgeSnapshot) or
                not candidate.ready_for_promotion or not verify_snapshot_seal(candidate) or
                not isinstance(candidate.validation_sources, SnapshotValidationSources)):
            raise SnapshotBuildError((SnapshotIssue("activation_rejected", "candidate"),))
        # A malicious caller can recompute corpus_hash and snapshot_id after
        # modifying a snapshot. The only valid activation proof is complete
        # offline structural reconstruction from the preserved builder inputs.
        # Rebuilding covers source bytes, catalog, PDF pages, all evidence,
        # pointers, manifest counts, statuses and readiness gates.
        from .saturn_knowledge_snapshot import stage_saturn_knowledge_snapshot
        inputs = candidate.validation_sources
        try:
            fresh = stage_saturn_knowledge_snapshot(
                inputs.site, inputs.catalog, inputs.external, scope=inputs.scope)
            if (not fresh.ready_for_promotion or fresh.candidate != candidate):
                raise SnapshotBuildError((
                    SnapshotIssue("activation_structure_mismatch", "candidate"),))
        except (TypeError, ValueError, AttributeError, KeyError, IndexError) as exc:
            if isinstance(exc, SnapshotBuildError):
                raise
            raise SnapshotBuildError((
                SnapshotIssue("activation_structure_mismatch", type(exc).__name__),)) from None
        with self._lock:
            self._active = candidate
            return candidate.snapshot_id
