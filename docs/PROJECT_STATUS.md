## CURRENT — Consolidated Stage 5F–5I PR #32 (12 November 2026)

**Status:** DRAFT / IMPLEMENTATION IN PROGRESS, **NOT ACCEPTED**. Baseline AI main `84d783331cc755e688a7f8637be13c297c07f43e`; site main `084d759487bfab6e111549c9b5469711ac5fc13e` (READ-ONLY). Single branch `feat/saturn-real-corpus-llm-validation-v0.1`, single [PR #32](https://github.com/UkWood/LLM-RAG-chat-bot/pull/32); no merge.

- Stage 5F: partial engineering implementation — pinned experimental site/PDF sample and existing production-like RAG CLI; **real PDF ingestion/snapshot/query not measured yet**.
- Stage 5G: real open calibration **runner implemented**, real gold/25–40 cases/metrics **NOT_RUN**.
- Stage 5H: independent real blind infrastructure and source-backed independently authored dataset **NOT_IMPLEMENTED / NOT_RUN**.
- Stage 5I: local loopback-only provider and Stage 5C exact-class allowlist implemented with offline/mocked tests. **Real inference NOT_RUN**, model quality **NOT_ESTABLISHED**. Existing Stage 5B free-form limitations remain.
- Exact-head CI and independent Acceptance Review are required. None of the new unit tests constitute real-site or real-LLM evidence.
- Stage 5E synthetic historical frozen artifacts unchanged. No Stage 6, production or cloud egress.
- [Live implementation report and reproduction commands](stages/2026-11-12-saturn-real-corpus-llm-validation.md).

---

## PR #31 — Stage 5E consolidated correction state (11 November 2026)

- Session A requested 2 BLOCKER + 3 IMPORTANT; Session B corrected in existing `feat/saturn-grounding-evaluation-v0.1` / PR #31, no merge. Need/owner source scope, blind complete-time provenance, extractive substring, session-pinned diagnostics and separate error/claim metrics are addressed. Independent final acceptance review remains pending.
- Original open 28-case calibration bytes and first report unchanged, with their original source/scorer identity. Revised scorer/rubric `0.1.1` will be measured in a separately versioned report; controlled fault-injection is not an independent blind result.
- Only Stage 5E implementation/test/docs/CI changed; Stage 4A–5D, source-site repo, historical planner blind and frozen evaluation artifacts not changed.
- `independent_blind_evaluation=NOT_RUN`; `production_readiness=false`; no real sample, model provider, Stage 6 or merge. [Corrections detail](stages/2026-11-11-saturn-grounding-evaluation.md).

## CURRENT — Stage 5E Saturn Grounding Evaluation v0.1 (11 November 2026)

**Status:** coding candidate / independent Acceptance Review required, **NOT MERGED**. Verified `main=8dc9d2fbd20854bd54903ff617581ed4ecad6e31` after Stage 5D PR #30. Branch `feat/saturn-grounding-evaluation-v0.1` adds Saturn-specific gold validation, independent scoring, stage attribution, offline runner, deterministic safe reports and frozen one-shot blind protocol. Existing production answer stages, historical datasets/reports and Saturn-Main-Site remain untouched.

**Measured calibration baseline:** 28 authored open synthetic Saturn cases; 17/17 complete positives, 5/5 correct needs_support, 3/3 clarification, 3/3 partial, 24/24 valid citations, 0 unsupported technical claims, 0 false refusals. Fixture snapshot `23363c78bdec37ffeb74fd5cc985e0bb781764049e4178f070f452651967d0cf`; dataset SHA-256 `eff320bc664fdb23dc7ee69ddb479c796a5c5aeee341a043f3d782119ab733e8`. First observed CI run [#43082293017](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43082293017), evaluation code commit `4fde232947e6989a242fd3308e0c7cf4eedb29d1`. Actual report committed under `evaluation/reports/saturn-grounding-calibration-v0.1.json`.

**Not completed:** new independent blind = `NOT_RUN`, real sample evaluation = `NOT_RUN`, product acceptance / production readiness = `false`; full exact-head push+PR CI and independent Session A review pending. No Stage 6. See [Stage 5E report](stages/2026-11-11-saturn-grounding-evaluation.md).

## Stage 5D PR #30 — Consolidated CR-01 / CR-02 Corrections (2026-11-11)

- Session A's independent review of head `6b00e4b08a55098a73d8f1e6ded6c3108c5da811`: **1 BLOCKER + 1 IMPORTANT**. Both corrected together in existing PR #30 and branch `feat/saturn-answer-assembly-v0.1`.
- CR-01: answer and statement strings are **literal plain text**. No `html.escape`, `html.unescape` or HTML/Markdown interpretation in backend. Safe UI text rendering remains a future responsibility.
- CR-02: output text overflow collects **every affected need ID before discarding statements/citations**; returns safe `error` and accurate final counters without leaking partial technical output.
- New targeted CR01-T01–T07 and CR02-T01–T06, plus Stage 4A–5C and existing Stage 5D regressions. Exact final SHA / GitHub CI results are recorded in PR #30 and Stage 5D report.
- **NO MERGE / NO Stage 5E.** `UkWood/Saturn-Main-Site` remains READ-ONLY.

## Stage 5D — Answer Assembly, Citations & Final Policy Gate v0.1 (2026-11-11)

- **Baseline main:** `9d6c6fa1da180e62feb22134efa92724d8173f17`; Stage 5C **PR #29 MERGED**, merge CI [#43052161495](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/43052161495).
- **Active implementation:** `feat/saturn-answer-assembly-v0.1`; one PR to `main`, independent Session A review required; **NO MERGE / NO Stage 5E**.
- Stage 5D consumes the real issued session/context; calls Stage 5C itself, re-runs Stage 5B on the same pinned snapshot, independently confirms canonical claims, renders exact backend text, constructs site/PDF/document metadata citations and performs a final operational policy recheck under the session lock.
- Output: frozen `SaturnAnswerResult`, statement/citation records, statuses `answered/partial/clarification/needs_support/error`; no production model, API, UI or deployment. Source quotes are explicitly non-entailing and omitted from main answer text.
- Budgets: max 6 technical statements, 10 document matches, 16 citations, 12,000 characters of answer text; no silent truncation. See [Stage 5D report](stages/2026-11-11-saturn-answer-assembly.md) and the PR for exact head and CI.

## Stage 5C — Bounded Generation & Atomic Claim Verification v0.1 (2026-11-11)

- **Current main baseline:** `973c3d2f3ae2c5c7a079a3e92072121bf9082edf`; PR #28 **MERGED**. Historical older sections calling PR #28 OPEN or Stage 5C unstarted are superseded, not retroactively rewritten.
- **Stage 5C PR:** [#29](https://github.com/UkWood/LLM-RAG-chat-bot/pull/29) (single draft under CI; no merge); exact final head and CI documented in PR. 
- **Active feature branch:** `feat/saturn-atomic-claim-verification-v0.1`; one Stage 5C PR, independent Acceptance Review required; **NO MERGE / NO Stage 5D**.
- Implements new immutable Saturn-specific bounded provider request, exact-class offline Fake provider, independent per-claim canonical verification of fields/relations/extractive site and PDF quotes, rejection accounting, completeness and pre/post operational policy rechecks. Context/session lifecycle stays pinned to Stage 5A.
- Limits: 6 needs, 6 provider evidence, 6 claims, 8000 total source characters, 1000 quoted characters. No cloud, new API, frontend, ingestion, source policy or changes in `UkWood/Saturn-Main-Site`.
- [Stage report](stages/2026-11-11-saturn-atomic-claim-verification.md). Exact final SHA, offline suite and push/PR CI are recorded in the PR after checks.

## PR #28 — CR-01 / CR-02 Consolidated Corrections (2026-11-11)

- Existing PR #28, branch feat/saturn-question-needs-gate-v0.1, reviewed head 79a6a3b27a4be73bac509758a143e8d119d223cf; main baseline 0f0286cf55b72c4793d66f5d648f5b37ab8356f4. Session A requested CR-01 BLOCKER and CR-02 IMPORTANT; these corrections remain in the same PR. NO MERGE / NO Stage 5C.
- CR-01: non-substantive null/empty strings/lists/objects no longer count as covered_structured; existing evidence IDs retained. Numeric 0, false and nonempty structures keep their source semantics.
- CR-02: source-compatible canonical field paths, bracketed JSON keys and repeated indexes, safe literal punctuation, no separator split in quoted key, bounded needs and conservative unresolved fallback.
- CR01-T01–T07 and CR02-T01–T10 tests plus adversarial regressions; actual full offline and exact-head push/PR CI results must be confirmed in [PR #28](https://github.com/UkWood/LLM-RAG-chat-bot/pull/28). Historical green checks are not correction acceptance.
- Saturn-Main-Site read-only, Stage 5A lifecycle/retrieval/ADR/provider unchanged. [Stage report](stages/2026-11-11-saturn-question-needs-gate.md).

## Stage 5B — Question Needs, Sufficiency & Conflict Gate v0.1 (2026-11-11)

- **Live baseline:** `main=0f0286cf55b72c4793d66f5d648f5b37ab8356f4`; Stage 5A PR #27 MERGED. Older sections about #27 OPEN/NO 5B below are historical checkpoints.
- **One feature PR:** [#28](https://github.com/UkWood/LLM-RAG-chat-bot/pull/28), `feat/saturn-question-needs-gate-v0.1`, base SHA above; **OPEN / independent Acceptance Review pending; NO MERGE / NO Stage 5C**.
- Deterministic conservative parser: exact source-declared entity identity, bounded field lists, exact relations, document title/owner lookup, original spans, explicit unresolved remainder, max six requirements. Free-form engineering questions remain unresolved, not guessed.
- `SaturnQuestionGate.assess(session, context)` executes against the issuing Stage 5A pinned snapshot under session lock, with operational-policy rechecks before and after. Immutable needs/findings/assessment separate structured coverage, metadata lookup, text candidates, selected-context absence, ambiguity and scoped potential conflicts.
- New offline regression tests in `test_saturn_question_needs.py` cover T-01–T-29; T-30 is complete `scripts/verify_offline.py` plus exact-head push/PR CI. Final test results belong to the PR description; **never infer SUCCESS before actual jobs conclude**.
- [Stage report](stages/2026-11-11-saturn-question-needs-gate.md). Only RAG repo changed; `UkWood/Saturn-Main-Site` remains strictly READ-ONLY. No generation, claim verification, final citations, provider or retrieval-index changes.

## PR #27 — CR-01/CR-02 Acceptance Corrections (2026-11-11)

- **Текущий PR:** [#27](https://github.com/UkWood/LLM-RAG-chat-bot/pull/27), ветка `feat/saturn-evidence-context-v0.1`, baseline `main=340e7d63e6899d855a01547003d1d983e9078eda`, initial reviewed head `c95cef4aebfbdef512e4cb54d0b14585d089deb1`. Статус: **CHANGES REQUESTED**, исправления CR-01/02 внесены, exact-head CI и повторный независимый review обязательны.
- **CR-01 BLOCKER:** прямой конструктор `SaturnAnswerSession` запрещён; factory under service publication lock делает bundle capture + Qdrant `_retain()`, при construction failure освобождает lease. `_service/_bundle/_lock` и lifecycle/ownership immutable для обычного assignment; `_issued` immutable tuple, только controlled update; close idempotent, Qdrant deferred release.
- **CR-02 IMPORTANT:** invalid UTF-8 surrogate → `invalid_request`; corrupted context fingerprint → `context_identity_mismatch`. Operational-policy capture обёрнут в typed `SaturnPolicyCaptureError` на границе 4B; любые прочие обычные backend errors → `retrieval_unavailable` без анализа текста исключения и без утечки provider diagnostics.
- **Тесты:** добавлены T-01–T-15 в `test_saturn_evidence_context.py`, в том числе настоящие Thread/Event concurrency, multiple reader leases, failure cleanup, provider/index faults, Unicode, immutable ownership. Полный `python scripts/verify_offline.py` и оба jobs на финальном SHA — обязательная проверка, результаты публикуются в [PR #27](https://github.com/UkWood/LLM-RAG-chat-bot/pull/27), не предполагать PASS заранее.
- [Stage report](stages/2026-11-11-saturn-evidence-context.md). Никаких изменений `UkWood/Saturn-Main-Site`; сохранены 4A/4B semantics и граница Stage 5A; **NO MERGE / NO 5B**.

## Текущий этап — Stage 5A Saturn Evidence Context v0.1 (2026-11-11)

- `main=340e7d63e6899d855a01547003d1d983e9078eda`: PR #26 **MERGED**, точный baseline CI [#42914744740](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42914744740) оба jobs SUCCESS. Нижние разделы о PR #26 OPEN — сохранённая история.
- **В реализации:** `feat/saturn-evidence-context-v0.1`, отдельный PR. Pinned request-scoped `SaturnAnswerSession`, Qdrant lease, `SaturnTypedEvidence` с канонической identity и отдельный `SaturnDocumentReference`, `SaturnEvidenceContext`, operational-policy recheck, fail-closed limits/errors.
- Новый `backend/tests/unit/test_saturn_evidence_context.py` покрывает positive/negative, concurrency, policy, metadata и проверку source fidelity. Проверки полного offline suite и CI exact final PR head фиксировать в PR, не заявлять PASS без исполнения.
- [Stage report](stages/2026-11-11-saturn-evidence-context.md). Нет sufficiency/generation/claim/citation/UI. Сессия A отвечает за независимое Acceptance Review; **NO MERGE / NO 5B**. Сайт `UkWood/Saturn-Main-Site` read-only без изменений.

## PR #26 — Consolidated Acceptance Review Corrections CR-01–CR-03 (2026-11-10)

- **Тот же PR и ветка:** [#26](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26), `feat/saturn-channel-aware-retrieval-v0.1`. Review baseline `2ef92e3e69acbd9999ad3bb15b43e610e95e7106`. **CHANGES IMPLEMENTED; независимый re-review ещё не выполнен; NO MERGE / NO STAGE 5.**
- **CR-01:** frozen active bundle + lexical/metadata artifacts, sealed Qdrant и immutable alias mapping, service active-pointer protection, единый atomic publish, deferred Qdrant close по active/in-flight leases.
- **CR-02:** BM25 searches use prepared terms/counts; eligible-only DF/N/average; repeated queries не токенизируют весь корпус, original scoring verified by independent reference test.
- **CR-03:** signed numbers, Unicode minus normalization, decimal comma/dot and literal ranges; identifiers preserved; tokenizer `0.2.0` + representation `0.1.1` участвуют в manifest/index identity.
- **Тесты и CI:** исходный baseline 387 backend tests (11 optional skips), 5 project checks; после CR добавлены targeted regression methods. Итоговые actual counts/CI on exact final PR head — в [PR #26 Checks](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26/checks), проверять после docs commit.
- **Отчёт:** [Consolidated Acceptance Review Corrections](stages/2026-11-10-saturn-channel-aware-retrieval.md). Scope неизменен; source `UkWood/Saturn-Main-Site` только READ-ONLY, canonical/ADR/legacy/frozen evaluation untouched. Не делать merge до независимого re-review.

## Текущий этап 4B — Saturn Channel-Aware Retrieval v0.1 (2026-11-10)

- **Verified baseline:** `main=2da357db4543c9ca173db7663bbd18396d221cc3` — PR #25 **MERGED** (проверено по GitHub). Все старые записи «PR #25 OPEN» ниже — исторические checkpoint, не текущее состояние.
- **Ветка:** `feat/saturn-channel-aware-retrieval-v0.1`, ожидаемый PR #26. Merge **не выполнять** до независимого Acceptance Review.
- **Код:** отдельные `retrieval/saturn_channel.py` и `retrieval/saturn_qdrant.py`; BM25, optional local Qdrant, RRF, document metadata channel, exact snapshot/index manifest, runtime policy recheck, один atomically published bundle pointer. Legacy synthetic Registry и ingestion contracts не менялись.
- **Тесты:** `test_saturn_channel_retrieval.py`, exact-head `offline-checks` / `onnx-contracts` проверяются по GitHub Actions. Не объявлять semantic relevance PASS: нет закреплённого реального encoder и согласованного Saturn benchmark.
- **Границы:** нет generation, citations, UI, production Qdrant, cloud/remote endpoints; stage 5 не начат. Известное ограничение 4A по независимой верификации absolute SITE_URL origin сохраняется.
- **Документ:** [отчёт 4B](stages/2026-11-10-saturn-channel-aware-retrieval.md). `UkWood/Saturn-Main-Site` строго READ-ONLY.

# Состояние проекта

## PR #25 — Consolidated Corrections CR-01–CR-04 (2026-11-10)

Existing [PR #25](https://github.com/UkWood/LLM-RAG-chat-bot/pull/25): **OPEN, NOT MERGED**, corrected code head `812f5156d5613b90b39dfd5f1a25454795d434dc`. Source-derived projections/units/YAML, full relation reconstruction, catalog-link exact replay and independently revalidated atomic activation; 18 новых adversarial test methods. **Code-head offline: 360 backend tests OK (11 skips), 5 project checks PASS**; [push CI](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42892414054), [PR CI](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42892426380). Exact final PR head/CI — в описании PR. Ограничение: production URL origin `astro.config.mjs` не может быть отдельно доказан без config bytes в source package; вопрос передан архитектурной сессии A. [Отчёт](stages/2026-11-10-unified-knowledge-snapshot.md). Независимый re-review, **NO MERGE / NO 4B**. Saturn-Main-Site READ-ONLY.

## Этап 4A — Unified Knowledge Snapshot v0.1 (2026-11-10)

**Baseline:** PR #24 MERGED, `main=01cb640e1b67ee84b4dff00afa6a798bc5203c54`.
**PR #25:** [feat: implement Unified Knowledge Snapshot v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/25), **OPEN, NOT MERGED**. Рабочая ветка `feat/unified-knowledge-snapshot-v0.1`.

Новые Saturn-only contracts/validator/builder/atomic manager, isolated answer/document channels, stable manifest, exact source/physical PDF provenance, stage diagnostics, strict readiness gates, offline contract/integration tests. Независимый Acceptance Review после exact-head CI; merge только по отдельному разрешению. Не затронуты synthetic/registry, canonical adapters/ADR и read-only Saturn-Main-Site. Этап 4B ещё не начат.

[Отчёт этапа](stages/2026-11-10-unified-knowledge-snapshot.md). Исторические разделы ниже сохраняют pre-merge статусы PR #24, не являются текущим checkpoint.


## PR #24 — CR-01/CR-02 Consolidated Acceptance Review Corrections (2026-11-10)

Исправляющий code commit `86c352adc3bfed4cbc80265812b77f6f5a6e07b5`: заменён unbounded subprocess stdout/stderr capture на bounded multiplexed pipes с прекращением worker и reaping; signal termination перед JSON parsing детерминированно даёт resource_limit. Девять CR regression methods, **328 backend tests OK (11 skips)**, 5 project tests PASS; [push CI #42852633667](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42852633667) SUCCESS, offline-checks / onnx-contracts. Final docs/head CI и independent re-review проверять через [PR #24](https://github.com/UkWood/LLM-RAG-chat-bot/pull/24). OPEN, NOT MERGED. Production OS sandbox не реализована. Saturn-Main-Site READ-ONLY; этап 4 не начат.


## Этап 3B — External Document Adapter v0.1 (2026-11-10)

PR #23 успешно MERGED в main `dee6011fa67de0bcc62b8304b7549b4ebde396b1`; main Actions run #42838702444 SUCCESS. Это подтверждённый baseline. Новая feature branch: feat/external-document-adapter-v0.1, [PR #24](https://github.com/UkWood/LLM-RAG-chat-bot/pull/24) OPEN, NOT MERGED. Добавляются независимый External Document Adapter, immutable PDF revisions/evidence, URL/SSRF policy, bounded transport и isolated development worker; новые offline tests. Реальная production OS sandbox **не подтверждена**, поэтому worker по умолчанию отключён. Проверенный 3B code head 887108ea65feec91ddcd01631d742aaceb8c2b62: push Actions [#42847781478](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42847781478) и PR [#42847795850](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42847795850) оба SUCCESS, 320 backend tests (11 skips), 5 project tests PASS, ONNX PASS. Финальный документационный head проверить отдельно. Независимый review и merge не выполнены. Saturn-Main-Site только READ-ONLY; этап 4 не начат.

[Отчёт этапа 3B](stages/2026-11-10-external-document-adapter.md). Все записи ниже, где PR #23 обозначен OPEN, являются историческими pre-merge checkpoint.



## PR #23 — Consolidated Review Corrections, code checks PASS (2026-11-10)

В существующем PR #23 устранены CR-01–CR-04 без изменения архитектурных контрактов/ADR: Markdown/HTML PDF link scanner, безопасная URL identity, 8 неизменённых read-only site fixtures, универсальный coding prompt. Проверенный **code head** `b2ee0164c49f53cba7121df92c6538e557b4b7e3` (`60ca2856265e2d3a8f5276897892122a7c20a9e3` — implementation commit). GitHub Actions [push #42816240259](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42816240259), [PR #42816246557](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42816246557) **SUCCESS**: 288 backend tests (11 skips), ONNX PASS; 7 новых regression cases. [Подробности и ограничения](stages/2026-11-10-support-catalog-adapter.md). После обновления документации сверить CI финального PR head; **PR OPEN, NOT MERGED**. Не начинать 3B.


## Текущий этап 3A — Support Catalog Adapter v0.1 (2026-11-10)

**Основа:** PR #22 MERGED в `main`, merge commit `ff9baa8819714d5cb4ba9c61827dbf4666acd0b6`; main CI [#42777814511](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42777814511) SUCCESS.

**Реализовано, PR OPEN:** [#23 — Support Catalog Adapter v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/23), ветка `feat/support-catalog-adapter-v0.1` от указанного main. Реализуется чистый offline каталогизатор `SiteContentPackage → SupportDocument[]`, отдельные PDF-кандидаты и источник-специфичные occurrences/diagnostics. Canonical contracts, Site Content Adapter, ADR и сайт не меняются. Exact PR head/CI фиксировать после завершения проверок; без независимого Acceptance Review merge запрещён.

[Детали и ограничения этапа](stages/2026-11-10-support-catalog-adapter.md). Предыдущая запись о PR #22 ниже — исторический pre-merge checkpoint; статус OPEN утратил актуальность после merge.


## GitHub Snapshot Provider v0.1 — PR #22 consolidated review corrections (2026-11-10)

**PR #22:** [feat: implement GitHub Snapshot Provider v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/22) — **OPEN; NOT MERGED; awaiting independent re-review**.
**Branch:** `feat/github-snapshot-provider-v0.1`. Base main `9b2e0882b81fa2737e7efebb109c079a39b392d8`.

- Four review issues corrected in the existing PR: nonrecursive endpoint without `recursive` (BLOCKER), source-directory symlink/gitlink detection (BLOCKER), selective fallback traversal excluding assets/archives (IMPORTANT), exact `refs/heads/main` response identity check (MINOR).
- RED tests commit `491f14fe1e926958d8d934113a014398a76b2140`: CI [#42774670369](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42774670369) **FAILURE** — 12 expected failing outcomes out of 254 tests.
- Corrective implementation code head `27b64b439b699bef396122c395cf091fb60735f0`: push CI [#42774964424](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42774964424) **SUCCESS**, 254 backend tests passed with 11 existing optional skips; ONNX contracts PASS.
- 42 provider regression tests (nine new methods). Additional test hardening includes over 300 unrelated archive/asset directories and nested symlink in fallback.
- Direct read-only GitHub API verification against `Saturn-Main-Site@084d7594`: `/git/trees/{sha}` returned 16 immediate root entries, while `?recursive=0` and `?recursive=1` returned 1,119 recursive entries; child-tree direct lookups also returned only immediate entries with matching SHA.
- No local shell test execution: runner has no checkout/network. Offline and ONNX suites were actually run in GitHub Actions. Exact commands and RED→GREEN evidence are in [stage report](stages/2026-11-09-github-snapshot-provider.md).
- No changes to canonical contracts, pure Saturn Site Content Adapter, ADR-0012/0013/0014 or `Saturn-Main-Site`. No Git clone/CLI, new dependencies, Gitea/PDF/retrieval/runtime work.
- Final documentation/test commit changes PR head; check its exact SHA and CI before independent acceptance. Merge only on separate owner command.

## Previous implementation checkpoint — PR #22 before consolidated review (2026-11-09)

**PR #22:** [feat: implement GitHub Snapshot Provider v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/22) — **OPEN, not merged**.
**Branch:** `feat/github-snapshot-provider-v0.1`  
**Base:** `main` at `9b2e0882b81fa2737e7efebb109c079a39b392d8`.  
**Implementation code head:** `ce501d2df5d120a3a437f6e32359a71e7d0543b6`.

Добавлены provider-neutral `SnapshotProvider` Protocol и первая GitHub REST реализация `GitHubSnapshotProvider`. Provider pin-ит `refs/heads/main` один раз, читает immutable commit/tree/blob IDs, поддерживает GitHub recursive-tree truncation fallback, применяет утверждённую selection policy и формирует существующий `PinnedSiteSnapshot` без изменений adapter/contracts.

**CI implementation code head:** push [run #42696950473](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42696950473) и PR [run #42696961675](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42696961675) — оба `offline-checks` и `onnx-contracts` **SUCCESS**. Offline suite: **245 backend tests passed, 11 existing optional skips**; project checks PASS.

Добавлено 33 provider-specific offline tests: pinning/branch movement, recursive and fallback tree completeness, deterministic selection, route-source drift, symlink/submodule rejection, Git blob SHA-1, SHA-256 provenance, sizes/base64, errors/retries/resource limits, partial-snapshot rejection и integration с `adapt_snapshot()`.

Read-only metadata audit текущего `Saturn-Main-Site@main` на commit `084d759487bfab6e111549c9b5469711ac5fc13e`: recursive tree complete (`truncated=false`), 1,119 entries, 477 selected files / 2,233,425 bytes, largest selected file 32,186 bytes; `src/pages/` 23 files (19 `.astro`, 4 `.ts`), route drift отсутствует. Исходный репозиторий не изменялся.

GitHub repository metadata не предоставляет `object_format`; runtime требует явный `SATURN_GITHUB_OBJECT_FORMAT=sha1` и read-only `SATURN_GITHUB_TOKEN`. Каждый blob проверяется по canonical SHA-1. Live provider smoke test и runtime/scheduling integration не выполнялись. Новых зависимостей нет.

Не реализованы: Gitea Provider, PDF ingestion, Git-backed PDF retrieval, retrieval/embeddings/reranking, LLM/provider, API/UI, deployment и production scheduling. `UkWood/Saturn-Main-Site` остаётся строго READ-ONLY.

Перед merge нужен один полный Acceptance Review текущего PR head. Все замечания выдаются единым консолидированным списком. Merge запрещён без отдельной команды владельца.

## Previous completed stage — Snapshot Provider Contract (PR #21 merged, 2026-11-09)

**PR #21:** [docs: approve provider-neutral Snapshot Provider contract](https://github.com/UkWood/LLM-RAG-chat-bot/pull/21) — **MERGED**.  
**Merge commit:** `9b2e0882b81fa2737e7efebb109c079a39b392d8`.  
**Reviewed architecture/contract head:** `0f2a1226b757ae346d65b05df13be657e3581d35`.

PR #21 был documentation-only этапом: принят provider-neutral Snapshot Provider Contract v0.1 и ADR-0014. При первоначальном review PR был OPEN; впоследствии владелец дал команду merge, после чего PR #21 был слит. PR-head CI [#42624653260](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624653260) и push CI [#42624644980](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624644980) прошли SUCCESS на reviewed architecture head. Main CI после merge [#42688738332](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42688738332) также SUCCESS.

PR #21 не содержал provider implementation, PDF ingestion или runtime changes. Его исторический scope и reviewed head сохранены в [stage report](stages/2026-11-09-snapshot-provider-contract.md).
## Previous completed stage — Saturn Site Content Adapter (PR #20 merged, 2026-11-09)

**PR #20:** [feat: add trusted Saturn site content adapter](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20) — **MERGED**.  
**Implementation head:** `9b36551adf61070426caa9250650bb32d638a66a`.  
**Merge commit:** `361529963bd48772f0d9d478dfb3b963ec5a8d03` (base до merge: `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`).  
PR #17/#18 также слиты; ADR-0012/0013 и canonical contracts остаются действующей архитектурной основой.

Pure/offline Saturn Site Content Adapter включён в main. Он принимает immutable `PinnedSiteSnapshot`, проверяет Git blob SHA по точным bytes, динамически обнаруживает Markdown collections и сохраняет raw source evidence. Stable logical source ID отделён от физического GitHub/Gitea remote. Canonical URLs строятся по реальным Astro routes; route/config changes и parser-version changes отражаются в manifest/drift. Старые manifests совместимы; неизвестные explicit `pages.kind` не классифицируются как `Page` автоматически.

Кодовый head проверен GitHub Actions: PR-head [run #232](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569426503) — **SUCCESS**; push [run #231](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569421610) — **SUCCESS**. Offline suite: 212 tests passed, 11 existing optional skips; ONNX contracts PASS. Synthetic baseline не изменился: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 0.85. Это прежняя synthetic evaluation, не метрика качества нового адаптера.

Не реализованы: GitHub/Gitea Snapshot Provider, Gitea Actions, PDF fetching/parsing, retrieval integration, LLM/provider, API/UI и deployment. Не использовался legacy SourceRecord/Registry approval path. ADRs не изменялись. Saturn-Main-Site остаётся строго READ-ONLY на проверенном commit `084d759487bfab6e111549c9b5469711ac5fc13`.

**Результат последующего этапа:** архитектурное согласование Snapshot Provider contract завершено и зафиксировано в ADR-0014 и открытом docs-only PR #21. Реализация провайдера остаётся отдельной будущей задачей и требует отдельной команды владельца.

## Planner V2 corrective revision — 2026-11-06

Owner requested continuing after PR10 merge review found two Important blockers: discarded `нет` and protocol qualifiers. Corrections reject negation, unsupported Modbus/TCP/RTU qualification and modification requests outside supported lookup bindings before generation; unqualified protocol queries remain supported, V1 default unchanged. [Corrective report](stages/2026-11-06-planner-v2-corrections.md), [plan addendum](superpowers/plans/2026-11-06-typed-planner-v2.md). Final local verification5project+168backend PASS in both environments (base11optional skips/optional0), calibration14/14 positives20/20statuses without V1-positive regression; independent review fix pass complete. Current-head remote CI/merge outcome must be checked in PR10.

This is a post-blind corrective version. First experiment7bc6f11/dataset/START/report are immutable historical evidence; old8/24+14/16 numbers do NOT measure the corrected runtime. Its independent quality is NOT_RUN, prototype NOT accepted. No consumed-set replay/tuning or new safety/generalization claim. Fresh independent data/freeze needed before a future quality claim. Real sources/cloud unchanged; Saturn-Main-Site strictly READ-ONLY. Historical entries below describe earlier revisions.


## Typed planner V2: first blind assessment — 2026-11-06

Owner-approved PR9 design implemented in feat/typed-planner-v2; v1 remains default. Freeze7bc6f118e820fc5d4f648fb22997ad65d9e1c99c; independently authored/reviewed40case dataset consumed once after exclusive START. Actual V2 positives8/24, negative/ambiguity14/16, all22/40; V1 positives0/24, negative/ambiguity12/16. V2 emitted quote support/canonical validity1.0,unsafe0,errors0; quality target FALSE, full prototype NOT accepted. Calibration14/14 positives did not generalize. No code/config/grader changes after first result. [Stage report](stages/2026-11-06-typed-planner-v2.md), [first report](../evaluation/reports/2026-11-06-planner-v2-first-blind.json), [ADR0009](decisions/0009-typed-planner-v2.md).

Final local verification5project+161backend PASS in both environments (base11optional skips/optional0); independent review fixes RED→GREEN. Existing local bundles only, no new dependencies/approvals/cloud; Saturn-Main-Site strictly READ-ONLY. Next: separately designed/calibrated broader planner and fresh independent evaluation, not tuning on consumed cases or UI/cloud masking current coverage. Historical proposed/pending entries below superseded; publication/CI evidence appended after actual results.


## Актуально: после merge PR8, planner design — 2026-11-06

PR8 MERGED в maine0e44e54996b9f9e713899f7949746f27e33485b; main CI42209130861 SUCCESS проверен. Предыдущие open/unmerged сведения ниже исторические. Grounding quality остаётся8/20 positives, targetFalse; source-hit20/20 не означает answer20/20.

Подготовлен [proposed typed planner/projection design](superpowers/specs/2026-11-06-planner-expansion-design.md), [design report](stages/2026-11-06-planner-expansion-design.md). Код/новый dataset/benchmark НЕ создавались. Требуется принятие дизайна перед implementation. Рекомендация: compositional typed requirements, complete canonical fact groups, separate backend references, fresh independent blind set; semantic/generative router отдельно. Старые30cases сохранять как regression, tuning только calibration, не использовать exposed held_out как независимое доказательство. Новый proposed quality gate:24/24 positives +16/16 negative/ambiguity outcomes; меньший результат не является приёмкой. Saturn-Main-Site READ-ONLY, real sources/cloud по-прежнему закрыты.


## Текущий этап5: evidence gate — 2026-11-06

PR #7 MERGED в main861871b609f76ecad065e4b635e86ec3638b2cc8 после проверки clean head/all CI success; дальнейший merge нового PR не разрешён автоматически. Реализован bounded canonical evidence gate + Fake provider + exact claim/citation validation. [Design](superpowers/specs/2026-11-06-evidence-gate-design.md), [plan](superpowers/plans/2026-11-06-evidence-gate.md), [ADR0008](decisions/0008-evidence-gate.md), [stage report](stages/2026-11-06-evidence-gate.md).

Actual frozen dataset:8/20 positive answers, refusal8/8,clarification2/2,status accuracy.6,evidence recall.3; emitted claims/citations1.0,unsupported0. Held_out positives0/6. Grounding target NOT met, full prototype NOT accepted. Strict one-entity schema/manual grammar misses broader questions; keep failures, no held_out tuning. Source-hit20/20 prior retrieval remains valid but is not answer coverage. Next: separately designed/calibration-tested planner expansion before claiming full stage5/prototype acceptance; cloud/real sources still disabled. No new dependencies, Saturn-Main-Site READ-ONLY. Verification/review/PR evidence in stage report. Older sections below historical.


## Актуально: local reranking implementation — 2026-11-06

Owner approved design PR #6 and implementation. New bounded stage4 implemented after main92e7022: separate CPU pair scorer, canonical/policy-safe captured rerank and explicit atomic local preparation. Official mmarco-MiniLM revision1427fd652930e4ba29e8149678df786c240d8825 experiment: source-hit20/20, all-source/gold evidence1.0, MRR.916667,nDCG.867586; baseline hybrid17/20,nDCG.629721. Frozen data/settings; no held_out tuning. Retrieval target passes this small synthetic set only. Grounding/refusal/answer quality NOT_RUN, full prototype NOT accepted.

[Stage report](stages/2026-11-06-local-reranking.md), [accepted design](superpowers/specs/2026-11-06-local-reranking-design.md), [implementation plan](superpowers/plans/2026-11-06-local-reranking.md), [ADR-0007](decisions/0007-local-reranking.md). Prior proposed/open state below is historical. Weights/card/tokenizer only work/; explicit restoration required after environment replacement. License card Apache-2.0 declaration only, not production legal clearance. Next stage5 evidence gate/grounded pipeline; real sources pending, cloud disabled, Saturn-Main-Site READ-ONLY. Actual verification/review/publication follow in stage report; never infer merge from green CI.


## Текущий статус — 2026-11-06, после merge PR #5

PR #5 merged: main `92e70223c579d10dfc785263d24a23d92940c6c1`, main CI42166311910 success. Подготовка E5 и actual dense/hybrid measurements опубликованы; источник правды — [отчёт](stages/2026-11-06-model-preparation.md). Исторические упоминания open PR #5/no checkpoint ниже относятся к предыдущим переходам.

Следующий bounded этап4: [local reranking design](superpowers/specs/2026-11-06-local-reranking-design.md), статус proposed. Изучены card/config лёгкого multilingual cross-encoder; pretrained reranker не получен и не выполнялся. До implementation нужен детальный план после принятия дизайна. Evidence gate/grounding/refusal — отдельный этап5. [Результат проектирования](stages/2026-11-06-local-reranking-design.md).


## Продолжение 2026-11-06: actual checkpoint и измерение

Предыдущий сетевой blocker снят: runtime policy unrestricted/enforced, huggingface.co и us.aws.cdn.hf.co вернули HTTP200 через штатный proxy. Получен официальный intfloat/multilingual-e5-small revision614241f622f53c4eeff9890bdc4f31cfecc418b3; CPU smoke прошёл, artifacts только в ignored work/. Model card декларирует MIT; отдельного LICENSE нет, сохранена точная строка декларации, это не production legal clearance.

На неизменных 10docs/44chunks/30cases: dense source-hit@5=18/20 (calibration12/14, held_out6/6), hybrid17/20 (13/14,4/6), BM25 baseline17/20 (14/14,3/6). Цель100% не пройдена. Reranking/grounding/refusal NOT_RUN; M1 generator не менялся. Не подгонять held_out. Следующий шаг — отдельный план reranking/evidence gate и calibration-only улучшений; реальные источники по-прежнему pending/UNKNOWN, Saturn-Main-Site только чтение.

Проверки: base verifier 5 project +93 backend tests, 6 optional skips; optional verifier 5+93 без skips. Десять targeted preparation tests PASS; canonical URL regression RED→GREEN. Обновлён optional CI. Отчёт: [model preparation](stages/2026-11-06-model-preparation.md). Публикация/CI фиксируются ниже по фактическому результату. Прежние блокеры и сведения о PR #4 ниже исторические (PR #4 merged a1093fb).


## Промежуточная передача 2026-11-06

PR #4 слит в main a1093fb, CI42097546595 success. Ветка feat/embedding-model-preparation содержит незавершённую подготовку локального embedding bundle; 8 целевых тестов PASS, полный suite/review/CI/PR ещё впереди. Реальная модель не получена, dense/hybrid quality NOT_RUN. Владелец обновил разрешение huggingface.co, но активная среда осталась на прежней политике и CONNECT403; продолжение в новой среде описано в [HANDOFF](HANDOFF.md). Сведения о PR #4 ниже относятся к прошлой публикации.

Обновлено:2026-11-05. Репозиторий UkWood/LLM-RAG-chat-bot.

## Выполнено

- PR #1/#2/#3 слиты. Main до текущего этапа be71efd, [CI42089988455](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42089988455) success. Snapshot contracts +10 synthetic docs/30 gold cases доступны в main.
- Новый этап3b: настоящий local BM25, embedded Qdrant memory/path adapter, policy-filtered publication/search/RRF и diagnostics; optional pinned single-file CPU ONNX adapter без model downloads.
- [Measured lexical baseline](../evaluation/reports/2026-11-05-lexical-retrieval.json): source-hit@5=17/20=85%, calibration14/14, held_out3/6. All-source success80%, gold-evidence recall72.5%, MRR≈.701667. Source-hit failures q005/q013/q016 сохранены. Target100% не пройден, held_out не подгонялся.
- Measured runner отделён от preflight; gold labels применяются после search, negatives не портят positive denominator. Unified verification включает code tests/preflight и lexical report.
- Independent review external ONNX sidecar hole воспроизведён и закрыт canonical single-file validation + pinned bytes loading. Optional CI проверяет actual numeric graph inference/security contracts, не язык/семантику.

## Неизмеренное и ограничения

Владелец подтвердил отсутствие local embedding checkpoint. Dense/hybrid/reranking/grounding/refusal в quality report=not_run. Qdrant test vectors не подменяют model quality. Lexical code CI green не означает приёмку прототипа. [Согласованные критерии](acceptance/prototype-v1.md) и ADR-0004 действуют, полный M2 не завершён.

Индексы/active publication process-local; Qdrant reopen проверен, но server/distributed/durable coordinated promotion и SLA отсутствуют. Raw source receipts только в памяти, output не подключён к M1 provider. Реальные sources (8 pending/UNKNOWN), registry bytes и Saturn-Main-Site не менялись. Cloud/API/UI/deployment не реализованы; ADR-0001 proposed.

## Текущая публикация

Ветка feat/local-retrieval-baseline от be71efd. Commits15197e7,5c1f2f2,812a2d2. [PR #4](https://github.com/UkWood/LLM-RAG-chat-bot/pull/4) открыт, push CI42094770037 на95eb0b0 success в обоих jobs (основной+optional ONNX). Последний head/checks и evidence в [отчёте этапа](stages/2026-11-05-local-retrieval.md). Новый этап не слит.

## Следующий шаг

Получить/подготовить trusted local embedding checkpoint с exact hashes/manifest и корректным pooling/prefixes по model card; выполнить actual dense/hybrid benchmark на текущем corpus. Затем reranking/grounding. Пока модели нет, можно развивать проверяемые adapters/контракты и evaluation, не заявляя semantic quality и не подгоняя held_out.

[Roadmap](superpowers/plans/2026-11-03-ai-consultant-roadmap.md), [local retrieval design](superpowers/specs/2026-11-05-local-retrieval-design.md), [ADR-0006](decisions/0006-local-retrieval.md), [handoff](HANDOFF.md).

## Публикация 2026-11-06

Commit b653014162b72b589eebd543a370a637f1dba92c опубликован в feat/embedding-model-preparation. [PR #5](https://github.com/UkWood/LLM-RAG-chat-bot/pull/5) открыт, не слит. [Push CI42165522960](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42165522960) на b653014 завершился success в обоих jobs, включая actual numeric preparation/swap tests. PR-event CI42165549055 на момент фиксации ещё in_progress; не считать его проверенным. Эта запись — отдельный docs commit, его CI следует проверять отдельно.

Публикация дизайна: [PR #6](https://github.com/UkWood/LLM-RAG-chat-bot/pull/6), branch feat/local-reranking-design, исходный commit55958ed. PR открыт, не принят/не слит; implementation не начата. CI проверять на текущем head PR, не выводить success из статуса предыдущих запусков.

## Публикация stage4

[PR #7](https://github.com/UkWood/LLM-RAG-chat-bot/pull/7), feat/local-reranking, implementation/fix commit2463ab0. PR открыт, НЕ слит. Design PR #6 закрыт как superseded: его accepted design и документация включены в #7; это не merge #6.

После review fix официальный pretrained benchmark повторён: metrics/baseline_metrics, все per-case ranks/raw scores и pinned identities точно совпали с committed report. Первоначальные timing measurements сохранены, повтор не используется для tuning. Full final base5+112PASS(skips11),optional5+112PASS(0 skips). Независимый review завершён, Important defect исправлен RED→GREEN, deferred product minors нет.

CI при публикации: push42168512725 и PR42168537774 на2463ab0 in_progress; это наблюдение, не заявление success. Проверять текущий head/actual checks в PR перед merge; новый docs commit проверяется отдельно. No automatic merge. Следующий отдельный stage5 — evidence gate/grounded pipeline, с собственным design/plan/quality gates.

Verified remote CI: [push42168613444](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42168613444) на d03a95d74535822f800b9cf02918eee7a7a863fe завершился SUCCESS, offline-checks и onnx-contracts (включая новые actual CPU pair contracts) оба success. Это CI реализации; данная запись — отдельный docs commit, его status проверять по текущему head PR #7. PR остаётся open/unmerged.

## Публикация

[PR #8](https://github.com/UkWood/LLM-RAG-chat-bot/pull/8), branch feat/evidence-gate, implementation commitf01ca77. PR открыт, НЕ слит; предыдущий PR7 merged861871b и main CI42169517262 SUCCESS. Текущие actual push/PR checks доступны в PR8; не выводить CI success из локальных тестов и не считать green CI quality acceptance.

Финальный actual replay после атомарного policy fix совпал с saved report по metrics/cases/model/snapshot/dataset identities. Единая optional команда завершилась strict_grounding_exit=1 именно из-за targetFalse, после133PASS backend tests; base verifier exit0. Ограниченная grammar/held_out0/6/false refusals не скрываются. Реальные source approvals/cloud/Saturn-Main-Site не менялись.

Публикация: [PR #9](https://github.com/UkWood/LLM-RAG-chat-bot/pull/9), feat/planner-expansion-design, initial commit1b14fb9. Design proposed, PR open/unmerged. До принятия владельцем код/new dataset не создавать. Актуальный CI смотреть на текущем head PR9; локальные doc checks не заменяют remote CI и не являются benchmark quality.

## Publication

[Implementation PR #10](https://github.com/UkWood/LLM-RAG-chat-bot/pull/10), branch feat/typed-planner-v2. PR open/unmerged; implementation freeze7bc6f11, first-result/report commitc0f0f3f. Docs-only PR9 superseded by this implementation including its owner-accepted design. Actual remote checks are available on the current head in PR10; local PASS is not a remote-CI claim or quality acceptance. The24/24+16/16 quality target remains FAILED. No runtime/config/grader change after freeze.

- **Corrected scorer 0.1.1 actual OPEN measurement** saved [here](../evaluation/reports/saturn-grounding-calibration-review-v0.1.1.json): 28/28, citations 24/24, positive 17/17, zero source-unsupported/off-question/extra text. Separately [controlled fault-injection report](../evaluation/reports/saturn-grounding-controlled-review-v0.1.1.json) shows expected policy/technical/simulated-conflict detections. Both executed at `bad73187f6e3dca187636ae5cea4cbca0c69dded`; 121 targeted tests. No independent blind.
