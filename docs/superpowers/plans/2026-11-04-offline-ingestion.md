# Offline ingestion implementation plan

> Execute inline with superpowers:executing-plans; independent whole-branch review before PR.

**Goal:** этап 2 offline ingestion + strict runtime registry validation on synthetic fixtures.
**Architecture:** immutable registry → deny-before-read byte loading → site/PDF adapters → provenance documents/chunks; no retrieval integration.
**Tech stack:** Python 3.12, pinned PyYAML/pypdf, unittest; tests offline after dependency installation.
**Spec:** [design](../specs/2026-11-04-offline-ingestion-design.md).

## Global constraints / Review focus

No real approvals/downloads/cloud/site edits. M1 unchanged. Check duplicate keys/types/unsafe locator, nested metadata leakage, source approval inheritance, denied-source reads, PDF extraction failures/resource limits. Synthetic outputs cannot enter M1 provider silently.

### Task 1 — runtime policy

Files: backend/src/saturn_ai/ingestion/{registry,contracts}.py; backend/tests/unit/test_registry.py.
Interfaces: load_registry(bytes)->Registry; SourceRecord.permits(usage, content_hash, source_commit)->bool.
- [x] Write negative tests for current 8 pending records and strict policy/schema/hash/commit/URL/date scopes.
- [x] Observe RED; implement strict immutable records and registry loader, duplicate detection.
- [x] GREEN and commit.

### Task 2 — offline parser pipeline

Files: backend/src/saturn_ai/ingestion/{site,pdf,pdf_worker,pipeline,__main__}.py, backend/requirements.lock, fixtures/ingestion/, backend/tests/unit/{test_ingestion,test_pdf}.py.
Interfaces: build_fixture(root, registry, commit)->IngestionResult; parse_site(record, bytes)->Document; parse_pdf(record, bytes)->Document. Source identities bind exact versions, locator and parser version.
- [x] Write tests for draft/software/category/relations, facts+units, Markdown tables, idempotence/source dedupe, denied-byte isolation, hash/commit drift, unsafe files, body metadata exclusion, and PDF page/errors/limits.
- [x] Observe RED; implement bounded parsers and provenance chunks. Use generated authored PDFs, no real downloads.
- [x] GREEN; run CLI for synthetic fixture and current pending registry validation; commit.

### Task 3 — verification and publication

Files: .github/workflows/ci.yml, README, docs/PROJECT_STATUS, HANDOFF, decisions and stage report.
- [x] Add pinned dependency installation and parser suite to CI; preserve M1 and previous checks.
- [x] Independent review, reproduce/fix findings through RED→GREEN, run full suite and CLI.
- [x] Record M1 merge 0cfe174 and CI success, new scoped results and remaining real-ingestion gates; push feature branch/PR and verify actual checks.
