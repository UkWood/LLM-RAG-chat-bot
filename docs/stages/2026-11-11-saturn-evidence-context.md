# Stage 5A — Saturn Evidence Context & Snapshot Binding v0.1

Дата: 2026-11-11  
Проект: AI Technical Consultant — МНПП «Сатурн»  
Baseline main: `340e7d63e6899d855a01547003d1d983e9078eda` (PR #26 merged)  
Ветка: `feat/saturn-evidence-context-v0.1`  
PR: [#27](https://github.com/UkWood/LLM-RAG-chat-bot/pull/27) (exact final head и CI — в PR).  
Статус: implementation candidate; **independent Acceptance Review обязателен, NO MERGE**.

## Consolidated Acceptance Review Corrections — PR #27 (CR-01 / CR-02)

**Исходный review head:** `c95cef4aebfbdef512e4cb54d0b14585d089deb1`.  
**PR:** [#27](https://github.com/UkWood/LLM-RAG-chat-bot/pull/27), та же feature branch; статус независимого review: **CHANGES REQUESTED**, исправления выполнены в рамках того же Stage 5A. Merge запрещён до отдельного распоряжения владельца.

### CR-01 BLOCKER — immutable session ownership / lease

- Прямой вызов `SaturnAnswerSession(service, bundle)` отвергается до побочных эффектов. `SaturnRetrievalService.open_answer_session()` использует внутреннюю `SaturnAnswerSession._from_service()`: получение bundle и `dense._retain()` происходят под единым publication `RLock`; ошибка создания освобождает полученный lease.
- Привязки `_service`, `_bundle`, `_lock`, `_closed`, `_issued` защищены от обычного `setattr`. Законные lifecycle mutations выполняются только контролируемым `object.__setattr__` внутри session-методов.
- `_issued` — immutable tuple пар `(context, fingerprint)`, пополняемый строго при выдаче контекста; `.append()`/`.clear()`/подмена fingerprint снаружи невозможны обычными операциями. Предел `MAX_SESSION_CONTEXTS`, ownership by identity и fingerprint сохранены.
- `close()` idempotent, синхронизирован с активным `build_context()` и освобождает Qdrant lease последним удерживающим reader. Публикация нового bundle не изменяет pinned snapshot; legacy `search_saturn()` API не меняется.

### CR-02 IMPORTANT — fail-closed classification boundaries

- Валидация `question` проверяет UTF-8 encodability **до** tokenization/hash; unpaired surrogate → `invalid_request`, обычный русский и инженерный Unicode сохраняются.
- `recheck_policy()` вычисляет fingerprint и hash внутри проверяемой границы; повреждённые nested dataclass fields и ошибка сериализации → `context_identity_mismatch` без утечки raw exception.
- `_search_captured()` выделяет ошибку **только** при захвате policy через `SaturnPolicyCaptureError(RuntimeError)`. Stage 5A переводит её в `policy_unavailable`; любой обычный `Exception` внутри retrieval/index → `retrieval_unavailable`. Содержание `RuntimeError`, даже включающее слово `policy`, не используется для классификации.
- Canonical materialization unexpected `Exception` → `evidence_integrity_failure`; policy provider outside retrieval → `policy_unavailable`. Ошибки безопасно диагностируются по `reason_code`; исходные исключения не включаются в публичный текст/traceback chaining. `KeyboardInterrupt`/`SystemExit` не подавляются.

### Regression coverage

В `test_saturn_evidence_context.py` добавлены **T-01–T-15**: immutable bindings, direct constructor/lease balance, issued registry integrity/cap, настоящие `Thread` + `Event` publication barriers, Qdrant deferred close, idempotent close, exception cleanup; invalid surrogate, valid RU/Unicode minus/decimal, corrupted nested context, unexpected `OSError`, provider failure within and outside retrieval, non-policy backend `RuntimeError`, legitimate empty result, сохранение существующих reason codes. Существующие Stage 4A/4B и legacy tests входят в полный offline suite.

**Верификация:** baseline на review head (предоставлен независимой сессией A): **431 backend tests OK (11 skips), 5 project tests PASS**, оба jobs SUCCESS для [push #42977748475](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42977748475) и [PR #42977756429](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42977756429). Это **исходные, не исправленные** проверки. Новый exact final PR head / фактические push+PR CI runs и числа проверок фиксируются в PR после завершения GitHub Actions.

Никаких изменений `UkWood/Saturn-Main-Site`, ingestion adapters, Qdrant implementation, canonical Saturn contracts, ADR-0012/0013, frozen datasets, legacy approval semantics или Stage 5B–5E.

## 1. Архитектура / граница

```text
SaturnRetrievalService (один authoritative _active bundle)
   | open_answer_session(): под publication RLock capture + dense._retain()
   v
SaturnAnswerSession (pinned immutable bundle, Qdrant reader lease, session RLock)
   | build_context(question, mode, top_k)
   |   4B _search_captured(pinned bundle) / current policy pre+post search
   |   canonical IDs, pointers, entity revisions/locators + PDF page/hash
   |   bounded immutable SaturnTypedEvidence + SaturnDocumentReference
   |   fresh operational policy capture, complete eligibility check
   v
SaturnEvidenceContext (question hash, snapshot_id, bundle_id, policy revision)
   | session.recheck_policy(context): issuing-session identity + fresh policy
   v
Later 5B–5D (NOT implemented; must repeat policy check before use)
```

Snapshot, lexical/metadata indexes, optional local Qdrant и manifest находятся в **одном** уже опубликованном `SaturnRetrievalBundle`. Вторая authoritative active ссылка не создаётся. Захват reader lease осуществляется внутри **того же** publication lock, что и `publish()`; retirement старого Qdrant ждёт закрытия последней session. Session закрывается через `with` / `close()`, повторный close безопасен, после close поиск и policy recheck запрещены. Session RLock предотвращает одновременное закрытие во время `build_context()`.

Существующий `search_saturn()` и его per-search lifetime не изменён.

## 2. Evidence contract и строгое происхождение

`SaturnTypedEvidence` использует *исходный* `EvidenceUnit.text`, а не заголовки, добавляемые в `SearchRecord.text`. Exact evidence ID разрешается в `answer_evidence`, `EvidencePointer` и SearchRecord закреплённого snapshot. Проверяются snapshot/bundle/index manifest, revision/entity/locator/URL и тип объекта.

- `site_field`: `SiteFact`, исходные `raw_value_json`, optional normalized/unit/qualifiers и точный `field_path`. Без unit conversion или изменения знака, десятичной записи и инженерных идентификаторов.
- `relation`: source-declared `SiteRelation`, исходный subject/predicate/object, `source_field_path`, без усиления смысла `related`.
- `site_passage`: точное воспроизведение исходного сегмента Markdown из `SiteEntity.body` с body line/column/heading locator, если присутствует.
- `pdf_passage`: исходная физическая страница, строгий PDF revision ID, bytes SHA-256, parser version, original URL, extracted state и source-backed owners/occurrences. Failed/metadata-only PDF не становится evidence.

`SaturnDocumentReference` представляет metadata отдельным immutable массивом. Title/kind/version/date/URL/owners/locators/occurrences/extraction status не используются в качестве технического факта.

## 3. Политика, budgets, ошибки

До возврата контекста выполняется актуальная `SaturnOperationalPolicy` проверка всех evidence и document references. Учитываются блокировки source revision, evidence ID, entity ID, document ID и PDF revision ID, включая source revisions PDF ссылок. При блокировке **отклоняется весь контекст**, без незаметного частичного ответа. `session.recheck_policy(context)` проверяет issuing-session identity и *текущую* policy. Только смена номера policy revision без блокировок допускается. Проверка не даёт бессрочного разрешения: следующие этапы повторяют её перед использованием.

Именованные limits: максимум 10 answer evidence, 10 document refs и 20 000 исходных символов; максимум 16 выданных context на одну session. Запрещено молчаливое усечение текста или qualifiers. Причины `SaturnContextError.reason_code`: `invalid_request`, `no_active_bundle`, `retrieval_unavailable`, `context_identity_mismatch`, `evidence_integrity_failure`, `policy_unavailable`, `policy_blocked`, `resource_budget_exceeded`, `session_closed`. Исключения не содержат question/PDF/credential URLs.

## 4. Изменения и проверка

### Проверенный промежуточный результат

После устранения дефекта test helper и добавления adversarial-проверок кодовый head `8ea58348dfca2ac5b1e4d6e29f71b7f85359263f` проверен GitHub Actions [push #42976766173](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42976766173): `offline-checks` **SUCCESS**, `onnx-contracts` **SUCCESS**. Offline verifier `python scripts/verify_offline.py`: **5 project tests OK; 429 backend tests OK (11 skips)** на CPU, без сети к сайту или реальной LLM. Это промежуточный head, **не** final PR head.

В дальнейшем добавлены полный in-session fingerprint выданного контекста (против reflective post-issuance mutation), классификация malformed retrieval candidates и дополнительные регрессионные тесты. Их результат не следует экстраполировать с предыдущего CI: exact final SHA, финальное количество тестов и два финальных GitHub Actions runs фиксируются в описании PR только после фактического завершения.


Код: `backend/src/saturn_ai/grounding/saturn_contracts.py`, `grounding/saturn_context.py`, минимальное расширение `retrieval/saturn_channel.py`. Новый offline test: `backend/tests/unit/test_saturn_evidence_context.py`; существующие 4A/4B contracts, source adapters, Qdrant API, ADR и legacy synthetic grounding не менялись.

Покрытие: fields/numeric literals, relations, site/pdf passages, multi-owner PDF, metadata-only, empty, determinism, lexical-only, policy revocation/recheck, forged candidates/bundle/manifest, context ownership, budgets, concurrent publication, Qdrant reader lease, exception release, Stage 4B compatibility.

**Полная финальная проверка и exact final PR head фиксируются в описании PR; промежуточный SUCCESS выше не заменяет проверку последнего commit.** CI PASS не заменяет independent Acceptance Review.

## 5. Известные границы

Stage 5A не решает sufficiency, relevance, factual conflicts, answer generation, claim verification и final citations. Policy check является моментальным; 5B–5D обязаны повторять `recheck_policy` перед дальнейшим использованием. Guarantee immutable model — в одном процессе против обычного Python assignment, не security sandbox против `object.__setattr__` или компрометированного процесса. Нет production Qdrant, embeddings, remote inference, persistent session restore или реальной semantic quality. Ограничение 4A об отсутствии raw `astro.config.mjs` production origin witness сохраняется.

`UkWood/Saturn-Main-Site`: **READ-ONLY, никаких изменений**. Merge только по отдельному явному распоряжению владельца.
