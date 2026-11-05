# Snapshot and baseline implementation plan

> Execute inline with superpowers:executing-plans. Scope approved by owner; independent whole-branch review before publication.

**Goal:** immutable snapshot/policy/index contracts plus 10-document/30-question synthetic baseline and reproducible preflight.
**Architecture:** ingestion → checked KnowledgeSnapshot → validated dense/lexical declarations → in-memory catalog; independent strict dataset validator.
**Tech stack:** Python 3.12, existing locked PyYAML/pypdf, unittest. No new dependencies/models/services.
**Spec:** [design](../specs/2026-11-05-snapshot-baseline-design.md).

## Global constraints / Review focus

Synthetic/test_only only. No real approvals, model quality claims or M1 behavior changes. Guard source/provenance forgery, old snapshot after policy change, fake descriptor coverage, contradictory dataset labels and preflight confused with evaluation. Inputs to builder/validator are untrusted records even if dataclasses are frozen.

### Task 1 — snapshot contracts

Files: backend/src/saturn_ai/snapshots.py; backend/tests/unit/test_snapshots.py.
Interfaces: build_snapshot(ingestion, registry)->KnowledgeSnapshot; IndexDescriptor; SnapshotBundle; SnapshotCatalog(registry).activate(bundle)/capture()/update_policy(registry)/revoke(source_id)/eligible_chunks(bundle, usage).
- [x] Write tests, observe missing feature RED.
- [x] Implement immutable explicit policy payloads, deterministic identities, coverage validation and atomic in-memory activation.
- [x] Tests must show idempotence, update/deletion/rollback, deny of forged/missing metadata, index mismatch, failed activation and revocation independent of snapshot.
- [x] GREEN and commit.

### Task 2 — authored corpus, dataset and preflight

Files: fixtures/evaluation/, evaluation/datasets/synthetic-v1.json, backend/src/saturn_ai/evaluation/{dataset,__main__}.py, scripts/generate_synthetic_pdfs.py, backend/tests/unit/test_evaluation.py.
Interfaces: validate_dataset(raw, snapshot)->Dataset; run_preflight(root, dataset_path)->dict summary. Cases carry fact/source/page labels, not executable answers.
- [x] Write tests for 10 docs/30 cases, category/split distribution, label support, malformed/contradictory labels, registry/hash drift, real source IDs; observe RED.
- [x] Author 8 Markdown + 2 generated PDF source fixtures and 30 cases with independent gold labels; implement strict validation and safe counts/revisions/per-case report with quality checks not_run.
- [x] GREEN, inspect preflight report and commit.

### Task 3 — unified verification and durable memory

Files: scripts/verify_offline.py, .github/workflows/ci.yml, README, ADR/stage/status/handoff and evaluation/reports/.
- [x] One documented command runs project checks + tests + preflight after separate dependency install.
- [x] Independent review; reproduce/fix important findings RED→GREEN, run full verification.
- [x] Record PR #2 merge 909072f and CI 42062413579 success; update scoped results, report and next step.
- [ ] Push feature PR, inspect actual CI and preserve evidence. No automatic merge.
