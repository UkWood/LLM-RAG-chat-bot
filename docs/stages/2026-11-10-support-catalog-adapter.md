# Этап 3A — Support Catalog Adapter v0.1

Дата: 2026-11-10  
Статус: **IMPLEMENTED, PR #23 OPEN — exact-head CI и независимый Acceptance Review обязательны до merge**  
Проект: `UkWood/LLM-RAG-chat-bot`  
Ветка: `feat/support-catalog-adapter-v0.1`  
Base `main`: `ff9baa8819714d5cb4ba9c61827dbf4666acd0b6` (merge PR #22, main CI #42777814511 SUCCESS).

## 1. Область реализации

Новый pure/offline модуль `backend/src/saturn_ai/ingestion/support_catalog_adapter.py` потребляет **только** канонический `SiteContentPackage`, сформированный `adapt_snapshot()`. Не меняются Canonical Contracts, Site Content Adapter, Schema Evolution, Snapshot Provider и ADR. Источник `UkWood/Saturn-Main-Site@084d759487bfab6e111549c9b5469711ac5fc13e` читался только через GitHub; commit HEAD проверен на дату этапа, без единого write.

Интерфейс: `adapt_support_catalog(package: SiteContentPackage) -> SupportCatalogResult`.

Результат:
- `documents: tuple[SupportDocument, ...]` — канонические документы по разрешённому HTTPS URL.
- `pdf_candidates: tuple[PdfCandidate, ...]` — PDF по case-insensitive **URL path**, без зависимости от `kind`.
- `occurrences: tuple[CatalogOccurrence, ...]` — полный source-specific журнал: исходный URL, resolved URL, title, kind, version, date, owner, Git `SiteSourceRevision.revision_id`, path и field/body locator.
- `issues: tuple[SiteParseIssue, ...]` — ошибки/конфликты с независимой семантикой `ready_for_promotion`; если upstream package имеет parse errors, публикация также запрещена.
- `catalog_version` — собственная версия каталога без расширения канонической модели.

## 2. Правила

Структурированные записи берутся из `products.documents`, `products.certificates` (`url` или `image` при `kind: scan`) и `systems.documents`. Markdown body обрабатывается во всех non-draft collections, включая неизвестные; извлекаются прямые inline, reference-style, shortcut-reference и ограниченные HTML `<a href="...">` ссылки на PDF. Ссылки из fenced code/inline code исключены; простое упоминание расширения PDF не импортируется.

HTTPS URL разрешаются консервативно; исходный адрес сохраняется в каждом occurrence. Проверяются scheme, credentials, malformed percent escapes, traversal, control chars, недоказанный origin/base. Fragment удаляется только из network resource identity; query сохраняется. Не выполняются HTTP/MIME/redirect checks. SSRF-host/path allowlist, redirects, content limits и загрузка — исключительная ответственность будущего External Document Adapter.

Дедуп выполняется по полному разрешённому URL без fragment. Один `document_id` стабилен при смене Git commit и добавлении owner. Все owner IDs, revision locators и исходные source metadata остаются доступными. Конфликт отдельных непустых metadata одного URL формирует `conflicting_document_metadata` с перечислением точных источников и severity error; выбираемое для отображения поле детерминировано, но публикация **fail-closed**. Неполные или некорректные отдельные записи диагностируются и не препятствуют сбору независимых корректных сведений; весь результат не объявляется PASS.

## 3. Control fixture

Небольшие реальные read-only schema samples из:
- `src/content/products/fps.md`: `/ftp/public/doc/fps/re%20FPS.pdf`.
- `src/content/products/bsk-69.md`: два PDF и `certificates: [{kind: scan, image: ...jpg}]` (для контрольной fixture отобран один PDF и scan).
- `src/content/products/archtool.md`: ZIP software и PDF manual — фактически подтверждено через чтение исходника.

Проверяемая fixture из сокращённых записей `fps` + `bsk-69` ожидает **3 support documents, 2 PDF candidates, 3 owner links**. Это fixture, **не полный подсчёт по 438 записям** реального сайта. Физические PDF не скачивались.

## 4. Offline тесты

Добавлено `backend/tests/unit/test_support_catalog_adapter.py` с 27 отдельными test methods для documents/products/systems, certificates/image, Markdown links, drafts, unknown collections, shared owners, duplicate provenance, conflicting metadata, URL resolution/query/fragment, PDF-kind mismatch, malformed entries, unsafe schemes, missing base, code fences, content changes, add/remove owner, stable IDs, exact revisions, immutable contract и контрольных source-derived fixtures.

Запуск проверок: `python scripts/verify_offline.py` (project checks, project and backend unittest suites, synthetic baseline) и GitHub Actions `offline-checks` + `onnx-contracts`. Для каждого exact head итоговый CI подтверждается отдельно, а не переносится с предыдущего commit.

## 5. Не выполнялось

Нет PDF fetch/parsing/OCR, `PdfRevision`, MIME sniffing, full-text indexing, Unified Snapshot, retrieval integration, Gitea Provider, API, UI, LLM/provider, deployment/scheduling. Нет изменений в `UkWood/Saturn-Main-Site`. Не использован legacy `SourceRecord/Registry`. Изложенные результаты и тесты не означают приёмки качества консультаций по инженерным вопросам.

## 6. Проверка реализации и саморевью

- [PR #23](https://github.com/UkWood/LLM-RAG-chat-bot/pull/23) открыт. Слияние в main не разрешено.
- Предыдущий полностью проверенный head `ee083ad52380d60e1e5e755c6ca7462c3f61aced`: [push CI #42785236436](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42785236436) SUCCESS — 279 backend tests, 11 existing optional skips, ONNX contracts SUCCESS.
- Дополнительное саморевью выявило и исправило ссылки со скобками в URL (реальная схема Saturn), false positives в HTML comments и escaped Markdown links. Два новых регрессионных теста включены. Финальные изменения требует подтвердить CI **последнего PR head**, а не предыдущего commit.
- Синтетическая lexical evaluation source-hit@5 = 0.85 — историческая метрика другого компонента, не качество Support Catalog.
- Независимый Acceptance Review ещё не выполнен; полный реальный каталог на всех 438 записях сайта не строился. Обработка сложных форм Markdown за пределами bounded grammar остаётся ограничением.

## 7. Acceptance workflow

Соблюдать **один полный Acceptance Review → консолидированный список замечаний → одна корректирующая итерация**. Проверить архитектуру, code diff, независимость от сети, fail-closed, URLs/provenance, positive/negative tests, документацию и exact PR-head CI. **Не сливать PR** до отдельного явного разрешения владельца.
