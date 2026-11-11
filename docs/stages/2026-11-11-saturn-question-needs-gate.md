# Stage 5B — Question Needs, Sufficiency & Conflict Gate v0.1

Date: 2026-11-11. Project: AI Technical Consultant — МНПП «Сатурн».

## Live baseline and implementation

Baseline: `UkWood/LLM-RAG-chat-bot@0f0286cf55b72c4793d66f5d648f5b37ab8356f4` (Stage 5A PR #27 merged, previous historical status text is superseded).

Working branch: `feat/saturn-question-needs-gate-v0.1`. One [PR #28](https://github.com/UkWood/LLM-RAG-chat-bot/pull/28), not merged. Stage 5C is not started.

```text
Stage 4B retrieved candidates
    -> Stage 5A SaturnAnswerSession (pinned bundle / lease)
    -> validated SaturnEvidenceContext
    -> Stage 5B SaturnQuestionGate.assess(session, context)
         -> deterministic Question Needs (including unparsed remainder)
         -> exact source-declared identity and field-path resolution
         -> per-need structured / metadata / passage / absent decisions
         -> conservative comparison of structured values and scope
         -> aggregate provisional gate decision
    -> future Stage 5C (not implemented)
```

## Public contracts

`SaturnQuestionNeed` is a frozen dataclass: deterministic need ID, kind `field_value/relation/document_lookup/unresolved`, exact source `question_span`, `original_text`, source entity/field/predicate/object IDs, resolution state and optional exact document title. `original_text == question[start:end]`.

`SaturnNeedFinding` is frozen and maintains one-to-one ID mapping with each need; statuses: `covered_structured`, `document_found`, `text_candidate`, `missing_in_context`, `ambiguous`, `potential_conflict`, `unresolved`. Each evidence ID and document ID tuple is sorted/unique. Metadata never turns into an engineering fact.

`SaturnNeedsAssessment` is frozen: original question SHA256, pinned snapshot and bundle IDs, *last* operational policy revision, ordered needs/findings, `gate_status` and safe bounded integer diagnostics. Gate values: `provisionally_covered`, `partially_covered`, `needs_clarification`, `potential_conflict`, `insufficient_evidence`, `unresolved_question`. No value is a final user answer.

## Supported exact grammar v0.1

- `ENTITY: field_path?` — one exact structured field, source-declared title/entity ID/alias/designation/model identity.
- `ENTITY: field_path, another.path?` and `and`/`и` joined field lists — one need per field, no arbitrary split of prose.
- `relation(ENTITY A, source_predicate, ENTITY B)?` — directional exact declared relation.
- `Документ: exact title` or `Document: exact title | owner=ENTITY` — only selected document metadata.
- Recognized field prefix followed by unparsed text creates an additional `unresolved` need. Otherwise unsupported question becomes one whole-question unresolved need.
- Max six needs, no truncation on overflow. No hardcoded list of technical fields, devices or predicate aliases.

Unsupported: natural-language recommendation/comparison/compatibility, semantic relation strengthening, qualifier extraction from prose, inferred negative capability, automatic unit conversions, mixed-version equivalence, LLM planning, generation or claim checking. These are explicit conservative limitations, not hidden fallbacks.

## Evidence and conflict policy

Only canonical, selected Stage 5A typed evidence with exact entity/field/relation/source identity can provisionally cover a need. Matching strings in Markdown/PDF are `text_candidate` only, including passages with source-backed owners, and require Stage 5C claim verification. A document title/URL confirms only a metadata lookup. A missing selected fact is `missing_in_context`, **not** absence in the corpus.

Conflict comparison applies only to matching entity/field and source revision/qualifiers/unit; different scopes are `ambiguous`. Different comparable scalar values result in `potential_conflict` without winner selection. Numeric strings with commas/dots, signs, attached units or ranges are not normalized or compared as equivalent; unapproved conversions are prohibited. Question grammar v0.1 cannot express qualifiers, so qualified facts remain ambiguous for unconditional requests.

Stage 5A `_evaluate_pinned` holds session RLock throughout, verifies issued context identity/fingerprint/policy before evaluation, and repeats policy verification before return. Blocked evidence/document fails closed and invalid/unavailable policy is an error, not an empty search result. Only original pinned snapshot is used even during later bundle publication.

## Verification and acceptance

Test file: `backend/tests/unit/test_saturn_question_needs.py` (T-01–T-29 positive/negative/adversarial). T-30: `python scripts/verify_offline.py` and both GitHub Actions jobs `offline-checks`/`onnx-contracts` on exact final branch SHA, for BOTH push and PR runs.

**Verified intermediate revision (not the final head):** `96fc4938abcb246a494fae4a7e9a6c49d6b10878` ran 5 project tests PASS and 476 backend tests OK (11 optional skips); [push run #42993215615](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42993215615) and [PR run #42993223406](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42993223406) both completed SUCCESS, including `offline-checks` and `onnx-contracts`. Subsequent code revision `21407352d0f615aca31884d7e7d8809ad813fccd` added grammar/number-comparability hardening and regression tests; these are NOT covered by the earlier intermediate workflow results. Exact final PR head and subsequent push/PR CI results are recorded in [PR #28](https://github.com/UkWood/LLM-RAG-chat-bot/pull/28) after execution. Independent Acceptance Review remains necessary.

Scope changes: `grounding/saturn_question_needs.py`, `grounding/saturn_sufficiency_gate.py`, a minimal Stage 5A locked integration hook, the new test file and documentation. Unchanged: retrieval, canonical knowledge contracts, adapters, ADR, provider config, frozen datasets, UI/API, site source and deployment.

`UkWood/Saturn-Main-Site` was not accessed for writing. No merge and no Stage 5C.

## PR #28 — Consolidated Acceptance Review Corrections (CR-01 / CR-02)

**Reviewed baseline:** 79a6a3b27a4be73bac509758a143e8d119d223cf. Status: CHANGES REQUESTED; one BLOCKER + one IMPORTANT. Final correction head and exact-head CI are tracked in PR #28; this report must not pre-claim a PASS.

**CR-01:** Before positive field coverage, inspect exact canonical raw_value_json of every matched evidence. null, empty strings (including whitespace-only), [], {} produce ambiguous / non_substantive_field_value and retain all evidence IDs. Mixed substantive and empty values fail closed. 0, false, negative numbers, nonempty strings/arrays/objects remain substantive. No raw-value transformation or unit conversion.

**CR-02:** A small bounded scanner now recognizes Stage 4A canonical paths: dotted components, repeated [index], bracketed canonical JSON-quoted keys and original punctuation. Commas/and/и/? inside quoted JSON key are literal field bytes, not delimiters. Source-declared unusual root keys may be used by exact match against pinned snapshot facts only. Unknown ordinary fields remain diagnosable; malformed/ambiguous expressions fail closed into unresolved. Original spans and maximum six requirements remain intact.

**Regression tests:** CR01-T01–T07 plus CR02-T01–T10 and extra negative cases in test_saturn_question_needs.py. Real Stage 4A source fixtures traverse Stage 4B publish, Stage 5A issued context and Stage 5B public assess; synthetic mixtures only test pure helpers. Full offline and exact-head push/PR CI mandatory before repeated Acceptance Review.

**Scope:** only Stage 5B parser/gate/tests and current documentation. No edits to Stage 4A adapter, 4B retrieval, Stage 5A lifecycle, policy, ADR, provider, frozen evaluations or Saturn-Main-Site. No merge; no Stage 5C.
