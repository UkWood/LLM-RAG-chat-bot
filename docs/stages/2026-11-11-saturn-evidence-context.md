# Stage 5A — Saturn Evidence Context & Snapshot Binding v0.1

Дата: 2026-11-11  
Проект: AI Technical Consultant — МНПП «Сатурн»  
Baseline main: `340e7d63e6899d855a01547003d1d983e9078eda` (PR #26 merged)  
Ветка: `feat/saturn-evidence-context-v0.1`  
PR: Stage 5A feature PR (ссылка и final head — в описании PR после публикации).  
Статус: implementation candidate; **independent Acceptance Review обязателен, NO MERGE**.

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

Код: `backend/src/saturn_ai/grounding/saturn_contracts.py`, `grounding/saturn_context.py`, минимальное расширение `retrieval/saturn_channel.py`. Новый offline test: `backend/tests/unit/test_saturn_evidence_context.py`; существующие 4A/4B contracts, source adapters, Qdrant API, ADR и legacy synthetic grounding не менялись.

Покрытие: fields/numeric literals, relations, site/pdf passages, multi-owner PDF, metadata-only, empty, determinism, lexical-only, policy revocation/recheck, forged candidates/bundle/manifest, context ownership, budgets, concurrent publication, Qdrant reader lease, exception release, Stage 4B compatibility.

**Фактические команды, числа tests/skips, push/PR CI results и exact final PR head должны фиксироваться в описании PR по окончании checks.** CI PASS не заменяет independent Acceptance Review.

## 5. Известные границы

Stage 5A не решает sufficiency, relevance, factual conflicts, answer generation, claim verification и final citations. Policy check является моментальным; 5B–5D обязаны повторять `recheck_policy` перед дальнейшим использованием. Guarantee immutable model — в одном процессе против обычного Python assignment, не security sandbox против `object.__setattr__` или компрометированного процесса. Нет production Qdrant, embeddings, remote inference, persistent session restore или реальной semantic quality. Ограничение 4A об отсутствии raw `astro.config.mjs` production origin witness сохраняется.

`UkWood/Saturn-Main-Site`: **READ-ONLY, никаких изменений**. Merge только по отдельному явному распоряжению владельца.
