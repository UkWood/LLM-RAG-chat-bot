"""Unified Knowledge Snapshot v0.1 builder for trusted Saturn adapter results.

Public strict entrypoint: build_saturn_knowledge_snapshot(site, catalog, external).
Diagnostic entrypoint: stage_saturn_knowledge_snapshot(...).
Nothing in this module fetches sources, downloads PDF, runs workers or searches.
"""
from dataclasses import asdict, replace
from hashlib import sha256
import re

from .ingestion.saturn_contracts import EvidenceUnit, canonical_json, stable_id
from .ingestion.saturn_site_adapter import SiteContentPackage
from .ingestion.support_catalog_adapter import SupportCatalogResult
from .ingestion.external_document_adapter import ExternalDocumentResult
from .saturn_knowledge_contracts import (
    BUILDER_VERSION, DocumentMatch, EvidencePointer, SaturnKnowledgeSnapshot,
    SaturnSnapshotBuildResult, SaturnSnapshotManifest, SnapshotBuildError,
    SnapshotIssue, SaturnSnapshotManager, snapshot_content, sorted_canonical,
    verify_snapshot_seal,
)
from .saturn_knowledge_validation import validate_saturn_snapshot_inputs


MAX_PASSAGE_CHARS = 2400
_ATX = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s{0,3}(" + chr(96) + r"{3,}|~{3,})")


def site_passages(entity):
    """Emit source-exact Markdown slices, preserving physical line/column ranges.

    Supported segmentation: ATX headings outside code fences, soft max length,
    whole lines and long-line column splits. No AST/HTML/CommonMark rendering,
    fact inference, table interpretation or semantic rewriting.
    """
    text_lines = entity.body.splitlines(keepends=True)
    items = []
    current = ""
    start = 1
    end = 0
    heading = None
    column = None
    fence = None

    def flush():
        nonlocal current, column
        if current.strip():
            locator = "body:line=" + str(start) + "-" + str(end)
            if column is not None:
                locator += ":column=" + str(column)
            locator += ":heading=" + canonical_json(heading)
            items.append(EvidenceUnit(
                evidence_id=stable_id("saturn-site-passage-v1",
                    entity.source_revision_id, locator,
                    sha256(current.encode("utf-8")).hexdigest()),
                evidence_type="site_passage", source_revision_id=entity.source_revision_id,
                entity_id=entity.entity_id, locator=locator, text=current,
            ))
        current = ""
        column = None

    for line_number, line in enumerate(text_lines, 1):
        marker = _FENCE.match(line)
        if marker:
            tick = marker.group(1)
            if fence is None:
                fence = (tick[0], len(tick))
            elif tick[0] == fence[0] and len(tick) >= fence[1]:
                fence = None
        if fence is None and marker is None:
            match = _ATX.match(line.rstrip("\r\n"))
            if match:
                flush()
                heading = match.group(1)
        if len(line) > MAX_PASSAGE_CHARS:
            flush()
            for offset in range(0, len(line), MAX_PASSAGE_CHARS):
                current = line[offset: offset + MAX_PASSAGE_CHARS]
                start = end = line_number
                column = offset + 1
                flush()
            continue
        if current and len(current) + len(line) > MAX_PASSAGE_CHARS:
            flush()
        if not current:
            start = line_number
        end = line_number
        current += line
    flush()
    return tuple(items)


def _field_projection(fact, owner):
    if re.match(r"^(?:documents|certificates)(?:$|[.[])", fact.field_path):
        return None
    components = [fact.field_path + ": " + fact.raw_value_json]
    if fact.normalized_value_json is not None:
        components.append("normalized=" + fact.normalized_value_json)
    if fact.unit is not None:
        components.append("unit=" + fact.unit)
    if fact.qualifiers_json is not None:
        components.append("qualifiers=" + fact.qualifiers_json)
    unit = EvidenceUnit(
        evidence_id=stable_id("saturn-field-projection-v1", fact.fact_id,
                              fact.source_revision_id, canonical_json(components)),
        evidence_type="site_field", source_revision_id=fact.source_revision_id,
        entity_id=fact.entity_id,
        locator=fact.source_revision_id + "#" + fact.field_path,
        text="; ".join(components),
    )
    return unit, EvidencePointer(unit.evidence_id, "SiteFact",
                                 fact.fact_id, owner.canonical_url)


def _relation_projection(rel, owner):
    unit = EvidenceUnit(
        evidence_id=stable_id("saturn-relation-projection-v1", rel.relation_id),
        evidence_type="relation", source_revision_id=rel.source_revision_id,
        entity_id=rel.subject_entity_id,
        locator=rel.source_revision_id + "#" + rel.source_field_path,
        text=rel.subject_entity_id + " " + rel.predicate + " " +
             rel.object_entity_id,
    )
    return unit, EvidencePointer(unit.evidence_id, "SiteRelation",
                                 rel.relation_id, owner.canonical_url)


def stage_saturn_knowledge_snapshot(
    site: SiteContentPackage,
    catalog: SupportCatalogResult,
    external: ExternalDocumentResult,
) -> SaturnSnapshotBuildResult:
    """Validate first; stage useful diagnostics without overriding readiness."""
    try:
        validation = validate_saturn_snapshot_inputs(site, catalog, external)
    except (TypeError, ValueError, AttributeError, KeyError, IndexError) as exc:
        return SaturnSnapshotBuildResult(None, (
            SnapshotIssue("invalid_adapter_structure", type(exc).__name__),))
    if validation.issues:
        return SaturnSnapshotBuildResult(None,
                                         sorted_canonical(validation.issues))

    gates = (site.ready_for_promotion, catalog.ready_for_promotion,
             external.ready_for_promotion)
    issues = [
        SnapshotIssue(name + "_not_ready", name)
        for name, flag in zip(("site", "catalog", "external"), gates) if not flag
    ]
    for relation in validation.unresolved_relations:
        issues.append(SnapshotIssue("unresolved_relation", relation.relation_id,
                                    "warning"))

    source_revisions = sorted_canonical(site.source_revisions)
    entities = sorted_canonical(site.entities)
    facts = sorted_canonical(site.facts)
    relations = sorted_canonical(validation.resolved_relations)
    unresolved = sorted_canonical(validation.unresolved_relations)
    dictionaries = tuple(sorted(site.dictionaries, key=lambda x: x.path))
    documents = sorted_canonical(catalog.documents)
    occurrences = sorted_canonical(catalog.occurrences)
    associations = sorted_canonical(external.associations)
    pdf_revisions = sorted_canonical(external.revisions)
    statuses = sorted_canonical(external.statuses)
    pdf_diagnostics = sorted_canonical(external.diagnostics)

    owner_by_id = {owner.entity_id: owner for owner in entities}
    evidence = []
    pointers = []
    for fact in facts:
        result = _field_projection(fact, owner_by_id[fact.entity_id])
        if result:
            unit, pointer = result
            evidence.append(unit)
            pointers.append(pointer)
    for relation in relations:
        unit, pointer = _relation_projection(relation,
                                            owner_by_id[relation.subject_entity_id])
        evidence.append(unit)
        pointers.append(pointer)
    for entity in entities:
        for passage in site_passages(entity):
            evidence.append(passage)
            pointers.append(EvidencePointer(
                passage.evidence_id, "SiteEntity",
                entity.entity_id, entity.canonical_url))
    pdf_by_id = {
        stable_id("saturn-pdf-revision-v1", rev.document_id, rev.url,
                  rev.bytes_sha256, rev.parser_version): rev
        for rev in pdf_revisions
    }
    for passage in external.evidence:
        pdf = pdf_by_id.get(passage.source_revision_id)
        if pdf is None:
            return SaturnSnapshotBuildResult(None, (
                SnapshotIssue("unknown_pdf_evidence_revision",
                              passage.source_revision_id),))
        evidence.append(passage)
        pointers.append(EvidencePointer(
            passage.evidence_id, "PdfRevision",
            passage.source_revision_id, pdf.url))

    if len({x.evidence_id for x in evidence}) != len(evidence):
        return SaturnSnapshotBuildResult(None, (
            SnapshotIssue("duplicate_evidence_id", "assembled corpus"),))

    occurrences_by_doc = {}
    for occurrence in occurrences:
        occurrences_by_doc.setdefault(occurrence.document_id, []).append(occurrence)
    status_by_doc = {status.document_id: status for status in statuses}
    matches = tuple(
        DocumentMatch(
            doc, tuple(occurrences_by_doc[doc.document_id]),
            status_by_doc[doc.document_id].status
            if doc.document_id in status_by_doc else None,
            status_by_doc[doc.document_id].revision_id
            if doc.document_id in status_by_doc else None,
        )
        for doc in documents
    )
    evidence = sorted_canonical(evidence)
    pointers = sorted_canonical(pointers)
    issues = sorted_canonical(issues)
    counts_map = {
        "source_revisions": len(source_revisions),
        "entities": len(entities),
        "facts": len(facts),
        "relations": len(relations),
        "unresolved_relations": len(unresolved),
        "dictionaries": len(dictionaries),
        "support_documents": len(documents),
        "occurrences": len(occurrences),
        "associations": len(associations),
        "pdf_revisions": len(pdf_revisions),
        "pdf_statuses": len(statuses),
        "pdf_diagnostics": len(pdf_diagnostics),
        "answer_evidence": len(evidence),
        "document_matches": len(matches),
    }
    for kind in ("site_field", "relation", "site_passage", "pdf_passage"):
        counts_map[kind] = sum(x.evidence_type == kind for x in evidence)

    manifest = SaturnSnapshotManifest(
        site_manifest=site.manifest, site_parser_version=site.parser_version,
        catalog_version=catalog.catalog_version,
        pdf_parser_version=external.parser_version,
        builder_version=BUILDER_VERSION,
        source_revision_ids=tuple(sorted(r.revision_id for r in source_revisions)),
        pdf_revision_states=tuple(sorted(
            (rid, rev.extraction_state, rev.bytes_sha256)
            for rid, rev in pdf_by_id.items())),
        counts=tuple(sorted(counts_map.items())),
        corpus_hash="", snapshot_id="",
    )
    snapshot = SaturnKnowledgeSnapshot(
        source_revisions, entities, facts, relations, unresolved,
        dictionaries, documents, occurrences, associations,
        pdf_revisions, statuses, pdf_diagnostics,
        evidence, pointers, matches, issues, gates, manifest,
    )
    manifest = replace(manifest, corpus_hash=stable_id(
        "saturn-unified-corpus-v1", snapshot_content(snapshot)))
    unsigned = {key: value for key, value in asdict(manifest).items()
                if key != "snapshot_id"}
    manifest = replace(manifest, snapshot_id=stable_id(
        "saturn-unified-snapshot-v1", unsigned))
    snapshot = replace(snapshot, manifest=manifest)
    if not verify_snapshot_seal(snapshot):
        return SaturnSnapshotBuildResult(None, (
            SnapshotIssue("manifest_seal_failure", "snapshot"),))
    return SaturnSnapshotBuildResult(snapshot, issues)


def build_saturn_knowledge_snapshot(
    site: SiteContentPackage,
    catalog: SupportCatalogResult,
    external: ExternalDocumentResult,
) -> SaturnKnowledgeSnapshot:
    """Strict public contract; partial/invalid inputs cannot produce active data."""
    staged = stage_saturn_knowledge_snapshot(site, catalog, external)
    if not staged.ready_for_promotion:
        raise SnapshotBuildError(staged.issues)
    return staged.candidate
