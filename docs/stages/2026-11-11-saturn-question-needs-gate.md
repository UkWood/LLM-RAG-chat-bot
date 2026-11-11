# Stage 5B — Question Needs, Sufficiency & Conflict Gate v0.1

Date: 2026-11-11. Project: AI Technical Consultant — МНПП «Сатурн».

## Live baseline and implementation

Baseline: `UkWood/LLM-RAG-chat-bot@0f0286cf55b72c4793d66f5d648f5b37ab8356f4` (Stage 5A PR #27 merged, previous historical status text is superseded).

Working branch: `feat/saturn-question-needs-gate-v0.1`. One [draft PR #28](https://github.com/UkWood/LLM-RAG-chat-bot/pull/28), not merged. Stage 5C is not started.

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

**CI and final verified counts:** to be filled in the PR after actual final-head workflow completion. Do not interpret this implementation report as a PASS or independent Acceptance Review.

Scope changes: `grounding/saturn_question_needs.py`, `grounding/saturn_sufficiency_gate.py`, a minimal Stage 5A locked integration hook, the new test file and documentation. Unchanged: retrieval, canonical knowledge contracts, adapters, ADR, provider config, frozen datasets, UI/API, site source and deployment.

`UkWood/Saturn-Main-Site` was not accessed for writing. No merge and no Stage 5C.
