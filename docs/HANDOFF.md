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

## PR #27 — Stage 5A Consolidated Review Corrections (2026-11-11)

- **Текущий PR:** [#27](https://github.com/UkWood/LLM-RAG-chat-bot/pull/27), ветка `feat/saturn-evidence-context-v0.1`, baseline `main=340e7d63e6899d855a01547003d1d983e9078eda`, initial reviewed head `c95cef4aebfbdef512e4cb54d0b14585d089deb1`. Статус: **CHANGES REQUESTED**, исправления CR-01/02 внесены, exact-head CI и повторный независимый review обязательны.
- **CR-01 BLOCKER:** прямой конструктор `SaturnAnswerSession` запрещён; factory under service publication lock делает bundle capture + Qdrant `_retain()`, при construction failure освобождает lease. `_service/_bundle/_lock` и lifecycle/ownership immutable для обычного assignment; `_issued` immutable tuple, только controlled update; close idempotent, Qdrant deferred release.
- **CR-02 IMPORTANT:** invalid UTF-8 surrogate → `invalid_request`; corrupted context fingerprint → `context_identity_mismatch`. Operational-policy capture обёрнут в typed `SaturnPolicyCaptureError` на границе 4B; любые прочие обычные backend errors → `retrieval_unavailable` без анализа текста исключения и без утечки provider diagnostics.
- **Тесты:** добавлены T-01–T-15 в `test_saturn_evidence_context.py`, в том числе настоящие Thread/Event concurrency, multiple reader leases, failure cleanup, provider/index faults, Unicode, immutable ownership. Полный `python scripts/verify_offline.py` и оба jobs на финальном SHA — обязательная проверка, результаты публикуются в [PR #27](https://github.com/UkWood/LLM-RAG-chat-bot/pull/27), не предполагать PASS заранее.
- [Stage report](stages/2026-11-11-saturn-evidence-context.md). Никаких изменений `UkWood/Saturn-Main-Site`; сохранены 4A/4B semantics и граница Stage 5A; **NO MERGE / NO 5B**.

## Stage 5A — Saturn Evidence Context & Snapshot Binding v0.1 (2026-11-11)

- **LIVE verified main:** `340e7d63e6899d855a01547003d1d983e9078eda`; PR #26 **MERGED**, baseline Actions [#42914744740](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42914744740) offline-checks/onnx-contracts SUCCESS. Исторические строки ниже о #26 OPEN относятся к прошлому checkpoint.
- **Активная разработка:** `feat/saturn-evidence-context-v0.1`; один PR Stage 5A в `main`. Новый `SaturnAnswerSession` atomically pins один 4B bundle с Qdrant reader lease; `build_context()` выдаёт source-exact typed evidence и отдельно document metadata. `recheck_policy()` fail-closed проверяет актуальные source/evidence/document/PDF/entity блокировки. Strict immutable bounds 10/10/20k.
- **Тесты:** `backend/tests/unit/test_saturn_evidence_context.py` и полный `python scripts/verify_offline.py`; exact final head и push/PR CI — в описании PR. Не утверждать PASS до получения результатов.
- **Отчёт:** [Stage 5A](stages/2026-11-11-saturn-evidence-context.md). Вне scope sufficiency, generation, claim verification, citations, UI и deployment. **READY FOR INDEPENDENT REVIEW только после full CI на exact final head; NO MERGE / NO STAGE 5B**. `UkWood/Saturn-Main-Site` строго READ-ONLY.

## PR #26 — Consolidated Acceptance Review Corrections CR-01–CR-03 (2026-11-10)

- **Существующий PR:** [#26 — Channel-Aware Retrieval v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/26), та же ветка `feat/saturn-channel-aware-retrieval-v0.1`; первоначальный review head `2ef92e3e69acbd9999ad3bb15b43e610e95e7106`; **NO MERGE / NO STAGE 5**.
- CR-01 BLOCKER: замороженные `SaturnRetrievalBundle`, prepared lexical/metadata indexes, read-only dictionary aliases, sealed Qdrant identity и недоступный обычному assignment `service._active`; публикация единым pointer swap; Qdrant active/in-flight leases и deferred close при retirement.
- CR-02 IMPORTANT: prepared term counts и lengths используются при каждом запросе без повторного tokenize всего корпуса; BM25 DF/N/average пересчитываются по policy-eligible records. Существующие k1/b, RRF и разные evidence/document channels сохранены.
- CR-03 IMPORTANT: signed decimals/ranges как literal tokens; Unicode minus U+2212 → ASCII minus для numeric tokens; `-20`, `+20`, `20` различны; `0,5` — единый токен; engineering identifiers не смешиваются. Tokenizer `0.2.0`, evidence representation `0.1.1`, versioned index manifest.
- Regression suite расширен с baseline **387 backend tests (11 skips)**; synthetic legacy, canonical 4A snapshot, Saturn source fixtures и local Qdrant memory/path покрыты. Точный финальный SHA и **обе** GitHub Actions проверки фиксируются в описании PR **после** документационной синхронизации, без изменения этого документа ради SHA.
- [Consolidated stage report](stages/2026-11-10-saturn-channel-aware-retrieval.md). Не изменять legacy Registry/ADR/ingestion/source site; не заявлять semantic quality. Передать целиком повторному независимому Acceptance Review архитектурной сессии.

## Текущий handoff — этап 4B, Saturn Channel-Aware Retrieval v0.1 (2026-11-10)

- GitHub подтверждает **PR #25 MERGED**, текущий baseline `main=2da357db4543c9ca173db7663bbd18396d221cc3`. Прежние записи о PR #25 OPEN ниже — исторические.
- Ветка реализации: `feat/saturn-channel-aware-retrieval-v0.1`; PR #26 либо фактический номер. `retrieval/saturn_channel.py`, `retrieval/saturn_qdrant.py`, offline tests и [отчёт этапа](stages/2026-11-10-saturn-channel-aware-retrieval.md).
- Архитектура: strict 4A snapshot structural replay before indexing/publish; canonical Answer Evidence отдельно от SupportDocument metadata; BM25 + local optional Qdrant + RRF; bounded source-declared dictionary aliases; deterministic manifest/coverage; только **одна authoritative active bundle-ссылка**; operational policy pre/post search fail-closed. Старый approval-based Registry не используется.
- Нельзя выдавать synthetic/controlled Qdrant tests за реальную semantic quality Saturn. Production encoder, durable/multi-worker recovery, backend citations и stage 5 вне scope. Известное ограничение 4A: конфигурационные bytes `astro.config.mjs` не представлены во входе и absolute production SITE_URL origin независимо не доказуем.
- Перед Acceptance Review подтвердить финальный exact PR head и оба GitHub Actions jobs (`offline-checks`, `onnx-contracts`), полный diff и численные результаты. **Не выполнять merge и не начинать этап 5.** `UkWood/Saturn-Main-Site` строго READ-ONLY.

# Передача контекста — реализация кода

## PR #25 — Consolidated Acceptance Review Corrections (2026-11-10)

- **Existing PR #25:** [Unified Knowledge Snapshot v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/25), branch `feat/unified-knowledge-snapshot-v0.1`, **OPEN, NOT MERGED**; baseline main `01cb640e1b67ee84b4dff00afa6a798bc5203c54`.
- Corrected implementation code head `812f5156d5613b90b39dfd5f1a25454795d434dc`. CR-01 исходные байты → source projections; CR-02 полное множество declared relations; CR-03 точные Markdown links через повторный Support Catalog Adapter; CR-04 structural replay при activation вместо одного reseal.
- 18 новых CR regression methods. Проверка code head: **360 backend tests OK (11 skips), 5 project checks PASS**, [push CI #42892414054](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42892414054), [PR CI #42892426380](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42892426380). Exact final PR head/checks сверять в PR после документационной синхронизации.
- **Контрактное ограничение для сессии A:** в `SiteContentPackage` отсутствуют байты `astro.config.mjs`, поэтому verified canonical route да, независимое доказательство единого production host — нет. Это не обходится фиктивной проверкой. Отдельное архитектурное решение о config-provenance — только вне scope 4A.
- [Consolidated stage report](stages/2026-11-10-unified-knowledge-snapshot.md). Никаких изменений 3 адаптеров, canonical contracts, ADR, legacy, `Saturn-Main-Site`. **MERGE только по разрешению владельца, 4B не начинать.**

## Актуальный этап 4A — Unified Knowledge Snapshot v0.1 (2026-11-10)

- **PR #24 MERGED** в main: `01cb640e1b67ee84b4dff00afa6a798bc5203c54`.
- **PR #25 OPEN, NOT MERGED:** [Unified Knowledge Snapshot v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/25); ветка `feat/unified-knowledge-snapshot-v0.1` от указанного main.
- Реализованы независимые immutable contracts, validator трёх каналов, stable evidence/manifest, отдельные `answer_evidence` и `document_matches`, stage candidate и атомарный in-memory manager.
- `partial_text`, failed PDF и OCR-required не могут заменить активный snapshot. Unknown data сохраняются, неопределённые relations не создают dangling evidence.
- [Отчёт 4A](stages/2026-11-10-unified-knowledge-snapshot.md). Результаты exact-head CI — в PR #25; независимый Acceptance Review обязателен. Не выполнять merge. Этап 4B не начат. Saturn-Main-Site только READ-ONLY.
- Все устаревшие статусы OPEN для PR #24 в исторических разделах ниже относятся к времени до его merge.


## PR #24 — CR-01/CR-02 исправлены (2026-11-10)

Consolidated implementation head: `86c352adc3bfed4cbc80265812b77f6f5a6e07b5`. Subprocess stdout bounded во время обработки, stderr DEVNULL, shutdown/reap при отказе или timeout; returncode<0 → resource_limit до JSON parsing. Девять новых CR-01/CR-02 test methods (один прежний заменён), итого 328 backend tests OK (11 skips), 5 project tests PASS. [Push CI #42852633667](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42852633667) SUCCESS: offline-checks и onnx-contracts. Отдельный docs commit и его exact-head CI проверять по PR #24. **PR остаётся OPEN, NOT MERGED; требуется независимый Acceptance Review.** Production PDF OS isolation не реализована, Saturn-Main-Site READ-ONLY.


## Текущий этап 3B — External Document Adapter v0.1 (2026-11-10)

- PR #23 MERGED в main: dee6011fa67de0bcc62b8304b7549b4ebde396b1, main CI #42838702444 SUCCESS. Это текущий baseline.
- Рабочая ветка: feat/external-document-adapter-v0.1. [PR #24](https://github.com/UkWood/LLM-RAG-chat-bot/pull/24) OPEN, NOT MERGED. Проверенный code head 887108ea65feec91ddcd01631d742aaceb8c2b62; push CI #42847781478 / PR CI #42847795850 SUCCESS; 320 backend tests (11 skips), 5 project tests PASS, ONNX PASS. Код и offline-тесты 3B: secure HTTPS host/path + DNS pinning, bounded transport, отдельный PDF worker (только явный тестовый режим, production sandbox не подтверждена), SHA-256 revision/evidence, immutable associations/cache.
- Требуется полный exact-head CI и независимый Acceptance Review сессией A. **Не сливать PR и не начинать этап 4.** Статусы PR #23 OPEN ниже являются историческими.
- [Отчёт этапа 3B](stages/2026-11-10-external-document-adapter.md). Сайт Saturn-Main-Site READ-ONLY.



## Consolidated CR-01–CR-04 PR #23 — исправления и code CI (2026-11-10)

PR [#23](https://github.com/UkWood/LLM-RAG-chat-bot/pull/23) **OPEN, NOT MERGED**. Исправленная code revision `b2ee0164c49f53cba7121df92c6538e557b4b7e3`; implementation commit `60ca2856265e2d3a8f5276897892122a7c20a9e3`. [Push CI #42816240259](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42816240259) и [PR CI #42816246557](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42816246557): **SUCCESS**, 288 backend tests (11 skips), ONNX PASS. В том же PR исправлены Markdown/HTML links, URL traversal/identity, добавлены 8 exact read-only Saturn fixtures и универсальный session prompt. [Consolidated stage report](stages/2026-11-10-support-catalog-adapter.md). Последний PR head и его CI проверить после документационной синхронизации; merge и этап 3B запрещены до команды владельца.


## Актуальный handoff — этап 3A, 2026-11-10

- PR #22 **MERGED** в `main` коммитом `ff9baa8819714d5cb4ba9c61827dbf4666acd0b6`; main CI [#42777814511](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42777814511) SUCCESS.
- Текущая implementation branch: `feat/support-catalog-adapter-v0.1`, [PR #23](https://github.com/UkWood/LLM-RAG-chat-bot/pull/23), base exact merge commit выше. Этап: Support Catalog Adapter v0.1; до независимого Acceptance Review PR **не сливать**.
- Interface: `adapt_support_catalog(SiteContentPackage) -> SupportCatalogResult`; `documents`, `pdf_candidates`, `occurrences` (полная metadata/provenance всех вхождений), `issues`, `ready_for_promotion`.
- Support Catalog pure/offline, получает результат существующего site adapter; не делает fetch, PDF parsing, approvals или мутации source. Документы вне PDF остаются metadata-only; PDF candidates отделены от extracted evidence.
- См. [stage report](stages/2026-11-10-support-catalog-adapter.md); exact branch SHA и CI проверять после последних изменений.
- Весь следующий текст о PR #22 OPEN и ожидающемся ревью сохранён как **исторический checkpoint до merge**, а не текущий статус.


Дата: 2026-11-10  
Основной репозиторий: [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot)  
Текущий этап: GitHub Snapshot Provider v0.1 — [PR #22](https://github.com/UkWood/LLM-RAG-chat-bot/pull/22)
Статус PR #22: **OPEN, NOT MERGED**
Рабочая ветка: `feat/github-snapshot-provider-v0.1`
Base `main` для PR #22: `9b2e0882b81fa2737e7efebb109c079a39b392d8`
Original implementation code head: `ce501d2df5d120a3a437f6e32359a71e7d0543b6`  
Consolidated review corrective code head: `27b64b439b699bef396122c395cf091fb60735f0`  
**PR head после documentation/test sync проверять по GitHub, а не по сохранённому SHA.**

## 1. Текущий статус

**2026-11-10 — четыре независимых review замечания PR #22 устранены в существующей feature branch.** Статус — CHANGES IMPLEMENTED; повторное независимое Acceptance Review владельцем ещё не выполнено; merge не разрешён.

- №1 BLOCKER: исправлен non-recursive GitHub REST endpoint: без любого параметра `recursive`. Подтверждена реальная разница GitHub API: root tree без параметра = 16 записей; `recursive=0` и `recursive=1` = 1 119.
- №2 BLOCKER: скрывающие source directories symlink/gitlink теперь fail closed, включая вложенные `src/content/**` и `src/data/**`, `src/pages/**`; посторонние asset links не блокируют sync.
- №3 IMPORTANT: non-recursive fallback проходит только relevant source trees, без `public/**`, архивов и assets. Новые Markdown collections, YAML dictionaries и Astro routes динамически обнаруживаются.
- №4 MINOR: `ref` API response должен точно равняться `refs/heads/main`, иначе `TreeValidationError`.
- RED test-only commit `491f14fe`: 12 failure outcomes (254 tests, 11 skipped), [CI #42774670369](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42774670369).
- GREEN corrective code commit `27b64b43`: 254 tests, 11 skipped, push CI [#42774964424](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42774964424) SUCCESS, ONNX contracts SUCCESS. Отдельно усилена проверка large-asset mock и nested fallback symlink; CI финального head нужно подтвердить.
- Provider regression suite: **42 tests** (33 original + 9 new).
- Реальный live provider smoke test не проводился; GitHub API semantics проверялись отдельно read-only. Источник `Saturn-Main-Site` не изменён. Код canonical contracts/adapter/ADR не изменён.
- [Подробный отчёт ревью и команды проверки](stages/2026-11-09-github-snapshot-provider.md).


- PR #20 — Saturn Site Content Adapter — **MERGED**.
- PR #21 — Snapshot Provider Contract / ADR-0014 — **MERGED**. Merge commit в main: `9b2e0882b81fa2737e7efebb109c079a39b392d8`.
- Main CI после merge PR #21: [run #42688738332](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42688738332) — SUCCESS.
- PR #22 реализует первый GitHub Snapshot Provider за утверждённой provider-neutral границей. PR открыт, не слит.
- Implementation code head `ce501d2d` прошёл push CI [#42696950473](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42696950473) и PR CI [#42696961675](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42696961675): оба `offline-checks` и `onnx-contracts` завершились SUCCESS.
- Offline suite на implementation code head: **245 backend tests passed, 11 existing optional skips**; project checks — PASS; ONNX contracts — PASS.
- Добавлены provider-neutral `SnapshotProvider` Protocol и `GitHubSnapshotProvider`; canonical contracts, Saturn Site Content Adapter и schema evolution не изменялись.
- Provider разрешает `refs/heads/main` ровно один раз, pin-ит commit/tree и дальше использует только immutable object IDs.
- GitHub recursive tree fallback реализован через полный non-recursive обход от pinned root tree SHA; truncated non-recursive subtree завершает sync ошибкой.
- Файловая политика соответствует Snapshot Provider Contract: Markdown, YAML, обязательные schema/config, `.astro`/`.ts` routes (кроме `.d.ts`) и утверждённые optional route dependencies.
- Каждый выбранный blob декодируется из base64, сверяется по declared size и canonical Git blob SHA-1; raw bytes сохраняются без преобразований, raw SHA-256 передаётся существующему adapter provenance.
- GitHub API metadata не возвращает `object_format`; требуется явная trusted configuration `SATURN_GITHUB_OBJECT_FORMAT=sha1`, а каждый blob дополнительно проверяется по SHA-1. Другие форматы fail closed.
- Runtime token задаётся через `SATURN_GITHUB_TOKEN`; необходим credential только с read-only Contents access. Секреты в репозитории не добавлялись.
- Read-only metadata audit `Saturn-Main-Site@main` на commit `084d759487bfab6e111549c9b5469711ac5fc13e`: 1,119 tree entries, 477 выбранных файлов, 2,233,425 bytes; максимальный выбранный файл 32,186 bytes; `src/pages/` — 23 файла (19 `.astro`, 4 `.ts`), route drift не обнаружен.
- Этот аудит читал только Git tree metadata. Live smoke test самого provider не запускался; production runtime/scheduling integration не входит в этап.
- `UkWood/Saturn-Main-Site` остаётся строго READ-ONLY.

## 2. Решения владельца — обязательны

- Stable trusted logical source ID: `UkWood/Saturn-Main-Site`, branch `main`. Snapshot Providers отображают свои физические GitHub/Gitea remotes и namespace на этот ID; адрес провайдера не входит в контракт адаптера.
- Snapshot Provider использует Git REST API: GitHub — первая реализация, Gitea — последующая реализация того же provider-neutral контракта.
- Gitea tree pagination and commit-SHA/tree-SHA behavior must pass version-specific conformance tests; unsupported behavior fails closed. src/pages route-source allowlist is `.astro` and `.ts`, other types create drift diagnostics.
- Gitea provider обязан обрабатывать `page`/`per_page` и сверять все страницы по `page`, tree `sha`, `total_count` и уникальности entries. Документация Gitea описывает входной `sha` как commit SHA, а текущий upstream код принимает commit или tree ID; прямой tree-SHA lookup проверяется на точной версии целевого сервера. При несовместимости — recursive pagination по закреплённому commit SHA, иначе явная ошибка.
- `refs/heads/main` разрешается один раз на sync. После pinning все операции выполняются только по immutable commit/tree/blob IDs; повторной проверки подвижной ветки в той же sync нет.
- Git provider является trust source для ref → commit → tree identity mapping и полноты tree enumeration. Независимая криптографическая проверка raw commit/tree objects не заявляется.
- Каждый выбранный blob проверяется по canonical Git object hash с учётом object format репозитория; raw content SHA-256 хранится отдельно. Текущие canonical contracts поддерживают SHA-1; другой формат требует отдельной versioned эволюции contracts/adapter.
- Snapshot ограничен Markdown collections, YAML dictionaries, content schema, Astro routes и утверждёнными route/config dependencies; unrelated binary assets не скачиваются массово. Для `src/pages/` поддерживаются только `.astro` и `.ts` (не `.d.ts`); неизвестное расширение вызывает route-source drift и fail-closed. Read-only baseline Saturn-Main-Site на commit `084d759487bfab6e111549c9b5469711ac5fc13e`: 23 файла, 19 `.astro`, 4 `.ts`.
- PDF остаются обязательной частью knowledge corpus: discovery/cataloguing — Support Catalog Adapter, fetch/extraction — External Document Adapter. Будущий selective Git-blob retrieval допускается по pinned commit/path/blob SHA, но сейчас не реализуется.
- Все non-draft записи сайта, объявленные сайтом связи, справочники и прямые PDF-ссылки из documents/certificates или Markdown body доверенные. Ручная проверка/approval не нужна.
- `draft: true` исключается из публичного corpus.
- Сайт строго READ-ONLY: не менять его файлы, ветки, URL, assets, CI или поиск.
- Изменения сайта автоматически синхронизируются; commit/hash нужны для воспроизводимости и citations, а не approval.
- Новые поля/collections сохраняются как generic evidence; несовместимые типы не интерпретируются старым mapping, а дают drift report.
- PDF обрабатываются автоматически по доверенным ссылкам, но только с технической HTTPS host/path allowlist, SSRF/redirect и resource-limit защитой.
- Cloud data egress к внешней LLM — отдельное решение; source trust его не разрешает.
- ChatGPT — основная среда проектирования, реализации и review. Codex — только для ограниченных рутинных coding tasks по точному brief.

## 3. Реализовано в PR #20 и включено в main

Новый модуль: `backend/src/saturn_ai/ingestion/saturn_site_adapter.py`.

- Принимает immutable `PinnedSiteSnapshot`: trust root, branch, commit SHA, tree SHA и отсортированные файлы с Git blob SHA + исходными bytes. Blob SHA проверяется по точным байтам.
- `PinnedSiteSnapshot.repository` — стабильный logical source ID (`UkWood/Saturn-Main-Site`), а не физический Git remote URL.
- Динамически обнаруживает Markdown collections под `src/content/<collection>/`; словари `src/data/*.yaml|yml` и `src/content.config.ts` включаются в manifest/fingerprints.
- `src/content.config.ts` только fingerprint-ится — Astro/TypeScript/JS не исполняются.
- Safe YAML: YAML 1.2 boolean semantics, запрет anchors/aliases/explicit tags, duplicate keys и non-string keys; ограничены размер, token count, depth и node count.
- Raw bytes, raw frontmatter text и Markdown body сохраняются. Неизвестные поля и вложенные значения становятся raw facts; неизвестные collections — `SiteContent`.
- Явные relations берутся только из проверенной схемы. `pages.groups` остаётся navigation data, а не инженерной связью.
- Для `systems.kind` при отсутствии поля применяется только объявленный в source schema default `system`; явное неизвестное значение остаётся generic `SiteContent` с warning. Для `pages.kind` отсутствие значения означает `Page`, известные `solution`/`section` отображаются явно, неизвестное значение остаётся generic `SiteContent`.
- Используются PR #18 contracts: source revisions, schema inventory, dictionary fingerprints, deterministic sync manifest и file/schema diff.
- Ошибка записи диагностируется отдельно. Raw bytes остаются в package; package с error issues не допускается к promotion.

### Review corrections, вошедшие в merge

- Canonical URLs строятся по реальным Astro routes и production `SITE_URL` fallback из `astro.config.mjs`; GitHub Pages preview values и provider URLs исключены.
- Проверенные маршруты: products, systems, groups, articles, news, pages и `pages/home` → `/`. Вложенные slugs без соответствующего catch-all route не получают предположительный URL.
- `src/pages/**`, `astro.config.mjs`, `src/content.config.ts`, `src/lib/url.ts`, `src/lib/nav.ts`, `src/lib/service.ts`, `src/data/nav.yaml` и `src/data/industries.yaml` включены в source revisions/manifest. Добавление, изменение и удаление route/config files отражается в drift report.
- `SiteSyncManifest.parser_version` участвует в snapshot identity; смена версии вызывает parser-version drift. Старые manifests и builder calls поддерживаются через явный unversioned marker.
- `SiteSourceRevision` сохраняет семантику raw source provenance; версия site parser находится в processing manifest согласно ADR-0013.

Тесты: `backend/tests/unit/test_saturn_site_adapter.py`; fixtures: `backend/tests/fixtures/saturn_site/`.

## 4. Граница с прежним ingestion

Существующие `site.py`, `registry.py`, `pipeline.py`, `contracts.py` обслуживают прежний synthetic/fixture ingestion path. В нём есть фиксированные collections и per-source approval contracts.

**Не удалять и не ослаблять эти approval gates глобально. Не подключать доверенный Saturn main через старый SourceRecord/Registry.** Новая Saturn-интеграция идёт отдельным путём на основе `saturn_contracts.py` и собственных adapter contracts. Существующие synthetic tests и historical evaluation должны продолжать работать без регрессий.

## 5. GitHub Snapshot Provider v0.1 — реализация в PR #22

PR #22: [feat: implement GitHub Snapshot Provider v0.1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/22) — **OPEN, not merged**.

Новые файлы:
- `backend/src/saturn_ai/ingestion/snapshot_provider.py` — provider-neutral `SnapshotProvider` Protocol.
- `backend/src/saturn_ai/ingestion/github_snapshot_provider.py` — GitHub REST implementation.
- `backend/tests/unit/test_github_snapshot_provider.py` — 42 offline tests после review corrections.

Реализовано:
- Фиксированный physical repository `UkWood/Saturn-Main-Site`, API origin `https://api.github.com`, logical source ID остаётся `UkWood/Saturn-Main-Site`.
- `refs/heads/main` разрешается один раз. Проверяются ref → commit → root tree identities; повторного чтения moving branch нет.
- Recursive tree; при `truncated=true` частичный ответ полностью отбрасывается и выполняется non-recursive traversal от pinned root tree SHA через child tree SHAs.
- Проверяются tree response SHA, path hierarchy, duplicate paths, object type/mode, SHA format, depth, declared sizes и полнота обхода.
- `src/pages/**`: все регулярные файлы должны иметь lowercase `.astro` или `.ts`, `.d.ts` исключён и диагностируется; неизвестные расширения вызывают `RouteSourceDriftError` и fail closed.
- Выбор файлов соответствует утверждённой таблице контракта: Markdown `.md`, YAML `.yaml`/`.yml`, обязательные `src/content.config.ts` и `astro.config.mjs`, optional `src/lib/url.ts`, `nav.ts`, `service.ts`.
- Каждый выбранный blob получается по immutable blob SHA, декодируется из base64, проверяется по API/tree size и canonical Git blob SHA-1. Raw bytes передаются в `SnapshotFile` без текстовых преобразований; raw SHA-256 остаётся отдельным content digest.
- Результат — существующий immutable `PinnedSiteSnapshot`, принимаемый существующим `adapt_snapshot()` без изменений адаптера.
- HTTPS с default TLS certificate verification; redirect не следует; API origin/repository фиксированы; credentials передаются только в Authorization header; retry/timeouts/request count/tree/file/snapshot limits bounded.
- Ошибка любого обязательного blob или subtree не возвращает частичный snapshot.

Конфигурация runtime:
```text
SATURN_GITHUB_TOKEN=<read-only GitHub token with Contents: read>
SATURN_GITHUB_OBJECT_FORMAT=sha1
```

GitHub repository metadata не предоставило `object_format`, поэтому алгоритм задаётся явно trusted environment configuration и подтверждается пересчётом каждого выбранного blob. Текущие canonical contracts остаются SHA-1-only.

Не менялись: `saturn_contracts.py`, `saturn_site_adapter.py`, `schema_evolution.py`, ADR-0012/0013/0014 и canonical contracts. Новые зависимости отсутствуют.

Live provider smoke test не выполнялся: offline tests используют mock HTTP transport. Read-only tree metadata audit текущего сайта подтверждает, что все 477 выбранных файлов укладываются в текущие ресурсные limits. Runtime wiring, scheduling и production credentials не добавлялись.

Вне scope: Gitea Provider, Support Catalog Adapter, PDF download/parser, Git-backed PDF retrieval, embeddings/reranking, LLM/provider, API/UI, deployment и production scheduling.

## 6. Результаты предыдущих этапов — PR #20 и PR #21

- PR #20: **MERGED**.
- Кодовый head: `9b36551adf61070426caa9250650bb32d638a66a`.
- Merge commit: `361529963bd48772f0d9d478dfb3b963ec5a8d03`.
- PR-head GitHub Actions [run #232](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569426503): SUCCESS.
- Push GitHub Actions [run #231](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569421610): SUCCESS.
- Offline verification: 212 tests passed, 11 existing optional skips; ONNX contracts PASS.
- Synthetic baseline preflight: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 0.85. Это прежняя non-blocking synthetic baseline, не оценка качества адаптера.
- Saturn-Main-Site проверен read-only на commit `084d759487bfab6e111549c9b5469711ac5fc13`; изменений в нём не было.
- ADR-0012 и ADR-0013 не изменялись.
- PR #21 был documentation-only: reviewed architecture/contract head `0f2a1226b757ae346d65b05df13be657e3581d35`; PR-head CI [#42624653260](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624653260) и push CI [#42624644980](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624644980) — SUCCESS.
- PR #21 впоследствии слит в main merge commit `9b2e0882b81fa2737e7efebb109c079a39b392d8`; main CI после merge [#42688738332](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42688738332) — SUCCESS.
- Историческая запись о том, что PR #21 был OPEN, относится к моменту первоначального review; актуальный статус — MERGED.

## 7. Разделение сессий и порядок работы

Архитектурные решения, ADR и изменение scope согласуются в отдельной сессии «Saturn AI — Архитектура и управление». Coding session реализует только bounded задачу из owner-approved brief.

При продолжении:
1. Сначала проверить актуальные `main`, PR #22 head, changed files и CI; не полагаться на сохранённый SHA как на текущий PR head.
2. Считать PR #20 и PR #21 завершёнными и слитыми; не возвращаться к их реализации/review.
3. Продолжать работу только в существующем PR #22 и только в рамках его scope/консолидированного review. Не создавать дублирующую feature branch.
4. Передавать все замечания одним списком с severity, точным местом и критерием исправления; после исправлений повторно проверять весь список целиком.
5. Не менять canonical contracts, Saturn Site Content Adapter, ADR-0012/0013/0014 или исходный Saturn site без отдельного архитектурного решения.
6. PR #22 не сливать без отдельной явной команды владельца.
7. Не начинать Gitea, PDF ingestion, retrieval integration, LLM/API/UI или deployment автоматически после PR #22; для каждого следующего этапа требуется отдельное задание.