# ADR-0012: интеграция знаний Сатурна с существующим Grounded RAG

Дата: 2026-11-09  
Статус: **ACCEPTED — owner-approved baseline, updated source trust policy**  
Область: UkWood/LLM-RAG-chat-bot

## Контекст

PR #16 утвердил selective reuse существующего Grounded RAG вместо полного слияния экспериментального PR #13. Read-only аудит реальной схемы Saturn-Main-Site завершён в PR #17.

Владелец подтвердил, что содержимое сайта, его структурированные данные, взаимосвязи сущностей и PDF, опубликованные по ссылкам сайта, проверены специалистами компании и являются доверенными источниками. Сайт остаётся в разработке, поэтому структура и состав данных будут меняться.

## Решение

### 1. Selective reuse

Не сливать PR #13 целиком. Выборочно адаптировать после проверки:
- BM25/Qdrant/RRF;
- local reranker как измеряемый retrieval component;
- безопасные fetch/parser механизмы;
- content-addressed storage и atomic snapshot promotion;
- OpenAI-compatible provider interface;
- bounded generation, verification, citations и diagnostic harness.

Существующие synthetic contracts и historical reports сохраняются. Они не считаются production Saturn schemas.

### 2. Три канала источников

1. **Site Content Adapter** — read-only Git snapshot, Markdown/frontmatter, Astro schema и YAML dictionaries.
2. **Support Catalog Adapter** — metadata documents/certificates и все связи с владельцами.
3. **External Document Adapter** — автоматическая загрузка и извлечение PDF, ссылки на которые присутствуют в доверенном Support Catalog.

Metadata каталога и полнотекстовое содержимое PDF остаются разными evidence types, но отдельного ручного допуска PDF не требуется.

### 3. Доверие и revisions

- Текущая main-ветка UkWood/Saturn-Main-Site является trust root.
- Все записи, связи и справочники сайта, кроме явно draft: true, автоматически считаются пригодными для локального индексирования и генерации.
- Все прямые PDF-ссылки, обнаруженные в non-draft содержимом сайта — в documents/certificates и Markdown body, — автоматически попадают в каталог, загружаются с configured trusted origin/path и индексируются после успешного извлечения.
- Никаких ручных approval/review workflow для страниц, relations, полей или PDF.
- Git commit, blob SHA, content SHA-256, field path, URL и PDF hash сохраняются для traceability, воспроизводимости и citations. Hash change создаёт новую техническую revision и запускает re-ingestion, а не новую процедуру подтверждения.
- Изменения, добавления и удаления автоматически отражаются в следующем Knowledge Snapshot.

### 4. Эволюция схемы

Adapter не должен зависеть от неизменного списка collections или полей:
- обнаруживать collections и файлы в src/content/;
- учитывать изменения src/content.config.ts и src/data/*.yaml;
- сравнивать schema/dictionary fingerprints между sync runs;
- сохранять неизвестные additive fields в raw extension area и индексировать их как именованные field/value evidence;
- неизвестную collection импортировать как generic SiteContent, не теряя title/body/frontmatter;
- новые значения справочников и новые параметры принимать без изменения кода, если структура значения совместима;
- при несовместимом изменении типа/смысла отключать только устаревшую typed projection, сохранять raw value и выдавать drift report;
- не интерпретировать неизвестное поле по старому mapping и не терять его молча.

Mapping и parser имеют собственные версии в AI-репозитории. Их обновление — штатная инженерная работа, покрываемая fixtures и contract tests.

### 5. Canonical model и retrieval

Сохранять отдельно Entity, Fact, Relation, SupportDocument, DocumentRevision и EvidenceUnit. Каждая запись должна иметь source revision, field/path/page locator и canonical URL, если он определён.

Relation импортируется согласно смыслу поля сайта. Не создавать новые engineering relations по совместному упоминанию; не повышать related до compatible_with. System и Category различать. Отсутствующее поле/default не является отрицательным техническим утверждением.

Retrieval возвращает отдельно:
- answer evidence: structured facts/relations и текстовые passages сайта/PDF;
- document matches: metadata каталога для поиска файла.

### 6. Grounded answer

Сохранить bounded flow:
question → channel-aware retrieval → typed evidence → generation → deterministic verification → backend citations.

Backend проверяет entity identity, evidence IDs, exact source locators, values, units, qualifiers и полноту ответа. LLM не назначает URL, PDF page или citation metadata.

### 7. Provider boundary

Доверие к публичному содержимому сайта не означает автоматического разрешения на передачу контекста внешнему LLM. cloud_generate остаётся отдельным runtime/data-egress permission, зависящим от выбранного provider, endpoint, region и retention policy. Локальная генерация и локальная индексация не требуют per-source approval.

## Неизменные ограничения

- UkWood/Saturn-Main-Site строго READ-ONLY; credentials только read-only.
- Текущие /search/ и /service/search/ сайта не изменяются.
- User input никогда не становится URL для server-side fetch.
- Fetch ограничен HTTPS, configured host/path allowlist, size/time/page limits и SSRF/redirect protections. Это техническая безопасность, а не проверка достоверности источника.
- Ошибка fetch/extraction не превращается в пустой валидный PDF. Metadata остаётся доступной, а содержимое недоступно до успешного извлечения.
- Никаких provider/model/region, production deployment или публичного widget без отдельных решений.
- PR #12 и PR #13 не сливаются автоматически.

## Не решается этим ADR

ADR-0012 не выбирает конкретную LLM/provider/model, embedding/reranker revision, OCR engine, persistence technology, production hosting, latency/concurrency targets или budget.

## План

[Целевая архитектура v0.2](../site-specific/v0.2/02-architecture.md), [implementation plan](../site-specific/v0.2/03-implementation-plan.md), [read-only schema mapping and evolution rules](../site-specific/v0.2/04-read-only-schema-audit.md), [ADR-0013](0013-saturn-relation-provenance.md).
