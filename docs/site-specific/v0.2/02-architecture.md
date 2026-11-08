# Целевая архитектура AI Technical Consultant для Сатурна v0.2

Дата: 2026-11-08  
Статус: **ACCEPTED — owner-approved source trust and schema evolution model**  
Основание: site-specific v0.1 и ADR-0011. Это уточнение интеграции, не замена фундаментального ТЗ.

## 1. Архитектурная цель

Построить независимый AI Technical Consultant, который отвечает на инженерные вопросы только по допущенным материалам Сатурна, сохраняет происхождение каждого факта и показывает проверяемые ссылки на страницы сайта и физические страницы PDF.

Сайт остаётся отдельным статическим Astro-проектом. AI-консультант получает только read-only snapshot и не меняет сайт, его URL, assets, search-index.json, doc-index.json или пользовательские поиски.

Весь ingestion, knowledge model, retrieval, answer generation, API, UI и эксплуатационные инструменты находятся в UkWood/LLM-RAG-chat-bot.

## 2. Архитектурная схема

~~~mermaid
flowchart TB
  subgraph SITE["Saturn-Main-Site — READ ONLY"]
    GIT["Pinned Git commit"]
    MD["Markdown collections + frontmatter"]
    YAML["YAML dictionaries"]
    DOCS["documents / certificates metadata"]
  end

  subgraph FILES["Внешнее хранилище документов"]
    PDF["Только exact allowlisted PDF URLs"]
  end

  subgraph INGEST["Knowledge ingestion"]
    REG["Source revision registry + deny-by-default policy"]
    SA["Site Content Adapter"]
    CA["Support Catalog Adapter"]
    DA["External Document Adapter"]
    EX["Isolated extraction + quality report"]
    KM["Canonical Knowledge Model"]
    KS["Immutable Knowledge Snapshot + manifest"]
    IDX["Index build and atomic promotion"]
  end

  GIT --> MD
  GIT --> YAML
  MD --> SA
  YAML --> SA
  DOCS --> CA
  REG --> SA
  REG --> CA
  CA --> DA
  PDF --> DA
  REG --> DA
  DA --> EX
  SA --> KM
  CA --> KM
  EX --> KM
  KM --> KS --> IDX

  subgraph QUERY["Query and answer"]
    UI["Standalone UI"]
    API["FastAPI"]
    QP["Query coordinator"]
    SR["Site facts and relations"]
    CR["Support metadata lookup"]
    DR["PDF text retrieval"]
    HY["BM25 + dense + RRF"]
    RR["Local reranker"]
    EG["Evidence and policy gate"]
    LLM["Configured LLM provider"]
    VG["Claim verification + completeness"]
    OUT["Answer / partial / clarification / support"]
  end

  UI --> API --> QP
  QP --> SR
  QP --> CR
  QP --> DR
  SR --> HY
  DR --> HY
  HY --> RR --> EG
  CR --> OUT
  EG --> LLM --> VG --> OUT
  EG --> OUT
  OUT --> API --> UI
  IDX --> SR
  IDX --> CR
  IDX --> DR
~~~

## 3. Три независимых source adapters

### 3.1. Site Content Adapter

Вход: read-only Git snapshot UkWood/Saturn-Main-Site@main, все collections под src/content/, src/content.config.ts и YAML dictionaries под src/data/.

Adapter обнаруживает collections и файлы динамически, а не полагается на жёсткий список из шести текущих коллекций. Известные типы mapping:
- products → Product/Device; software — subtype Product по текущей классификации;
- systems с kind=system → System;
- systems с kind=category → Category;
- groups → CatalogGroup;
- articles/news → Article/News;
- pages с kind=solution/section → Solution/SectionPage; остальные — Page.

Сохраняются все frontmatter fields, body, references, specs, units, qualifiers, documents и certificates. Известные поля получают typed projection; неизвестные поля сохраняются в raw_fields и индексируются как labelled field/value evidence. Неизвестная collection импортируется как generic SiteContent, не теряя содержимое.

draft: true исключается из публичного corpus. Отсутствующее поле и schema default не являются отрицательным утверждением. Новые значения dictionaries и новые spec names не должны требовать изменения кода.

### 3.2. Support Catalog Adapter

Автоматически собирает documents/certificates из products/systems и обнаруживает прямые PDF-ссылки в Markdown body всех non-draft collections. Для каждой ссылки сохраняет owner page/product/system и точный source locator. Сохраняет:
- title, kind, version/date;
- original URL и resolved canonical URL;
- всех owners и точные source field paths;
- commit/blob provenance.

Один документ может иметь несколько owners. Дедупликация не должна терять metadata или owner links. Metadata lookup остаётся отдельным типом результата и не подменяет текст PDF.

### 3.3. External Document Adapter

Все прямые PDF-ссылки из доверенного сайта, доступные по configured HTTPS host/path allowlist, автоматически загружаются и обрабатываются. Сюда входят structured documents/certificates и ссылки в Markdown body. Отдельный manual approval не требуется.

Для каждого файла сохраняются URL, bytes SHA-256, page count, parser version, extraction state и физические страницы. Новый hash запускает re-extraction. Несколько владельцев сохраняются.

Технические ограничения остаются обязательными: HTTPS, allowlisted hosts/paths, запрет user-controlled fetch, SSRF/redirect protection, size/time/page limits, изоляция parser. Ошибка fetch/extraction оставляет metadata в каталоге, но не создаёт фиктивный PDF text evidence.

## 4. Каноническая модель знаний

Модель отделяет идентичность сущности от версии источника, а факты и связи — от текстового представления для поиска.

### 4.1. SourceIdentity и SourceRevision

SourceIdentity — стабильная логическая идентичность источника.

SourceRevision — неизменяемая версия для воспроизводимости:
- source_id, revision_id, source_kind;
- repository, branch, exact Git commit + path + blob SHA либо exact URL + fetched bytes SHA-256;
- content hash, title/media type, observed_at;
- trust-policy version и parser/extractor version.

SourceRevision не содержит approval_state, approved_by или approved_at. Новая revision доверенного источника автоматически становится кандидатом следующего sync; hash нужен для traceability, а не для допуска.

### 4.2. Entity

Entity описывает объект предметной области:
- entity_id, entity_type;
- title/name/designation;
- canonical_url;
- source_id/revision_id;
- source collection/path;
- source status и qualifiers.

Типы: Device/Product, System, Category, Software, Group, Article, Solution, News, Page и generic SiteContent. Software может быть semantic subtype Product.

### 4.3. Fact

Fact — утверждение из конкретного поля источника:
- fact_id, subject_entity_id, predicate/field_path;
- raw_value без потери исходного представления;
- optional normalized_value, unit, qualifiers/conditions;
- source_id/revision_id, field path;
- parser/projection version.

Нормализация не заменяет raw_value. Строки specs, единицы, диапазоны, условия и оговорки сохраняются.

### 4.4. Relation

Relation хранит source-declared directed relation:
- relation_id, subject_entity_id, predicate, object_entity_id;
- source_id/revision_id, source field path;
- optional qualifiers.

Обратные relations — вычисляемые projections со ссылкой на исходную связь. Смысл связи следует полю сайта; нельзя подменять его более сильным predicate или создавать новую инженерную связь по co-occurrence.

### 4.5. SupportDocument, DocumentRevision и EvidenceUnit

SupportDocument содержит title, kind, version/date, URL и всех owners.

DocumentRevision содержит exact URL, bytes SHA-256, physical page count, extraction state/quality, extracted text hash и parser version. Approval state отсутствует.

EvidenceUnit — адресуемое доказательство: structured fact, relation, site passage, PDF passage или metadata match. Metadata match не используется как доказательство содержимого PDF.

Citation формирует backend: canonical page URL или original PDF URL, source revision/hash, field path/heading и физическая PDF page. LLM не назначает citation metadata.

## 5. Source trust, revision traceability и schema evolution

### 5.1. Trust root

UkWood/Saturn-Main-Site branch main — доверенный источник. Все non-draft records, declared relations, dictionaries и PDF links из documents/certificates автоматически допускаются к local indexing/local generation. Никаких per-source, per-relation или per-PDF approval workflow нет.

### 5.2. Revision traceability

Каждый SourceRevision содержит repository, branch, exact commit, path, Git blob SHA, content SHA-256, collection/slug, field path и canonical URL. Для PDF сохраняются original URL, bytes SHA-256, parser version и physical page locators.

Изменение hash запускает автоматическую обработку новой версии; не переводит её в pending и не требует ручного допуска.

### 5.3. Schema drift

На каждой sync сравниваются Git tree, src/content.config.ts, collections, observed field inventory и fingerprints dictionaries.

- Content add/update/delete — автоматически отражается в следующем snapshot.
- Новые поля, collections и dictionary values сохраняются в generic representation и labelled evidence.
- Новые collections получают generic SiteContent mapping до появления специализированного mapping.
- Если тип/структура поля изменились, старый typed mapping для этого поля отключается; raw value сохраняется и появляется drift event.
- Обновление parser/mapping — обычная задача разработки в AI-репозитории, покрываемая fixtures и contract tests.
- Новый snapshot публикуется атомарно после проверки целостности. Частичный build не становится active.

### 5.4. Runtime policy

local_index и local_generate разрешены для доверенного non-draft сайта и успешно извлечённых PDF. cloud_generate остаётся отдельным egress permission для выбранного provider и не является source approval.

Explicit operational block/revoke может временно выключить fetch или использование источника по причинам безопасности/эксплуатации, но не меняет оценку достоверности его содержимого.

## 6. Retrieval architecture

### 6.1. Разделить answer evidence и document lookup

Результат retrieval состоит из двух логически разных потоков.

**Answer evidence:**
- структурированные facts;
- explicit relations;
- содержательные site passages;
- извлечённые PDF passages.

Для этих evidence применяются BM25 и dense retrieval, fusion и, после подтверждения на real corpus, local reranker.

**Document matches:**
- Support Catalog metadata;
- title/type/version/URL/owners.

Этот поток предназначен для поиска нужного файла. Metadata-only match не считается доказательством технического утверждения из содержимого файла.

### 6.2. Query coordinator

Первый вариант не должен зависеть от сложного LLM planner. Coordinator:
- принимает исходный вопрос без потери отрицаний, qualifiers, обозначений и единиц;
- выполняет bounded retrieval по применимым каналам;
- сохраняет отдельные traces и source types;
- не подменяет отсутствующее evidence похожим документом;
- возвращает document matches отдельно от answer evidence.

Если вопрос явно просит найти документ, metadata channel может дать прямой результат со ссылкой. Если вопрос спрашивает технический факт, ссылка на документ не считается ответом, пока его содержимое не извлечено и не допущено.

### 6.3. Ranking

- BM25 и dense остаются самостоятельными retrieval channels.
- RRF может объединять сопоставимые answer-evidence candidates.
- Metadata-only document matches не смешиваются с fact/passage scores в один непрозрачный рейтинг.
- Reranker получает bounded набор совместимых evidence passages; structured facts передаются как явные typed projections.
- После ranking и до generation policy проверяется повторно.

Не фиксировать новые веса, thresholds или planner behavior без calibration measurements.

## 7. Grounded answer flow

Предлагаемый pipeline:

1. Validate question and request limits.
2. Capture one immutable Knowledge Snapshot and current policy view.
3. Query coordinator runs channel-aware retrieval.
4. Build bounded evidence set with canonical IDs.
5. Check that every selected source revision is allowed for local generation or cloud generation, depending on provider.
6. LLM drafts atomic claims and evidence pointers; it does not produce citations.
7. Deterministic backend checks evidence IDs, source/revision identity, exact quotes or structured field values, units, numeric values, qualifiers, entity identity and current policy.
8. Independent verification pass checks relevance to the original question, completeness, ambiguity and conflicts.
9. Backend rechecks live policy immediately before rendering.
10. Backend builds citations and answer status.

### 7.1. Answer statuses

Предлагаемые статусы:
- answered — все запрошенные части подтверждены;
- partial — часть запрошенных частей подтверждена, остальные явно обозначены;
- clarification — вопрос неоднозначен или источники конфликтуют и требуется уточнение;
- needs_support — достаточного подтверждения в разрешённом корпусе нет;
- error — техническая ошибка, не маскируемая под отсутствие evidence.

Частичный ответ допустим только по реально подтверждённым частям исходного вопроса. Нельзя добавлять справочные характеристики, не запрошенные пользователем, чтобы сделать ответ длиннее.

### 7.2. Conflicts

Если два допущенных источника противоречат друг другу:
- не выбирать значение по близости, большинству или догадке;
- проверить revision, date/version и scope;
- если политика источников не разрешает конфликт однозначно, вернуть conflict/clarification outcome;
- показать оба происхождения только если обе revisions разрешены к использованию;
- не скрывать конфликт в пересказе.

### 7.3. Citation rules

- Для сайта — canonical page URL и конкретный field path/section.
- Для PDF — original document URL и физическая page.
- Для каждого citation — source revision/hash.
- URL, title, page и version формируются backend из manifest.
- Нельзя цитировать pending/revoked/UNKNOWN sources.
- Отсутствие точной страницы или field provenance — ошибка качества extraction, а не повод придумать citation.

## 8. Provider boundary

Provider остаётся заменяемым интерфейсом. PR #13 даёт полезную OpenAI-compatible реализацию, но архитектура не выбирает модель.

До отдельного решения:
- Fake provider используется для contract tests;
- реальные внешние вызовы выполняются только при наличии разрешённого runtime и явного разрешения владельца на передачу данных выбранному provider;
- cloud_generate — runtime/data-egress permission, а не per-source approval;
- API key хранится только в runtime secrets/environment;
- модель, endpoint, region, retention и budget согласуются отдельно;
- локальная модель рассматривается как отдельный deployment option, не как автоматический fallback.

Исторический operator profile 4096 tokens из PR #13 — диагностическая настройка конкретного запуска, не решение о default production budget.

## 9. Безопасность и эксплуатационные границы

- Git access к Saturn-Main-Site — read-only на уровне credentials.
- Adapter не содержит Git write APIs и не запрашивает write scopes.
- External fetcher получает только точные URL из доверенного Support Catalog и configured host/path allowlist.
- User input никогда не становится URL для server-side fetch.
- Redirects, DNS rebinding, private IP, oversized files, decompression/parser abuse и timeouts закрываются на fetch/parser boundary.
- PDF parser работает изолированно.
- Qdrant доступен только локально/private network.
- Secrets не попадают во frontend, Git, logs или citations.
- Logs не становятся evidence и не используются как corpus.
- No user uploads, CRM, registration, memory or admin CMS in MVP.
- Deployment, public API and site widget — отдельные gates.

## 10. Нерешённые вопросы

Эта архитектура намеренно не выбирает:
- конкретную LLM/model/provider/region;
- локальный или внешний inference;
- embedding/reranker model revision;
- OCR engine;
- финальную схему SQLite/JSON persistence;
- production hosting, API domain и reverse proxy;
- latency/concurrency targets до ответа ИТ;
- состав ограниченного pilot corpus;
- runtime permissions и provider data-egress settings.

Эти решения принимаются по реальным входным данным, benchmark и отдельному решению владельца.
