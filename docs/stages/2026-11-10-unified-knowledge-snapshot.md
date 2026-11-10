# Этап 4A — Unified Knowledge Snapshot v0.1

Дата: 2026-11-10
Репозиторий: UkWood/LLM-RAG-chat-bot
Baseline main: 01cb640e1b67ee84b4dff00afa6a798bc5203c54 (PR #24 merged)
Ветка: feat/unified-knowledge-snapshot-v0.1
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/25
Статус: реализация для независимого Acceptance Review; merge запрещён.

## Consolidated Acceptance Review Corrections — PR #25 (CR-01–CR-04)

**Корректирующий code head:** `812f5156d5613b90b39dfd5f1a25454795d434dc`.
Один консолидированный цикл исправлений в прежней ветке и PR #25. После исправления собственных тестовых предположений и сохранения legacy diagnostic code выполнено `python scripts/verify_offline.py`: **360 backend tests OK (11 existing optional skips), 5 project checks PASS**, все 18 новых тестовых методов CR-01–CR-04 проходят. Существующие 342 теста не регрессировали.
Проверки code head: [push Actions #42892414054](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42892414054) и [PR Actions #42892426380](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42892426380). На проверенном code head `onnx-contracts` SUCCESS, push `offline-checks` SUCCESS; exact status обоих запусков и итогового документационного PR head фиксируется в [PR #25](https://github.com/UkWood/LLM-RAG-chat-bot/pull/25). **Не заменять проверку финального PR head прежним code-head CI.**

### CR-01 — Source-derived projection integrity

Строгое повторное offline-чтение `RawSiteRecord.content` через уже утверждённые `_split_markdown` / `_load_yaml`; сравнение с `raw_frontmatter_text`, `body`, `draft`, collection/slug. Независимо восстанавливаются `SiteEntity.raw_frontmatter_json`, title, type и route-based canonical path по source mapping; `SiteFact` полностью сравнивается с `_facts_for_entity` (включая unit, normalized value и qualifiers). YAML dictionaries повторно парсятся из тех же bytes и сравниваются с обоими raw представлениями. Хэши Git blob и content SHA-256 проверяются независимо от supplied projections. Несоответствие — fail closed. Нет выполнения Astro/TypeScript, сети или новых canonical IDs.

Негативные тесты: title, entity_type, canonical path/individual host, синхронная подмена frontmatter + facts, unit, normalized/qualifiers, dictionary raw JSON и изменение raw body/frontmatter/draft без изменения исходных байтов.

**Существенная граница доказуемости:** `SiteContentPackage` хранит Git SHA `astro.config.mjs`, но **не сами байты** production `SITE_URL` fallback. Поэтому 4A доказывает канонический маршрут, однородность origin разных записей и исходное происхождение иных значений, но **не может независимо доказать абсолютный host всех URL, если все они одновременно согласованно подменены**. Это не объявляется успешной верификацией отсутствующих config bytes. Сессии A предлагается отдельно решить, нужен ли в будущем versioned read-only config-provenance contract (или доказуемый trusted origin); текущие ADR и Site Adapter не меняются.

### CR-02 — Complete source-declared relations

Ожидаемое множество `SiteRelation` независимо восстанавливается через существующую `_relation_candidates` из **проверенного** YAML frontmatter, с точными predicate, array index/field path, immutable revision и stable ID. Draft targets исключаются по исходному `draft`, отсутствующие non-draft targets сохраняются в `unresolved_relations` с предупреждением. Пропущенные, добавленные, изменённые, повторные relations блокируют сборку. Сохранён ранее ожидаемый код `relation_source_mismatch`, добавлены более точные `relation_projection_coverage_mismatch` / `relation_projection_mismatch`. Engineering inference не добавлялся.

### CR-03 — Exact Markdown PDF link provenance

`adapt_support_catalog(site)` повторно вызывается **offline** на source-verified site package; результат целиком сравнивается с присланными `documents`, `pdf_candidates`, `occurrences`, `issues` и readiness. Используется единственный уже проверенный scanner Support Catalog Adapter для inline/reference/autolink/HTML и защиты от code/comments. Подмена `raw_url`, `resolved_url`, origin owner, source field/line/column, occurrence ordinal, document ID, PDF candidate owner/URL/locator отклоняется даже при согласованной подмене нескольких catalog fields.

### CR-04 — Validated atomic activation

`SaturnKnowledgeSnapshot` сохраняет immutable `SnapshotValidationSources` (исходные три adapter result objects) **только как структурное основание для повторной проверки**; сравнение snapshot-корпуса остаётся независимым от порядка входных коллекций, прежняя stable-ID scheme сохранена. `SaturnSnapshotManager.activate()` перед установкой active заново выполняет полный offline builder/validator, сравнивает candidate включая counts, evidence/pointers, source and PDF revisions и readiness. Корректный `corpus_hash` и пересчитанный `snapshot_id` без совпадающей повторной структурной проверки уже недостаточны. При отказе active pointer не изменяется; pointer swap/capture остаётся атомарным под `RLock`.

Негативные тесты: re-sealed изменённые manifest counts; удалённый evidence при оставшемся pointer; nonexistent canonical pointer; подмена PDF revision/page evidence; forged readiness gates; подмена validation sources. Положительные: первая и повторная activation; existing concurrent capture/activation; отказ не заменяет ранее опубликованный snapshot.

### Изменённые файлы и тесты

Код: `backend/src/saturn_ai/saturn_knowledge_validation.py`, `saturn_knowledge_contracts.py`, `saturn_knowledge_snapshot.py`. Добавлен `backend/tests/unit/test_saturn_knowledge_acceptance_cr.py` (18 методов; внутри — несколько adversarial subcases). Существующий `test_saturn_knowledge_snapshot.py` и ранее принятые adapters/canonical contracts/ADR/legacy path не менялись. В `Saturn-Main-Site` изменений нет.

Ограничения прежние: stage 4A — только offline assembly/activation; production PDF sandbox, индексирование/retrieval/LLM/UI/deployment и проверка provenance реального Git commit и PDF bytes остаются на своих upstream/runtime границах. Сохранение входных immutable witness увеличивает memory footprint и стоимость повторной проверки при activation; performance benchmark не заявляется. **PR остаётся OPEN; независимый повторный Acceptance Review сессии A обязателен; merge и этап 4B запрещены.**

## 1. Новые модули

- backend/src/saturn_ai/saturn_knowledge_contracts.py — immutable groups, content identity/seal, thread-safe in-memory pointer.
- backend/src/saturn_ai/saturn_knowledge_validation.py — независимая строгая проверка трёх входных результатов.
- backend/src/saturn_ai/saturn_knowledge_snapshot.py — pure/offline assembly, канонические поисковые projections и stage/strict API.
- backend/tests/unit/test_saturn_knowledge_snapshot.py — offline unit/contract/integration regression.

Не изменены canonical saturn_contracts, три адаптера, GitHub Provider, legacy synthetic snapshots.py, ADR и исходный Saturn-Main-Site.

## 2. Public API и immutable модель

Строгий:
`build_saturn_knowledge_snapshot(site, catalog, external) -> SaturnKnowledgeSnapshot`.

Диагностический:
`stage_saturn_knowledge_snapshot(site, catalog, external) -> SaturnSnapshotBuildResult`.
Непригодный структурно кандидат возвращается как `candidate=None` с кодами `SnapshotIssue`. Полный по структуре, но не готовый к активации PDF result сохраняет корректные metadata, подтверждённые passages и diagnostics в candidate, однако `ready_for_promotion=False`. Строгий API выбрасывает `SnapshotBuildError`.

`SaturnSnapshotManager.activate(candidate)` / `capture()` — независимый in-memory thread-safe pointer swap. Нет active до первой активации — `LookupError`; отказ оставляет прежний active без изменений.

Данные разделены на source_revisions, entities, facts, relations, unresolved_relations, dictionaries, support_documents, document_occurrences, document_associations, pdf_revisions, pdf_statuses, pdf_diagnostics, answer_evidence, evidence_pointers и document_matches. Frozen dataclasses/tuple/bytes исключают изменяемый corpus. Оригинальные frontmatter/body, raw facts/qualifiers, dictionary bytes/raw YAML/JSON и original/normalized поля сохраняются в canonical objects.

## 3. Evidence и provenance

- `site_field`: labelled projection raw JSON, normalized value, unit, qualifiers, exact field path; EvidencePointer → SiteFact. Document/certificate fields сохраняются в canonical facts, но не выдаются как техническое answer evidence.
- `relation`: только source-declared predicate, source field path и revision, без inference или усиления отношений. Relations к отсутствующим/draft targets представлены отдельно в unresolved_relations и warning; dangling answer evidence исключается.
- `site_passage`: точные slices исходного Markdown с physical line/column/ATX heading, limit 2400 символов, stable ID по revision/locator/content; длинные строки режутся по колонкам. Нет CommonMark render, HTML очистки, NLP extraction, семантического объединения таблиц, автоматического разрешения Markdown links. Кодовые fences исключены из распознавания headings.
- `pdf_passage`: только оригинальный ExternalDocumentResult.evidence после валидации физической страницы, bytes hash/parser version, page map и извлечённого text SHA. Нет повторного PDF extraction и изобретённого текста.
- `document_matches`: отдельные SupportDocument + original CatalogOccurrence + status/revision id. Это **metadata lookup**, а не подтверждение содержимого PDF.

## 4. Межканальная валидация / readiness

Проверяются trust root, pinned commit, sync manifest/source file inventory, source revision/blob/content hash для доступных raw records/dictionaries, entity identity/body/frontmatter, полнота facts, relation identity и dangling projections, schema/dictionary fingerprints, document URL/ID/owner/locator/conflicts, PDF candidate coverage, all statuses/associations, parser/bytes revisions, cache page map/text hash, exact PDF EvidenceUnit, diagnostics и readiness agreement.

Проверка не полагается на один `ready_for_promotion` upstream. Ошибки имеют код `SnapshotIssue` и блокируют построение пригодного immutable snapshot. Политика 3B не меняется: `partial_text`, `ocr_required`, failed fetch и parser error сохраняются диагностически, но препятствуют активации. Дополнительного ручного approval нет.

## 5. Manifest, identity, reconciliation

Manifest включает source site manifest (repo/branch/commit/tree; parser/adapter/mapping; inventory/fingerprints), версии catalog/PDF parser/builder, canonical revision IDs, PDF revision/status/hashes, counts по группам и evidence types. Корпус идентифицируется canonical JSON + stable_id; input collections сортируются детерминированно перед сборкой; timestamps и random nonce отсутствуют.

Изменения source commit/content, документов/owners/occurrences, relations, PDF bytes, parser, statuses, evidence и diagnostics меняют snapshot identity. Удалённые записи не переносятся из старого активного snapshot. Перед activation проверяются content seal, snapshot identity и полная повторная структурная сборка из immutable validation sources; pointer swap выполняется под RLock. Атомарная публикация BM25/vector индексов — отдельный этап 4B.

## 6. Offline тесты

Source inventory проверяет точную полноту исходных `src/content/*.md` records
и YAML dictionaries `src/data/*.{yaml,yml}`; лишние либо отсутствующие
records блокируют сборку. Upstream Site/Support Adapter issues сохраняются
в диагностике staged candidate с исходными code, path и severity.


Файл `backend/tests/unit/test_saturn_knowledge_snapshot.py` проверяет immutable contracts, canonical linkage, metadata isolation, unknown fields/collections, словари, headings/physical locators, determinism при перестановке входов, content/revision/owner changes, fail-closed variants PDF, corrupted fields/associations/evidence/revisions/cache, previous-active retention и concurrent capture.

End-to-end integration использует 8 **source-derived**, не изменённых Saturn files из `backend/tests/fixtures/saturn_support_real/`; PDF bytes генерируются локально, HTTP и extraction заменены mock; реальные PDF и исходный сайт не скачиваются.

Обязательные проверки: `python scripts/verify_offline.py`, targeted unit tests, exact-head `offline-checks` и `onnx-contracts`. Проверенный implementation head `f6552de83bddf937b848526c0594fb3b403dc923`: 5 project tests PASS, 341 backend tests OK (11 existing optional skips); ONNX contracts SUCCESS; lexical synthetic baseline без изменений. Дополнительные tests source-inventory/upstream diagnostics включены в финальный commit. Его exact-head CI и финальная итоговая сводка — в PR #25; зелёный предыдущий head не подменяет финальную проверку.

## 7. Ограничения и следующий шаг

Нет query/search/retrieval, embeddings, reranker, LLM, OCR, web fetch, scheduler, DB, deploy или production PDF worker. Это snapshot-слой, не принятие качества инженерных ответов. Внешний Saturn-Main-Site READ-ONLY. После независимого review и отдельного разрешения владельца на merge можно ставить этап 4B Channel-Aware Retrieval.
