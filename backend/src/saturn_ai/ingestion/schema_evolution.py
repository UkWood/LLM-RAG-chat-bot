"""Schema inventory, drift detection and deterministic Saturn sync planning."""
from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
from collections.abc import Mapping, Sequence

from .saturn_contracts import (
    DictionaryFingerprint,
    FileChangeSet,
    LEGACY_PARSER_VERSION,
    SchemaDriftEvent,
    SchemaField,
    SchemaInventory,
    SiteFileRevision,
    SiteSyncManifest,
    SiteSyncPlan,
    TRUSTED_SITE_BRANCH,
    TRUSTED_SITE_REPOSITORY,
    canonical_json,
    stable_id,
)

# Files that determine Astro route patterns, route generation inputs, public origin,
# or base-path handling. Git-provider-specific CI workflows are intentionally excluded.
_ROUTE_SOURCE_FILES = frozenset({
    "astro.config.mjs",
    "src/content.config.ts",
    "src/lib/url.ts",
    "src/lib/nav.ts",
    "src/lib/service.ts",
    "src/data/nav.yaml",
    "src/data/industries.yaml",
})


def is_route_source_path(path: str) -> bool:
    """Whether a pinned source file can affect route generation or canonical URLs."""
    return path.startswith("src/pages/") or path in _ROUTE_SOURCE_FILES


def _value_type(value) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        if not value:
            return "array[empty]"
        signatures = sorted({_value_type(item) for item in value if item is not None})
        return "array[" + ("|".join(signatures) if signatures else "null") + "]"
    raise ValueError("Unsupported frontmatter value type")


def _merge_types(values: list[str]) -> tuple[str, bool]:
    nullable = "null" in values
    types = set(values) - {"null", "array[empty]"}
    if not types:
        return ("array[empty]" if "array[empty]" in values else "null"), nullable
    if types <= {"integer", "number"}:
        return "number" if "number" in types else "integer", nullable
    return (next(iter(types)) if len(types) == 1
            else "union[" + "|".join(sorted(types)) + "]"), nullable


def _collect_value(collection: str, field_path: str, value, buckets: dict) -> None:
    buckets[(collection, field_path)].append(_value_type(value))
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str) or not child_key.strip():
                raise ValueError("Nested frontmatter keys must be non-empty strings")
            _collect_value(collection, f"{field_path}.{child_key}", child_value, buckets)
    elif isinstance(value, list) and value and all(isinstance(item, Mapping) for item in value):
        for item in value:
            for child_key, child_value in item.items():
                if not isinstance(child_key, str) or not child_key.strip():
                    raise ValueError("Nested list keys must be non-empty strings")
                _collect_value(collection, f"{field_path}[].{child_key}", child_value, buckets)


def _collect_field_types(collection: str, record: Mapping, buckets: dict) -> None:
    for key, value in record.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Frontmatter keys must be non-empty strings")
        _collect_value(collection, key, value, buckets)


def build_schema_inventory(
    collection_records: Mapping[str, Sequence[Mapping]],
    schema_source_bytes: bytes,
    dictionary_files: Mapping[str, bytes],
) -> SchemaInventory:
    """Build an observed inventory without executing the site's TypeScript schema."""
    if not isinstance(collection_records, Mapping) or type(schema_source_bytes) is not bytes:
        raise ValueError("Invalid schema inventory input")
    if not isinstance(dictionary_files, Mapping):
        raise ValueError("Invalid dictionary file map")

    names = tuple(collection_records.keys())
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Invalid collection name")
    collections = tuple(sorted(names))

    buckets = defaultdict(list)
    for collection in collections:
        records = collection_records[collection]
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise ValueError("Collection records must be a sequence")
        for record in records:
            if not isinstance(record, Mapping):
                raise ValueError("Each content record must be a mapping")
            _collect_field_types(collection, record, buckets)

    fields = []
    for (collection, field_path), values in sorted(buckets.items()):
        value_type, nullable = _merge_types(values)
        fields.append(SchemaField(collection, field_path, value_type, nullable))

    dictionaries = []
    for path, content in sorted(dictionary_files.items()):
        if not isinstance(path, str) or not isinstance(content, bytes):
            raise ValueError("Invalid dictionary entry")
        dictionaries.append(DictionaryFingerprint(path, sha256(content).hexdigest()))

    return SchemaInventory(
        schema_source_sha256=sha256(schema_source_bytes).hexdigest(),
        collections=collections,
        fields=tuple(fields),
        dictionaries=tuple(dictionaries),
    )


def compare_schema(previous: SchemaInventory, current: SchemaInventory) -> tuple[SchemaDriftEvent, ...]:
    """Describe source schema changes; additive changes are informational, type changes break mapping."""
    if not isinstance(previous, SchemaInventory) or not isinstance(current, SchemaInventory):
        raise ValueError("Schema inventories are required")

    events = []
    old_collections, new_collections = set(previous.collections), set(current.collections)
    for collection in sorted(new_collections - old_collections):
        events.append(SchemaDriftEvent("collection_added", "info", collection))
    for collection in sorted(old_collections - new_collections):
        events.append(SchemaDriftEvent("collection_removed", "warning", collection))

    old_fields = {(item.collection, item.field_path): item for item in previous.fields}
    new_fields = {(item.collection, item.field_path): item for item in current.fields}
    for key in sorted(new_fields.keys() - old_fields.keys()):
        item = new_fields[key]
        events.append(SchemaDriftEvent("field_added", "info",
                                       f"{item.collection}.{item.field_path}", after=item.value_type))
    for key in sorted(old_fields.keys() - new_fields.keys()):
        item = old_fields[key]
        events.append(SchemaDriftEvent("field_removed", "warning",
                                       f"{item.collection}.{item.field_path}", before=item.value_type))
    for key in sorted(old_fields.keys() & new_fields.keys()):
        old, new = old_fields[key], new_fields[key]
        subject = f"{old.collection}.{old.field_path}"
        if old.value_type != new.value_type:
            events.append(SchemaDriftEvent("field_type_changed", "breaking", subject,
                                           before=old.value_type, after=new.value_type))
        if old.nullable != new.nullable:
            events.append(SchemaDriftEvent("field_nullability_changed", "warning", subject,
                                           before=str(old.nullable), after=str(new.nullable)))

    old_dicts = {item.path: item.content_sha256 for item in previous.dictionaries}
    new_dicts = {item.path: item.content_sha256 for item in current.dictionaries}
    for path in sorted(new_dicts.keys() - old_dicts.keys()):
        events.append(SchemaDriftEvent("dictionary_added", "info", path, after=new_dicts[path]))
    for path in sorted(old_dicts.keys() - new_dicts.keys()):
        events.append(SchemaDriftEvent("dictionary_removed", "warning", path, before=old_dicts[path]))
    for path in sorted(old_dicts.keys() & new_dicts.keys()):
        if old_dicts[path] != new_dicts[path]:
            events.append(SchemaDriftEvent("dictionary_changed", "info", path,
                                           before=old_dicts[path], after=new_dicts[path]))

    if previous.schema_source_sha256 != current.schema_source_sha256:
        events.append(SchemaDriftEvent("schema_definition_changed", "info", "src/content.config.ts",
                                       before=previous.schema_source_sha256,
                                       after=current.schema_source_sha256))
    return tuple(sorted(events, key=lambda item: (item.kind, item.subject, item.before or "", item.after or "")))


def compare_file_revisions(
    previous: Sequence[SiteFileRevision],
    current: Sequence[SiteFileRevision],
) -> FileChangeSet:
    """Return deterministic add/change/delete sets keyed by repository path."""
    if any(not isinstance(item, SiteFileRevision) for item in (*previous, *current)):
        raise ValueError("Invalid source file revision")
    old_by_path = {item.path: item for item in previous}
    new_by_path = {item.path: item for item in current}
    if len(old_by_path) != len(previous) or len(new_by_path) != len(current):
        raise ValueError("Duplicate source file path")
    added = tuple(sorted(new_by_path.keys() - old_by_path.keys()))
    deleted = tuple(sorted(old_by_path.keys() - new_by_path.keys()))
    changed = tuple(sorted(
        path for path in old_by_path.keys() & new_by_path.keys()
        if (old_by_path[path].blob_sha != new_by_path[path].blob_sha
            or old_by_path[path].content_sha256 != new_by_path[path].content_sha256)
    ))
    return FileChangeSet(added, changed, deleted)


def build_sync_manifest(
    *,
    commit_sha: str,
    tree_sha: str,
    schema_inventory: SchemaInventory,
    file_revisions: Sequence[SiteFileRevision],
    adapter_version: str,
    mapping_version: str,
    parser_version: str = LEGACY_PARSER_VERSION,
    repository: str = TRUSTED_SITE_REPOSITORY,
    branch: str = TRUSTED_SITE_BRANCH,
) -> SiteSyncManifest:
    """Create a deterministic immutable manifest for one exact source snapshot."""
    files = tuple(sorted(file_revisions, key=lambda item: item.path))
    payload = {
        "repository": repository,
        "branch": branch,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "schema_inventory": asdict(schema_inventory),
        "file_revisions": [asdict(item) for item in files],
        "adapter_version": adapter_version,
        "mapping_version": mapping_version,
    }
    if parser_version != LEGACY_PARSER_VERSION:
        payload["parser_version"] = parser_version
    snapshot_id = stable_id("saturn-site-snapshot-v1", payload)
    return SiteSyncManifest(
        repository=repository,
        branch=branch,
        commit_sha=commit_sha,
        tree_sha=tree_sha,
        adapter_version=adapter_version,
        mapping_version=mapping_version,
        parser_version=parser_version,
        schema_inventory=schema_inventory,
        file_revisions=files,
        snapshot_id=snapshot_id,
    )


def plan_sync(previous: SiteSyncManifest | None, current: SiteSyncManifest) -> SiteSyncPlan:
    """Compare an immutable source snapshot with the last successful manifest."""
    if not isinstance(current, SiteSyncManifest):
        raise ValueError("Current manifest is required")
    if previous is None:
        changes = FileChangeSet(added=tuple(sorted(item.path for item in current.file_revisions)))
        drift = tuple(SchemaDriftEvent("initial_inventory", "info", "site") for _ in (0,))
    else:
        if not isinstance(previous, SiteSyncManifest):
            raise ValueError("Previous manifest must be a SiteSyncManifest")
        changes = compare_file_revisions(previous.file_revisions, current.file_revisions)
        drift_events = list(compare_schema(previous.schema_inventory, current.schema_inventory))

        old_routes = {
            item.path: item for item in previous.file_revisions
            if is_route_source_path(item.path)
        }
        new_routes = {
            item.path: item for item in current.file_revisions
            if is_route_source_path(item.path)
        }
        for path in sorted(old_routes.keys() | new_routes.keys()):
            old = old_routes.get(path)
            new = new_routes.get(path)
            if old is None:
                drift_events.append(SchemaDriftEvent(
                    "route_source_added", "info", path, after=new.blob_sha
                ))
            elif new is None:
                drift_events.append(SchemaDriftEvent(
                    "route_source_deleted", "breaking", path, before=old.blob_sha
                ))
            elif old.blob_sha != new.blob_sha or old.content_sha256 != new.content_sha256:
                drift_events.append(SchemaDriftEvent(
                    "route_source_changed", "warning", path,
                    before=old.blob_sha, after=new.blob_sha,
                ))

        if previous.parser_version != current.parser_version:
            drift_events.append(SchemaDriftEvent(
                "parser_version_changed", "warning", "saturn-site-parser",
                before=previous.parser_version, after=current.parser_version,
            ))
        drift = tuple(sorted(
            drift_events,
            key=lambda item: (item.kind, item.subject, item.before or "", item.after or ""),
        ))
    return SiteSyncPlan(current, changes, drift)
