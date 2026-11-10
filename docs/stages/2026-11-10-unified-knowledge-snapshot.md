# Этап 4A — Unified Knowledge Snapshot v0.1

Дата: 2026-11-10
Репозиторий: UkWood/LLM-RAG-chat-bot
Baseline main: 01cb640e1b67ee84b4dff00afa6a798bc5203c54 (PR #24 merged)
Ветка: feat/unified-knowledge-snapshot-v0.1
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/25
Статус: реализация для независимого Acceptance Review; merge запрещён.

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

Изменения source commit/content, документов/owners/occurrences, relations, PDF bytes, parser, statuses, evidence и diagnostics меняют snapshot identity. Удалённые записи не переносятся из старого активного snapshot. Перед activation проверяется content seal и snapshot identity; pointer swap выполняется под RLock. Атомарная публикация BM25/vector индексов — отдельный этап 4B.

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
