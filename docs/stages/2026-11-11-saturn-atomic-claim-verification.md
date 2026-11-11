# Stage 5C — Bounded Generation & Atomic Claim Verification v0.1

Date: 2026-11-11. Project: AI Technical Consultant — МНПП «Сатурн».

## Acceptance Review Correction — CR-01: verifier failure isolation (2026-11-11)

Independent session A review of head `2ac508104a28bc3fc4a087bd4ee22bbd460e71bb` requested one IMPORTANT correction. This change is confined to the same PR #29 and branch. All other Stage 5C behavior remains accepted.

In `saturn_generation._verification()`, ordinary mismatch results returned by `verify_pinned_draft()` continue to become `SaturnRejectedClaim` using their documented safe reason codes. An **unexpected raised `Exception`** now immediately raises `SaturnContextError("claim_verification_unavailable") from None`, aborting the whole operation without any partially successful `SaturnClaimVerificationResult` and suppressing internal diagnostic exception chaining. `BaseException` is never caught.

The pre-existing Fake provider exception path still returns `verification_state="failed"` with `provider_unavailable`; policy/session failures, invalid provider output, claim types, exact canonical verification, and all budgets are unchanged. No new public contracts are introduced.

`backend/tests/unit/test_saturn_atomic_claims.py` adds CR01-T01–T07 covering thrown OSError and RuntimeError with confidential error text, ordinary `claim_value_mismatch`, a crash after one valid claim, policy/session/publication/close regressions, provider error separation, and positive/negative field, relation, site/PDF quote and ID-binding paths.

**Verification:** final exact head and both push/pull-request CI checks are recorded in PR #29 after checks finish. Existing baseline on the original reviewed head: 536 backend tests OK (11 optional skips), 5 project tests PASS. These baseline results do not constitute verification of CR-01.

## Scope and provenance

- Base `main`: `973c3d2f3ae2c5c7a079a3e92072121bf9082edf` (Stage 5B, PR #28 MERGED).
- Branch: `feat/saturn-atomic-claim-verification-v0.1`.
- Pull request: [PR #29](https://github.com/UkWood/LLM-RAG-chat-bot/pull/29), no merge. Final exact-head CI is recorded in the PR upon completion.
- Historical references claiming PR #28 OPEN / Stage 5C not started are superseded by the live main baseline. Historical checkpoints remain untouched.

## Architecture

```text
Stage 4B SaturnRetrievalService
    -> Stage 5A SaturnAnswerSession.build_context (issued context, immutable pinned snapshot)
    -> Stage 5B SaturnQuestionGate.assess (fresh under session lifecycle + policy lock)
    -> Stage 5C SaturnClaimVerificationService.verify
         -> choose at most one exact allowed evidence per eligible need
         -> minimal immutable SaturnGenerationRequest (no URLs, corpus or secrets)
         -> exact-class-allowlisted SaturnFakeClaimProvider (offline only)
         -> check output type, count, IDs and duplicate proposals
         -> canonical backend verification under original pinned session
         -> operational policy recheck before and after provider call
         -> immutable SaturnClaimVerificationResult
    -> Stage 5D (future): answer assembly, citations and final policy gate
```

Stage 5C does not create user-visible answers or citations. There is no real cloud/local LLM integration, HTTP API, frontend, ingestion or retrieval change, or revised source trust policy. The Fake is a contract fixture; CI does **not** measure real model answer quality.

## Public contracts and verification

- `SaturnGenerationRequest`: question SHA256, snapshot ID, bundle ID, current policy revision and bounded minimal per-need/evidence inputs.
- `SaturnClaimDraft`: need ID, evidence ID, kind and asserted payload. The provider never grants truth status.
- `SaturnVerifiedClaim`: exact need/evidence binding; statuses `verified_structured` and `quote_integrity_verified`, canonical backend-checked payload and source identity; physical PDF page only from the original source.
- `SaturnRejectedClaim`: stable `proposal_index` and safe `reason_code`, not untrusted model payloads.
- `SaturnClaimVerificationResult`: original question/snapshot/bundle/policy identities, verified/rejected claims, unresolved needs, aggregate state and integer-only diagnostics.

The verifier reconstructs the exact canonical source values from the pinned `SaturnKnowledgeSnapshot`: `SiteFact` ID, entity, full field path, raw JSON, source revision, unit and qualifiers; `SiteRelation` ID, directed triple, source field path/revision; or exact source text in the authenticated site/PDF evidence, including PDF bytes SHA, parser version, document identity, owner and *physical page*. No numeric conversion, normalization, inference, semantic entailment or evidence laundering.

Each eligible need selects only one evidence ID already issued by Stage 5A and attached to that need by a freshly computed Stage 5B assessment. `document_found` is metadata only; document-only requests skip the provider (`generation_not_required`). `text_candidate` may produce an exact quote, but remains unresolved for engineering truth. Global ambiguity, conflict and unresolved question disallow generation. Partial structured coverage preserves all unfulfilled needs.

Final `complete` requires every structured need verified and every other need a valid metadata lookup; any extra/duplicate/rejected claim prevents a full positive state. Provider/network failures, malformed output and budget violations never masquerade as missing knowledge. Context/session/policy violations reuse fail-closed Stage 5A safe `SaturnContextError` codes.

## Limits

| Resource | Limit |
|---|---:|
| Selected needs | 6 |
| Provider evidence units | 6 |
| Atomic proposals | 6 |
| Total provider source text | 8000 characters |
| Exact extractive quote | 1000 characters |
| Single provider assertion payload | 10000 characters |

Oversized provider output tuples, payloads and identifiers are rejected before individual source comparisons. The request is immutable and provider-facing evidence contains no URL, full corpus or snapshot manager. Provider allowlist accepts the **exact class** `SaturnFakeClaimProvider` (not a duck-typed object with `offline=True`). No production registry or egress permission is added.

## Testing and acceptance

`backend/tests/unit/test_saturn_atomic_claims.py` contains public-path positive and adversarial test groups covering T-01–T-50 scenarios, with direct verifier tests only where corrupting canonical source objects would be impossible inside a valid issued session. The existing Stage 4A/4B/5A/5B and legacy tests are part of `python scripts/verify_offline.py`.

Final test counts and push/pull-request workflow links are to be verified on the **same exact final head** and recorded in the PR. Until both `offline-checks` and `onnx-contracts` pass in both workflows, Stage 5C remains under development.

## Known limits and next dependency

Stage 5C provides no production model integration, free-form semantic claim entailment, comparisons, calculated values or converted units; exact extracts cannot automatically establish engineering truth. An offline deterministic fixture does not substitute for real generator evaluation. Policy is checked at capture/return boundaries; Stage 5D must check again before user-facing publication. Next stage after independent approval is **Stage 5D — Answer Assembly, Citations & Final Policy Gate**, not part of this PR.

`UkWood/Saturn-Main-Site` was not modified. No merge or Stage 5D work is authorized.
