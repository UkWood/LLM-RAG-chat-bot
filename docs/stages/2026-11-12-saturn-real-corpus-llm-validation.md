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
