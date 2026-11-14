"""Strict independent integrity checks across the three trusted Saturn adapters.

No network, PDF parsing, source ingestion, source approvals, or legacy registry.
Structural failure is distinct from an upstream readiness failure.
"""
from dataclasses import dataclass, replace
from hashlib import sha1, sha256
import json
import re
from urllib.parse import urlsplit, urlunsplit

from .ingestion.saturn_contracts import (
    SiteEntity, SiteFact, SiteRelation, SiteSourceRevision, SiteSyncManifest,
    SupportDocument, PdfRevision, EvidenceUnit, canonical_json, stable_id,
    TRUSTED_SITE_BRANCH, TRUSTED_SITE_REPOSITORY,
)
from .ingestion.saturn_site_adapter import (
    RawSiteRecord, SiteContentPackage, SiteDictionary, SiteParseIssue,
    _RELATION_FIELDS, _safe_reference_slug, _content_location, _split_markdown,
    _load_yaml, _entity_type, _canonical_url, _facts_for_entity,
    _entity_id, _relation_candidates, MAX_MARKDOWN_BYTES,
    MAX_DICTIONARY_BYTES, MAX_FRONTMATTER_BYTES,
)
from .ingestion.support_catalog_adapter import (
    CatalogOccurrence, PdfCandidate, SupportCatalogResult, _is_pdf,
    _origin, adapt_support_catalog,
)
from .ingestion.external_document_transport import CODES
from .ingestion.external_document_adapter import (
    CachedPdfExtraction, DocumentAssociation, DocumentDiagnostic,
    DocumentStatus, ExternalDocumentResult,
)
from .saturn_knowledge_contracts import SnapshotIssue, SaturnScopedExperiment

# The adapter package carries raw content and dictionary bytes but not the
# astro.config.mjs bytes. The source origin can therefore be checked for route
# shape and inter-entity consistency, but NOT proven from config bytes in 4A.
# See the limitations in the stage report / architecture handoff.


_FIELD_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[SnapshotIssue, ...]
    resolved_relations: tuple[SiteRelation, ...]
    unresolved_relations: tuple[SiteRelation, ...]


def _fields(value, parent=""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = key if not parent else (
                parent + "." + key if _FIELD_KEY.fullmatch(key)
                else parent + "[" + canonical_json(key) + "]"
            )
            yield path, canonical_json(child)
            yield from _fields(child, path)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            path = parent + "[" + str(i) + "]"
            yield path, canonical_json(child)
            yield from _fields(child, path)


def _git_blob_sha(content: bytes) -> str:
    return sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def _revision_id(rev: PdfRevision):
    return stable_id("saturn-pdf-revision-v1", rev.document_id, rev.url,
                     rev.bytes_sha256, rev.parser_version)


def validate_saturn_snapshot_inputs(site, catalog, external, *, scope=None) -> ValidationResult:
    errors = []

    def issue(code, subject):
        errors.append(SnapshotIssue(code, str(subject)))

    if not isinstance(site, SiteContentPackage):
        issue("invalid_site_input", "site")
    if not isinstance(catalog, SupportCatalogResult):
        issue("invalid_catalog_input", "catalog")
    if not isinstance(external, ExternalDocumentResult):
        issue("invalid_external_input", "external")
    if scope is not None:
        if not isinstance(scope, SaturnScopedExperiment):
            issue("invalid_scoped_contract", "scope")
        else:
            try:
                scope.__post_init__()  # robust to low-level attribute replacement
            except (TypeError, ValueError, AttributeError):
                issue("invalid_scoped_contract", "scope digest")
    if errors:
        return ValidationResult(tuple(errors), (), ())

    groups = (
        ("source_revisions", site.source_revisions, SiteSourceRevision),
        ("entities", site.entities, SiteEntity),
        ("facts", site.facts, SiteFact),
        ("relations", site.relations, SiteRelation),
        ("raw_records", site.raw_records, RawSiteRecord),
        ("dictionaries", site.dictionaries, SiteDictionary),
        ("site_issues", site.issues, SiteParseIssue),
        ("documents", catalog.documents, SupportDocument),
        ("candidates", catalog.pdf_candidates, PdfCandidate),
        ("occurrences", catalog.occurrences, CatalogOccurrence),
        ("catalog_issues", catalog.issues, SiteParseIssue),
        ("statuses", external.statuses, DocumentStatus),
        ("revisions", external.revisions, PdfRevision),
        ("evidence", external.evidence, EvidenceUnit),
        ("associations", external.associations, DocumentAssociation),
        ("diagnostics", external.diagnostics, DocumentDiagnostic),
        ("cache", external.cached_extractions, CachedPdfExtraction),
    )
    for name, items, kind in groups:
        if type(items) is not tuple or any(not isinstance(x, kind) for x in items):
            issue("invalid_collection", name)
    if errors:
        return ValidationResult(tuple(errors), (), ())

    manifest = site.manifest
    if (not isinstance(manifest, SiteSyncManifest) or
            site.sync_plan.manifest != manifest):
        issue("site_manifest_mismatch", "site")
        return ValidationResult(tuple(errors), (), ())
    if (manifest.repository != TRUSTED_SITE_REPOSITORY or
            manifest.branch != TRUSTED_SITE_BRANCH):
        issue("untrusted_source", "manifest")
    if site.parser_version != manifest.parser_version:
        issue("site_parser_mismatch", "manifest")
    if scope is not None:
        if (scope.source_commit != manifest.commit_sha or
                scope.source_tree != manifest.tree_sha):
            issue("scope_source_identity_mismatch", "site commit/tree")
        # Experimental Stage 5F must not silently reuse the old PDF parser.
        if external.parser_version != "saturn-pdf-pypdf-6.10.0/0.3.0":
            issue("scope_pdf_parser_version_mismatch", "external parser")
    if catalog.catalog_version not in (
            "saturn-support-catalog/0.2.0", "saturn-support-catalog/0.1.0"):
        issue("invalid_catalog_version", "catalog")
    if (catalog.catalog_version == "saturn-support-catalog/0.1.0" and
            external.parser_version != "saturn-pdf-pypdf-6.10.0/0.1.0"):
        issue("invalid_catalog_version", "historical synthetic fixture only")
    if not isinstance(external.parser_version, str) or not external.parser_version:
        issue("invalid_pdf_parser_version", "external")
    if type(catalog.upstream_ready) is not bool or catalog.upstream_ready != site.ready_for_promotion:
        issue("catalog_upstream_mismatch", "catalog")
    if type(external.ready_for_promotion) is not bool or type(external.complete) is not bool:
        issue("invalid_external_readiness", "external")

    def index(values, key, code):
        by_id = {}
        for value in values:
            identifier = key(value)
            if identifier in by_id:
                issue(code, identifier)
            by_id[identifier] = value
        return by_id

    files = index(manifest.file_revisions, lambda x: x.path, "duplicate_manifest_file")
    revisions = index(site.source_revisions, lambda x: x.revision_id,
                      "duplicate_source_revision")
    rev_by_path = index(site.source_revisions, lambda x: x.path,
                        "duplicate_source_path")
    if set(files) != set(rev_by_path):
        issue("source_inventory_mismatch", "source revisions")
    for path, rev in rev_by_path.items():
        source = files.get(path)
        if (source is None or rev.repository != manifest.repository or
                rev.branch != manifest.branch or rev.commit_sha != manifest.commit_sha or
                rev.blob_sha != source.blob_sha or rev.content_sha256 != source.content_sha256):
            issue("source_revision_mismatch", path)

    records = index(site.raw_records, lambda x: x.path, "duplicate_raw_record")
    dictionaries = index(site.dictionaries, lambda x: x.path, "duplicate_dictionary")
    expected_records = {
        path for path in rev_by_path
        if path.startswith("src/content/") and path.endswith(".md")
    }
    if set(records) != expected_records:
        issue("raw_record_inventory_mismatch", "src/content/*.md")
    expected_dictionaries = {
        path for path in rev_by_path
        if path.startswith("src/data/") and path.endswith((".yaml", ".yml"))
    }
    if set(dictionaries) != expected_dictionaries:
        issue("dictionary_source_inventory_mismatch", "src/data/*.yaml")

    for record in (*site.raw_records, *site.dictionaries):
        revision = revisions.get(record.source_revision_id)
        if (revision is None or revision.path != record.path or
                type(record.content) is not bytes or
                sha256(record.content).hexdigest() != revision.content_sha256 or
                _git_blob_sha(record.content) != revision.blob_sha):
            issue("source_bytes_mismatch", record.path)

    # Re-parse the checked original bytes with the approved offline parser.
    # Never accept a caller-provided frontmatter/body/draft as its own witness.
    raw_metadata = {}
    draft_keys = set()
    for path, record in records.items():
        location = _content_location(path)
        if location != (record.collection, record.slug):
            issue("source_record_location_mismatch", path)
        try:
            if type(record.content) is not bytes or len(record.content) > MAX_MARKDOWN_BYTES:
                raise ValueError("Markdown source bytes/size invalid")
            frontmatter_text, body = _split_markdown(record.content.decode("utf-8-sig"))
            if len(frontmatter_text.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
                raise ValueError("Frontmatter source size exceeded")
            metadata = _load_yaml(
                frontmatter_text, byte_count=len(frontmatter_text.encode("utf-8")),
                require_mapping=True)
            draft = metadata.get("draft") is True
        except (UnicodeDecodeError, ValueError, RecursionError):
            issue("source_record_unverifiable", path)
            continue
        if (record.raw_frontmatter_text != frontmatter_text or
                record.body != body or record.draft is not draft):
            issue("source_record_projection_mismatch", path)
        raw_metadata[path] = metadata
        if draft and location is not None:
            draft_keys.add(location)

    fingerprints = {x.path: x.content_sha256
                    for x in manifest.schema_inventory.dictionaries}
    if set(fingerprints) != set(dictionaries):
        issue("dictionary_inventory_mismatch", "schema inventory")
    for path, dictionary in dictionaries.items():
        if (type(dictionary.content) is not bytes or
                fingerprints.get(path) != sha256(dictionary.content).hexdigest()):
            issue("dictionary_content_mismatch", path)
            continue
        try:
            if len(dictionary.content) > MAX_DICTIONARY_BYTES:
                raise ValueError("Dictionary size exceeded")
            yaml_text = dictionary.content.decode("utf-8-sig")
            expected_json = canonical_json(_load_yaml(
                yaml_text, byte_count=len(dictionary.content),
                require_mapping=False, max_bytes=MAX_DICTIONARY_BYTES))
        except (UnicodeDecodeError, ValueError, RecursionError):
            issue("dictionary_source_unverifiable", path)
            continue
        if (dictionary.raw_yaml_text != yaml_text or
                dictionary.raw_value_json != expected_json):
            issue("dictionary_projection_mismatch", path)

    entities = index(site.entities, lambda x: x.entity_id, "duplicate_entity")
    # With only SiteContentPackage available, config bytes are absent.
    # Derive only the consistent origin of source-provided canonical URLs.
    # Cross-entity mismatch is rejected; an origin shared by ALL malicious
    # URLs is not independently verifiable (documented contract limitation).
    origin = _origin(site.entities)
    url_origins = {
        urlunsplit((x.scheme, x.netloc, "", "", ""))
        for entity in site.entities if entity.canonical_url
        for x in (urlsplit(entity.canonical_url),)
    }
    if len(url_origins) > 1:
        issue("canonical_origin_mismatch", "site entities")

    frontmatter = {}
    expected_facts = {}
    for entity in site.entities:
        rev = revisions.get(entity.source_revision_id)
        rec = records.get(rev.path) if rev is not None else None
        metadata = raw_metadata.get(rev.path) if rev is not None else None
        if (entity.draft or rev is None or rec is None or rec.draft is not False or
                rec.body != entity.body or rec.collection != entity.collection or
                rec.slug != entity.slug or
                rev.path != "src/content/" + entity.collection + "/" + entity.slug + ".md" or
                entity.entity_id != _entity_id(entity.collection, entity.slug)):
            issue("invalid_entity_provenance", entity.entity_id)
        if metadata is None:
            issue("entity_source_unverifiable", entity.entity_id)
            continue
        expected_frontmatter = canonical_json(metadata)
        if entity.raw_frontmatter_json != expected_frontmatter:
            issue("entity_frontmatter_mismatch", entity.entity_id)
        title_raw = metadata.get("title")
        expected_title = (title_raw if isinstance(title_raw, str) and
                          title_raw.strip() else entity.slug)
        expected_type, _ = _entity_type(entity.collection, metadata)
        if entity.title != expected_title:
            issue("entity_title_mismatch", entity.entity_id)
        if entity.entity_type != expected_type:
            issue("entity_type_mismatch", entity.entity_id)
        route_issues = []
        if origin is not None:
            expected_url = _canonical_url(
                entity.collection, entity.slug, origin, set(rev_by_path),
                rec.path, route_issues)
        else:
            # A placeholder makes route/path validation independent of URL
            # origin; no configured origin can be proven without config bytes.
            expected_url = _canonical_url(
                entity.collection, entity.slug, "https://unverified.invalid",
                set(rev_by_path), rec.path, route_issues)
            if expected_url is not None:
                expected_url = None
                issue("canonical_origin_unverifiable", entity.entity_id)
        if entity.canonical_url != expected_url:
            issue("entity_canonical_url_mismatch", entity.entity_id)
        frontmatter[entity.entity_id] = dict(_fields(metadata))
        for fact in _facts_for_entity(entity.entity_id, metadata,
                                      entity.source_revision_id):
            expected_facts[fact.fact_id] = fact

    expected_entity_ids = {
        _entity_id(record.collection, record.slug)
        for record in site.raw_records
        if record.path in raw_metadata and record.draft is False and
        record.collection is not None and record.slug is not None
    }
    if set(entities) != expected_entity_ids:
        issue("entity_projection_coverage_mismatch", "non-draft records")

    provided_facts = index(site.facts, lambda x: x.fact_id, "duplicate_fact")
    if set(provided_facts) != set(expected_facts):
        issue("fact_projection_coverage_mismatch", "source frontmatter")
    for key in set(provided_facts) & set(expected_facts):
        if provided_facts[key] != expected_facts[key]:
            issue("fact_projection_mismatch", key)

    # Reconstruct all declared relations from verified source metadata; do
    # not derive completeness from the already supplied SiteRelation objects.
    expected_relations = {}
    draft_references = set(draft_keys)
    for entity in site.entities:
        rev = revisions.get(entity.source_revision_id)
        if rev is None or rev.path not in raw_metadata:
            continue
        source_issues = []
        for predicate, field_path, target_collection, target_slug in _relation_candidates(
            entity.collection, raw_metadata[rev.path], rev.path, source_issues
        ):
            if (target_collection, target_slug) in draft_references:
                continue
            target_id = _entity_id(target_collection, target_slug)
            relation_id = stable_id(
                "saturn-site-relation-v1", entity.entity_id, predicate,
                target_id, entity.source_revision_id, field_path)
            expected_relations[relation_id] = SiteRelation(
                relation_id, entity.entity_id, predicate, target_id,
                entity.source_revision_id, field_path)
    actual_relations = index(site.relations, lambda x: x.relation_id,
                             "duplicate_relation")
    if set(expected_relations) != set(actual_relations):
        issue("relation_projection_coverage_mismatch", "source-declared references")
    for key, supplied in actual_relations.items():
        if supplied != expected_relations.get(key):
            # Preserve the established stage-4A diagnostic code while also
            # reporting the new source-completeness failure precisely.
            issue("relation_source_mismatch", key)
            if key in expected_relations:
                issue("relation_projection_mismatch", key)

    valid_relations, unresolved = [], []
    for relation in site.relations:
        if relation.subject_entity_id not in entities:
            issue("invalid_relation_provenance", relation.relation_id)
        if relation.object_entity_id in entities:
            valid_relations.append(relation)
        else:
            unresolved.append(relation)

    documents = index(catalog.documents, lambda x: x.document_id,
                      "duplicate_document")
    index(catalog.occurrences,
          lambda x: (x.document_id, x.owner_entity_id,
                     x.source_revision_id, x.field_path),
          "duplicate_occurrence")
    by_doc = {}
    for occ in catalog.occurrences:
        by_doc.setdefault(occ.document_id, []).append(occ)
        rev = revisions.get(occ.source_revision_id)
        owner = entities.get(occ.owner_entity_id)
        url = urlsplit(occ.resolved_url)
        canonical = urlunsplit((url.scheme, url.netloc, url.path, url.query, ""))
        doc = documents.get(occ.document_id)
        if (doc is None or rev is None or owner is None or
                owner.source_revision_id != occ.source_revision_id or
                rev.path != occ.source_path or
                occ.source_locator != occ.source_revision_id + "#" + occ.field_path or
                canonical != doc.url):
            issue("invalid_document_occurrence", occ.source_locator)
        if owner is not None:
            if occ.field_path.startswith("body:"):
                match = re.fullmatch(
                    r"body:line=(\d+):column=(\d+):heading=.+:occurrence=(\d+)",
                    occ.field_path)
                lines = owner.body.splitlines()
                if (match is None or int(match.group(1)) > len(lines) or
                        int(match.group(1)) < 1 or int(match.group(2)) < 1 or
                        int(match.group(2)) > len(lines[int(match.group(1)) - 1]) or
                        lines[int(match.group(1)) - 1][int(match.group(2)) - 1] not in "[<"):
                    issue("invalid_document_locator", occ.source_locator)
            else:
                try:
                    original = json.loads(frontmatter[owner.entity_id][occ.field_path])
                    if (not isinstance(original, dict) or
                            occ.raw_url not in (original.get("url"), original.get("image"))):
                        issue("invalid_document_locator", occ.source_locator)
                except (ValueError, KeyError, TypeError):
                    issue("invalid_document_locator", occ.source_locator)
    if set(documents) != set(by_doc):
        issue("incomplete_document_occurrences", "catalog")
    for doc in catalog.documents:
        occs = by_doc.get(doc.document_id, [])
        if (doc.document_id != "saturn-doc:" + stable_id(
                "saturn-support-document-url-v1", doc.url) or
                doc.owner_entity_ids != tuple(sorted({x.owner_entity_id for x in occs})) or
                doc.source_locators != tuple(sorted({x.source_locator for x in occs}))):
            issue("document_provenance_mismatch", doc.document_id)
        for field in ("title", "kind", "version", "date"):
            values = {getattr(x, field) for x in occs if getattr(x, field) is not None}
            if len(values) > 1 and (field in ("version", "date") or
                                      catalog.catalog_version == "saturn-support-catalog/0.1.0"):
                issue("conflicting_document_metadata", doc.document_id + ":" + field)
            # A single source-neutral display value is deterministic; all
            # alternatives remain preserved in the actual occurrence records.
            expected = min(values) if values else None
            if field == "title" and expected is None:
                expected = doc.url.rsplit("/", 1)[-1]
            if field == "kind" and expected is None:
                expected = "other"
            if getattr(doc, field) != expected:
                issue("document_metadata_mismatch", doc.document_id + ":" + field)

    candidates = index(catalog.pdf_candidates, lambda x: x.document_id,
                       "duplicate_pdf_candidate")
    if set(candidates) != {d.document_id for d in catalog.documents if _is_pdf(d.url)}:
        issue("pdf_candidate_coverage_mismatch", "catalog")
    for candidate in catalog.pdf_candidates:
        doc = documents.get(candidate.document_id)
        occs = by_doc.get(candidate.document_id, [])
        if (doc is None or candidate.resolved_url != doc.url or
                candidate.owner_entity_ids != tuple(sorted({x.owner_entity_id for x in occs})) or
                candidate.source_locators != tuple(sorted({x.source_locator for x in occs})) or
                candidate.source_revision_ids != tuple(sorted({x.source_revision_id for x in occs})) or
                candidate.raw_urls != tuple(sorted({x.raw_url for x in occs}))):
            issue("pdf_candidate_provenance_mismatch", candidate.document_id)

    # The catalog adapter itself is the sole Markdown/HTML link interpreter:
    # exact inline/reference/autolink/HTML offsets, escapes, headings and
    # code/comment exclusions must match a fresh offline derivation from the
    # already checked site package. No second, weaker link parser is allowed.
    try:
        # Always derive the FULL source catalog from verified original Markdown.
        # Caller-supplied selected catalogs are NEVER a witness to themselves.
        full_catalog = adapt_support_catalog(site, catalog_version=catalog.catalog_version)
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
        issue("catalog_reconstruction_failed", "source package")
    else:
        derived_catalog = full_catalog
        if scope is not None:
            if not full_catalog.ready_for_promotion:
                issue("scope_full_source_not_ready", "source catalog")
            selected_ids = set(scope.selected_document_ids)
            expected_selected = tuple(candidate for candidate in full_catalog.pdf_candidates
                                      if candidate.document_id in selected_ids)
            if (len(expected_selected) != len(selected_ids) or
                    tuple(sorted(candidate.resolved_url for candidate in expected_selected))
                    != scope.selected_pdf_urls or
                    len({candidate.resolved_url for candidate in expected_selected})
                    != len(expected_selected)):
                issue("scope_source_selection_mismatch", "PDF URLs/document IDs")
            derived_catalog = replace(
                full_catalog,
                documents=tuple(doc for doc in full_catalog.documents
                                if doc.document_id in selected_ids),
                pdf_candidates=expected_selected,
                occurrences=tuple(occ for occ in full_catalog.occurrences
                                  if occ.document_id in selected_ids),
            )
            if (set(catalog.documents) != set(derived_catalog.documents) or
                    set(catalog.pdf_candidates) != set(expected_selected) or
                    set(catalog.occurrences) != set(derived_catalog.occurrences)):
                issue("scope_source_projection_mismatch", "selected document provenance")
        if (catalog.occurrences != derived_catalog.occurrences and
                sorted(catalog.occurrences, key=lambda x: x.source_locator) !=
                sorted(derived_catalog.occurrences, key=lambda x: x.source_locator)):
            issue("source_occurrence_mismatch", "exact source PDF links")
        if (catalog.documents != derived_catalog.documents and
                set(catalog.documents) != set(derived_catalog.documents)):
            issue("source_document_mismatch", "support metadata")
        if (catalog.pdf_candidates != derived_catalog.pdf_candidates and
                set(catalog.pdf_candidates) != set(derived_catalog.pdf_candidates)):
            issue("source_pdf_candidate_mismatch", "PDF ownership and URLs")
        if (catalog.issues != derived_catalog.issues or
                catalog.upstream_ready != derived_catalog.upstream_ready or
                catalog.catalog_version != derived_catalog.catalog_version):
            issue("source_catalog_diagnostics_mismatch", "catalog adapter")

    statuses = index(external.statuses, lambda x: x.document_id,
                     "duplicate_pdf_status")
    associations = index(external.associations, lambda x: x.document_id,
                         "duplicate_pdf_association")
    pdf_revisions = index(external.revisions, _revision_id, "duplicate_pdf_revision")
    if set(statuses) != set(candidates) or set(associations) != set(candidates):
        issue("pdf_status_coverage_mismatch", "external")
    used = set()
    for doc_id, candidate in candidates.items():
        status = statuses.get(doc_id)
        assoc = associations.get(doc_id)
        if status is None or assoc is None:
            continue
        if (assoc.revision_id != status.revision_id or
                assoc.owner_entity_ids != candidate.owner_entity_ids or
                assoc.source_locators != candidate.source_locators or
                assoc.source_revision_ids != candidate.source_revision_ids):
            issue("pdf_association_mismatch", doc_id)
        if status.status not in CODES | {"extracted", "partial_text"}:
            issue("invalid_pdf_status", doc_id)
        if status.revision_id is None:
            if status.status in {"extracted", "partial_text", "ocr_required"}:
                issue("pdf_status_without_revision", doc_id)
            continue
        rev = pdf_revisions.get(status.revision_id)
        if (rev is None or rev.document_id != doc_id or
                rev.url != candidate.resolved_url or
                rev.parser_version != external.parser_version):
            issue("pdf_revision_mismatch", doc_id)
            continue
        used.add(status.revision_id)
        if status.status in {"extracted", "partial_text"}:
            if rev.extraction_state != "extracted":
                issue("pdf_extraction_state_mismatch", doc_id)
        elif status.status == "ocr_required":
            if rev.extraction_state != "fetched":
                issue("pdf_extraction_state_mismatch", doc_id)
        elif rev.extraction_state != "failed":
            issue("pdf_failure_state_mismatch", doc_id)
    if used != set(pdf_revisions):
        issue("orphan_pdf_revision", "external")

    cache = index(external.cached_extractions, lambda x: _revision_id(x.revision),
                  "duplicate_pdf_cache")
    actual_evidence = index(external.evidence, lambda x: x.evidence_id,
                            "duplicate_pdf_evidence")
    expected_evidence = {}
    for rid, rev in pdf_revisions.items():
        entry = cache.get(rid)
        if rev.extraction_state != "extracted":
            if entry is not None:
                issue("invalid_pdf_cache_state", rid)
            continue
        if entry is None or entry.revision != rev:
            issue("missing_pdf_extraction", rid)
            continue
        extraction = entry.extraction
        if (type(extraction.page_count) is not int or
                type(extraction.pages) is not tuple or
                extraction.page_count != rev.page_count or
                len(extraction.pages) != rev.page_count or
                any(type(p) is not tuple or len(p) != 2 or
                    type(p[0]) is not int or p[0] != i or
                    not isinstance(p[1], str) or "\x00" in p[1] or
                    p[1] != p[1].strip()
                    for i, p in enumerate(extraction.pages, 1))):
            issue("invalid_pdf_page_map", rid)
            continue
        digest = sha256(canonical_json([[n, t] for n, t in extraction.pages])
                        .encode("utf-8")).hexdigest()
        if digest != rev.extracted_text_sha256:
            issue("pdf_text_hash_mismatch", rid)
            continue
        for page, text in extraction.pages:
            if text:
                unit = EvidenceUnit(
                    evidence_id=stable_id("saturn-pdf-passage-v1", rid, page,
                                          sha256(text.encode("utf-8")).hexdigest()),
                    evidence_type="pdf_passage", source_revision_id=rid,
                    locator=rev.url + "#page=" + str(page),
                    page_number=page, text=text,
                )
                expected_evidence[unit.evidence_id] = unit
        status = statuses.get(rev.document_id)
        pages_with_text = sum(bool(t) for _, t in extraction.pages)
        if status and (status.status == "extracted") != (pages_with_text == rev.page_count):
            issue("pdf_completeness_mismatch", rid)
    if set(cache) != {rid for rid, rev in pdf_revisions.items()
                      if rev.extraction_state == "extracted"}:
        issue("pdf_cache_coverage_mismatch", "external")
    if (actual_evidence != expected_evidence or
            any(unit.evidence_type != "pdf_passage" for unit in external.evidence)):
        issue("pdf_evidence_mismatch", "external")

    complete = all(status.status == "extracted" for status in external.statuses)
    if (external.complete != complete or
            external.ready_for_promotion != (complete and catalog.ready_for_promotion)):
        issue("external_readiness_mismatch", "external")
    diagnostics = index(external.diagnostics, lambda x: (x.document_id, x.code),
                        "duplicate_pdf_diagnostic")
    expected_diag = {
        (status.document_id, "ocr_required" if status.status == "partial_text"
         else status.status)
        for status in external.statuses if status.status != "extracted"
    }
    if set(diagnostics) != expected_diag:
        issue("pdf_diagnostics_mismatch", "external")
    return ValidationResult(tuple(errors), tuple(valid_relations), tuple(unresolved))
