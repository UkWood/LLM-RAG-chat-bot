# Целевая архитектура AI Technical Consultant для Сатурна v0.2

Дата: 2026-11-08  
Статус: **ACCEPTED BASELINE — owner approved PR #16; relation provenance addendum pending ADR-0013**  
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

Вход:
- точный Git commit Saturn-Main-Site;
- выбранные Markdown-файлы коллекций;
- schema definition из src/content.config.ts;
- необходимые YAML dictionaries из src/data/;
- manifest с commit, path и SHA-256.

Коллекции, описанные в read-only inventory v0.1:
- products;
- systems;
- groups;
- articles;
- news;
- pages.

Adapter должен учитывать фактическую схему конкретного pinned commit, а не предполагать, что схема не менялась.

Особенности mapping:
- products — изделия и оборудование;
- software — семантический тип записи products, обычно определяемый через группу каталога, а не отдельная Astro-коллекция;
- systems.kind=system — инженерная система;
- systems.kind=category — каталоговая категория, не инженерная система;
- pages.kind=solution — типовое решение;
- draft=true — не допускается в knowledge package;
- status, notice и иные технические qualifiers сохраняются как исходные значения;
- состав системы может быть получен из обратных ссылок products.systems, но каждая derived inverse relation должна хранить ссылку на исходное поле продукта.

Для products должны сохраняться, если присутствуют в pinned schema:
title, name, article, group, systems, status, notice, interfaces, protocols, ip, temperature_c, mass_kg, dimensions_mm, lifetime_years, power, specs, inputs, outputs, features, connectors, documents, certificates, related, variant_of, software, articles, solutions и body.

Это перечень известных полей из inventory v0.1, а не разрешение жёстко зашивать все поля без проверки schema. Неизвестные поля нельзя молча терять: adapter должен либо сохранить их в controlled extension area, либо сообщить validation warning/error по согласованному правилу.

### 3.2. Support Catalog Adapter

Вход:
- approved Site Content package;
- documents и certificates из разрешённых products и systems;
- точные исходные URL и метаданные документа.

Для каждой записи документа сохранять:
- стабильный document_id;
- title;
- document kind/type;
- version/date, если указаны;
- support section/category;
- original URL из source field;
- canonical URL, полученный по проверенному правилу site asset origin;
- всех owners (product/system), включая canonical URL карточек;
- source revision и точный field path каждого owner link.

Один файл может иметь несколько владельцев. Deduplication по URL не должна удалять owner relationships.

Support Catalog — самостоятельный metadata channel. Он позволяет найти файл, его тип и владельцев, но не подтверждает содержание PDF и не должен превращаться в технический claim о характеристиках изделия.

Нельзя вручную собирать URL из предполагаемой структуры каталогов. Нужно сохранять исходную ссылку и использовать проверенную логику разрешения asset origin, применявшуюся сайтом на pinned revision.

### 3.3. External Document Adapter

Вход:
- отдельная approved revision Support Catalog entry;
- exact URL;
- per-file approval;
- allowlist host/path и лимиты fetch.

Правила:
- никаких произвольных URL из пользовательского вопроса;
- никаких массовых обходов старого файлового сервера;
- никаких скачиваний всех ссылок, найденных crawler;
- PDF допускается только после отдельного approval конкретного файла/revision;
- source page approval не наследуется PDF;
- исходные bytes сохраняются с SHA-256;
- при изменении bytes на прежнем URL возникает новая revision и требуется новый approval;
- redirect по умолчанию запрещён; если нужен, допускается только явно проверенный переход внутри утверждённого origin/path scope;
- DNS/private/loopback/link-local targets должны блокироваться;
- лимиты размера, времени, числа страниц и типа содержимого задаются конфигурацией;
- ошибки fetch и extraction не превращаются в пустой корректный документ.

Извлечение должно сохранять физические номера страниц. Для таблиц, схем и сканов формируется extraction quality report. Если текстовое извлечение не позволяет надёжно подтвердить значения, документ помечается OCR_REQUIRED или MANUAL_REVIEW_REQUIRED и не используется как положительный evidence до проверки.

## 4. Каноническая модель знаний

Модель должна отделять идентичность сущности от версии источника, а факты и связи — от текстового представления для поиска.

### 4.1. SourceIdentity и SourceRevision

SourceIdentity — стабильная логическая идентичность источника.

SourceRevision — конкретная неизменяемая версия, к которой относится approval:
- source_id;
- revision_id;
- source_kind;
- source commit + path для Git content либо exact URL + fetched bytes SHA-256 для external document;
- content hash;
- title/media type;
- observed_at;
- approval_state;
- visibility;
- allowed_usage;
- approval_id, approved_by, approved_at;
- policy_revision;
- publication_verified;
- parser/extractor version, если применимо.

Approval действует только на точную revision/hash. Ни одинаковый URL, ни одинаковый title, ни прежний approval не дают права использовать изменившееся содержимое.

### 4.2. Entity

Entity описывает объект предметной области:
- entity_id;
- entity_type;
- title/name/designation;
- canonical_url;
- source_id и revision_id;
- source collection/path;
- source status и qualifiers.

Поддерживаемые типы: Device/Product, System, Category, Software, Group, Article, Solution, News, Page.

Software может быть semantic subtype Product. Это не означает появления новой source collection.

### 4.3. Fact

Fact — отдельное утверждение, полученное из конкретного поля источника:
- fact_id;
- subject_entity_id;
- predicate/field_path;
- raw_value — исходное значение без потери форматирования;
- normalized_value — optional typed projection;
- unit;
- qualifiers/conditions;
- source_id/revision_id;
- provenance field path;
- parser/projection version.

Нормализация не должна заменять raw_value. Например, числовое значение, единица, диапазон, условие, отрицание или оговорка должны оставаться различимыми. Строки specs и канонические поля не сливаются без сохранения происхождения.

### 4.4. Relation

Relation — только явно заданная связь:
- relation_id;
- subject_entity_id;
- predicate;
- object_entity_id;
- source_id/revision_id;
- source field path;
- optional qualifiers.

Разрешены только relation mappings, подтверждённые реальной schema сайта: systems, related, variant_of, software, articles, solutions и другие проверенные поля.

Обратные relations допускаются как вычисляемые проекции, но обязаны указывать исходную directed relation. Совместимость, назначение, состав, принадлежность или поддержка протокола не выводятся из совместного упоминания в тексте.

### 4.5. SupportDocument и DocumentRevision

SupportDocument — запись каталога: title, kind, version, URL, support section и owners.

DocumentRevision — отдельные fetched bytes и результат extraction:
- exact URL;
- bytes SHA-256;
- physical page count;
- extraction state/quality;
- extracted text hash;
- parser version;
- approval на конкретный revision.

Metadata record и extracted document revision — разные объекты с разными разрешениями.

### 4.6. EvidenceUnit и Citation

EvidenceUnit — адресуемое доказательство одного из типов:
- structured fact;
- explicit relation;
- entity field/description;
- PDF/text passage с heading/page;
- approved support metadata для поиска документа.

Текстовая projection EvidenceUnit может индексироваться BM25/vector, но при retrieval должен возвращаться canonical evidence pointer.

Citation формирует backend, а не LLM. В зависимости от evidence type она содержит:
- source title;
- canonical page URL либо original document URL;
- source revision/content hash;
- field path/section;
- физическую PDF page;
- document/entity owner references.

LLM не может самостоятельно назначать source ID, URL, page, version или citation number.

## 5. Source policy и обновление revisions

### 5.1. Default deny

Новая запись по умолчанию:
- visibility=UNKNOWN;
- approval_state=pending;
- allowed_usage=[];
- cloud_allowed=false.

Для каждого source revision отдельно разрешаются:
- local_index;
- local_generate;
- cloud_generate.

Точные имена и обратная совместимость с текущими registry fields проверяются при проектировании contracts. Семантика должна оставаться явной и fail-closed.

### 5.2. Изменение источника

Если изменился Git commit/path content hash или PDF bytes hash:
1. создаётся новая SourceRevision;
2. новая revision получает pending;
3. прежняя approval не наследуется;
4. новая revision не входит в active snapshot до approval;
5. прежняя revision сохраняется в audit storage, но не обслуживает ответы, если источник больше не считается актуальным;
6. явный revoke немедленно блокирует дальнейшее использование старой revision через live policy check.

Обнаружение изменений можно автоматизировать. Approval — нет.

### 5.3. Snapshot promotion

Knowledge Snapshot immutable и содержит:
- точный список source revisions;
- policy revision;
- adapter/parser/chunker versions;
- entity/fact/relation manifests;
- catalog/document manifests;
- BM25/Qdrant descriptors;
- hashes всех существенных artifacts.

Build выполняется в отдельной staging area. Snapshot становится active только после полной проверки manifest, approvals и indexes. Ошибка сборки не публикует частичный snapshot.

При этом live revocation действует независимо от snapshot. Старый snapshot не даёт права продолжать выдавать отозванный источник. Health/staleness policy должна блокировать ответ, если нет актуального проверенного состояния.

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

Provider остаётся заменяемым интерфейсом. PR #13 даёт полезную OpenAI-compatible реализацию и строгую обработку ошибок, но архитектура не выбирает модель.

До отдельного решения:
- Fake provider используется для contract tests;
- реальные внешние вызовы выполняются только при наличии разрешённого runtime, approved public evidence и явного разрешения владельца;
- cloud generation требует cloud_generate для каждой передаваемой revision;
- API key хранится только в runtime secrets/environment;
- модель, endpoint, region, retention и budget согласуются отдельно;
- локальная модель рассматривается как отдельный deployment option, не как автоматический fallback.

Исторический operator profile 4096 tokens из PR #13 — диагностическая настройка конкретного запуска, не решение о default production budget.

## 9. Безопасность и эксплуатационные границы

- Git access к Saturn-Main-Site — read-only на уровне credentials.
- Adapter не содержит Git write APIs и не запрашивает write scopes.
- External fetcher получает только exact approved URLs.
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
- окончательный список примерно 10 pilot source objects;
- значения source approvals и allowed_usage.

Эти решения принимаются по реальным входным данным, benchmark и отдельному решению владельца.
