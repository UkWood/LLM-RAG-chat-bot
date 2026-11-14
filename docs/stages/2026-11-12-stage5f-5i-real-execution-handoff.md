# Stage 5F–5I — Real Experimental Execution Handoff

**Date:** 2026-11-12. **Project:** AI Technical Consultant — МНПП «Сатурн».
**Scope:** PR #32 only; no merge, no Stage 6, source site READ-ONLY.
**Engineering baseline:** `b1b10813dd26680d95bdded74964adfb53a442cf`
(accepted CR-01…CR-07). No accepted production code change is proposed here.

## 1. What actually happened in this session

A live connected **read-only GitHub** request resolved the private
`UkWood/Saturn-Main-Site` at pinned commit
`084d759487bfab6e111549c9b5469711ac5fc13e` and root tree
`a5297822bf3a5e071b10cc1dca553481c1b84d47`.
GitHub reported **1119 tree entries, truncated=false**.
The 10 exact Markdown records were fetched at the pinned revision;
each file's UTF-8 byte size and SHA-256 was computed and the Git blob
SHA-1 independently recomputed from `blob <bytes>\\0<raw bytes>`.
**10/10 recomputed SHA-1 match the GitHub tree**. Both Astro essentials
`astro.config.mjs` and `src/content.config.ts` exist. All four PDF
paths are explicitly declared by the selected source Markdown.

**Machine-readable source-only partial inventory:**
[`evaluation/experiments/2026-11-12-stage5f-pinned-source-inventory-partial.json`](../../evaluation/experiments/2026-11-12-stage5f-pinned-source-inventory-partial.json).

An external public PDF viewer yielded provisional page-count *hints*
for four PDF URLs (65, 39, 83 and 69). These counts are **not**
measurements by the project's controlled extraction worker, and no
PDF byte hashes have been obtained. Some external viewer results can
be cached. Do not use them to complete the 5F manifest.

### Real environment diagnostics, not mocks

- Local Python available, but `SATURN_GITHUB_TOKEN` and
  `SATURN_GITHUB_OBJECT_FORMAT` are **unset**.
- This container cannot resolve `api.github.com` or
  `www.mnppsaturn.ru` (curl returns **Could not resolve host**).
- The private Saturn source repository is accessible through the
  linked GitHub connector, **not through an exportable personal
  access token**. Do not extract/reuse connector credentials.
- The AI repo's GitHub Actions token alone does not grant permission
  to read the different **private** Saturn website repository.
- No local `ollama`, `llama-server`, or `llama-cli` executable was
  available; HTTP `127.0.0.1:11434/v1/models` was unreachable.
- No local model weights, approved tokenizer, hardware evidence,
  real-source gold, signed human review or blind gold was supplied.
- Consequently, no 5F real PDF ingestion, no 5G real calibration,
  no 5I inference and no 5H blind occurred.

## 2. Unblock 5F — controlled integration host (administrator)

Provision a controlled **development-only** Linux/Windows host with
outbound TLS/DNS to `api.github.com` and the four exact URLs on
`www.mnppsaturn.ru`. Enable Python and locked dependencies in
`backend/requirements.lock`. The source repository is **private**:
provision a fine-grained read-only credential scoped to
`UkWood/Saturn-Main-Site` with Contents/Metadata read access, through
the approved secret mechanism. Do not store or print the token in
source, reports, PRs or CI logs. Confirm `SATURN_GITHUB_OBJECT_FORMAT=sha1`.

```bash
# Run from the checked-out PR #32 head (verify git rev-parse HEAD).
# Token must already be provided by the approved secret manager.
export SATURN_GITHUB_OBJECT_FORMAT=sha1
test -n "${SATURN_GITHUB_TOKEN:-}" || { echo "MISSING_GITHUB_TOKEN"; exit 2; }
test "$(git rev-parse --abbrev-ref HEAD)" = "feat/saturn-real-corpus-llm-validation-v0.1" || exit 2

# Install *project-locked* parser and application dependencies before run.
# See existing repo requirements and CI; do not install arbitrary PDF plugins.
PYTHONPATH=backend/src python -m saturn_ai.real_corpus_stand \
  --allow-real-network --allow-development-pdf-worker \
  --provider fake --question 'БКД-ПК-RF.2: mass_kg?' \
  --report /secure/experiments/5f-positive.json

PYTHONPATH=backend/src python -m saturn_ai.real_corpus_stand \
  --allow-real-network --allow-development-pdf-worker \
  --provider fake --question 'БКД-ПК-RF.2: nonexistent_parameter?' \
  --report /secure/experiments/5f-missing.json
```

These are *real evidence/retrieval runs with the existing Fake draft
provider*, **not** actual LLM inference. Each invocation creates
its own report and must preserve the same exact source commit. Do not
re-use or overwrite either JSON report. Confirm reported
`manifest.selected_files`, `pdf_revisions`, bytes SHA-256,
`parser_version`, `page_count`, per-document statuses,
`snapshot_id`, `corpus_hash`, `retrieval_bundle_id`, and the
positive/missing-result `answer` and `stage_trace`. Record actual
errors including HTTP, source permission, extraction, timeouts and
policy revocations. **If any PDF fails, 5F remains FAIL or
BLOCKED_BY_ENVIRONMENT**, never fabricate empty PDF evidence.
The PDF worker is explicitly *not production-sandboxed*.

Save checksums of **local** reports and exact code SHA; for privacy
share only sanitized audit metadata with Session A unless explicitly
authorized to disclose source content.

## 3. Unblock 5G — open real calibration (Saturn engineer)

After full 5F snapshot availability:

1. Review all 30 entries in
   `evaluation/datasets/saturn-real-open-question-candidates-v0.1.json`
   against **real typed facts, source revision IDs, Git blob identity,
   units, qualifiers, relations, and document ownership**.
   These are *questions to investigate*, not gold.
2. Independently author 25–40 source-backed `real_sample` cases using
   the exact Stage 5E `SaturnGoldDataset` schema and pinned snapshot.
   Classify answered/missing/ambiguous/partial and give substantive
   reasons for every non-answered case. Avoid generating gold from
   LLM or RAG answers.
3. A different qualified Saturn reviewer inspects the technical
   source provenance and source pointers and supplies the separate
   `APPROVED_REAL_OPEN_CALIBRATION` record with all fields required
   by `validate_open_real_calibration`: dataset SHA, dataset ID,
   source manifest SHA, snapshot/corpus hashes, all reviewed case IDs,
   author/reviewer, role, date and detailed method.
   This human attestation is not automatically proof of expertise.
4. Run the existing Stage 5G CLI, separately for Fake baseline and
   **after 5I is real** for local provider. Neither run is blind.

```bash
PYTHONPATH=backend/src python -m saturn_ai.real_corpus_evaluation \
  --dataset /secure/experiments/open-real-source-gold.json \
  --report /secure/experiments/5g-open-fake.json \
  --allow-real-network --allow-development-pdf-worker --provider fake
```

Preserve the immutable dataset, review, real report,
retrieval/grounding metrics, false refusals, citations and a
defect register with exact case/source IDs, severity and independent
reviewer decision. No hard-coded PASS if results are poor.

## 4. Unblock 5I — one candidate local model (administrator + Session A)

**Proposed, NOT APPROVED/EXECUTED model:** official
[Qwen/Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF),
`Qwen3-4B-Q4_K_M.gguf` (~2.5 GB GGUF), Apache-2.0,
`llama.cpp` loopback-only OpenAI-compatible server. This is a
small baseline proposal, **not** a quality prediction or a frozen
revision. Session A/owner and administrator must approve license,
revision, exact file, independent tokenizer identity, context length
and hardware before the first real experiment.

On an approved local host (not a cloud inference endpoint), download
and inspect the **exact approved immutable revision** of model and
tokenizer. Keep weights in a protected directory, not in Git. Record
both actual file SHA-256; include actual `llama.cpp` build/version,
quantization, model revision, generation parameters, context window,
CPU/RAM/GPU identities and observed memory usage in an independent
review record.

Example only **after weights and runtime are installed and approved**:

```bash
sha256sum /secure/models/Qwen3-4B-Q4_K_M.gguf /secure/models/tokenizer.json
llama-server -m /secure/models/Qwen3-4B-Q4_K_M.gguf \
  --host 127.0.0.1 --port 11434 -c 8192 \
  --alias qwen3-4b-q4km

# Verify model alias and server capabilities, then run real RAG:
PYTHONPATH=backend/src python -m saturn_ai.real_corpus_stand \
  --allow-real-network --allow-development-pdf-worker \
  --provider local_llm --allow-local-inference \
  --local-endpoint http://127.0.0.1:11434/v1/chat/completions \
  --local-model-id qwen3-4b-q4km \
  --local-model-sha256 ACTUAL_MEASURED_MODEL_SHA256 \
  --question 'БКД-ПК-RF.2: mass_kg?' \
  --report /secure/experiments/5i-local-positive.json
```

Check `actual_inference_status == INVOKED` and
`successful_inference_requests > 0`; source evidence alone is **not**
model inference. Inspect the actual untrusted drafts, canonical
verified/rejected claims, citations, model/request latencies, available
token usage and CPU/RAM/GPU measurement. If Stage 5B cannot parse a
natural Russian question, record a **planner/parser limitation** and
do not attribute it to Qwen. Do not silently change Stage 5B canonical
need semantics without a new Session A architecture decision.
Loopback-only provider requires inference server on the **same host**
as the Python process; remote-host LLM is out of scope.

## 5. Independent 5H — Session A ownership only

**DO NOT RUN NOW.** The first blind requires prior successful 5F,
real 5G with engineer-reviewed gold and evidence, genuine 5I
inference, independent model/tokenizer verification, approved
40-case blind dataset, frozen code/model/corpus/config/thresholds.
Coding Session B does not see or author hidden gold.

After authorized freeze, the existing real-blind runner validates
the *open* expert-reviewed real gold before durable START, then opens
independent blind gold **only after START**, writes exclusive report and
durable COMPLETE/FAILED receipts, and calculates the frozen scorecard.
Keep the first attempt and any failures unchanged. A new blind test
after tuning needs new independent gold and architecture approval.
`production_readiness` is separately decided by the owner.

## 6. Exact experimental gate ledger

| Gate | Status | Evidence | Remaining owner |
|---|---|---|---|
| 5F | **BLOCKED_BY_ENVIRONMENT** | 10/10 source bytes independently rehashed, four source-declared PDFs identified; no project PDF SHA/page extraction or full snapshot | Admin: read-only credentials, DNS/TLS, controlled dev PDF worker |
| 5G | **NOT_RUN** | 30 candidates (not gold), no technical review or measured calibration | Saturn engineer + independent reviewer |
| 5I | **BLOCKED_BY_ENVIRONMENT** | No local inference executable, model weights, runtime or measurements | Admin + Session A/owner approve source/revision/hardware |
| 5H | **NOT_RUN** | No independent sealed blind dataset or preapproved freeze | Session A + independent expert |

**Stage 5 = NOT_ACCEPTED.** Successful CI verifies engineering
contracts, not source/model performance. No merge, no Stage 6.
