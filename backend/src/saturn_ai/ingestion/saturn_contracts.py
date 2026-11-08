"""Canonical, immutable contracts for the trusted Saturn site source.

These are production-facing contracts. They intentionally contain no per-source
approval fields: source trust comes from the configured read-only repository root.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from pathlib import PurePosixPath


TRUSTED_SITE_REPOSITORY = "UkWood/Saturn-Main-Site"
TRUSTED_SITE_BRANCH = "main"
ADAPTER_VERSION = "saturn-site-adapter/0.1.0"
MAPPING_VERSION = "saturn-site-mapping/0.1.0"

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value) -> str:
    """Return stable JSON for hashes and lossless raw-value storage."""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("Value is not canonical-JSON serializable") from None


def stable_id(namespace: str, *parts) -> str:
    if not isinstance(namespace, str) or not namespace.strip():
        raise ValueError("Stable ID namespace is required")
    return sha256(canonical_json([namespace, *parts]).encode("utf-8")).hexdigest()


def _required_text(value, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{field} must be a non-empty string")


def _check_hash(value, pattern, field: str) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"Invalid {field}")


def _safe_source_path(value: str) -> str:
    _required_text(value, "source path")
    path = PurePosixPath(value)
    if (path.is_absolute() or "\\" in value or "%" in value or
            any(part in ("", ".", "..") for part in path.parts) or
            not value.startswith("src/")):
        raise ValueError("Unsafe source path")
    return path.as_posix()


def _canonical_json_text(value: str, expected_type=None) -> None:
    _required_text(value, "canonical JSON")
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Invalid canonical JSON") from None
    if canonical_json(parsed) != value:
        raise ValueError("JSON value is not canonically encoded")
    if expected_type is not None and not isinstance(parsed, expected_type):
        raise ValueError("Unexpected JSON value type")


@dataclass(frozen=True)
class SiteSourceRevision:
    repository: str
    branch: str
    commit_sha: str
    path: str
    blob_sha: str
    content_sha256: str

    def __post_init__(self):
        if self.repository != TRUSTED_SITE_REPOSITORY or self.branch != TRUSTED_SITE_BRANCH:
            raise ValueError("Unexpected Saturn source root")
        _check_hash(self.commit_sha, _SHA1, "Git commit SHA")
        _safe_source_path(self.path)
        _check_hash(self.blob_sha, _SHA1, "Git blob SHA")
        _check_hash(self.content_sha256, _SHA256, "content SHA-256")

    @property
    def revision_id(self) -> str:
        return stable_id("saturn-site-revision-v1", self.repository, self.branch,
                         self.commit_sha, self.path, self.blob_sha, self.content_sha256)


@dataclass(frozen=True)
class SiteEntity:
    entity_id: str
    collection: str
    slug: str
    entity_type: str
    title: str
    canonical_url: str | None
    draft: bool
    source_revision_id: str
    raw_frontmatter_json: str
    body: str

    def __post_init__(self):
        for field in ("entity_id", "collection", "slug", "entity_type", "title",
                      "source_revision_id"):
            _required_text(getattr(self, field), field)
        if type(self.draft) is not bool:
            raise ValueError("draft must be boolean")
        if self.canonical_url is not None:
            _required_text(self.canonical_url, "canonical_url")
        if not isinstance(self.body, str) or "\x00" in self.body:
            raise ValueError("Invalid Markdown body")
        _canonical_json_text(self.raw_frontmatter_json, dict)


@dataclass(frozen=True)
class SiteFact:
    fact_id: str
    entity_id: str
    field_path: str
    raw_value_json: str
    source_revision_id: str
    normalized_value_json: str | None = None
    unit: str | None = None
    qualifiers_json: str | None = None

    def __post_init__(self):
        for field in ("fact_id", "entity_id", "field_path", "source_revision_id"):
            _required_text(getattr(self, field), field)
        _canonical_json_text(self.raw_value_json)
        if self.normalized_value_json is not None:
            _canonical_json_text(self.normalized_value_json)
        if self.qualifiers_json is not None:
            _canonical_json_text(self.qualifiers_json, dict)
        if self.unit is not None:
            _required_text(self.unit, "unit")


@dataclass(frozen=True)
class SiteRelation:
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_revision_id: str
    source_field_path: str

    def __post_init__(self):
        for field in ("relation_id", "subject_entity_id", "predicate",
                      "object_entity_id", "source_revision_id", "source_field_path"):
            _required_text(getattr(self, field), field)


@dataclass(frozen=True)
class SupportDocument:
    document_id: str
    title: str
    kind: str
    url: str
    owner_entity_ids: tuple[str, ...]
    source_locators: tuple[str, ...]
    version: str | None = None
    date: str | None = None

    def __post_init__(self):
        for field in ("document_id", "title", "kind", "url"):
            _required_text(getattr(self, field), field)
        if type(self.owner_entity_ids) is not tuple or not self.owner_entity_ids:
            raise ValueError("A support document must retain at least one owner")
        if len(set(self.owner_entity_ids)) != len(self.owner_entity_ids):
            raise ValueError("Duplicate support document owner")
        if any(not isinstance(value, str) or not value.strip() for value in self.owner_entity_ids):
            raise ValueError("Invalid support document owner")
        if type(self.source_locators) is not tuple or not self.source_locators:
            raise ValueError("A support document must retain source locators")
        if len(set(self.source_locators)) != len(self.source_locators):
            raise ValueError("Duplicate support document locator")
        if any(not isinstance(value, str) or not value.strip() for value in self.source_locators):
            raise ValueError("Invalid support document locator")
        if self.version is not None:
            _required_text(self.version, "document version")
        if self.date is not None:
            _required_text(self.date, "document date")


@dataclass(frozen=True)
class PdfRevision:
    document_id: str
    url: str
    bytes_sha256: str
    parser_version: str
    extraction_state: str
    page_count: int | None = None
    extracted_text_sha256: str | None = None

    def __post_init__(self):
        for field in ("document_id", "url", "parser_version"):
            _required_text(getattr(self, field), field)
        _check_hash(self.bytes_sha256, _SHA256, "PDF bytes SHA-256")
        if self.extraction_state not in {"fetched", "extracted", "failed"}:
            raise ValueError("Invalid PDF extraction state")
        if self.page_count is not None and (type(self.page_count) is not int or self.page_count < 0):
            raise ValueError("Invalid PDF page count")
        if self.extraction_state == "extracted":
            if self.page_count is None or self.page_count < 1:
                raise ValueError("Extracted PDF requires physical pages")
            _check_hash(self.extracted_text_sha256, _SHA256, "extracted text SHA-256")
        elif self.extracted_text_sha256 is not None:
            raise ValueError("Text hash requires successful extraction")


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    evidence_type: str
    source_revision_id: str
    locator: str
    text: str
    entity_id: str | None = None
    page_number: int | None = None

    def __post_init__(self):
        for field in ("evidence_id", "evidence_type", "source_revision_id", "locator"):
            _required_text(getattr(self, field), field)
        if self.evidence_type not in {
            "entity", "site_field", "site_passage", "relation",
            "document_metadata", "pdf_passage"
        }:
            raise ValueError("Unknown evidence type")
        if not isinstance(self.text, str) or "\x00" in self.text:
            raise ValueError("Invalid evidence text")
        if self.entity_id is not None:
            _required_text(self.entity_id, "entity_id")
        if self.evidence_type == "pdf_passage":
            if type(self.page_number) is not int or self.page_number < 1:
                raise ValueError("PDF evidence requires a physical page number")
        elif self.page_number is not None:
            raise ValueError("Page number is only valid for PDF evidence")


@dataclass(frozen=True)
class SiteFileRevision:
    path: str
    blob_sha: str
    content_sha256: str
    collection: str | None = None
    slug: str | None = None

    def __post_init__(self):
        _safe_source_path(self.path)
        _check_hash(self.blob_sha, _SHA1, "Git blob SHA")
        _check_hash(self.content_sha256, _SHA256, "content SHA-256")
        if self.collection is not None:
            _required_text(self.collection, "collection")
        if self.slug is not None:
            _required_text(self.slug, "slug")


@dataclass(frozen=True)
class SchemaField:
    collection: str
    field_path: str
    value_type: str
    nullable: bool = False

    def __post_init__(self):
        for field in ("collection", "field_path", "value_type"):
            _required_text(getattr(self, field), field)
        if type(self.nullable) is not bool:
            raise ValueError("nullable must be boolean")


@dataclass(frozen=True)
class DictionaryFingerprint:
    path: str
    content_sha256: str

    def __post_init__(self):
        _safe_source_path(self.path)
        if not self.path.startswith("src/data/"):
            raise ValueError("Dictionary must be under src/data/")
        _check_hash(self.content_sha256, _SHA256, "dictionary SHA-256")


@dataclass(frozen=True)
class SchemaInventory:
    schema_source_sha256: str
    collections: tuple[str, ...]
    fields: tuple[SchemaField, ...]
    dictionaries: tuple[DictionaryFingerprint, ...]

    def __post_init__(self):
        _check_hash(self.schema_source_sha256, _SHA256, "schema source SHA-256")
        if (type(self.collections) is not tuple or
                any(not isinstance(name, str) or not name.strip() for name in self.collections) or
                tuple(sorted(set(self.collections))) != self.collections):
            raise ValueError("Collections must be unique, non-empty and sorted")
        if (type(self.fields) is not tuple or
                any(not isinstance(item, SchemaField) for item in self.fields) or
                tuple(sorted(self.fields, key=lambda x: (x.collection, x.field_path))) != self.fields):
            raise ValueError("Schema fields must be sorted SchemaField values")
        field_keys = [(f.collection, f.field_path) for f in self.fields]
        if len(field_keys) != len(set(field_keys)):
            raise ValueError("Duplicate schema field")
        if (type(self.dictionaries) is not tuple or
                any(not isinstance(item, DictionaryFingerprint) for item in self.dictionaries) or
                tuple(sorted(self.dictionaries, key=lambda x: x.path)) != self.dictionaries):
            raise ValueError("Dictionary fingerprints must be sorted")
        dict_paths = [d.path for d in self.dictionaries]
        if len(dict_paths) != len(set(dict_paths)):
            raise ValueError("Duplicate dictionary path")


@dataclass(frozen=True)
class SchemaDriftEvent:
    kind: str
    severity: str
    subject: str
    before: str | None = None
    after: str | None = None

    def __post_init__(self):
        for field in ("kind", "severity", "subject"):
            _required_text(getattr(self, field), field)
        if self.severity not in {"info", "warning", "breaking"}:
            raise ValueError("Invalid schema drift severity")


@dataclass(frozen=True)
class FileChangeSet:
    added: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()

    def __post_init__(self):
        groups = (self.added, self.changed, self.deleted)
        for group in groups:
            if type(group) is not tuple or tuple(sorted(set(group))) != group:
                raise ValueError("File change paths must be unique and sorted")
        if set(self.added) & set(self.changed) or set(self.added) & set(self.deleted) or set(self.changed) & set(self.deleted):
            raise ValueError("File change categories must be disjoint")


@dataclass(frozen=True)
class SiteSyncManifest:
    repository: str
    branch: str
    commit_sha: str
    tree_sha: str
    adapter_version: str
    mapping_version: str
    schema_inventory: SchemaInventory
    file_revisions: tuple[SiteFileRevision, ...]
    snapshot_id: str

    def __post_init__(self):
        if self.repository != TRUSTED_SITE_REPOSITORY or self.branch != TRUSTED_SITE_BRANCH:
            raise ValueError("Unexpected site repository or branch")
        _check_hash(self.commit_sha, _SHA1, "Git commit SHA")
        _check_hash(self.tree_sha, _SHA1, "Git tree SHA")
        _required_text(self.adapter_version, "adapter_version")
        _required_text(self.mapping_version, "mapping_version")
        _check_hash(self.snapshot_id, _SHA256, "snapshot ID")
        if not isinstance(self.schema_inventory, SchemaInventory):
            raise ValueError("Schema inventory is required")
        if (type(self.file_revisions) is not tuple or
                any(not isinstance(item, SiteFileRevision) for item in self.file_revisions) or
                tuple(sorted(self.file_revisions, key=lambda x: x.path)) != self.file_revisions):
            raise ValueError("File revisions must be sorted SiteFileRevision values")
        paths = [item.path for item in self.file_revisions]
        if len(paths) != len(set(paths)):
            raise ValueError("Duplicate source file path")
        payload = {
            "repository": self.repository,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "tree_sha": self.tree_sha,
            "schema_inventory": asdict(self.schema_inventory),
            "file_revisions": [asdict(item) for item in self.file_revisions],
            "adapter_version": self.adapter_version,
            "mapping_version": self.mapping_version,
        }
        expected_snapshot_id = stable_id("saturn-site-snapshot-v1", payload)
        if self.snapshot_id != expected_snapshot_id:
            raise ValueError("Snapshot ID does not match manifest contents")


@dataclass(frozen=True)
class SiteSyncPlan:
    manifest: SiteSyncManifest
    file_changes: FileChangeSet
    schema_drift: tuple[SchemaDriftEvent, ...]

    def __post_init__(self):
        if not isinstance(self.manifest, SiteSyncManifest) or not isinstance(self.file_changes, FileChangeSet):
            raise ValueError("Invalid sync plan")
        if (type(self.schema_drift) is not tuple or
                any(not isinstance(item, SchemaDriftEvent) for item in self.schema_drift)):
            raise ValueError("Schema drift events must be immutable SchemaDriftEvent values")
