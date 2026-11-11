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

## PR #31 — Independent Acceptance Review correction cycle (11 Nov 2026)

**Session A review:** 2 BLOCKER + 3 IMPORTANT, one consolidated correction in the SAME PR #31. All changes here are limited to Stage 5E evaluator code, tests, documentation and CI. No Stage 4A–5D changes. Existing v0.1 open dataset bytes and first measured v0.1 report bytes remain exactly as first committed; they are not retroactively upgraded.

### CR-01 — Need and owner scope

- Independently recompute each observed Stage 5B need ID from its question hash/span/kind/source fields; check exact question spans, unique IDs, finding IDs and canonical source meaning.
- Explicitly match source-authored gold fact/relation/document requirements against runtime need semantics; parser output **cannot define gold**.
- Per-statement need ID must exist, be unique and match its typed source evidence; final statement ID binds need, document/evidence, kind and citation.
- `answered` cannot contain unresolved; `partial` must contain genuinely unresolved needs; `needs_support` and `clarification` account for all unresolved needs.
- Owner-qualified original C16 retains an *authored source-scope sidecar* mapped to `products/device-x` in `saturn_answer_dataset.py` (exact dataset ID + exact case ID + exact authored question). The original frozen JSON is **not modified**. Newly authored owner-qualified documents must include explicit `owner_entity_id` in gold. Citation must contain only that owner's authenticated occurrences.
- Snapshot, bundle, question and need evidence identities independently rechecked; a correctly supported statement from another question is not necessarily correct for this question.

### CR-02 — Complete blind provenance

- The frozen manifest now binds a valid 40-hex Git commit SHA (no `unavailable`), exact dataset hash, snapshot/corpus, deterministic bundle ID, config hash, scorer and rubric revisions, count and unique expected case IDs.
- `BlindRun.complete(report_bytes, dataset=...)` independently validates full report schema, bound experiment ID, code revision, dataset/snapshot/corpus/bundle/config identities, source-backed gold case IDs and authored statuses, per-case counter coherence, recomputed metrics and group breakdowns. Unknown fields, duplicate JSON keys and inconsistent counts are rejected.
- Durable START evidence is checked again on completion; exclusive `O_EXCL` START/FAILED/COMPLETE behavior is preserved. Git SHA failure aborts CLI before START. Controlled tests use only copies of **open authored cases**, never a real hidden/blind set.
- The `SaturnFakeClaimProvider` profile remains offline test-only. No actual blind dataset is read or executed. `independent_blind_evaluation=NOT_RUN` for all public measurements.

### CR-03 — Exact substring quotation

- A `source_quote` passes extractive integrity when its exact literal text occurs **anywhere** within the source's verified site/PDF passage, including the middle. Altered text or a mismatched PDF page/revision/parser fails.
- Quotes still have zero power to prove technical field/relation requirements and are omitted from the primary answer.

### CR-04 — One pinned retrieval bundle

- Diagnostic retrieval runs on `session._bundle` under the same session lock as context construction/assessment/verification/assembly. An independently captured `service.search_saturn` active pointer is no longer used.
- Retrieval evidence/document IDs must match the actual context; snapshot, bundle, question and derived stage identity must agree. Concurrent publication is regression-tested by replacing the active bundle during retrieval.
- Document attribution distinguishes not retrieved, retrieved but not selected, selected but not a satisfied document need, and missing only at answer assembly. Explicit policy blocks and potential conflicts have separate reasons; without enough diagnostic evidence the reason is `undetermined`.

### CR-05 — Measurement semantics

- Separate counters and clearly labeled ratios: `source_unsupported_claims` (only technical assertions, denominator technical assertions), `off_question_source_backed_claims` (denominator all issued field/relation/document assertions) and `extra_unsupported_answer_text` (case denominator).
- Expected `answered`, `needs_support`, `clarification` and `partial` receive separate status-group breakdowns; partial cases are not counted as ordinary negative refusals.
- Separate `policy_restriction`, `evidence_conflict` and `technical_error` rates. `saturn_controlled.py` deliberately injects known policy restriction, local retrieval error and a **simulated** conflict into three already-public calibration questions; the resulting supplemental report must be labeled `synthetic_controlled_fault_injection`, never blind, real-site or production acceptance.
- Corrected scorer/rubric identities are `saturn-grounding-evaluator/0.1.1` / `saturn-grounding-rubric/0.1.1`. The original calibration report remains the first measured `0.1.0` artifact, not a rewritten correction result.

### Review reproducibility

```bash
PYTHONPATH=backend/src python -m unittest discover -s backend/tests/unit -p 'test_saturn_grounding_evaluation*.py' -v
python scripts/verify_offline.py
PYTHONPATH=backend/src python -m saturn_ai.evaluation.saturn_grounding --profile calibration --dataset evaluation/datasets/saturn-grounding-calibration-v0.1.json --report /tmp/saturn-calibration-corrected.json
PYTHONPATH=backend/src python -m saturn_ai.evaluation.saturn_controlled
```

A dedicated fast `saturn-evaluator-targeted` job was added to the existing CI, alongside the full offline, ONNX and calibration jobs. Independent Acceptance Review and a separate owner-directed merge remain mandatory; no Stage 6.

**Known limits:** deterministic Fake provider and narrow source-declared query grammar; no independently authored blind, external LLM generalization, real-device verification or production readiness. The simulated conflict is a fault-injection test of *measurement classification*, not a real engineering conflict benchmark.


### Revised measurements, scorer/rubric 0.1.1 (preserved as NEW files)

- [Actual revised open calibration JSON](../../evaluation/reports/saturn-grounding-calibration-review-v0.1.1.json) — measured on code SHA `bad73187f6e3dca187636ae5cea4cbca0c69dded`, **same original gold SHA-256** `eff320bc664fdb23dc7ee69ddb479c796a5c5aeee341a043f3d782119ab733e8`: 28/28 fully correct, 17/17 positive, 5/5 needs_support, 3/3 clarification, 3/3 partial, citations 24/24, requirement recall 23/23, false refusals 0/17, source-unsupported 0/21 technical assertions, off-question 0/23 answer assertions, extra unsupported text 0/28 cases, policy restrictions 0/28, evidence conflicts 0/28, errors 0/28.
- [Separate controlled fault injection JSON](../../evaluation/reports/saturn-grounding-controlled-review-v0.1.1.json) — **3 intentionally failing cases**, policy 1/3, error 1/3, injected conflict 1/3, expected complete-answer rate 0/3. These are *deliberate injections*, not three real failures of unmodified application source evidence, and never blind or real sample.
- Dedicated `saturn-evaluator-targeted` suite: **121 tests** (original 83 + 38 review-correction tests); exact-head final push/PR CI to be checked in PR. The historical original calibration JSON and first v0.1 report are protected in CI by their original Git blob SHA (`a4ca1c2567e391319e26b0ca905c38f8739400cb`, `ffd6259552c56cd86c230490f60339e437303f7f`).

**Final CR-02 defense-in-depth:** `BlindRun.complete` replays `validate_gold(raw_bytes, pinned_snapshot)` itself after START, without accepting a caller-created gold dataclass. Separate test verifies that a known verified unresolved need cannot be disguised as an admissible `partial`; malformed report cases fail closed. Total targeted suite **121** tests.


## PR #31 — Final Consolidated Acceptance Corrections CR-06–CR-09 (12 Nov 2026)

**Scope:** Stage 5E evaluator-only changes in existing PR #31. The original v0.1 calibration gold and first report are unchanged. All v0.1.1 measured reports are likewise retained; these corrections introduce distinct scorer/rubric identities `saturn-grounding-evaluator/0.1.2` and `saturn-grounding-rubric/0.1.2`. No production Stage 4A–5D, ranking, policy, Fake provider, external site or hidden blind changes.

### CR-06 — Extractive quote integrity (BLOCKER)

- The independent Stage 5E quote scorer rejects empty or whitespace-only strings and modified strings; accepts substantive exact substrings from anywhere within site/PDF passage (including the middle).
- All canonical citation metadata remains bound, including PDF physical page, document/bytes revision and parser. The trace must bind the quote to the original question need and selected candidate.
- The `pdf_quote` gold requirement now has explicit semantics: only a matching `source_quote` from the exact gold document ID, PDF revision, evidence ID, physical page and **exact independently authored quote** satisfies *extractive integrity*. An unrelated exact quote from the same PDF cannot satisfy it.
- Dedicated `extractive_quote_integrity` counts and `engineering_requirement_recall` make clear that quote integrity is **not** a verified field/relation or engineering claim. This is a contextual evidence test; quote-only questions remain `needs_support`.

### CR-07 — Independent semantic need binding (BLOCKER)

- Independent lexical check requires `field_path` to equal the actual exact source-declared field token within its original question span; hashing an altered field path and need ID is insufficient. Every field in a multi-need list is checked, including unresolved ones.
- The source-question entity is independently matched against pinned snapshot entity ID/title/slug and explicit source-declared aliases. Relation subject, object and predicate; owner-qualified document title/owner are likewise checked without invoking Stage 5B parser.
- Nested/indexed/JSON-quoted paths and source-declared punctuation are treated as **opaque literal spans**, not split on punctuation within a field; only separators **between** recorded spans are syntax-checked. Baseline C11/C12/C20/C25/C28 and C16 remain regression fixtures.

### CR-08 — COMPLETE receipt SHA integrity (IMPORTANT)

- `BlindRun.complete` validates raw source-backed gold and final report, writes canonical UTF-8 JSON through the existing `O_EXCL` durable writer, then hashes the **actual bytes at the persisted report path** to construct `COMPLETE.report_sha256`.
- An equivalent non-canonical input may be normalized, but the receipt MUST hash exactly the saved file, not the caller's original bytes. START/FAILED/COMPLETE one-shot semantics and no-overwrite protections are unchanged. This does not execute a hidden/blind experiment.

### CR-09 — Retrieval applicability and per-need attribution (IMPORTANT)

- `source_hit_at_5` and `document_hit_at_5` are `null` / NOT_APPLICABLE unless a complete pinned retrieval diagnostic trace is available; a known measured miss is `false`. Unavailable measurement is excluded from the hit-rate denominator, and explicitly reported as `source_hit_at_5_not_measured_cases` / `document_hit_at_5_not_measured_cases`.
- Evidence recall likewise has no denominator for a pre-retrieval failure. Technical errors cannot masquerade as ordinary retrieval misses.
- Attribution follows **each specific missing requirement's** observed need/finding/evidence, not an unrelated need's `covered_structured` status: parser/need, sufficiency, generation and final assembly causes are distinguished only where observed.
- Legacy adversarial tests T71–T74 use fully observed pinned traces before deliberate mutation, rather than treating partial synthetic traces as proof of retrieval completion.

### Tests and measurement constraints

- Added **26 CR06–CR09 targeted tests** to the existing 121 Stage 5E tests (147 targeted cases total). Tests exercise nonempty/mid-passage/PDF provenance, source-authored `exact_quote`, field/entity tampering, unusual field tokens, multi-need parser attribution, retrieval NOT_APPLICABLE, and persisted canonical/noncanonical JSON SHA receipts.
- The new open calibration and controlled-fault measurements are versioned **0.1.2** separately from historical 0.1 and 0.1.1 reports. Calibration uses the same frozen, open 28-case gold (`eff320bc664fdb23dc7ee69ddb479c796a5c5aeee341a043f3d782119ab733e8`).
- Controlled examples include intentionally policy-blocked evidence, an injected retrieval error and a *simulated* conflict; they are **not real-site failures or independent blind**. `independent_blind_evaluation=NOT_RUN`, `production_readiness=false` throughout.
- Final independent Acceptance Review and explicit owner-directed merge are separate decisions; no Stage 6.



### Final independently measurable Stage 5E revision 0.1.2

- [Final open calibration report](../../evaluation/reports/saturn-grounding-calibration-final-review-v0.1.2.json) — measured on `ab5b946d9f14edca89af66e644a2325ed57695b8`, **28/28** fully correct, 17/17 positive, 5/5 needs_support, 3/3 clarification, 3/3 partial; engineering requirement recall 23/23, citation validity 24/24, source-hit@5 18/18, document-hit@5 2/2, 0 source-unsupported technical assertions, 0 off-question assertions, 0 extra unsupported answer text.
- [Final controlled-fault report](../../evaluation/reports/saturn-grounding-controlled-final-review-v0.1.2.json) — measured on the same code SHA. Of 3 intentionally injected faults, policy restriction 1, technical error 1, simulated conflict 1. `source_hit_at_5` 1/2 **measured** cases, **1 not measured** (technical retrieval failure C02 is `null`, excluded from denominator). All controlled cases intentionally fail complete-answer assessment; no hidden blind test performed.
- The earlier separately recorded `saturn-grounding-calibration-review-v0.1.2.json` showed **27/28** because independent semantic validation incorrectly rejected case C27, a field with a preserved unresolved suffix. This was fixed in evaluator code at `ab5b946...`; the original intermediate report is **retained, not rewritten**. The final report above is the authoritative corrected measurement. This historical transient was an *evaluator false negative*, not a production Stage 5B change.
- An extra C27 mixed field/unresolved regression means **147 targeted tests** (original Stage 5E 121 + final-review 26). Original frozen v0.1 calibration and its first measured report, and v0.1.1 reports, remain unchanged. The `0.1.2` measurement is open synthetic calibration, not a blind benchmark; `production_readiness=false`.

