"""Strict independent integrity checks across the three trusted Saturn adapters.

No network, PDF parsing, source ingestion, source approvals, or legacy registry.
Structural failure is distinct from an upstream readiness failure.
"""
from dataclasses import dataclass
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
)
from .ingestion.support_catalog_adapter import (
    CatalogOccurrence, PdfCandidate, SupportCatalogResult, _is_pdf,
)
from .ingestion.external_document_adapter import (
    CachedPdfExtraction, DocumentAssociation, DocumentDiagnostic,
    DocumentStatus, ExternalDocumentResult,
)
from .saturn_knowledge_contracts import SnapshotIssue


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


def validate_saturn_snapshot_inputs(site, catalog, external) -> ValidationResult:
    errors = []

    def issue(code, subject):
        errors.append(SnapshotIssue(code, str(subject)))

    if not isinstance(site, SiteContentPackage):
        issue("invalid_site_input", "site")
    if not isinstance(catalog, SupportCatalogResult):
        issue("invalid_catalog_input", "catalog")
    if not isinstance(external, ExternalDocumentResult):
        issue("invalid_external_input", "external")
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
    if not isinstance(catalog.catalog_version, str) or not catalog.catalog_version:
        issue("invalid_catalog_version", "catalog")
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
    for record in (*site.raw_records, *site.dictionaries):
        revision = revisions.get(record.source_revision_id)
        if (revision is None or revision.path != record.path or
                type(record.content) is not bytes or
                sha256(record.content).hexdigest() != revision.content_sha256 or
                _git_blob_sha(record.content) != revision.blob_sha):
            issue("source_bytes_mismatch", record.path)
    fingerprints = {x.path: x.content_sha256
                    for x in manifest.schema_inventory.dictionaries}
    if set(fingerprints) != set(dictionaries):
        issue("dictionary_inventory_mismatch", "schema inventory")
    for path, dictionary in dictionaries.items():
        if (fingerprints.get(path) != sha256(dictionary.content).hexdigest() or
                dictionary.raw_yaml_text is None or dictionary.raw_value_json is None):
            issue("dictionary_content_mismatch", path)
        else:
            try:
                if canonical_json(json.loads(dictionary.raw_value_json)) != dictionary.raw_value_json:
                    issue("dictionary_value_mismatch", path)
            except (TypeError, ValueError):
                issue("dictionary_value_mismatch", path)

    entities = index(site.entities, lambda x: x.entity_id, "duplicate_entity")
    frontmatter = {}
    for entity in site.entities:
        rev = revisions.get(entity.source_revision_id)
        rec = records.get(rev.path) if rev is not None else None
        if (entity.draft or rev is None or rec is None or rec.draft is not False or
                rec.body != entity.body or rec.collection != entity.collection or
                rec.slug != entity.slug or
                rev.path != "src/content/" + entity.collection + "/" + entity.slug + ".md" or
                entity.entity_id != "saturn:" + stable_id(
                    "saturn-site-entity-v1", entity.collection, entity.slug)):
            issue("invalid_entity_provenance", entity.entity_id)
        try:
            frontmatter[entity.entity_id] = dict(_fields(json.loads(
                entity.raw_frontmatter_json)))
        except (ValueError, TypeError):
            issue("invalid_entity_frontmatter", entity.entity_id)
            frontmatter[entity.entity_id] = {}
    if site.ready_for_promotion:
        for record in site.raw_records:
            if record.draft is False and record.collection and record.slug:
                entity_id = "saturn:" + stable_id(
                    "saturn-site-entity-v1", record.collection, record.slug)
                if entity_id not in entities:
                    issue("missing_nondraft_entity", record.path)

    index(site.facts, lambda x: x.fact_id, "duplicate_fact")
    fact_paths = set()
    for fact in site.facts:
        owner = entities.get(fact.entity_id)
        if (owner is None or owner.source_revision_id != fact.source_revision_id or
                frontmatter.get(fact.entity_id, {}).get(fact.field_path) != fact.raw_value_json or
                fact.fact_id != stable_id("saturn-site-fact-v1", fact.entity_id,
                                          fact.field_path, fact.raw_value_json,
                                          fact.source_revision_id)):
            issue("invalid_fact_provenance", fact.fact_id)
        fact_paths.add((fact.entity_id, fact.field_path))
    expected_paths = {(eid, path) for eid, fields in frontmatter.items()
                      for path in fields}
    if fact_paths != expected_paths:
        issue("incomplete_fact_projection", "frontmatter fields")

    index(site.relations, lambda x: x.relation_id, "duplicate_relation")
    valid_relations, unresolved = [], []
    for relation in site.relations:
        owner = entities.get(relation.subject_entity_id)
        if (owner is None or owner.source_revision_id != relation.source_revision_id or
                relation.source_field_path not in frontmatter.get(
                    relation.subject_entity_id, {}) or
                relation.relation_id != stable_id("saturn-site-relation-v1",
                    relation.subject_entity_id, relation.predicate,
                    relation.object_entity_id, relation.source_revision_id,
                    relation.source_field_path)):
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
            if len(values) > 1:
                issue("conflicting_document_metadata", doc.document_id + ":" + field)
            expected = next(iter(values)) if values else None
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
