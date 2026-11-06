# Local Reranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans, inline. Владелец принял дизайн PR #6 и явно поручил реализацию; отдельного подтверждения плана не требуется.

**Goal:** bounded policy-safe local pair reranking and actual unchanged synthetic benchmark.
**Architecture:** captured IndexSet → hybrid top30 → canonical passages → pinned CPU ONNX scorer → current-policy survivors → top5. Separate pair manifest and evaluator; baseline search unchanged.
**Tech Stack:** Python3.12, unittest, existing locked numpy/tokenizers/ONNX/ORT/Qdrant, no new dependencies.
**Spec:** [accepted design](../specs/2026-11-06-local-reranking-design.md).

## Global Constraints

- Query<=4000chars, passages<=20000chars, <=30pairs, batch<=8, <=512tokens longest_first; single raw logit [batch,1].
- Frozen corpus10docs44chunks/dataset30cases, BM25k1=1.2/b=.75, channel40/RRF60; input30/final5. No held_out tuning.
- Immutable verified bytes, single-file ONNX, atomic no-replace, no runtime downloads. No model/artifact dumps in Git.
- Saturn-Main-Site read-only, no real source approvals/cloud/API/UI/generation/evidence gate in this stage.
- Numeric fixtures runtime_contract only; actual semantic report requires prepared semantic_candidate.

## Review Focus

- Concurrent index publication must not change the canonical snapshot used for scoring (Task1 test).
- Revocation while scorer runs must exclude newly denied chunks and renumber survivors (Task1 test).
- Alternate output shapes/NaN/score count mismatch must fail, not fallback (Tasks1/2 tests).
- Complete artifact swap must not mix reported provenance and runtime identity (Task2 test).
- Missing pool gold or overlapping evidence labels must not inflate nDCG/oracle (Task3 tests).

### Task 1: policy-safe rank orchestration

Files: retrieval/reranking.py (Reranker protocol, RerankTrace), retrieval/service.py (captured search helper + rerank), backend/tests/unit/test_reranking.py.
Interfaces: Reranker.identity dict; score_pairs(query,list[str])->list[float]; service.rerank(query,reranker,mode='hybrid')->RerankTrace(snapshot_id,mode,baseline,input_candidates,scored,final,reranker_identity,scoring_seconds). baseline SearchTrace final limited5; input candidates<=30; final<=5.
- [x] Write tests for score ordering/tie rank, canonical text, invalid query/limits/score count/NaN/Inf/duplicate/wrong source/snapshot, empty pool; policy revoke during scorer and active publication capture.
- [x] Run `PYTHONPATH=backend/src work/venv/bin/python -m unittest discover -s backend/tests -p test_reranking.py -v`; expect RED absent rerank.
- [x] Implement typed trace + strict validation and shared captured search, preserve existing search outputs. Same command expected GREEN.
- [x] Commit Task1 and ledger results.

### Task 2: pinned ONNX pair adapter and explicit preparation

Files: retrieval/reranker_model.py, scripts/prepare_local_reranker.py, config/rerankers/mmarco-minilm.profile.json, tests/unit/test_reranker_model.py; embeddings.py only shared low-level byte graph loader extraction if needed.
Interfaces: LocalONNXReranker(directory), read_reranker_provenance(directory,require_semantic=True,identity=None), prepare_local_reranker(profile_raw,model_path,tokenizer_path,card_path,license_path,destination)->smoke; load_semantic_reranker(directory)->(scorer,provenance) rejects complete bundle swap.
- [x] Write numeric actual CPU graph tests (dynamic pair batch/token shapes), pair tokenization/truncation/pad, shape/finite rejection, drift, external-data, runtime_contract benchmark guard, bundle swap, collision/symlink/cleanup.
- [x] Run targeted test_reranker_model.py; expect RED missing module.
- [x] Implement strict versioned profile + manifest with hashes, exact-byte ORT CPU, separate pair scorer; reuse bounded file reads/atomic publish, no embedding mean pooling. Same command expected GREEN in optional profile, numeric tests skipped in base.
- [x] Explicit operator curl pinned official checkpoint/card/config/tokenizer; review graph/format/license evidence, prepare under work/. Record exact blocker if incompatibility, no fallback/guess.
- [x] Commit Task2; weights never tracked.

### Task 3: evaluation, CLI, diagnostics

Files: evaluation/reranking.py, evaluation/__main__.py, retrieval/__main__.py, tests/unit/test_reranking_evaluation.py.
Interfaces: evidence_ndcg(case,snapshot,final)->float|None; run_reranking_evaluation(root,dataset_path,model_directory,reranker_directory)->report. CLI --stage reranking --mode hybrid --model-dir --reranker-dir; require-source-hit-target remains explicit gate.
- [x] Write hand-computed IDCG all snapshot relevant chunks, missing pool gold, duplicate chunks, negative null, binary multiple evidence matches, pool coverage, baseline/reranked metrics/no label leakage and runtime_contract rejection tests; RED.
- [x] Implement separate measured report with identity/config/provenance/software, source/MRR/recall/nDCG, top30 IDs/scores, timing separately; ground/refusal not_run. GREEN targeted.
- [x] Actual fixed E5+reranker run; preserve poorer result as-is, no dataset/config tuning. No checkpoint -> precise blocker/not_run.
- [x] Add optional numeric CI, CLI docs/ADR/stage/status/handoff, commit.

### Task 4: review, verify, publish

- [x] Run base+optional `scripts/verify_offline.py`; expected project/backend tests PASS, lexical17/20. All new targeted tests pass in optional profile.
- [x] Independent whole-branch review against main92e7022, including inherited design docs; fix Important/Critical via RED→GREEN and full suite. Keep review rulings in ledger.
- [x] Check diff/no artifacts; push feature PR, inspect actual CI. Do not merge automatically. Update durable report with actual results/limitations/next stage.
