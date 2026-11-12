# Stage 5F–5I — Consolidated Real Corpus & Local Model Validation v0.1

**Date:** 2026-11-12  
**Role:** Coding Session B; Session A retains architecture and independent acceptance.  
**PR:** [#32](https://github.com/UkWood/LLM-RAG-chat-bot/pull/32) — DRAFT, one branch `feat/saturn-real-corpus-llm-validation-v0.1`.  
**Status:** IMPLEMENTATION IN PROGRESS — **NOT AN ACCEPTED EXPERIMENT**. No merge; no Stage 6.

## 1. Baselines and immutable boundary

- AI `main`: `84d783331cc755e688a7f8637be13c297c07f43e` verified before branch creation.
- READ-ONLY site `main`: `084d759487bfab6e111549c9b5469711ac5fc13e` verified. No site write tools invoked.
- Source trust: ADR-0012/0013 unchanged. No cloud egress; no new approvals.
- Stage 4A–5E public verified answer, citation and evaluation gates are reused.
- Historical frozen datasets and reports are **unchanged**.

## 2. Stage 5F implementation — experimental stand

`backend/src/saturn_ai/real_corpus_stand.py` composes existing:
`GitHubSnapshotProvider.fetch_snapshot` → selected verified Git source bytes →
`adapt_snapshot` → `adapt_support_catalog` → selected real HTTPS PDFs
via `adapt_external_documents` → `build_saturn_knowledge_snapshot` →
`build_saturn_retrieval_bundle` → Stage 5A/5B/5C/5D answer plus Stage 5E
diagnostic trace.

The source provider pins Git main and verifies blob SHA; the stand rejects any
site commit other than the exact baseline. It never synthesizes missing source
bytes. There is no untrusted user-supplied URL fetch and no site mutation.
The actual sample contains ten selected source records, plus four specific
linked PDF documents (14 selected source objects before supporting
Astro/schema/dictionary/route files):

| Source | Role |
|---|---|
| `src/content/products/bkd-pk-rf-2.md` | controller fields, units, PDF |
| `src/content/products/bkd-ups.md` | controller specs, units, PDF |
| `src/content/products/server-lanmon.md` | software/protocols, PDF |
| `src/content/systems/sistema-liftovogo-dispetcherskogo-kontrolya-sldks-1.md` | system, relations, PDF |
| `src/content/systems/newel.md` | linked system |
| `src/content/systems/informatsionno-izmeritelnaya-sistema-easdkiu.md` | linked system |
| `src/content/systems/programmnoe-obespechenie.md` | software group system |
| `src/content/groups/newel.md` | source-declared group |
| `src/content/groups/easdkiu.md` | source-declared group |
| `src/content/groups/programmnoe-obespechenie.md` | source-declared group |

The four exact PDF paths are named in `PDF_PATHS` in the module. Their bytes
hashes and physical page counts may **only** be populated after successful real
download/extraction. PDF failures abort the strict Knowledge Snapshot, rather
than creating fake text evidence. Real source and PDF manifests are emitted
from observed objects; output is local and exclusive-create.

The provider currently obtains the whole verified source file selection before
the stand selects its small corpus; it does **not** pretend to be a selective
GitHub network fetch. This must be measured for time/request budget.

### Invocation (real network is opt-in)

Install pinned dependencies with `backend/requirements.lock`. Set
`SATURN_GITHUB_TOKEN` to a read-only GitHub token and
`SATURN_GITHUB_OBJECT_FORMAT=sha1`. Do not commit either.

```bash
PYTHONPATH=backend/src python -m saturn_ai.real_corpus_stand \
  --allow-real-network --allow-development-pdf-worker \
  --provider fake --question 'БКД-ПК-RF.2: mass_kg?' \
  --report /tmp/saturn-real-stand.json
```

The existing subprocess PDF worker is explicitly DEVELOPMENT-ONLY and lacks a
production OS sandbox. Do not expose it in a service or production deployment.
The transport retains 3B HTTPS host/path allowlist, DNS pinning, SSRF and
redirect protections, size/page/time/resource limits. No arbitrary ZIP
unpacking or OCR.

## 3. Stage 5G implementation — open real evaluation runner

`backend/src/saturn_ai/real_corpus_evaluation.py` accepts a separately
authored exact-source-backed dataset with Stage 5E `real_sample` split.
It reuses `validate_gold`, `_run_question`, `score_answer`,
`build_report` and one pinned real source snapshot. Every runtime call
receives **only the original question**, never gold labels, expected answers,
or source pointers from the scorer.

Fake and local provider profiles are separate, including separate hashes and
latency measurement; report metadata includes source commit/tree,
snapshot/bundle IDs, dataset SHA and evaluator/rubric revisions. Scoring
logic is not modified. Reports never assert blind PASS.

```bash
PYTHONPATH=backend/src python -m saturn_ai.real_corpus_evaluation \
  --dataset /secure/local/real-open-calibration.json \
  --report /secure/local/real-open-report.json \
  --allow-real-network --allow-development-pdf-worker --provider fake
```

**Not yet done:** 25–40 real questions, independently checked real gold,
first actual measured calibration, defect register and threshold decision.
A unit test using synthetic fixtures with the real-profile API is ONLY a
contract test; it is not a reported real quality measurement.

## 4. Stage 5H — versioned independent real-source blind infrastructure

**Status: ENGINEERING INFRASTRUCTURE IMPLEMENTED (candidate); REAL BLIND NOT_RUN.**

`backend/src/saturn_ai/real_blind.py` contains a separate v0.1 real-source
freeze profile, including exact code revision, corpus/source manifest/snapshot/
bundle, independent dataset digest and author/reviewer metadata, model/provider
config, tokenizer and prompt revisions, rubric/scorer revisions, and fixed
provisional 24-positive/16-negative thresholds. Freeze and explicit
independent model-weight SHA attestation must originate outside Coding Session B.
The module does **not** generate independent questions or gold.

`RealBlindRun` reuses the original Stage 5E durable START/FAILED mechanics
without editing Stage 5E; its real-source completion checks the original
`real_sample` gold after START, validates case identities, source-backed
pointers, source-anchored per-case outcomes, all report metrics/denominators,
and writes exclusive persisted report bytes + SHA-256 COMPLETE receipt.
The runner passes only question text to the Stage 5A–5D runtime and scores
separately. A repeated START is refused. The original frozen synthetic
blind artifacts and contracts are unchanged.

**Important limitation:** local model digest is caller-declared in the
inference adapter. The independent reviewer must inspect and attest actual
weights and tokenizer/config outside this adapter; an arbitrary supplied
string is not cryptographic proof. The `model_weights_verification` freeze
field is an external assertion, not an automated check. Do not execute
an independent blind until Session A confirms these identities and thresholds.

```bash
PYTHONPATH=backend/src python -m saturn_ai.real_blind \
  --freeze /secure/real-blind-freeze.json \
  --independent-gold /secure/real-blind-gold.json \
  --report /secure/real-blind-report.json \
  --receipts-dir /secure/real-blind-receipts \
  --allow-real-network --allow-development-pdf-worker \
  --allow-local-inference \
  --local-endpoint http://127.0.0.1:11434/v1/chat/completions \
  --local-model-id EXACT_FROZEN_MODEL \
  --local-model-sha256 ACTUAL_REVIEWED_WEIGHTS_SHA256
```

This command is an **instruction only**, not a claim that an experiment ran.
No independent gold set is committed or available; therefore
`independent_blind_evaluation=NOT_RUN`, `quality_target_met=null`,
`production_readiness=false`.


## 5. Stage 5I — experimental local provider

`backend/src/saturn_ai/grounding/saturn_local_provider.py` adds a strict,
bounded OpenAI-compatible loopback-only `SaturnLocalClaimProvider`. Only
`http://127.0.0.1:PORT/v1/chat/completions` or
`http://[::1]:PORT/v1/chat/completions` with restricted ports may be used.
No cloud fallback, proxies, redirects, user-defined hostnames or API keys.
Response is validated as bounded structured JSON and converted to **untrusted**
`SaturnClaimDraft` values.

The existing `SaturnClaimVerificationService` has an exact-class allowlist
for both Fake and Local providers. All accepted claims still pass the
independent snapshot-pinned verifier, full answer gate and backend citations.
Provider errors produce safe technical failures rather than false refusals.
No model weights are downloaded or added to Git.

```bash
PYTHONPATH=backend/src python -m saturn_ai.real_corpus_stand \
  --allow-real-network --allow-development-pdf-worker \
  --provider local_llm --allow-local-inference \
  --local-endpoint http://127.0.0.1:11434/v1/chat/completions \
  --local-model-id YOUR_LOCAL_MODEL_ID \
  --local-model-sha256 YOUR_ATTESTED_MODEL_WEIGHTS_SHA256 \
  --question 'БКД-ПК-RF.2: mass_kg?' \
  --report /tmp/saturn-local-pilot.json
```

`local-model-sha256` is **caller-declared**, not cryptographically attested
by the inference server. Until the actual model digest, tokenization,
quantization, hardware, context window and prompt/config are independently
frozen, this is not a reproducible blind experiment.

**Not yet done:** real local model invocation, chosen licensed model,
CPU/GPU/RAM measurement, robust natural-language Stage 5B extension,
actual local calibration, production latency targets. Stage 5B remains the
existing intentionally limited deterministic grammar; this stand does not
claim that free-form Russian engineering questions already work.

## 6. Test and measurement separation

Added offline tests for:
- exact commit enforcement and verified blob retention in selected corpus;
- mandatory source path and PDF source path checks;
- excluded document absence;
- local-only transport configuration;
- malformed/malicious model outputs, rejected claims and provider failure;
- real profile contract against synthetic fixture **only**.

The existing CI jobs still determine regression PASS on their **exact commit
SHA**; this report does not infer PASS from fixture tests or from code
existing. At the time of this initial document, no actual live real-corpus
manifest, real PDF bytes/page hashes, real open calibration report, local
model run or independent blind report is available.

## 7. Known risks and remaining work

1. Stage 5F real download and PDF extraction may fail (large, OCR-only,
   unpublished, permission-denied, or resource-limited files). Preserve
   diagnostics without fabrication.
2. GitHub provider is complete-snapshot-first; measure request budget and
   repeatability. A change of source main requires a new pinned profile.
3. Open real dataset authoring and independent source validation are pending.
4. Stage 5H independent blind infrastructure and independent dataset are
   pending; do not reuse synthetic freeze under a real label.
5. Stage 5I must actually be run on installed local weights/hardware. Stage 5B
   natural-language semantics require separate versioned compatibility plan
   if they cannot be added without changing existing need interpretation.
6. Local model reports must distinguish missing invocation from actual
   inference. No fake or mocked data counts as a real LLM measurement.
7. Exact-head CI and the full independent PR acceptance are required before
   merge. No production-readiness claim or Stage 6.

**Current release gate:** `IMPLEMENTATION IN PROGRESS — EXPERIMENTAL
VALIDATION NOT RUN`. Nothing in this report authorizes merge.


## Independent Acceptance Review Corrections — CR-01…CR-05

**Review baseline:** `7eda73849b814a296182346f4238ce920ed082db`.
**Execution:** same branch / same PR #32, no merge. All new tests are
controlled synthetic tests unless explicitly identified as a real run.
Historical Stage 5E frozen gold, scorer, rubric and reports remain untouched.

### CR-01 — BLOCKER: one generation/verification for an evaluated answer

- **Root cause:** `_run_question` called `verifier.verify()` separately and
  then `assembly.assemble()`, which already performed verification. With a
  stateful LLM the diagnostic trace could reflect different claims from the
  published answer.
- **Files:** `grounding/saturn_answer_assembly.py`,
  `evaluation/saturn_grounding.py`,
  `backend/tests/unit/test_saturn_single_generation.py`.
- **Fix:** Stage 5D retains its public `assemble()` answer contract and
  exposes a private `_assemble_diagnostics()` that returns the final answer,
  SAME-path Stage 5B assessment and SAME-path Stage 5C verified result.
  Evaluator uses this return and never independently calls Stage 5C.
  Provider drafts still pass the original snapshot-pinned independent verifier
  and two final Stage 5D policy checks; the evaluator cannot submit drafts.
- **Tests:** CR01-T01–T06 cover stateful one-call provider, trace-to-final
  statement identities, error fail-closed, pinned IDs and concurrent publication;
  CR01-T07 requires the unchanged legacy Stage 5E suite.
- **Residual:** Stage 5B is the accepted bounded grammar; no unapproved
  natural-language semantics change.

### CR-02 — IMPORTANT: deterministic frozen blind threshold scorecard

- **Root cause:** blind runner wrote `quality_target_met=null` without
  evaluating the frozen 24/16/zero-error requirements.
- **Files:** `real_blind_assurance.py`, `real_blind.py`,
  `backend/tests/unit/test_saturn_real_blind.py`.
- **Fix:** six deterministically computed criteria: 24/24 positive
  fully-correct, 16/16 negative fully-correct, zero unsupported technical
  claims, zero invalid citations, zero positive assertions for missing facts,
  and explicit required-retrieval-measurement completeness. Each criterion
  reports numerator, denominator, required value, actual result, MET /
  NOT_MET / NOT_APPLICABLE and a reason for non-applicability. No applicable
  measurement may be replaced with a favorable zero. The aggregate
  `quality_target_met` is Boolean and is recomputed from per-case gold/outcomes
  during completion. Frozen threshold changes invalidate identity.
- **Tests:** full synthetic MET, one positive error, one negative error,
  unsupported claim, citation error, unavailable retrieval, tampered scorecard
  or summary. **Quality target does not authorize production**:
  `production_readiness` remains `false`.

### CR-03 — IMPORTANT: exact blind composition and open-gold independence

- **Root cause:** old check counted anything not `answered` as negative,
  including partial and technical error.
- **Files:** `real_blind_assurance.py`, `real_blind.py`,
  `backend/tests/unit/test_saturn_real_blind.py`.
- **Fix:** only 24 answerable + 16 explicitly classified `needs_support`
  or `clarification` are permitted; mapped category/status whitelist and
  substantive negative rationale are mandatory. `partial` and `error`
  are excluded from negative gold. Exact source pointers are validated by
  unchanged Stage 5E `validate_gold`; positive structured source evidence
  cannot be relabeled as missing support. A `conflict` label requires
  multiple gold sources. Case IDs and normalized questions must be unique.
  Frozen open-calibration bytes SHA are checked pre-START; after START
  mechanical duplicate blind/open questions are rejected.
- **Tests:** correct 24/16, 23/17, partial-only negatives, short reason,
  unknown category, duplicate case, false pointer and frozen dataset hash.
- **Residual:** no automatic procedure proves semantic independence or the
  engineering validity of negative labels. Expert independent review
  remains a mandatory gate.

### CR-04 — IMPORTANT: source and model/config identity gate

- **Root cause:** caller-declared weight SHA, tokenizer/prompt strings and
  model ID were not enough to identify the actual experimental model.
- **Files:** `real_blind_assurance.py`, `real_blind.py`,
  `backend/tests/unit/real_blind_testkit.py`,
  `backend/tests/unit/test_saturn_real_blind.py`.
- **Fix:** independent immutable identity manifest includes model ID,
  revision, quantization, physically hashed model artifact,
  tokenizer name/revision/physically hashed file, actual Stage 5I prompt SHA,
  exact provider adapter revision, exact generation parameters, context
  window, runtime config digest, runtime name/version and hardware identity.
  A separately provided independent reviewer attestation is digest-bound
  into the freeze, with explicit `EXTERNALLY_VERIFIED` status and
  `runtime_attestation=false`. Before START, local files are physically
  SHA-256 hashed and compared to the frozen manifest. Absent reviewer
  attestation, changed file, changed prompt/template, model ID, tokenizer,
  generation parameter or freeze identity aborts.
- **Tests:** matched frozen identities and attestation; forged/swapped
  model, digest, tokenizer revision, prompt, params, reviewer or artifact.
- **Residual:** an OpenAI-compatible endpoint does NOT prove that its
  running server loaded the tested artifact. No `RUNTIME_VERIFIED` claim
  is made; independent reviewer must additionally document runtime binding
  and operational procedures. The retained provider's response model field
  is checked, but is not cryptographic attestation.

### CR-05 — IMPORTANT: full synthetic adversarial real-blind lifecycle

- **Root cause:** earlier tests covered START and freeze fragments only.
- **Files:** `real_blind.py`, `real_blind_assurance.py`,
  `backend/tests/unit/real_blind_testkit.py`,
  `backend/tests/unit/test_saturn_real_blind.py`.
- **Fix/tests:** synthetic fixture, fake local HTTP response and synthetic
  model-file bytes exercise Freeze → pre-START checks → durable exclusive
  START → 40 labeled cases → original 5E scorer → recalculated scorecard →
  report validation → durable COMPLETE SHA receipt; re-use and tamper cases
  cover CR05-T01–T14: duplicate START/COMPLETE, bad dataset → FAILED, altered
  outcome/citations/metrics/report bytes, missing case, changed runtime identity,
  technical errors, unmeasured retrieval, and re-used experiment ID.
- **Critical qualification:** passing these tests proves integrity contracts
  only; synthetic code-created gold is NOT an independent blind, and the
  fake completion never counts as real LLM inference.

### Correct independent blind invocation

Exact model and tokenizer files MUST be examined and checked by an independent
reviewer. The independent attestation and already-approved OPEN calibration
are inputs available before START; blind question/gold bytes are read only
AFTER durable START. This is an example of configuration, **not an executed run**:

```bash
PYTHONPATH=backend/src python -m saturn_ai.real_blind \
  --freeze /secure/real-blind-freeze.json \
  --independent-gold /secure/real-blind-gold.json \
  --independent-attestation /secure/reviewer-model-attestation.json \
  --open-calibration-gold /secure/real-open-calibration.json \
  --open-calibration-review /secure/approved-open-calibration-review.json \
  --model-artifact-file /secure/models/approved-weights.bin \
  --tokenizer-artifact-file /secure/models/approved-tokenizer.json \
  --report /secure/real-blind-report.json \
  --receipts-dir /secure/real-blind-receipts \
  --allow-real-network --allow-development-pdf-worker \
  --allow-local-inference \
  --local-endpoint http://127.0.0.1:11434/v1/chat/completions \
  --local-model-id FROZEN_LOCAL_MODEL \
  --local-model-sha256 ACTUALLY_MEASURED_WEIGHT_SHA256
```

### Real experimental gates and environment check (12 Nov 2026)

| Gate | State | Evidence | Next dependency |
|---|---|---|---|
| 5F real pinned website + linked PDF ingestion | **BLOCKED_BY_ENVIRONMENT** | Available current session has neither `SATURN_GITHUB_TOKEN` nor required `SATURN_GITHUB_OBJECT_FORMAT=sha1`; no genuine PDF download, SHA or pages measured | Provide read-only GitHub token and permitted HTTPS site access in controlled development host, then run documented 5F stand |
| 5G open real calibration | **NOT_RUN** | [30 source-page question candidates](../../evaluation/datasets/saturn-real-open-question-candidates-v0.1.json), **NOT gold**; no corpus/pointers or actual answers | Successful 5F snapshot + professional validation of 25–40 question/gold pairs, then run evaluator |
| 5I actual local inference | **BLOCKED_BY_ENVIRONMENT** | No `ollama`/`llama-server`/`llama-cli`, no configured local model artifact/attestation, and usual loopback port 11434 not reachable. Availability of an unrelated TCP port is not model verification | Select/install licensed local weights/runtime and attest identity, benchmark real inference |
| 5H independent real blind | **NOT_RUN** | Versioned code and controlled tests only; no blind gold supplied and model not frozen | Expert-authored blind dataset; complete 5F/5G/5I and Session A freeze/threshold approval BEFORE any START |

No engineering calibration, real model performance or independent blind result is
inferred from GitHub CI or synthetic tests. `production_readiness=false`.
The decision on a new natural-Russian question planner (Stage 5B extension)
requires a separate versioned Session A architecture approval.


### Measured GitHub CI baseline of correction set

On exact correction commit `8952d4984e4948c93c3f2590bfcd16e5548cce2a`:

- [PR workflow 43171805814](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43171805814): COMPLETED SUCCESS, four jobs PASS.
- [Push workflow 43171801744](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43171801744): COMPLETED SUCCESS, four jobs PASS.
- `offline-checks`: **787 Python backend tests PASS, 11 skipped**;
  the project checks also reported five tests PASS.
- `saturn-evaluator-targeted`, `saturn-calibration`,
  `onnx-contracts`: SUCCESS.
- CR-01 stateful tests and CR-02–05 adversarial/40-case synthetic
  lifecycle were included in the 787-test offline run.

Subsequent test/documentation commits change the head. Therefore
the above CI run is historical evidence at its exact SHA, not a PASS
assertion for any later head. Obtain new exact-head CI before review.

**Measured engineering contract PASS ≠ actual experiment PASS.**
The gated statuses 5F, 5G, 5H, 5I remain as recorded above.


## Second Independent Acceptance Review Corrections — CR-06 / CR-07

**Session A review baseline:** `4223d0e88596140482c778fef956c8efef91d8b1`.  
**Review result:** CHANGES REQUESTED — CR-06 BLOCKER, CR-07 IMPORTANT.  
**Working scope:** same PR #32, same existing branch. CR-01…CR-05,
Stage 4A–5E frozen artifacts/scorer and the independent Stage 5C verifier are
not altered.

### CR-06 — BLOCKER: approved open real-source calibration before blind START

**Root cause:** `real_dataset_contract` accepted an arbitrary JSON array of
question strings, even for `synthetic_calibration`. Hash equality validated
only file bytes, not split, source-backed gold or expert review.

**Correction:**

- `real_blind_assurance.validate_open_real_calibration` validates the raw
  *complete* open dataset using the existing independent
  `evaluation.saturn_answer_dataset.validate_gold(..., split="real_sample")`
  against the pinned real Knowledge Snapshot. Enforces matching
  `snapshot_id`, `corpus_hash`, SHA-256, unique case IDs/questions, Stage 5E
  valid source-backed positive requirements and supported negative reasons.
  Requires 25–40 nonempty, correctly shaped questions and a mix of positive
  and negative/ambiguous cases. Rejects synthetic/candidate/fixture/test-only
  labeled gold and Coding Session B authorship.
- An externally authored `APPROVED_REAL_OPEN_CALIBRATION` human technical
  review record is required. Its digest is a new
  `open_calibration_review_sha256` field in the real-blind freeze and config
  fingerprint. Review record binds reviewer, role, date, stated verification
  procedure, author, every reviewed case ID, dataset digest and pinned source
  manifest/snapshot/corpus identities. This is an **external human claim**
  checked for completeness and identity consistency; it is not automatically
  proof that a person really performed an expert review.
- `validate_real_freeze` performs the strict check **before** constructing
  durable START, then passes one validated `SaturnGoldDataset` instance into
  the blind run and completion validator. Blind gold bytes are still read
  only *after* START. Overlap checks compare every normalized question from
  that pinned, validated open dataset — never loose caller strings, and open
  expected answers never enter the blind runtime.
- Versioned real-only freeze revision becomes
  `saturn-independent-real-blind/0.1.1` due to the new required digest.
  No existing real blind was executed; historical Stage 5E synthetic freeze,
  dataset and reports remain unchanged. Existing CR-01…CR-05 safeguards
  continue to apply.

**Files:** `backend/src/saturn_ai/real_blind_assurance.py`,
`backend/src/saturn_ai/real_blind.py`,
`backend/tests/unit/real_blind_testkit.py`,
`backend/tests/unit/test_saturn_real_blind.py`,
`backend/tests/unit/test_saturn_real_open_preflight.py`.

**Tests:** CR06-T01–T11, T13 and additional independent-review checks in
`test_saturn_real_open_preflight.py`; CR06-T12 is the existing full
40-case **synthetic** lifecycle in `test_saturn_real_blind.py`. Only the
unit-test source fixtures simulate a reviewer; they are not approved real
gold, and no synthetic result is reported as model quality.

**Remaining external dependency:** an engineer must author/approve the real
25–40-case open dataset and signed-off human review record against real
evidence. The code cannot independently certify human technical expertise.

**Required extra CLI input:**
```bash
--open-calibration-review /secure/approved-open-calibration-review.json
```

An approved review record has exactly:
`schema_version=1`, `decision="APPROVED_REAL_OPEN_CALIBRATION"`,
`dataset_sha256`, `dataset_id`, `snapshot_id`, `corpus_hash`,
`source_manifest_sha256`, `case_count`, `reviewed_case_ids`,
`author`, `reviewer`, `reviewer_role`, `reviewed_at_utc`
and `verification_procedure`. Each field must be supplied by the
independent reviewer. Do not create an invented approval record for use
in production. The review digest must be included in the frozen experiment.

### CR-07 — IMPORTANT: stale per-request token usage

**Root cause:** `SaturnLocalClaimProvider.generate` updated `last_usage`
only when the response included a usage dict. Missing, malformed or failed
responses could leave successful prior-token counts visible.

**Correction:** reset `last_usage=None` at the beginning of every request;
accept only a nonempty usage dict whose keys are among the three
documented token counters and whose values are nonnegative exact integers
(no booleans, strings or partial invalid fields). Absence/invalidity remains
`None`, **never zero**. Existing successful request counts, latency recording,
localhost transport and independent verification are unchanged.

**Files:** `backend/src/saturn_ai/grounding/saturn_local_provider.py`,
`backend/tests/unit/test_saturn_local_provider.py`.

**Tests:** CR07-T01 valid usage; T02 usage then omitted usage; T03 invalid
negative/bool/string/empty/malformed usage; T04 successful request then
provider failure; T05 latency/success counter unchanged; T06 independent
SaturnClaimVerificationService still rejects forged claims.

### Real experimental gates after corrections

| Stage | Status | Actual measured evidence | External action needed |
|---|---|---|---|
| 5F | **BLOCKED_BY_ENVIRONMENT** | No actual PDF bytes/hash/pages or real snapshot measured; current runtime has no `SATURN_GITHUB_TOKEN` or `SATURN_GITHUB_OBJECT_FORMAT` | Administrator: read-only GitHub source token, allowed HTTPS access and approved development PDF worker |
| 5G | **NOT_RUN** | 30 unvalidated open real-source question candidates only, no expert-certified source pointers or measured results | Saturn technical specialist: source-backed 25–40 gold and review record following successful 5F |
| 5H | **NOT_RUN** | Only synthetic test harness; no independently authored hidden gold or finalized code/model/corpus freeze | Session A: expert-author blind gold, approve thresholds and freeze after real open calibration and local inference |
| 5I | **BLOCKED_BY_ENVIRONMENT** | No genuine model inference; no local model binary/weights; loopback `127.0.0.1:11434` unavailable | Administrator: approved licensed model/runtime, artifact SHA, tokenizer, RAM/GPU/CPU benchmark; Session A must approve architecture delta before changing Stage 5B natural-language semantics |

These conditions are NOT resolved by successful GitHub CI. No source repository
write, cloud inference, Stage 6 implementation or merge is authorized.

### Measured correction test evidence

**Exact code head:** `3d1a3a1ac04028b0e86820e584d2035fdb7de0ff`.

- [PR CI #43211669314](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43211669314): **COMPLETED SUCCESS**; four jobs PASS.
- [Push CI #43211660141](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43211660141): **COMPLETED SUCCESS**; four jobs PASS.
- `offline-checks`: **806 tests, OK (11 skipped)**, including new CR06 and
  CR07 adversarial tests, CR05 controlled 40-case test and previous CR01–05
  regressions. The auxiliary project check also reported 5 tests PASS.
- `onnx-contracts`, `saturn-calibration`,
  `saturn-evaluator-targeted`: PASS.

This documentation update creates a later SHA, so the authoritative final PR
head must be checked again after it. These runs are evidence for their
**exact code head**, not a claim of final docs-commit CI or real-source quality.

### Minimal development environment for genuine measurements

**5F:** Python + exact locked `backend/requirements.lock`, read-only
`SATURN_GITHUB_TOKEN` and `SATURN_GITHUB_OBJECT_FORMAT=sha1`, outbound
GitHub API access, controlled HTTPS access to `www.mnppsaturn.ru/ftp`,
explicit experimental PDF worker opt-in, resource limits and a secure local
report directory. A full pinned source revision and every PDF
bytes/page/parser SHA and diagnostic must be recorded before claiming PASS.

**5G:** a human-reviewed 25–40-question source-backed
`real_sample` dataset bound to the actual Stage 5F snapshot, plus
the separate `APPROVED_REAL_OPEN_CALIBRATION` expert review record.
The existing 30 candidate questions do NOT qualify.

**5I:** an installed local OpenAI-compatible model server binding only to
`127.0.0.1` or `::1` at `/v1/chat/completions`, explicit allowed model ID,
approved licensed weights/quantization, measured model and tokenizer SHA-256,
GPU/CPU/RAM and versioned runtime config, no cloud fallback, recorded
p50/p95 inference latencies and memory usage. Caller-declared model SHA does
not prove runtime-loaded weights; independent runtime configuration check
remains an external prerequisite.

**5H:** only after approved open calibration, verified model/corpus/runtime
freeze, independently authored and reviewed blind gold and Session A's
pre-START acceptance of thresholds. Never author a blind set in Coding B.

**Experimental status remains 5F BLOCKED_BY_ENVIRONMENT, 5G NOT_RUN,
5H NOT_RUN, 5I BLOCKED_BY_ENVIRONMENT; Stage 5 NOT_ACCEPTED.**
