# ADR-0012: интеграция знаний Сатурна с существующим Grounded RAG

Дата: 2026-11-08  
Статус: **PROPOSED — ожидает явного утверждения владельцем**  
Область: UkWood/LLM-RAG-chat-bot  
Основание: site-specific v0.1 и ADR-0011.

## Контекст

В main 3cd6787db2fe00fd7cea49bce8a355a27f292bf0 находятся согласованные site-specific требования и базовые ingestion/snapshot/retrieval/evaluation contracts.

В открытом Draft PR #13 (head 24a8409b7d5fb65d9f5144019f87f5d1bc75df0c) реализованы дополнительные компоненты:
- generic publication fetch/extract/store/refresh;
- hybrid BM25/Qdrant retrieval и reranker integration;
- OpenAI-compatible provider;
- bounded generation, verification и backend citations;
- diagnostic CLI и 15 synthetic diagnostic cases.

PR #13 не слит, основан на прежнем main и не реализует полноценную интеграцию структурированного Markdown/frontmatter/YAML, Support Catalog metadata и отдельно approved PDF как три независимых канала.

Human answer assessment PR #13 остаётся pending. 15/15 диагностических случаев без infrastructure errors и успешный CI не доказывают корректность ответов.

Site-specific v0.1 требует:
- Saturn-Main-Site строго read-only;
- отдельные adapters к структуре сайта, Support catalog и PDF;
- source-level provenance;
- отдельное approval для каждой source revision;
- default deny;
- раздельные local_index, local_generate и cloud_generate permissions;
- проверяемые evidence и backend-generated citations.

## Решение — предлагается к утверждению

### 1. Selective reuse, не wholesale merge

Не сливать PR #13 целиком и не использовать его ветку как base для site-specific v0.2.

После архитектурного approval и review переносить нужные компоненты выборочно:
- BM25/Qdrant/RRF;
- local reranker как измеряемый retrieval component;
- безопасные fetch/parser механизмы;
- content-addressed storage и atomic snapshot promotion;
- OpenAI-compatible provider interface;
- bounded generation/verification/citation flow;
- diagnostic harness.

Каждый компонент проходит адаптацию к canonical contracts и отдельные тесты. Старые synthetic contracts и historical reports сохраняются.

### 2. Три самостоятельных adapters

Создать:
1. Site Content Adapter — pinned read-only Git snapshot, Markdown/frontmatter, schema и YAML dictionaries.
2. Support Catalog Adapter — metadata documents/certificates из approved products/systems, с URL, type, version и всеми owners.
3. External Document Adapter — exact allowlisted PDF fetch, hash, extraction и physical page provenance после отдельного file approval.

Support metadata не является доказательством содержания PDF. Approval страницы не даёт approval связанного PDF.

### 3. Canonical knowledge model

Хранить раздельно:
- SourceIdentity;
- immutable SourceRevision;
- Entity;
- Fact;
- Relation;
- SupportDocument;
- DocumentRevision;
- EvidenceUnit;
- Citation reference.

Текстовые projections для BM25/vector допустимы, но retrieval обязан возвращать canonical typed evidence с исходным provenance.

### 4. Approval привязан к exact revision

Approval действует на конкретный source revision/hash и набор allowed_usage.

Новый commit/path hash или PDF bytes hash создаёт новую pending revision. Approval не наследуется. Изменения можно обнаруживать автоматически, но нельзя автоматически разрешать новую revision.

Pending/UNKNOWN/revoked sources не попадают в active retrieval/generation. Explicit revoke действует немедленно через live policy check.

### 5. Unified snapshot и раздельные retrieval outputs

Создать immutable Knowledge Snapshot, объединяющий:
- site entities/facts/relations;
- Support Catalog metadata;
- approved extracted document passages;
- source revision and approval manifests;
- parser/chunker/index descriptors.

Retrieval возвращает два раздельных типа результатов:
- answer evidence: facts, relations, site passages и PDF passages;
- document matches: Support Catalog metadata для поиска нужного файла.

Metadata-only document match не может подтверждать техническое утверждение о содержимом PDF.

### 6. Не вводить сложный planner до доказанной необходимости

Первый query coordinator выполняет bounded channel-aware retrieval и сохраняет исходный вопрос без потери negation, qualifiers, designations и units.

PR #12 Semantic Planner V3 не включать автоматически: его independent blind quality result 2/24 positive и 16/16 negative/ambiguity outcomes. Новый planner может рассматриваться только как отдельная гипотеза с calibration и новым independent evaluation.

### 7. Grounded answer и citations

Сохранить bounded answer flow как кандидата:
question → retrieval → typed evidence → generation → verification → backend rendering.

LLM предлагает claims и evidence pointers, но не назначает URLs, page numbers, versions или citation numbers. Backend проверяет entity identity, field/quote, numeric values, units, qualifiers, source revision, policy и полноту ответа. Backend формирует citations и повторно проверяет live policy перед rendering.

Предлагаемые статусы: answered, partial, clarification, needs_support, error. Конфликт источников не разрешается догадкой.

## Последствия

Положительные:
- согласованная модель v0.1 сохраняется;
- сайт остаётся независимым и read-only;
- структурированные характеристики не теряются в plain-text chunks;
- Support metadata и PDF text не смешиваются;
- approvals и citations становятся revision-aware;
- существующие retrieval и RAG компоненты можно переиспользовать без wholesale merge.

Затраты и ограничения:
- потребуется canonical data model и schema mapping;
- потребуется отдельный source registry/revision lifecycle;
- три adapters увеличивают число контрактов и тестов;
- relation mapping и extraction quality требуют ручной проверки;
- quality на synthetic corpus нельзя переносить на реальные материалы;
- интеграция PR #13 потребует ручной reconciliation с main и сохранения текущих handoff/status.

## Что остаётся неизменным

- UkWood/Saturn-Main-Site — строго READ-ONLY.
- Текущие /search/ и /service/search/ сайта не изменяются.
- Реальные source candidates остаются pending до отдельного допуска.
- PR #13 и PR #12 не сливаются автоматически.
- Frozen datasets, START manifests и historical reports не редактируются.
- Нет автоматического provider/model/region selection.
- Нет real ingestion, cloud calls, deployment или site widget без отдельного разрешения.

## Не решается этим ADR

ADR-0012 не выбирает:
- конкретную LLM, provider, model или region;
- embedding/reranker model revision;
- OCR engine;
- persistence technology;
- production hosting/API domain;
- latency/concurrency targets;
- точный состав pilot corpus;
- индивидуальные approvals и allowed_usage.

Эти решения требуют дополнительных измерений, входных данных и/или отдельного решения владельца.

## План проверки

Предлагаемая последовательность и measurable acceptance gates находятся в [implementation plan v0.2](../site-specific/v0.2/03-implementation-plan.md). Матрица reuse находится в [integration matrix](../site-specific/v0.2/01-integration-matrix.md).
