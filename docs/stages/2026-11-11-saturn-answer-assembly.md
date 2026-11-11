# Stage 5D — Answer Assembly, Citations & Final Policy Gate v0.1

Date: 2026-11-11. Project: AI Technical Consultant — МНПП «Сатурн».

## Baseline, branch and scope

- Base `main`: `9d6c6fa1da180e62feb22134efa92724d8173f17`; Stage 5C PR #29 **MERGED** (merge CI 43052161495; 543 backend tests, 11 optional skips, 5 project tests).
- Branch: `feat/saturn-answer-assembly-v0.1`.
- Single Stage 5D PR: linked in GitHub PR description on publication; independent Session A Acceptance Review required. **NO MERGE. NO Stage 5E.**
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
are escaped for plain text; original units, decimal spellings, field paths,
qualifiers, relation direction and predicates are preserved. There is no
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
Stage 5E independent grounding quality evaluation is the *next* planned stage;
not started here.
