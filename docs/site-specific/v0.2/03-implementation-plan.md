# План реализации site-specific architecture v0.2

Дата: 2026-11-08  
Статус: **PROPOSED — план не является разрешением на начало coding**  
База для планирования: main 3cd6787db2fe00fd7cea49bce8a355a27f292bf0.

## 1. Цель

Последовательно интегрировать три source adapters Сатурна с существующим retrieval и grounded answer foundation, сохраняя проверяемое происхождение данных и per-revision policy.

Реализация выполняется только после утверждения архитектуры владельцем. Основная работа и архитектурное управление остаются в ChatGPT. Codex получает только небольшие задачи с точным scope, исходным commit, тестами, критериями PASS/FAIL и условиями остановки.

## 2. Что не входит в этот план

- Любые изменения UkWood/Saturn-Main-Site.
- Изменение /search/ или /service/search/.
- Массовое сканирование старого файлового сервера.
- Ingestion UNKNOWN/pending/revoked sources.
- Передача материалов внешнему LLM без per-revision cloud approval.
- Выбор production LLM, model, region или бюджета.
- Production API, deployment, публичный widget и установка systemd timers до соответствующих gates.
- Админка, пользовательская регистрация, CRM, user memory и загрузка файлов пользователем.
- Автоматическое слияние PR #13 или PR #12.

## 3. Последовательность этапов

### Этап 0. Утверждение архитектуры

**Цель:** получить однозначное решение владельца по v0.2.

Deliverables:
- принятая матрица интеграции;
- принятый ADR-0012;
- принятая целевая архитектура;
- принятый implementation plan;
- зафиксированные open decisions и ограничения.

Acceptance:
- владелец подтвердил selective reuse вместо полного merge PR #13;
- подтверждены три adapters;
- подтверждены canonical Entity/Fact/Relation model;
- подтверждена per-revision approval policy;
- подтверждено разделение Support metadata и PDF evidence;
- подтверждено, что PR #12 V3 не включается автоматически;
- подтверждено, что PR #13 остаётся отдельной экспериментальной веткой до human assessment и отдельного решения об интеграции.

До этого этапа coding не начинается.

### Этап 1. Read-only schema audit и mapping

**Цель:** проверить реальную схему выбранного snapshot сайта и не проектировать адаптер по предположениям.

Работы:
1. Получить актуальный HEAD Saturn-Main-Site только чтением.
2. Выбрать и зафиксировать exact commit для mapping; исторический 084d759... из inventory v0.1 не считать автоматически актуальным.
3. Проверить src/content.config.ts и реальные примеры каждой используемой collection.
4. Проверить нужные src/data/*.yaml dictionaries.
5. Сопоставить schema fields с Entity/Fact/Relation/SupportDocument.
6. Отдельно проверить draft, status, systems.kind, product software groups, documents/certificates, reverse links.
7. Составить mapping table с обязательными, optional, unknown и unsupported fields.
8. Сохранить hash каждого просмотренного source file и ссылку на commit/path в AI-репозитории.

Deliverable:
- site schema mapping document;
- read-only audit manifest;
- список fixtures, которые потребуются для adapter tests.

Acceptance:
- все импортируемые поля имеют явный mapping;
- software/category/system distinctions подтверждены реальными данными;
- ни одна relation не создаётся по совместному упоминанию;
- все неизвестные/неподдержанные поля явно перечислены;
- ни одной операции записи в Saturn-Main-Site.

Этот этап выполняется в ChatGPT как read-only исследование и документация. Codex не нужен, пока mapping не утверждён.

### Этап 2. Canonical contracts и per-revision policy

**Цель:** определить проверяемые типы данных и запретить неявное наследование approval.

Scope будущей coding task:
- SourceIdentity и SourceRevision;
- Entity, Fact, Relation;
- SupportDocument и DocumentRevision;
- EvidenceUnit и Citation reference contracts;
- allowed_usage semantics;
- revision identity and approval checks;
- validation and serialization tests.

Acceptance:
- идентичность source отделена от revision;
- revision hash является частью approval scope;
- default deny;
- local_index, local_generate и cloud_generate различаются;
- новый hash получает pending и не попадает в active snapshot;
- revoke немедленно блокирует использование;
- старые synthetic contracts продолжают проходить без изменения поведения.

Остановка:
- если изменение требует переписывания legacy ingestion/retrieval contracts или замены policy semantics, остановиться и вынести отдельный ADR.

### Этап 3. Site Content Adapter

**Цель:** импортировать структурированные записи и словари из exact Git snapshot.

Scope:
- pinned commit reader с read-only access;
- Markdown/frontmatter parser;
- schema-aware collection mapping;
- dictionaries;
- draft filtering;
- entities/facts/relations;
- source path/hash/field provenance;
- deterministic output manifest.

Acceptance:
- повторный импорт одного commit даёт идентичный canonical package;
- изменение одного файла меняет только соответствующую source revision и зависимые projections;
- draft=true исключён;
- System и Category различаются;
- Software остаётся semantic subtype Product;
- исходные значения, units и qualifiers сохранены;
- relation record содержит точное исходное поле;
- unresolved relation не превращается в выдуманную связь;
- site repository открыт только для чтения.

### Этап 4. Support Catalog Adapter

**Цель:** построить отдельный каталог документов из approved documents/certificates.

Scope:
- extraction metadata из разрешённых products/systems;
- document type/section/version;
- exact original URL and checked canonical URL;
- owner links;
- deduplication with multiple owners;
- provenance на исходное поле.

Acceptance:
- один URL с несколькими владельцами возвращается одной document record со всеми owners;
- исходный URL не реконструируется из guessed directory;
- metadata result явно имеет evidence type support_metadata;
- metadata-only record не может попасть в technical answer claim как доказательство содержимого PDF;
- новая версия карточки требует отдельного approval.

### Этап 5. External Document Adapter

**Цель:** загружать и извлекать только отдельно допущенные файлы.

Scope:
- exact URL allowlist;
- bounded HTTPS fetch;
- redirect/DNS/private-address checks;
- size/time/page limits;
- content type validation;
- SHA-256 of raw bytes;
- isolated PDF worker;
- page-aware extraction;
- table/heading quality flags;
- OCR/manual review states.

Acceptance:
- URL из user question никогда не инициирует fetch;
- pending/revoked PDF не скачивается для ingestion и не передаётся LLM;
- изменившийся bytes hash создаёт новую pending revision;
- физические страницы сохраняются;
- extraction failure не выдаётся за пустой валидный документ;
- все limits и failure states тестируются;
- исходный PDF и его provenance связаны с Support Catalog owner records.

OCR не выбирается автоматически: сначала измерить качество на одобренных PDF, затем вынести отдельное решение при необходимости.

### Этап 6. Unified Knowledge Snapshot и atomic publication

**Цель:** собрать три канала в один согласованный, immutable и проверяемый snapshot.

Scope:
- canonical package validation;
- source revision manifest;
- approval/policy revision;
- structured facts/relations;
- Support Catalog;
- extracted document chunks;
- content-addressed artifacts;
- atomic build/promotion;
- live revocation.

Acceptance:
- каждый evidence object разрешается в source revision/hash;
- unapproved source отсутствует в active snapshot/index;
- partial build никогда не становится active;
- failed refresh не повреждает last known-good artifacts;
- live revoke блокирует источник даже при наличии старого snapshot;
- health/staleness не маскируется под успешный ответ;
- повторный build одинаковых входов воспроизводим.

### Этап 7. Channel-aware retrieval

**Цель:** объединить поиск без смешения типов доказательств.

Scope:
- site structured evidence retrieval;
- PDF full-text retrieval;
- Support metadata lookup;
- BM25/dense/RRF для сопоставимых answer evidence;
- channel traces;
- reranking только после calibration;
- explicit relation lookup/expansion.

Acceptance:
- document metadata matches отделены от answer evidence;
- запрос сохраняется без потери negation/qualifiers/units/designation;
- relation evidence содержит source field provenance;
- каждый candidate проходит policy filter до и после retrieval;
- метрики считаются по каналам и совместно;
- правильный source/evidence попадает в Top-5 минимум для 90% положительных retrieval cases пилотного набора;
- synthetic и real-sample reports не смешиваются.

### Этап 8. Grounded answer integration

**Цель:** связать canonical evidence с bounded generation и backend verification.

Scope:
- original question contract;
- atomic claims;
- typed evidence pointers;
- exact quotes для text chunks;
- field/value checks для structured facts;
- relation identity checks;
- numeric/unit/qualifier checks;
- completeness and relevance verification;
- partial/clarification/needs_support/error statuses;
- backend-generated citations;
- final live policy check.

Acceptance:
- все claims имеют evidence pointers;
- source/entity/unit/qualifier mismatch отвергается;
- LLM не задаёт URL/page/source metadata;
- неполный ответ не выдаётся за полный;
- конфликт не разрешается догадкой;
- revoked evidence удаляется до rendering;
- инфраструктурная ошибка не маскируется под needs_support;
- человеческая оценка остаётся обязательной для answer quality.

Перед использованием PR #13 application в pilot необходимо отдельно завершить human assessment его 15 diagnostic cases и зафиксировать findings. Этот review не заменяет новый site-specific benchmark.

### Этап 9. Site-specific pilot corpus и независимая evaluation

**Цель:** измерить реальную пригодность на примерно 10 approved source objects/documents.

Подготовка:
- владелец/ответственный выбирает source objects;
- каждый источник получает exact revision/hash и approval;
- PDF проверяется отдельно;
- создаётся calibration set;
- отдельно создаётся независимый blind set;
- frozen manifest и dataset hash фиксируются до запуска.

Acceptance по утверждённому v0.1:
- 24/24 positive cases — полностью корректные ответы;
- 16/16 negative/ambiguous cases — корректные отказы или уточнения;
- 0 unsupported technical claims;
- 100% корректность citations, source IDs, URLs, versions и PDF pages;
- false refusals и missed requested parts явно измерены;
- независимый reviewer не участвовал в tuning blind set.

Если gate не пройден, система не объявляется принятой. Запрещено компенсировать качество интерфейсом или более дорогой моделью.

### Этап 10. API и минимальный UI

**Цель:** предоставить standalone interface только после quality gates.

Scope:
- FastAPI endpoint;
- request/response schema;
- rate and size limits;
- CORS/HTTPS integration contract;
- отдельный static UI: input, answer, citations, clarification/refusal/error states;
- secrets только backend;
- no user accounts or memory.

Acceptance:
- API не выдаёт неподтверждённые данные;
- frontend не получает provider keys или direct Qdrant access;
- UI показывает provenance и PDF pages;
- ошибки provider и source policy видимы как отдельные состояния;
- security tests проходят.

### Этап 11. Закрытый технический пилот

Только после отдельного решения владельца и ответов ИТ:
- backend hosting;
- HTTPS reverse proxy/firewall/CORS/rate limits;
- backup/restore;
- monitoring/logging/privacy;
- CPU/RAM/latency/concurrency measurements;
- refresh/rollback/revocation runbook.

Публичный widget и любые изменения сайта не входят в этот этап автоматически.

## 4. Управление задачами Codex

Каждая будущая задача Codex оформляется отдельным brief по CHATGPT_WORKING_AGREEMENT:
- ID, цель, исходный branch/commit;
- ссылки на принятый ADR/spec/plan;
- точные разрешённые файлы;
- запрещённые файлы/репозитории;
- поведение и контракты;
- unit/integration/security tests;
- команды проверки;
- ожидаемый diff и отчёт;
- критерии PASS/FAIL;
- условия остановки.

Не передавать Codex весь план как одну задачу. Один bounded task — один reviewable PR или небольшой последовательный commit set.

Codex не получает права:
- менять архитектуру и source approvals;
- менять frozen datasets/reports;
- выбирать provider/model;
- выполнять real ingestion/cloud calls;
- менять Saturn-Main-Site;
- merge/deploy без прямого разрешения владельца.

## 5. Обязательные правила PR и проверки

- Новые работы идут в feature branch от актуального main.
- PR #13 не используется как base branch для v0.2.
- Не переносить исторические README/HANDOFF/PROJECT_STATUS из PR #13 поверх main.
- Проверять exact head SHA, changed files, diff, CI и review findings.
- Green CI — только техническая проверка, не answer acceptance.
- Не включать auto-merge.
- Merge — только после review и явного разрешения владельца.
- В конце этапа обновлять stage report, PROJECT_STATUS и HANDOFF с точными hashes и фактическими результатами.

## 6. Ближайший реальный шаг

После утверждения пакета v0.2 не писать сразу Site Content Adapter.

Сначала в ChatGPT выполнить Этап 1 — read-only schema audit:
1. проверить актуальный HEAD Saturn-Main-Site;
2. зафиксировать exact commit;
3. прочитать schema и representative source files;
4. составить mapping таблицу;
5. показать владельцу неизвестные и спорные поля;
6. только после утверждения mapping сформировать первую bounded coding task для canonical contracts.

Это сохраняет правило: сначала архитектура и ожидаемый результат, затем код.
