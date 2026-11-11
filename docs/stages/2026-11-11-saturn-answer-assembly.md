# Stage 5D — Answer Assembly, Citations & Final Policy Gate v0.1

Date: 2026-11-11. Project: AI Technical Consultant — МНПП «Сатурн».

## Baseline, branch and scope

- Base `main`: `9d6c6fa1da180e62feb22134efa92724d8173f17`; Stage 5C PR #29 **MERGED** (merge CI 43052161495; 543 backend tests, 11 optional skips, 5 project tests).
- Branch: `feat/saturn-answer-assembly-v0.1`.
- Single [Stage 5D PR #30](https://github.com/UkWood/LLM-RAG-chat-bot/pull/30): independent Session A Acceptance Review required. **NO MERGE. NO Stage 5E.**
- Site repository `UkWood/Saturn-Main-Site`: strictly read-only, **no changes**.

## Architecture / public entrypoint

```text
4B retrieval → 5A issuing SaturnAnswerSession / fingerprinted context
→ 5C SaturnClaimVerificationService.verify (fresh 5B assessment)
→ 5D SaturnAnswerAssemblyService.assemble(session,context)
    → ownership/policy pre-check
    → fresh 5B SaturnQuestionGate.assess against same pinned snapshot
    → independent canonical re-verification of every returned claim
    → deterministic statement selection in question-need order
    → site/pdf/document citations from pinned canonical snapshot
    → exact field/value/relation renderer, no LLM rewriting
    → status & unresolved requirements accounting
    → output budget gate
    → final session-locked operational policy check
→ immutable SaturnAnswerResult
```

`SaturnAnswerResult`: question digest, pinned snapshot/bundle/policy revision, status,
plain answer text, immutable tuple of `SaturnAnswerStatement`, tuple of
`SaturnCitation`, unresolved need IDs, safe reason code and bounded counters.

`SaturnAnswerStatement`: deterministic statement ID, need ID, verified evidence
or exact document ID, kind (`structured_field`, `structured_relation`,
`document_reference`, or explicitly non-entailing `source_quote`),
text and one or more citation IDs. Quote extracts are not included in the
primary `answer_text`, even when independently verified for exact substring
integrity; they never satisfy a technical need.

`SaturnCitation`: exact site source repository/branch/path, source revision,
Git commit/blob SHA, content SHA-256, entity URL and field/relation locator;
or exact PDF document/revision, public original URL, bytes SHA-256, parser
version and physical page from pinned evidence; or a separately tagged document
metadata reference carrying every selected owner/document CatalogOccurrence,
link revisions and extraction status. Document citations **never** count as
technical evidence. Multiple uses of the same canonical citation are
deduplicated only by stable exact identity, retaining need→statement bindings.

## Final status rules

- `answered`: all needs match source-backed verified structured claims or exact
  document metadata, no unresolved/ambiguous/conflicts/rejections, citations
  complete, policy still permits output.
- `partial`: at least one need safely satisfied, others missing or rejected;
  clearly marks incompleteness; no inferred negative device capability.
- `clarification`: unsupported/ambiguous query, competing interpretation or
  potential conflict: no arbitrary selected engineering fact is published.
- `needs_support`: unambiguous request without verified facts; quote-only
  evidence is contextual, not proof.
- `error`: technical Stage 5C failure or output budget; no technical claims or
  citations from the aborted operation. Session, verifier and policy integrity
  failures preserve safe `SaturnContextError.reason_code` exception boundaries.

No user-controlled text is executed as HTML or Markdown. Exact source strings
are preserved literally in plain text without HTML entity encoding or decoding;
original units, decimal spellings, field paths, qualifiers, relation direction
and predicates are preserved. A future UI must display these strings as text
rather than as trusted HTML/Markdown. There is no
retrieval or external provider call inside final assembly.

## Final policy gate / lifecycle

The issuing session lock guards pinned read, rendered output and last policy
checks; Stage 5A fingerprint ownership is rechecked. All evidence and document
records are checked against current policy, plus citation owners, link-source
revisions, PDF revisions and directed relation objects. Concurrent publication
never switches snapshots. Concurrent close invalidates outstanding operations,
and revocation during final output returns a safe policy failure. This is an
at-return best-effort publication boundary, **not** a perpetual authorisation
or an atomic API delivery guarantee; a future API must recheck at delivery.

## Resource limits

6 needs, 10 Stage 5A evidence, 10 document references, 6 Stage 5C claims;
at most 6 technical output statements, 10 document statements, 16 citations,
12,000 answer-text characters. Overflow becomes `error` with a safe code and
no truncated fact, conditions or citation. These are offline v0.1 bounds, not
production throughput targets.

## Verification / limitations

Target suite: `backend/tests/unit/test_saturn_answer_assembly.py`, scenarios
T-01–T-65 grouped under A–G (including fault injection). Full regression:
`python scripts/verify_offline.py` via push and pull_request GitHub Actions.
The PR description records exact final head, both event run URLs, job conclusions
and actual log totals. CI outcomes must not be asserted before completion.

Limitations: exclusively offline Fake claim provider, no semantic entailment,
no inferred compatibility/numeric conversion, no user testing, no production
LLM/HTTP/chat UI. A verified PDF/site extract only proves source integrity.
Stage 4A currently rejects promotion of a candidate with failed PDF extraction. Stage 5D nevertheless preserves a failed extraction status in a standalone metadata citation unit test; the full public document-lookup flow can only use promotable snapshots. Also, Stage 5B currently refuses conditional structured fields when its query grammar cannot express qualifiers; the Stage 5D renderer preserves qualifiers but cannot override that conservative gate. Stage 5E independent grounding quality evaluation is the *next* planned stage;
not started here.

## PR #30 — Consolidated Acceptance Review Corrections (CR-01/CR-02)

- Independently reviewed head: `6b00e4b08a55098a73d8f1e6ded6c3108c5da811`.
- **CR-01 BLOCKER (literal plain text):** `plain()` returns source characters
  unaltered instead of HTML entity encoding. Exact `<`, `&`, double quotes
  in canonical field paths, original URL query separators, and already-literal
  `&lt;` remain data. Neither `SaturnAnswerResult.answer_text` nor
  `SaturnAnswerStatement.text` is trusted HTML/Markdown. No HTML renderer,
  decoder or frontend changes were introduced.
- **CR-02 IMPORTANT (output overflow accounting):** `_result()` now collects
  ordered distinct need IDs from statements and existing unresolved needs
  **before** clearing all statements/citations when `answer_text` exceeds
  12,000 characters. The result contains only a safe `error` message and
  recomputed final diagnostics; it never silently truncates facts/conditions.
- New focused CR01-T01–T07 and CR02-T01–T06 tests cover literal source-backed
  values, nested quoted keys, document URLs, markup-shaped data, existing
  entities, status/provenance regression, single/multi/partial overflow,
  error privacy and upstream budget precedence. CR02 over-budget statement
  tests are negative boundary checks. Stage 5C limits currently prevent
  the analogous source-string overload on the ordinary positive public
  generation path; the actual public large-input case fails at Stage 5C.
- Existing Stage 5D tests updated only to match plain-text semantics; all
  other Stage 5D behavior, pinned snapshot, final policy gate and citation
  contracts unchanged. Source site strictly read-only.

The PR description carries the **exact final correction SHA**, both
push/pull_request CI URLs and actual suite totals after GitHub checks finish.
Independent Session A review remains required. **NO MERGE / NO Stage 5E.**
