# Stage 5J — Expert Feedback Lab & Markdown Journal v0.1

**Status:** Coding Session B implementation for independent Architecture Session A review. **NOT PRODUCTION. NO MERGE.**
**Decision:** A-5J-01, 2026-11-16.
**Dependency:** Experimental PR #32, pinned starting commit 28d49256020722d737fd6097e2778af4c55926e8. A stacked PR targets branch feat/saturn-real-corpus-llm-validation-v0.1; PR #32 remains untouched.

## Purpose and implementation

One Russian-language page lets the expert enter an arbitrary question, read the original Stage 4B–5D answer and source citations, see actual status/error, explicitly save an optional comment, browse/filter history and export JSON/CSV. It does not replace RAG: each request calls the existing real_corpus_stand.run_question with SaturnLocalClaimProvider. The pinned Stage 5F stand is built only once per server startup with prepare_real_stand, not once per question.

No database or ORM, no extra LLM review analysis, no automatic correction, no fake inference in the actual lab, no production HTTP endpoint. Fresh local provider instances per request avoid cross-request usage-state pollution.

## Linux startup (separate validation)

1. Check reviewed Stage 5J stacked branch, pinned source revision and locked requirements (backend/requirements.lock). Configure the existing GitHub Snapshot Provider environment as for Stage 5F.
2. Run the existing llama.cpp Qwen3-4B Q4_K_M model on Windows. Use the previously accepted SSH reverse forwarding so Linux can reach it **only** at http://127.0.0.1:11435/v1/chat/completions. Model SHA-256 must be the real local weight digest, NOT a guessed hash; it is declared, not server-verified.
3. Select an **absolute**, writable root outside Git (example: /home/uk/feedback-journal). Do not use a directory below the repository.
4. Start with all three explicit opt-ins (code revision is taken from Git HEAD):

~~~bash
PYTHONPATH=backend/src python -m saturn_ai.feedback_lab \
  --allow-real-network \
  --allow-development-pdf-worker \
  --allow-local-inference \
  --journal-root /home/uk/feedback-journal \
  --local-model-id Qwen3-4B \
  --local-model-sha256 ACTUAL_64_HEX_DIGEST
~~~

Open http://127.0.0.1:8765/ locally. HTTP port may be changed with --port but bind address cannot change. Do not open to LAN, modify Windows Firewall or add public endpoints.

Source verification and PDF extraction run **once at startup before HTTP serves**. Invalid pins, missing files, model configuration, required opt-ins, unsuitable journal root or missing Git code revision stop startup.

### Offline verification

~~~bash
PYTHONPATH=backend/src python -m unittest backend.tests.unit.test_saturn_feedback_lab -v
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -v
python scripts/verify_offline.py
~~~

Unit tests inject a deterministic question runner to test boundaries offline. They are not evidence of live Qwen inference or model quality; this requires Linux Validation Session tests.

## Append-only Markdown format v1

~~~text
feedback-journal/
  lab/YYYY/MM/DD/<request-id>/
    request.md
    answer.md
    reviews/<review-event-id>.md
  production/YYYY/MM/DD/<request-id>/
    request.md
    answer.md
~~~

Each file has UTF-8 Markdown front matter using one JSON-encoded value per line between --- markers. Values form a constrained JSON-values YAML subset; the parser decodes with JSON and never deserializes arbitrary YAML objects. The original question, answer and comment are preserved exactly in metadata, plus displayed as human-readable, inert text inside tilde-fenced Markdown blocks with a delimiter longer than any matching text run. Metadata is the machine-readable canonical record.

**request.md:** schema_version=1, record_type=request, request_id, channel, received_at_utc (ISO8601 UTC with Z), run_id (per-start experiment run ID), original question.

**answer.md:** schema_version=1, record_type=answer, linked request_id/channel, finished_at_utc, duration_ms, exact answer_text, status, reason_code, snapshot_id, bundle_id, Git code_revision, policy_revision, model_id, declared_model_sha256, model_digest_server_verified=false, original citations with provenance, diagnostics, unresolved_need_ids, stage_trace, local_inference and sanitized technical_error.

**reviews/*.md:** schema_version=1, record_type=review, review_event_id, request_id, channel=lab, reviewed_at_utc, expert, decision and original comment.

Reviews are separate immutable events. Derived state is unreviewed until explicit Save Assessment, accepted only after explicit save with empty/whitespace comment, commented after explicit save with nonempty comment. Commented does not mean incorrect. Production reviews are unavailable in v0.1 and production requests always stay unreviewed.

The implementation writes a new exclusive temporary file in the same directory, flushes and fsyncs, atomically creates the final name via a hard link that never overwrites an existing file, fsyncs the directory and removes the temporary file. It durably writes request.md **before** inference. If processing ends abruptly, request.md remains and answer.md is missing. The interface marks this incomplete, not successful. Failed writes return explicit errors. UUID-based ID isolation supports simultaneous requests without filename collisions.

### Synthetic example — NOT real Saturn corpus/model evidence

~~~markdown
---
schema_version: 1
record_type: "request"
request_id: "0123456789abcdef0123456789abcdef"
channel: "lab"
received_at_utc: "2026-11-16T12:00:00.000Z"
run_id: "fedcba9876543210fedcba9876543210"
question: "ТЕСТ: что это?"
---

## Оригинальный вопрос

~~~~text
ТЕСТ: что это?
~~~~
~~~

A synthetic matching answer.md would include status "needs_support", answer_text "Недостаточно данных.", citations [], snapshot_id "TEST-SNAPSHOT", bundle_id "TEST-BUNDLE", code_revision "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", policy_revision "TEST-POLICY", model_id "TEST-QWEN" and a clearly synthetic 64-character SHA-256. A synthetic review would include decision "accepted", expert "тестовый-эксперт", comment "" and only exist after explicit review submission.

## Security and deliberately excluded scope

- IPv4 listener always bound to 127.0.0.1. Exact HTTP Host check, exact Origin and process-random X-Lab-CSRF token on mutating endpoints, Sec-Fetch-Site validation when present, content-type and body-size limits. No CORS, auth provider, cookies or production API.
- The browser uses textContent (never innerHTML) to show all user and RAG text. Source links are restricted to HTTP(S), rel=noopener noreferrer. CSP, no-store, no-referrer, anti-framing, nosniff headers apply.
- UUID and channel validation, path containment, symlink refusal, exclusive writes, strict sizes and structured parsing. Suspected credential strings are rejected (not journaled). Screening cannot guarantee full discovery of secrets: **never submit tokens, passwords, private keys, SSH configuration or HTTP Authorization headers**.
- Incoming IP, cookies, User-Agent and authorization values are not persisted. HTTP raw requests are not logged. Only chosen expert pseudonyms are stored in lab review events. Runtime exception messages are not retained; error codes only.
- JSON export reconstructs exact metadata from Markdown; CSV prefix-escapes formulas when cells may start (after leading whitespace) with =, +, - or @, or control characters. CSV escaping is for export only.
- Production retention days and deletion-policy configuration live in the journal component; no deletion job runs in v0.1, no automatic lab cleanup. Production HTTP, LAN, multiuser authentication, HTTPS, privacy/consent and deletion scheduling need separate approval.
- The single-user prototype assumes OS permissions protect its journal directory. It is not a hardened multiuser application.

## Linux Validation Session — independent evidence required

1. Verify branch ancestry, PR #32 unchanged, head SHA, clean worktree, CI state.
2. Execute offline tests and unchanged preexisting calibration tests.
3. Confirm real Stage 5F startup verifies exact Git commit, selected content, four PDF bytes/page-count pins, snapshot and bundle identity. Confirm there is **no per-question source fetch**.
4. Confirm HTTP is only on 127.0.0.1, not 0.0.0.0/LAN; wrong Host, cross-origin and CSRF-less POST are refused. No Windows Firewall changes.
5. Run **real** Qwen through the approved SSH reverse tunnel. Ask representative supported/unsupported questions; inspect exact answer status, citations, provenance, declared model SHA and local inference diagnostics. No Fake provider/cloud fallback.
6. Deliberately stop the tunnel/model and observe technical failure as error, not a false success. Interrupt a request; check orphan request.md is retained.
7. Save explicit blank and nonblank reviews; check accepted/commented/unreviewed transitions and preservation of all review events.
8. Restart the lab; reconstruct history solely from Markdown. Check restrictive filesystem modes and path outside Git.
9. Export JSON/CSV and compare back to source records, including formula-like input. Confirm no authorization headers or visitor identifiers are stored.
10. Submit Linux report with source and model identities, true inference evidence, sanitized journal examples, failures, measured durations, HEAD and CI. Offline tests alone do **not** mean Stage 5J is accepted.

Only Architecture Session A performs independent acceptance. **NO MERGE / NO PRODUCTION DEPLOYMENT.**
