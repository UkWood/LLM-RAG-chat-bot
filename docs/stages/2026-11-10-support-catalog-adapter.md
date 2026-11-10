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

Добавлено `backend/tests/unit/test_support_catalog_adapter.py` с 34 отдельными test methods для documents/products/systems, certificates/image, Markdown links, drafts, unknown collections, shared owners, duplicate provenance, conflicting metadata, URL resolution/query/fragment, PDF-kind mismatch, malformed entries, unsafe schemes, missing base, code fences, content changes, add/remove owner, stable IDs, exact revisions, immutable contract и контрольных source-derived fixtures.

Запуск проверок: `python scripts/verify_offline.py` (project checks, project and backend unittest suites, synthetic baseline) и GitHub Actions `offline-checks` + `onnx-contracts`. Для каждого exact head итоговый CI подтверждается отдельно, а не переносится с предыдущего commit.

## 5. Не выполнялось

Нет PDF fetch/parsing/OCR, `PdfRevision`, MIME sniffing, full-text indexing, Unified Snapshot, retrieval integration, Gitea Provider, API, UI, LLM/provider, deployment/scheduling. Нет изменений в `UkWood/Saturn-Main-Site`. Не использован legacy `SourceRecord/Registry`. Изложенные результаты и тесты не означают приёмки качества консультаций по инженерным вопросам.

## 6. Проверка реализации и саморевью

- [PR #23](https://github.com/UkWood/LLM-RAG-chat-bot/pull/23) открыт. Слияние в main не разрешено.
- Предыдущий полностью проверенный head `ee083ad52380d60e1e5e755c6ca7462c3f61aced`: [push CI #42785236436](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42785236436) SUCCESS — 279 backend tests, 11 existing optional skips, ONNX contracts SUCCESS.
- Дополнительное саморевью выявило и исправило ссылки со скобками в URL (реальная схема Saturn), false positives в HTML comments и escaped Markdown links. Два новых регрессионных теста включены. Финальные изменения требует подтвердить CI **последнего PR head**, а не предыдущего commit.
- Синтетическая lexical evaluation source-hit@5 = 0.85 — историческая метрика другого компонента, не качество Support Catalog.
- Независимый Acceptance Review ещё не выполнен; полный реальный каталог на всех 438 записях сайта не строился. Обработка сложных форм Markdown за пределами bounded grammar остаётся ограничением.

## 7. CR-01–CR-04 — консолидированная корректирующая итерация (2026-11-10)

**Исправленная кодовая ревизия:** `b2ee0164c49f53cba7121df92c6538e557b4b7e3`.  
**Основной implementation commit:** `60ca2856265e2d3a8f5276897892122a7c20a9e3`; следующий тестовый commit `b2ee0164c49f53cba7121df92c6538e557b4b7e3` исключает provenance `README.md` из списка source blobs. PR [#23](https://github.com/UkWood/LLM-RAG-chat-bot/pull/23) **OPEN, NOT MERGED**.

- **CR-01 PASS:** ограниченный сканер поддерживает Markdown autolinks, кавычечный и некавычечный `href` HTML, вложенные/экранированные brackets и parentheses, точно исключает `data-href`, image links, inline/fenced code и HTML comments (включая ложные fences внутри комментариев). `body:line/column/heading/occurrence` привязаны к исходному тексту.
- **CR-02 PASS:** HTML entities интерпретируются для HTML-атрибутов; `%2Epdf` распознаётся. Percent-encoded separators, dot traversal и double/multi-encoded traversal отклоняются **до** `urljoin`, без переписывания законных percent-encoded filenames/query. `CatalogOccurrence.raw_url` хранит исходный spelling, `resolved_url` — абсолютное интерпретированное назначение с fragment, `SupportDocument.url` — идентичность ресурса без fragment. Дедуп и стабильность `document_id` сохранены. Небезопасные адреса дают `invalid_document_url` и `ready_for_promotion=False`.
- **CR-03 PASS:** отдельная папка `backend/tests/fixtures/saturn_support_real/` содержит **ровно 8 неизменённых source-derived файлов** и provenance README, с source commit `084d759487bfab6e111549c9b5469711ac5fc13e` / tree `a5297822bf3a5e071b10cc1dca553481c1b84d47`. Реальные Markdown `fps.md`, `bsk-69.md`, `archtool.md`, `spisok-podderzhivaemogo-oborudovaniya.md` импортируются цепочкой `PinnedSiteSnapshot → adapt_snapshot → adapt_support_catalog`. Сверяются **10 documents / 8 PDF candidates / 10 occurrences / 4 owner entities**, точные URL, Git blob/revision SHA, source locators, deterministic repeat, PDF/non-PDF, без сети.
- **CR-04 PASS:** `docs/CHATGPT_SESSION_GUIDE.md` теперь содержит универсальный стартовый prompt с обязательной проверкой GitHub live state и чтением верхних `HANDOFF/PROJECT_STATUS`, с сохранением ролей A/B и запрета merge без команды владельца.

**Новые regression cases:** 7 методов CR-01/02/03, всего 34 теста Support Catalog Adapter.  
**Фактическая проверка code head:** [push CI #42816240259](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42816240259) и [PR CI #42816246557](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42816246557) — **SUCCESS**, оба `offline-checks` и `onnx-contracts`. `python scripts/verify_offline.py` в offline job: **288 backend tests OK (11 existing optional skips)**, 5 project tests PASS, прежний synthetic lexical source-hit@5 = 0.85 (не quality measure нового каталога). Новый exact final PR head после документационного изменения проверять отдельно; code head не переименовывать в «current head».

**Scope:** Canonical contracts, Site Content Adapter, schema evolution, ADR-0012/0013/0014 не изменялись; read-only сайт не изменён. Ограниченный Markdown parser не претендует на полное CommonMark/HTML rendering; URL allowlist/SSRF, PDF fetch/extraction, Unified Snapshot, retrieval и этап 3B не входят в CR. Содержимое fixtures — только малый срез, не полный real-site ingestion.

## 8. Acceptance workflow

Соблюдать **один полный Acceptance Review → консолидированный список замечаний → одна корректирующая итерация**. Проверить архитектуру, code diff, независимость от сети, fail-closed, URLs/provenance, positive/negative tests, документацию и exact PR-head CI. **Не сливать PR** до отдельного явного разрешения владельца.
