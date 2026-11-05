# Local retrieval baseline implementation plan

> Execute inline with superpowers:executing-plans; independent code review before publication.

**Goal:** BM25 measured baseline + local Qdrant/encoder adapters bound to snapshot, without false semantic quality claims.
**Architecture:** checked snapshot → BM25 + Qdrant → policy-filtered candidates → optional RRF → diagnostic/evaluation report. Gold labels stay outside retrieval.
**Tech stack:** Python3.12, qdrant-client local, existing parser dependencies, optional ONNX/tokenizers CPU profile; hash locks.
**Spec:** [design](../specs/2026-11-05-local-retrieval-design.md).

## Global constraints / Review focus

Real corpus/cloud unchanged; no model checkpoint available per owner. Distinguish BM25 measurements, vector contract tests and unmeasured neural search. Check actual artifact coverage/metadata, stale snapshot/current policy, malformed model outputs, label leakage, denominator/failed-case honesty and held_out tuning.

### Task 1 — local index implementations

Files: backend/src/saturn_ai/retrieval/{lexical,dense,embeddings,service}.py, backend/tests/unit/test_retrieval.py, backend/requirements.lock (+optional ONNX lock).
Interfaces: BM25Index(snapshot).search(query, allowed_ids, limit); QdrantIndex(snapshot, encoder, path=None).search(...); RetrievalService(catalog).publish(indexset)/search(query, mode, top_k); LocalONNXEncoder(local_dir).
- [x] Write ranking/filter/shape/coverage/promotion/revocation tests, observe RED.
- [x] Pin dependencies and implement pure BM25 + real Qdrant local vectors, encoder boundary and current policy gating.
- [x] GREEN, actual index smoke/reopen tests, commit.

### Task 2 — measured evaluation

Files: backend/src/saturn_ai/evaluation/retrieval.py, CLI, backend/tests/unit/test_retrieval_evaluation.py, evaluation/reports/.
- [x] Write metric/denominator/split/no-label-leak and unmeasured-mode tests; RED.
- [x] Implement lexical baseline report, optional real-checkpoint hybrid mode and local diagnostics; keep dataset/corpus frozen.
- [x] Run fixed config on both splits once, record actual successes/failures, not acceptance-by-assertion. Commit.

### Task 3 — review/publication

- [x] Unified offline verification includes index tests + measured lexical report; model download not required.
- [x] Independent review, reproduce/fix important findings RED→GREEN; full suite PASS.
- [ ] Update ADR/stage/status/handoff, record PR #3 merge be71efd and main CI 42089988455 success; publish PR/check actual CI. No auto merge.
