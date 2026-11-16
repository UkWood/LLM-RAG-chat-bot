# NEW RAG — Stage 5K-A-R: Controlled Comparative Research

**Decisions:** A-5K-04 + mandatory addendum A-5K-05, 2026-11-17.
**Branch:** experiment/stage5k-comparative-rag-v0.1
**Base:** PR #34 HEAD 894e6abe190be8cff1f0615b103eea66d6374e05
**Status:** research experiment only; NO MERGE / NO PRODUCTION DEPLOYMENT.

## Two independent experimental lines

**E4B / Search-only.** A uses the existing BM25/metadata retrieval on the **verbatim original question**, top-10. D optionally builds an ephemeral in-memory cosine index with a real pinned licensed owner-provisioned LocalONNXEncoder, combines original lexical+real dense ranks by reciprocal rank fusion, and logs distinct experimental index identity. No Qdrant/database, cloud vector store, automatic model download, fake embeddings or semantic claim generation. If an approved encoder is not ready, report D_NOT_RUN_PREREQUISITES_MISSING; do not treat this as a zero-recall measurement. B/C results may also reveal the effects of LLM query expansion, but are not equivalent to a pure dense-index gain.

**E5B / Intent understanding.** B always calls the same bounded local Qwen planner before retrieval. C performs A retrieval first; only a fully resolved existing Stage 5B field_value need whose exact entity/field has a policy-eligible canonical source-backed fact in the original top-10 can take the deterministic fast-path. Otherwise C calls the SAME planner, validator, and query-fusion function as B. Route reasons and all LLM calls are logged. An all-planned result is C_ALWAYS_PLANNED_OBSERVED; no claimed cost savings.

Existing Stage 4B/5B, Stage 5A–5J, real_corpus_stand.run_question, the trusted site and production answer generator are unchanged.

## Frozen source and seed identities

Trusted read-only site repository: UkWood/Saturn-Main-Site
Source commit: 084d759487bfab6e111549c9b5469711ac5fc13e
Stage 5F: 10 Markdown + 4 pinned PDF; 256 physical pages
Snapshot ID: 19e861e4c09595feacfcb1e0221f7580b173e3e4b50c3d3ff3c9ca3435388dbd
Corpus hash: 6be30f3fcf1ecab62562989fe9b0ce02e0a0e95752a078e1e18bfdd4f98e450b
Baseline lexical Bundle ID: 903146cb5ebf903bec10e2827db3196b564c5d577b6ed3bfd880f8700f1d1f70

The unchanged real_corpus_stand.PINNED_PDF_REVISIONS pins the four original PDF bytes SHA-256 and physical pages. At startup prepare_real_stand independently checks site Git source, PDF bytes and source scope; verify_stand separately compares manifest, content, PDF and bundle identities.

The bundled file backend/src/saturn_ai/stage5k_seeds.zlib.b64 is a LOSSLESS zlib/base64 encoding of the original uploaded Stage5K_60_user_questions_UNREVIEWED.json. The loader verifies the SHA-256 **of the original decompressed JSON bytes**:
09aa35815f09bcbd8da1d7829d355984e9c549347e22ef25d090c0b0449ded38

All 60 original questions are used verbatim. The optional --questions parameter accepts only the exactly matching original unpacked JSON, with no whitespace changes. Every source record is UNREVIEWED; expected_answer is null, gold is false. Only case_id and exact original question enter runtime comparisons. No expert labels, correct answers or human approval statuses become query/router/planner inputs.

## Versioned design freeze

stage5k_contract.design_freeze() emits a canonical serialized contract and design_sha256. It pins:

- comparator_revision = stage5k-comparator/0.1.0
- router_revision = stage5k-exact-structured-evidence-router/0.1.0
- prompt_revision = stage5k-intent-prompt/0.1.0; exact prompt SHA-256
- fusion_revision = stage5k-query-rrf/0.1.0
- d_prerequisite_revision = stage5k-reviewed-onnx-ephemeral/0.1.0
- dataset/source/snapshot/corpus/bundle/model identities
- resource budgets and privacy policy

The untrusted JSON planner proposal has EXACT fields: question_sha256, model_id, declared_model_sha256, intent_type, entity_mentions, information_needs, qualifiers, negations, version_constraints, suggested_search_queries, ambiguities, completeness_requirements.

The validator disallows unknown/duplicate keys, changed model/digest or question hash, guessed source IDs, invented entity mentions/technical identifiers, loss of negations and factory-default qualifier, omitted exact question segments, unsafe tool instructions, oversized/multiple search queries and invalid JSON. It cannot verify semantic engineering truth and does not try to. Proposed search queries cannot replace the original question. Exact identifiers such as RF.2 cannot silently become RF.1.

For multiqueury and lexical/dense fusion use rank-only RRF 1/(60+rank) with stable evidence-ID ties. **Never sum raw cosine/BM25 scores.** Show per-query source ranks, provenance and top-10 budget exclusions. Source policy filters must reject blocked IDs, owner/source revisions or PDFs; validate evidence pointers and policy before logging candidates. PDF passages and metadata are not evidence of arbitrary claimed technical facts.

Limits: at most 60 cases, 3 subqueries, 4000 question characters, 48000 prompt/response bytes, 512 completion tokens, one LLM call per B/C question, 45-second timeout, 10 final evidence candidates. Direct numerical loopback only; no proxy, external bind, redirect, retry or auto-download. Qwen token usage is included only when actually returned and valid. Temperature zero is not guaranteed deterministic.

## Coding Session B offline checks / R0

    PYTHONPATH=backend/src python -m unittest backend.tests.unit.test_saturn_stage5k_research -v
    PYTHONPATH=backend/src python -m unittest discover -s backend/tests -v
    python scripts/verify_offline.py

The unit fixtures are synthetic and are marked OFFLINE_SYNTHETIC. Their results are NOT evidence of real Qwen effectiveness or real embedding feasibility.

Offline CLI for validating exact seeds, design and append-only reporting **without source/model work**:

    PYTHONPATH=backend/src python -m saturn_ai.stage5k_cli \
      --mode offline --variant all --output-root "$HOME/stage5k-research"

All offline arm statuses explicitly say NOT_RUN_OFFLINE_STAND_NOT_PREPARED (D: D_NOT_RUN_PREREQUISITES_MISSING). The offline CLI is intentionally not a surrogate live comparative benchmark.

## R1 — separate Linux Validation Session runbook

1. Independently verify PR/base/HEAD, immutable 60-question dataset hash, scope manifest, GitHub CI, unchanged PR #32/#34 and clean Linux worktree. No production or trusted-site writes.
2. Start **Windows llama.cpp llama-server** with pinned Qwen GGUF, model ID qwen3-4b-q4km; declared local GGUF SHA-256 7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5. This is the operator-declared local file digest, NOT an attestation that llama-server loaded those same bytes.
3. Establish previously approved SSH reverse forwarding. The only Linux Qwen endpoint is http://127.0.0.1:11435/v1/chat/completions (loopback). Do not modify Windows Firewall, deploy services, or expose LAN/cloud endpoints.
4. Create a private, trusted Linux owner-only journal path outside ALL Git worktrees:

    umask 077
    mkdir -m 700 "$HOME/stage5k-research"

Existing directories are not automatically chmodded. Files created by the journal are 0600 and directories 0700. Raw visitor questions should never enter the research dataset without separate privacy approval.
5. Run real Stage 5F pinned source build ONCE with explicit network/PDF flags; then all A/B/C/D arms share the same stand:

    PYTHONPATH=backend/src python -m saturn_ai.stage5k_cli \
      --mode local --variant all \
      --allow-real-network --allow-development-pdf-worker \
      --allow-local-inference \
      --output-root "$HOME/stage5k-research"

This produces immutable per-case/per-arm Markdown and canonical JSON sidecars in one new run directory, with separate E4B/E5B summaries. The D arm MUST report D_NOT_RUN unless independent prerequisites are met. If the tunnel/model fails, B/C must produce PLANNING_FAILED, not needs_support or a fabricated answer.
6. **Optional D only with independent artifact/license review:** provision a local ONNX encoder manifest.json, model.onnx and tokenizer.json; hash model/tokenizer bytes and verify license/source. In a private JSON review record give approval_status=APPROVED, reviewer, license, source_url, model_sha256, tokenizer_sha256, then add:

    --allow-d-onnx --d-encoder-dir /private/verified-encoder \
      --d-license-review /private/approved-review.json

The local ONNX runtime uses CPU and an ephemeral process-memory cosine index; no vector DB. Note the new D index SHA-256 separately from baseline lexical Bundle ID.
7. Inspect all 60 paired IDs, source hashes, policy trace, original and expanded queries, route reasons, technical errors, model calls, latencies, token usage if reported, and original top-10. Check RF.2 scripts vs remote config, regulatory status vs measurement inputs and factory IP vs a configuration example. Do not guess technical answers or treat word overlap as truth.
8. Interrupt model/tunnel and journal writing for negative and restart recovery checks; retain original Markdown/JSON and hash evidence manifest. Shut down lab processes/tunnels. Report real evidence to Architecture Session A.

## R2 expert labels, R3 architecture

A separate versioned independent specialist annotation file must contain dataset SHA-256, case_id, reviewer/time, exact entity IDs/intent/needs/negations/qualifiers, approved relevant evidence_id/document_id lists, distinguished statuses not_in_scope / not_found / insufficient_evidence / ambiguous, and cryptographic approval event hashes. Expert text comments are NOT automatically gold. Split dev/holdout by related **question families**, not random synonyms. Gold may not enter any inference/planning/router/fusion path.

Until independent labels exist, **intent accuracy, evidence hit@5/@10, recall, final-answer accuracy and architecture ranking = NOT_MEASURED**. Current Stage 5B supports a limited structured grammar; Stage 5C/5D do not entail arbitrary natural-language statements from PDF text. The experiment does NOT repair those production contracts. Stage 4B real semantic retrieval remains an open architecture issue until real D comparison or a separately approved evidence-based rejection.

**Gate R0: independent code/CI acceptance. Gate R1: Linux evidence. Gate R2: human validation. Gate R3: separate future architecture decisions and production PRs. NO MERGE.**
