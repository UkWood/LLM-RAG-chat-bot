# Stage 5E — Saturn Grounding Evaluation v0.1

**Date:** 2026-11-11. **Role:** Coding Session B. **Status:** implementation candidate; independent Session A Acceptance Review required. **No merge.**

## Baseline and scope

- Base `main`: `8dc9d2fbd20854bd54903ff617581ed4ecad6e31` (Stage 5D PR #30 merged; baseline offline/ONNX merge CI success).
- Feature branch: `feat/saturn-grounding-evaluation-v0.1`; one PR targeted to `main`.
- Saturn-specific measurement of pinned Stage 4A → 4B → 5A → 5B → 5C → 5D **without changing production answer contracts, retrieval, verifier, parser, trust root, or operational policy**.
- `UkWood/Saturn-Main-Site`: READ-ONLY, no modifications.
- Offline only: canonical fixture snapshot, lexical retrieval, fixed `top_k=10`, genuine session lifecycle, `SaturnFakeClaimProvider` exact class. No cloud, actual LLM, external requests, production UI/deployment or Stage 6.

## Evaluation architecture

1. `saturn_fixture.py`: independently authored open questions against checked-in Saturn site fixture bytes plus separately declared in-memory fixture additions and fake PDF physical pages; canonical Stage 4A adapters construct the single snapshot.
2. `saturn_answer_dataset.py`: immutable strict `SaturnEvaluationCase`/gold requirements, canonical raw bytes SHA-256, snapshot/corpus binding, actual fact/relation/document/PDF source checks and rejection of ambiguous, duplicate or fabricated pointers.
3. `saturn_grounding.py`: invokes the public production-like stages; **only** the question and fixed profile cross application boundary; obtains returned `SaturnAnswerResult` and bounded stage trace, then passes those to independent scorer. Technical error becomes explicit safe `error`.
4. `saturn_answer_scoring.py`: independently compares text, source-backed claim identity, raw field value/unit/qualifiers, exact directed relation, document metadata, source commits/blob/content hashes, URLs, field locator, PDF revision/parser/physical page, and citation-to-statement binding. A source quote never entails a technical value. `fully_correct` demands more than correct status. Unsafe extra assertions, missing requirements and false refusals are separated.
5. `saturn_answer_reporting.py`: deterministic JSON with per-case outcomes, denominators, quality metrics and category/profile/status/need-count breakdown. No raw questions, source passages or traceback by default.
6. `saturn_answer_freeze.py`: frozen code/snapshot/corpus/dataset/config/provider/scorer/rubric identity; exclusive durable START receipt before parsing blind gold, no silent retry or report overwrite, FAILED/COMPLETE receipts.

Historic `evaluation/datasets/synthetic-v1.json`, `planner-v2-blind.json` and its manifest, historic experimental reports and all legacy evaluation contracts are **untouched**. No retroactive interpretation of legacy metrics as Stage 5D quality.

## Open calibration (measured, not independent blind)

A source-backed open dataset of 28 cases is stored at `evaluation/datasets/saturn-grounding-calibration-v0.1.json`, exact raw bytes SHA-256:

`eff320bc664fdb23dc7ee69ddb479c796a5c5aeee341a043f3d782119ab733e8`

Fixture snapshot ID:

`23363c78bdec37ffeb74fd5cc985e0bb781764049e4178f070f452651967d0cf`

Fixture corpus hash:

`13c113ee056b93cb140f92ddeea134c803fb2947ab0218fb528a452888579516`

Retrieval bundle ID:

`8079ed604a85ac948a4273765412bc401ffe0497b0545b19c53d884833dad381`

Fixed runtime: `SaturnFakeClaimProvider`, lexical, `top_k=10`; configuration hash `58f6320e5d0e604ec04a0560d155f09ccebd1a290ea097cd07f35f6db98ee487`. Gold author: Coding Session B, **open calibration, not an independent blind author**.

The first actual execution was performed by GitHub Actions [push workflow #43082293017](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43082293017) on code commit `4fde232947e6989a242fd3308e0c7cf4eedb29d1`. Machine-readable result is preserved at `evaluation/reports/saturn-grounding-calibration-v0.1.json`.

| Metric | First measured result |
|---|---|
| Cases | 28 |
| Gold expected answered | 17 |
| Gold expected needs_support | 5 |
| Gold expected clarification | 3 |
| Gold expected partial | 3 |
| Positive complete-answer rate | 17/17 |
| Correct needs_support | 5/5 |
| Correct clarification | 3/3 |
| Status accuracy / overall correctness | 28/28 |
| Requirement recall | 23/23 |
| Unsupported technical claims | 0/23 issued technical assertions |
| Valid emitted citations | 24/24 |
| False refusal of answerable questions | 0/17 |
| Technical errors | 0/28 |
| Source-hit@5 (positive evidence cases) | 18/18 |
| Document-hit@5 (separate metadata channel) | 2/2 |
| Evidence recall | 21/21 |
| Failed case IDs | none |

**Interpretation:** This is an OPEN SYNTHETIC CALIBRATION measurement of deterministic fake-provider behavior in the approved tiny fixture corpus. `quality_target_met=null` and `production_readiness=false` in this report are intentional: a successful open set neither independently measures a realistic LLM nor establishes any product acceptance. Results can change on a separately authored blind or real-site sample. This score must not be called independent blind PASS.

## Independent blind and real sample

- Independently authored, reviewed and frozen blind case set not supplied: `independent_blind_evaluation=NOT_RUN`.
- Blind experiment requires code SHA, frozen dataset SHA, snapshot ID/corpus hash, settings hash, provider/scorer/rubric revisions and a one-shot durable START/FAILED/COMPLETE record. Do not use exposed old planner blind data; do not tune or change thresholds after first-run.
- Target 40 blind cases (24 answerable and 16 negative/ambiguous), acceptance thresholds and gold must be independently reviewed/approved before freezing and measuring product quality.
- No `real_sample` evaluation performed: verified gold from a pinned real site/PDF set is still missing. The fixture-only CLI refuses to masquerade as real sample.
- No production deployment, local production model or HTTP adapter.

## Commands and testing

Locked Python3.12 parser dependencies are required, but the evaluation runtime itself does not fetch models, source data or keys.

```sh
PYTHONPATH=backend/src python -m saturn_ai.evaluation.saturn_grounding \
  --profile calibration \
  --dataset evaluation/datasets/saturn-grounding-calibration-v0.1.json \
  --report /tmp/saturn-grounding-calibration.json
python scripts/verify_offline.py
```

Source-backed open fixture generation is available only with the explicit `--generate-calibration` flag (choose a new output path; never silently overwrite the frozen file). CI executes the calibration separately from the offline/ONNX code checks, because high/low quality is a measured output and **not a reason to conceal valid evaluator execution**. The report source is attached to the exact CI run/commit; a later docs-only SHA does not retroactively change that original measurement.

New targeted regression suite: `backend/tests/unit/test_saturn_grounding_evaluation.py`. Includes strict gold validation, tampered fact provenance, invalid source revision/hash/field, PDF pages/extract mismatch, false refusal and partial-score detection, deterministic full integration, metric denominators, frozen blind first-run/no-overwrite and a runtime-boundary spy. Exact test counts / final push + PR CI SHA to be confirmed in the PR.

## Known limitations and correction candidates

- Open data contains fixed synthetic fixture facts and mechanically rigid supported question grammar, so 100% performance is **not** evidence of general-language understanding.
- An independent human-authored 40-case blind set and separately approved thresholds still need to be provided; no blind results exist.
- PDF quoted passage can be checked for extractive integrity, but v0.1 cannot interpret PDF tables or promote a quote into engineering truth.
- Real sample and local semantic model evaluation remain separate activities.
- Observed Stage 4B–5D defects must be filed for Session A corrective decision, never silently tuned in this PR.
- Stage attribution is diagnostic, uses stage traces, and `undetermined` should be preserved when root cause cannot be demonstrated.
- Any subsequent report must preserve exact code/dataset/snapshot/config revision identity to permit comparison.

## Release / review gate

**READY FOR INDEPENDENT ACCEPTANCE REVIEW only after final exact-head push and PR CI are successful and full offline suite passes.** Coding Session B must not merge and must not start Stage 6. Session A issues consolidated substantive corrections and approves merge only under separate owner direction.
