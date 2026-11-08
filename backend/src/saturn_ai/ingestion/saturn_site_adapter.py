"""Pure/offline adapter for the trusted Saturn-Main-Site Markdown snapshot.

The adapter consumes an already pinned Git snapshot. It never performs network
access, executes Astro/TypeScript, downloads documents, or uses the legacy
SourceRecord/Registry approval workflow.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha1, sha256
import math
from pathlib import PurePosixPath
import re

import yaml
from yaml.tokens import AliasToken, AnchorToken, TagToken

from .saturn_contracts import (
    ADAPTER_VERSION,
    MAPPING_VERSION,
    DictionaryFingerprint,
    SiteEntity,
    SiteFact,
    SiteFileRevision,
    SiteRelation,
    SiteSourceRevision,
    SiteSyncManifest,
    SiteSyncPlan,
    TRUSTED_SITE_BRANCH,
    TRUSTED_SITE_REPOSITORY,
    canonical_json,
    stable_id,
)
from .schema_evolution import build_schema_inventory, build_sync_manifest, plan_sync


PARSER_VERSION = "saturn-site-parser/0.1.0"
MAX_MARKDOWN_BYTES = 1_000_000
MAX_DICTIONARY_BYTES = 2_000_000
MAX_FRONTMATTER_BYTES = 262_144
MAX_YAML_TOKENS = 20_000
MAX_YAML_NODES = 50_000
MAX_YAML_DEPTH = 32
SOFTWARE_GROUP_SLUG = "programmnoe-obespechenie"

# Only source-declared references are projected. In particular, pages.groups is
# deliberately absent: it is a navigation tree, not an engineering relation.
_RELATION_FIELDS = {
    "products": {
        "group": ("groups", "one"),
        "systems": ("systems", "many"),
        "related": ("products", "many"),
        "variant_of": ("products", "one"),
        "software": ("products", "many"),
        "articles": ("articles", "many"),
        "solutions": ("pages", "many"),
    },
    "systems": {
        "articles": ("articles", "many"),
        "solutions": ("pages", "many"),
    },
    "groups": {
        "system": ("systems", "one"),
    },
    "articles": {
        "products": ("products", "many"),
        "systems": ("systems", "many"),
    },
    "news": {
        "products": ("products", "many"),
    },
    "pages": {
        "systems": ("systems", "many"),
        "products": ("products", "many"),
    },
}

# Units are explicit in the audited source field names. Raw values are always
# retained independently; this mapping does not normalize or convert them.
_FIELD_UNITS = {
    "temperature_c": "°C",
    "mass_kg": "kg",
    "dimensions_mm": "mm",
    "lifetime_years": "years",
}


class SnapshotValidationError(ValueError):
    """The supplied snapshot is not a valid immutable trusted-site snapshot."""


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    blob_sha: str
    content: bytes

    def __post_init__(self):
        if type(self.content) is not bytes:
            raise SnapshotValidationError("Snapshot file content must be bytes")
        try:
            SiteFileRevision(self.path, self.blob_sha, sha256(self.content).hexdigest())
        except ValueError as exc:
            raise SnapshotValidationError(str(exc)) from None
        if git_blob_sha1(self.content) != self.blob_sha:
            raise SnapshotValidationError(f"Git blob SHA does not match bytes: {self.path}")

    @property
    def content_sha256(self) -> str:
        return sha256(self.content).hexdigest()


@dataclass(frozen=True)
class PinnedSiteSnapshot:
    repository: str
    branch: str
    commit_sha: str
    tree_sha: str
    files: tuple[SnapshotFile, ...]

    def __post_init__(self):
        if self.repository != TRUSTED_SITE_REPOSITORY or self.branch != TRUSTED_SITE_BRANCH:
            raise SnapshotValidationError("Unexpected Saturn trust root")
        if not isinstance(self.commit_sha, str) or re.fullmatch(r"[0-9a-f]{40}", self.commit_sha) is None:
            raise SnapshotValidationError("Invalid source commit SHA")
        if not isinstance(self.tree_sha, str) or re.fullmatch(r"[0-9a-f]{40}", self.tree_sha) is None:
            raise SnapshotValidationError("Invalid source tree SHA")
        if type(self.files) is not tuple or any(not isinstance(item, SnapshotFile) for item in self.files):
            raise SnapshotValidationError("Snapshot files must be an immutable tuple")
        if tuple(sorted(self.files, key=lambda item: item.path)) != self.files:
            raise SnapshotValidationError("Snapshot files must be sorted by path")
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise SnapshotValidationError("Duplicate snapshot path")

    @classmethod
    def from_mapping(
        cls,
        *,
        commit_sha: str,
        tree_sha: str,
        files: Mapping[str, tuple[str, bytes]],
        repository: str = TRUSTED_SITE_REPOSITORY,
        branch: str = TRUSTED_SITE_BRANCH,
    ) -> "PinnedSiteSnapshot":
        """Build a pinned snapshot from path -> (Git blob SHA, bytes)."""
        if not isinstance(files, Mapping):
            raise SnapshotValidationError("Snapshot file map is required")
        entries = tuple(
            SnapshotFile(path, value[0], value[1])
            for path, value in sorted(files.items())
        )
        return cls(repository, branch, commit_sha, tree_sha, entries)


@dataclass(frozen=True)
class SiteParseIssue:
    path: str
    stage: str
    code: str
    message: str
    severity: str = "error"

    def __post_init__(self):
        for name in ("path", "stage", "code", "message"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        if self.severity not in {"warning", "error"}:
            raise ValueError("Invalid issue severity")


@dataclass(frozen=True)
class RawSiteRecord:
    path: str
    source_revision_id: str
    collection: str | None
    slug: str | None
    content: bytes
    raw_frontmatter_text: str | None
    body: str | None
    draft: bool | None


@dataclass(frozen=True)
class SiteDictionary:
    path: str
    source_revision_id: str
    content: bytes
    raw_yaml_text: str | None
    raw_value_json: str | None


@dataclass(frozen=True)
class SiteContentPackage:
    source_revisions: tuple[SiteSourceRevision, ...]
    manifest: SiteSyncManifest
    sync_plan: SiteSyncPlan
    entities: tuple[SiteEntity, ...]
    facts: tuple[SiteFact, ...]
    relations: tuple[SiteRelation, ...]
    raw_records: tuple[RawSiteRecord, ...]
    dictionaries: tuple[SiteDictionary, ...]
    issues: tuple[SiteParseIssue, ...]
    parser_version: str = PARSER_VERSION

    @property
    def ready_for_promotion(self) -> bool:
        """A later publisher must not promote a package with parse errors."""
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)


class StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 booleans, no implicit dates, and strict keys."""

    yaml_implicit_resolvers = {
        first: [
            (tag, pattern)
            for tag, pattern in resolvers
            if tag not in {
                "tag:yaml.org,2002:bool",
                "tag:yaml.org,2002:timestamp",
            }
        ]
        for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ValueError("YAML mapping node expected")
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or not key.strip():
                raise ValueError("YAML mapping keys must be non-empty strings")
            if key in result:
                raise ValueError(f"Duplicate YAML key: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


StrictSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def git_blob_sha1(content: bytes) -> str:
    """Return the Git object SHA-1 for a blob's exact bytes."""
    if type(content) is not bytes:
        raise TypeError("Git blob content must be bytes")
    header = b"blob " + str(len(content)).encode("ascii") + b"\0"
    return sha1(header + content).hexdigest()


def _validate_yaml_value(value, *, depth=0, budget=None):
    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > MAX_YAML_NODES:
        raise ValueError("YAML node limit exceeded")
    if depth > MAX_YAML_DEPTH:
        raise ValueError("YAML nesting limit exceeded")

    if value is None or type(value) in (str, bool, int):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("NUL is not allowed in YAML strings")
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Non-finite YAML numbers are not supported")
        return
    if type(value) is list:
        for child in value:
            _validate_yaml_value(child, depth=depth + 1, budget=budget)
        return
    if type(value) is dict:
        for key, child in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("YAML mapping keys must be non-empty strings")
            _validate_yaml_value(child, depth=depth + 1, budget=budget)
        return
    raise ValueError(f"Unsupported YAML value type: {type(value).__name__}")


def _load_yaml(text: str, *, byte_count: int, require_mapping: bool):
    if byte_count > MAX_FRONTMATTER_BYTES:
        raise ValueError("YAML frontmatter size limit exceeded")
    try:
        for count, token in enumerate(yaml.scan(text, Loader=StrictSafeLoader), start=1):
            if count > MAX_YAML_TOKENS:
                raise ValueError("YAML token limit exceeded")
            if isinstance(token, (AliasToken, AnchorToken, TagToken)):
                raise ValueError("YAML aliases, anchors and explicit tags are disabled")
        value = yaml.load(text, Loader=StrictSafeLoader)
        _validate_yaml_value(value)
        if require_mapping and not isinstance(value, dict):
            raise ValueError("Frontmatter must be a YAML mapping")
        return value
    except (yaml.YAMLError, RecursionError, OverflowError) as exc:
        problem = getattr(exc, "problem", None) or type(exc).__name__
        raise ValueError(f"Invalid YAML: {problem}") from None


def _split_markdown(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)

    def line_value(line: str) -> str:
        return line.rstrip("\r\n")

    if not lines or line_value(lines[0]) != "---":
        raise ValueError("Missing opening frontmatter delimiter")
    closing = next(
        (index for index in range(1, len(lines)) if line_value(lines[index]) == "---"),
        None,
    )
    if closing is None:
        raise ValueError("Missing closing frontmatter delimiter")
    frontmatter = "".join(lines[1:closing])
    body = "".join(lines[closing + 1:])
    return frontmatter, body


def _content_location(path: str) -> tuple[str, str] | None:
    parts = PurePosixPath(path).parts
    if len(parts) < 4 or parts[:2] != ("src", "content"):
        return None
    collection = parts[2]
    relative = PurePosixPath(*parts[3:]).with_suffix("").as_posix()
    if not collection or not relative:
        return None
    return collection, relative


def _entity_id(collection: str, slug: str) -> str:
    return "saturn:" + stable_id("saturn-site-entity-v1", collection, slug)


def _entity_type(collection: str, metadata: dict) -> tuple[str, str | None]:
    if collection == "products":
        if metadata.get("group") == SOFTWARE_GROUP_SLUG:
            return "Software", None
        return "Device", None
    if collection == "systems":
        kind = metadata.get("kind")
        if kind == "system":
            return "System", None
        if kind == "category":
            return "Category", None
        return "SiteContent", "Unknown or absent systems.kind; retained as generic SiteContent"
    if collection == "groups":
        return "Group", None
    if collection == "articles":
        return "Article", None
    if collection == "news":
        return "News", None
    if collection == "pages":
        kind = metadata.get("kind")
        if kind == "solution":
            return "Solution", None
        if kind == "section":
            return "SectionPage", None
        return "Page", None
    return "SiteContent", None


def _child_field_path(parent: str, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
        return f"{parent}.{key}"
    return f"{parent}[{canonical_json(key)}]"


def _iter_field_values(path: str, value):
    """Yield container and nested values; array indices preserve source ordering."""
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_field_values(_child_field_path(path, key), child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_field_values(f"{path}[{index}]", child)


def _facts_for_entity(entity_id: str, metadata: dict, revision_id: str) -> list[SiteFact]:
    facts = []
    for field, value in metadata.items():
        for field_path, raw_value in _iter_field_values(field, value):
            raw_json = canonical_json(raw_value)
            unit = _FIELD_UNITS.get(field_path)
            fact_id = stable_id(
                "saturn-site-fact-v1",
                entity_id,
                field_path,
                raw_json,
                revision_id,
            )
            facts.append(SiteFact(
                fact_id=fact_id,
                entity_id=entity_id,
                field_path=field_path,
                raw_value_json=raw_json,
                source_revision_id=revision_id,
                unit=unit,
            ))
    return facts


def _safe_reference_slug(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Relation reference must be a non-empty slug")
    slug = value.strip()
    path = PurePosixPath(slug)
    if (
        path.is_absolute()
        or path.as_posix() != slug
        or "\\" in slug
        or "%" in slug
        or "\x00" in slug
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise ValueError("Unsafe relation reference")
    return slug


def _relation_candidates(collection: str, metadata: dict, path: str, issues: list):
    for field, (target_collection, cardinality) in _RELATION_FIELDS.get(collection, {}).items():
        if field not in metadata:
            continue
        value = metadata[field]
        if cardinality == "many":
            if value is None:
                issues.append(SiteParseIssue(path, "relation", "null_relation_value",
                                             f"{field} is null; raw fact retained", "warning"))
                continue
            if not isinstance(value, list):
                issues.append(SiteParseIssue(path, "relation", "invalid_relation_shape",
                                             f"{field} must be a list of slugs"))
                continue
            values = [(f"{field}[{index}]", item) for index, item in enumerate(value)]
        else:
            if value is None:
                issues.append(SiteParseIssue(path, "relation", "null_relation_value",
                                             f"{field} is null; raw fact retained", "warning"))
                continue
            values = [(field, value)]

        for source_field_path, reference in values:
            try:
                slug = _safe_reference_slug(reference)
            except ValueError as exc:
                issues.append(SiteParseIssue(path, "relation", "invalid_relation_reference",
                                             f"{source_field_path}: {exc}"))
                continue
            yield field, source_field_path, target_collection, slug


def adapt_snapshot(
    snapshot: PinnedSiteSnapshot,
    previous_manifest: SiteSyncManifest | None = None,
) -> SiteContentPackage:
    """Parse one exact pinned snapshot into canonical Saturn entities/facts/relations."""
    if not isinstance(snapshot, PinnedSiteSnapshot):
        raise SnapshotValidationError("PinnedSiteSnapshot is required")

    by_path = {item.path: item for item in snapshot.files}
    schema_file = by_path.get("src/content.config.ts")
    if schema_file is None:
        raise SnapshotValidationError("Pinned snapshot is missing src/content.config.ts")

    content_files = [
        item for item in snapshot.files
        if item.path.startswith("src/content/") and PurePosixPath(item.path).suffix.lower() == ".md"
    ]
    dictionary_files = [
        item for item in snapshot.files
        if item.path.startswith("src/data/")
        and PurePosixPath(item.path).suffix.lower() in {".yaml", ".yml"}
    ]
    relevant_files = tuple(sorted(
        [schema_file, *content_files, *dictionary_files],
        key=lambda item: item.path,
    ))

    source_revisions = tuple(
        SiteSourceRevision(
            snapshot.repository,
            snapshot.branch,
            snapshot.commit_sha,
            item.path,
            item.blob_sha,
            item.content_sha256,
        )
        for item in relevant_files
    )
    revision_by_path = {item.path: item for item in source_revisions}

    file_revisions = []
    locations = {}
    collection_records: dict[str, list[dict]] = {}
    for item in content_files:
        location = _content_location(item.path)
        locations[item.path] = location
        collection = location[0] if location else None
        slug = location[1] if location else None
        if collection is not None:
            collection_records.setdefault(collection, [])
        file_revisions.append(SiteFileRevision(
            item.path, item.blob_sha, item.content_sha256, collection, slug
        ))
    for item in (schema_file, *dictionary_files):
        file_revisions.append(SiteFileRevision(
            item.path, item.blob_sha, item.content_sha256
        ))

    issues: list[SiteParseIssue] = []
    raw_records: list[RawSiteRecord] = []
    dictionaries: list[SiteDictionary] = []
    parsed_records = []
    draft_keys = set()
    entities_by_key = {}
    entities: list[SiteEntity] = []
    facts: list[SiteFact] = []

    for item in dictionary_files:
        revision = revision_by_path[item.path]
        raw_text = None
        raw_json = None
        try:
            if len(item.content) > MAX_DICTIONARY_BYTES:
                raise ValueError("Dictionary size limit exceeded")
            raw_text = item.content.decode("utf-8-sig")
            value = _load_yaml(
                raw_text,
                byte_count=len(item.content),
                require_mapping=False,
            )
            raw_json = canonical_json(value)
        except (UnicodeDecodeError, ValueError) as exc:
            issues.append(SiteParseIssue(
                item.path, "dictionary", "dictionary_parse_error", str(exc)
            ))
        dictionaries.append(SiteDictionary(
            item.path, revision.revision_id, item.content, raw_text, raw_json
        ))

    for item in content_files:
        revision = revision_by_path[item.path]
        location = locations[item.path]
        collection, slug = location if location else (None, None)
        raw_frontmatter = None
        body = None
        draft = None
        metadata = None

        try:
            if len(item.content) > MAX_MARKDOWN_BYTES:
                raise ValueError("Markdown file size limit exceeded")
            text = item.content.decode("utf-8-sig")
            raw_frontmatter, body = _split_markdown(text)
            if len(raw_frontmatter.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
                raise ValueError("YAML frontmatter size limit exceeded")
            metadata = _load_yaml(
                raw_frontmatter,
                byte_count=len(raw_frontmatter.encode("utf-8")),
                require_mapping=True,
            )
            if collection is None or slug is None:
                raise ValueError("Markdown path must be src/content/<collection>/<slug>.md")
            draft = metadata.get("draft") is True
            collection_records[collection].append(metadata)
            parsed_records.append((item.path, collection, slug, metadata, revision, draft))
            if draft:
                raw_records.append(RawSiteRecord(
                    item.path, revision.revision_id, collection, slug, item.content,
                    raw_frontmatter, body, True
                ))
                draft_keys.add((collection, slug))
                continue

            entity_id = _entity_id(collection, slug)
            title_value = metadata.get("title")
            if isinstance(title_value, str) and title_value.strip():
                title = title_value
            else:
                # Slug is a locator-derived display label, not a source fact.
                title = slug
                issues.append(SiteParseIssue(
                    item.path, "mapping", "missing_title",
                    "No non-empty title; slug used only as the entity display label",
                    "warning",
                ))
            entity_type, mapping_warning = _entity_type(collection, metadata)
            if mapping_warning:
                issues.append(SiteParseIssue(
                    item.path, "mapping", "unknown_entity_discriminator",
                    mapping_warning, "warning",
                ))
            entity = SiteEntity(
                entity_id=entity_id,
                collection=collection,
                slug=slug,
                entity_type=entity_type,
                title=title,
                canonical_url=None,
                draft=False,
                source_revision_id=revision.revision_id,
                raw_frontmatter_json=canonical_json(metadata),
                body=body,
            )
            entity_facts = _facts_for_entity(entity_id, metadata, revision.revision_id)
            entities.append(entity)
            facts.extend(entity_facts)
            entities_by_key[(collection, slug)] = entity_id
            raw_records.append(RawSiteRecord(
                item.path, revision.revision_id, collection, slug, item.content,
                raw_frontmatter, body, False
            ))
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            raw_records.append(RawSiteRecord(
                item.path, revision.revision_id, collection, slug, item.content,
                raw_frontmatter, body, draft
            ))
            issues.append(SiteParseIssue(
                item.path, "content", "content_parse_error", str(exc)
            ))

    relations: list[SiteRelation] = []
    for path, collection, slug, metadata, revision, draft in parsed_records:
        if draft:
            continue
        subject_id = entities_by_key.get((collection, slug))
        if subject_id is None:
            continue
        for predicate, field_path, target_collection, target_slug in _relation_candidates(
            collection, metadata, path, issues
        ):
            if (target_collection, target_slug) in draft_keys:
                issues.append(SiteParseIssue(
                    path, "relation", "relation_target_draft",
                    f"{field_path} points to an excluded draft record; raw fact retained",
                    "warning",
                ))
                continue
            target_id = _entity_id(target_collection, target_slug)
            if (target_collection, target_slug) not in entities_by_key:
                issues.append(SiteParseIssue(
                    path, "relation", "relation_target_missing",
                    f"{field_path} references {target_collection}/{target_slug}; relation retained",
                    "warning",
                ))
            relation_id = stable_id(
                "saturn-site-relation-v1",
                subject_id,
                predicate,
                target_id,
                revision.revision_id,
                field_path,
            )
            relations.append(SiteRelation(
                relation_id=relation_id,
                subject_entity_id=subject_id,
                predicate=predicate,
                object_entity_id=target_id,
                source_revision_id=revision.revision_id,
                source_field_path=field_path,
            ))

    dictionary_bytes = {item.path: item.content for item in dictionary_files}
    schema_inventory = build_schema_inventory(
        collection_records,
        schema_file.content,
        dictionary_bytes,
    )
    manifest = build_sync_manifest(
        commit_sha=snapshot.commit_sha,
        tree_sha=snapshot.tree_sha,
        schema_inventory=schema_inventory,
        file_revisions=tuple(file_revisions),
        adapter_version=ADAPTER_VERSION,
        mapping_version=MAPPING_VERSION,
        repository=snapshot.repository,
        branch=snapshot.branch,
    )
    sync_plan = plan_sync(previous_manifest, manifest)

    return SiteContentPackage(
        source_revisions=source_revisions,
        manifest=manifest,
        sync_plan=sync_plan,
        entities=tuple(entities),
        facts=tuple(facts),
        relations=tuple(relations),
        raw_records=tuple(raw_records),
        dictionaries=tuple(dictionaries),
        issues=tuple(sorted(issues, key=lambda issue: (
            issue.path, issue.stage, issue.code, issue.message
        ))),
    )
