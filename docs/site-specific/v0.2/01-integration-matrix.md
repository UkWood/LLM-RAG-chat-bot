# Матрица интеграции PR #13 с site-specific v0.1

Дата: 2026-11-08  
Статус: **ACCEPTED BASELINE — owner approved PR #16**  
Сравниваемые точки:
- main: 3cd6787db2fe00fd7cea49bce8a355a27f292bf0;
- PR #13 head: 24a8409b7d5fb65d9f5144019f87f5d1bc75df0c;
- утверждённая архитектура: site-specific v0.1 в main.

## 1. Краткий вывод

PR #13 — содержательная экспериментальная реализация общего publication pipeline и grounded RAG. Она даёт потенциально полезные fetch/extract/store/refresh, hybrid retrieval, reranking, provider, answer verification и diagnostics.

Однако PR #13 не является готовой реализацией site-specific v0.1. Его основной источник — опубликованные HTML/PDF, тогда как Сатурну необходимы три самостоятельных адаптера:

1. структурированный контент Git snapshot сайта;
2. метаданные Support catalog из documents/certificates;
3. полнотекстовое содержимое отдельно допущенных внешних документов.

Поэтому рекомендуемый путь — **selective reuse**: переиспользовать проверенные общие компоненты после адаптации контрактов и policy, не сливать PR #13 целиком и не переносить его ветку механически.

## 2. Что важно учитывать в Git

PR #13:
- открыт, Draft, не слит;
- head 24a8409b7d5fb65d9f5144019f87f5d1bc75df0c;
- base указывает на старый main bb16530e5b9a4943abae5c1b0f526cb218f46b2d;
- текущий main продвинулся до 3cd6787db2fe00fd7cea49bce8a355a27f292bf0;
- compare показывает 19 commits ahead и 1 behind, статус diverged;
- GitHub сообщает mergeable=false;
- PR затрагивает README, HANDOFF и PROJECT_STATUS, которые после ответвления уже изменялись в main;
- PR #13 содержит собственный ADR-0011 с тем же номером, что и принятый site-source ADR-0011 в main. При будущей выборочной интеграции ADR из PR #13 нельзя переносить с прежним номером.

Текущие точные head CI PR #13 завершились SUCCESS: push run 42338488688 и PR run 42338493197. Это подтверждает технические проверки ветки, но не answer quality и не архитектурное соответствие v0.1.

## 3. Матрица существующих компонентов

| Компонент | Где существует | Текущее назначение | Решение v0.2 | Необходимое действие |
|---|---|---|---|---|
| ingestion contracts | main, backend/src/saturn_ai/ingestion/ | Базовые контракты и проверки ingestion | Переиспользовать как основу | Расширить каноническими Entity, Fact, Relation и provenance; не ломать старые контракты |
| snapshots | main, backend/src/saturn_ai/snapshots.py | Проверяемый snapshot и индексные контракты | Переиспользовать концепцию и совместимые части | Ввести richer KnowledgeSnapshot с manifest источников, revisions, policy и структурированными данными |
| retrieval contracts | main, backend/src/saturn_ai/retrieval/contracts.py | Candidate, trace и представление passage | Переиспользовать | Сохранить тип evidence и source channel без потери совместимости старого synthetic пути |
| BM25 | main, backend/src/saturn_ai/retrieval/lexical.py | Детерминированный локальный лексический поиск | Переиспользовать | Индексировать текстовые проекции структурированных фактов, relations и document chunks с сохранением canonical evidence IDs |
| Qdrant dense index | main, backend/src/saturn_ai/retrieval/dense.py | Локальный vector retrieval | Переиспользовать после проверки | Векторизовать только разрешённые evidence projections; не подменять structured facts обычным неразмеченным текстом |
| Hybrid retrieval / RRF | main, backend/src/saturn_ai/retrieval/service.py | Объединение lexical и dense кандидатов | Переиспользовать ядро | Добавить channel-aware orchestration; не смешивать metadata-only document matches с техническими evidence |
| Local reranker | main, backend/src/saturn_ai/retrieval/reranker_model.py и evaluation bundle | CPU reranking | Переиспользовать как экспериментальный компонент | Повторно измерить на site-specific calibration corpus; не переносить synthetic quality claim на Сатурн |
| Publication fetcher | только PR #13, publication/fetch.py | HTTP fetch и запрет redirects | Переиспользовать транспортные safeguards | Получать точные URL из доверенного Support Catalog; crawler не является источником фактов |
| Publication policy | только PR #13, publication/policy.py | Site root, PDF origins, общие лимиты и cloud flag | Частично переиспользовать | Использовать trust root сайта; отдельно сохранить runtime egress policy для внешнего provider |
| HTML extractor | только PR #13, publication/extract.py | Извлечение текста опубликованного HTML | Не использовать как основной Site Content Adapter | Структурированный импорт делать из Git snapshot и схемы Markdown/frontmatter/YAML |
| PDF extraction worker | только PR #13, publication/pdf_worker.py и extract.py | Изолированное извлечение PDF и физических страниц | Переиспользовать после review | Добавить extraction quality report, таблицы/heading anchors и явное состояние OCR_REQUIRED |
| Published snapshot | только PR #13, publication/snapshot.py | Immutable snapshot HTML/PDF sources | Переиспользовать идею | Расширить до общего snapshot трёх каналов, сохраняя типы и provenance |
| Publication store | только PR #13, publication/store.py | Версионирование, content-addressed storage, atomic state | Переиспользовать после review | Хранить source revisions, hashes, trust-policy version и snapshot manifest; hash служит traceability, не approval |
| Publication refresh | только PR #13, publication/refresh.py | Manual/daily refresh опубликованных страниц и PDF | Адаптировать | Разделить discovery, fetch, build и atomic promotion; изменение hash автоматически запускает re-ingestion |
| OpenAI-compatible provider | только PR #13, rag/provider.py | Конфигурируемый chat-completions client и строгая JSON-валидация | Переиспользовать интерфейс и transport checks | Не фиксировать Qwen/DeepSeek или endpoint до отдельного решения; секреты только в runtime environment |
| Grounded answer application | только PR #13, rag/application.py | Retrieval → generation → verification → backend citations | Кандидат на основное answer ядро | Сохранить bounded flow, адаптировать evidence contracts и проверить результаты независимой human assessment |
| RAG contracts/runtime | только PR #13, rag/contracts.py и rag/runtime.py | Answer/Citation contracts и проверка persisted indexes | Переиспользовать после адаптации | Привязать Answer и Citation к unified snapshot, typed evidence и актуальной per-revision policy |
| Operator CLI | только PR #13, rag/__main__.py и publication/__main__.py | Ручной refresh и ask smoke | Переиспользовать как внутренний инструмент | Сохранить operator-only границу; не превращать CLI в публичный API |
| RAG diagnostics | только PR #13, evaluation/rag_diagnostic.py | retrieval/oracle/end-to-end diagnostics | Переиспользовать harness | Разделять synthetic diagnostics, calibration и independent blind evaluation |
| PR #13 diagnostic dataset/reports | только PR #13, evaluation/datasets и evaluation/reports | Исторические synthetic cases и результаты | Сохранить неизменными | Не редактировать и не объявлять независимой приёмкой site-specific продукта |
| Human review forms | только PR #13, evaluation/reviews | SHA-bound формы оценки 15 ответов | Использовать для отдельного review | Заполнить человеком; пустые/null оценки не являются успехом |

## 4. Компоненты, которых не хватает для v0.1

| Требуемый компонент | Наличие в PR #13 | Что нужно разработать |
|---|---|---|
| Site Content Adapter | Нет полноценного структурированного адаптера | Чтение точного Git snapshot, Markdown/frontmatter и YAML словарей; mapping коллекций |
| Entity model | Только generic source/chunk identity | Канонические Device/Product, System, Category, Software, Group, Article, Solution, News, Page |
| Fact model | Технический текст в chunks | Отдельные факты с field path, raw value, units, qualifiers и provenance |
| Relation model | Нет полноценной typed relation graph | Явные связи из исходных полей; обратные проекции только с сохранением исходного поля |
| Support Catalog Adapter | Нет самостоятельного metadata adapter | Импорт documents/certificates, version/type/URL/owners, URL deduplication с сохранением всех owners |
| External Document Adapter | PDF обнаруживается через HTML crawler | Загрузка только явно разрешённых файлов из Support Catalog по exact allowlist |
| Trusted source policy and revision manifest | Недостаточно: общая publication policy | Trust root + exact source revision/hash для traceability; отдельный cloud egress permission |
| Unified Knowledge Snapshot | Generic PublishedSnapshot | Единый immutable snapshot для entities, facts, relations, catalog metadata и PDF evidence |
| Channel-aware retrieval | Есть lexical/dense hybrid, но нет трёхканального разделения | Разделить answer evidence retrieval и metadata-only document lookup |
| Structured evidence/citations | Преимущественно chunk quotes | Evidence pointer на Fact/Relation/DocumentChunk; backend citation с field/page/URL/hash |
| Source change reconciliation | Есть generic refresh | Изменение commit/path/hash автоматически запускает sync; удалённые записи исчезают из active snapshot |
| Site-specific benchmark | Нет real Saturn corpus | Calibration и blind sets по доверенным реальным источникам |

## 5. Ключевые расхождения и решения

### 5.1. HTTP crawler против Git snapshot

PR #13 начинает с опубликованных HTML-страниц и обнаруженных ссылок. Это полезно для generic publication pipeline, но не извлекает структурированную модель сайта с нужной точностью.

Для Сатурна authoritative input — зафиксированный read-only Git snapshot: commit + path + content hash. HTML-crawler не является источником фактов, relations или approval.

### 5.2. Автоматическое обновление и revisions

PR #13 допускает generic refresh опубликованных материалов. Для Сатурна authoritative input — read-only Git snapshot и ссылки доверенного Support Catalog.

- Любой новый commit main автоматически становится источником следующего sync.
- Изменение content hash создаёт новую immutable revision для traceability и автоматически запускает re-ingestion.
- Новые записи/поля/collections добавляются; удалённые исчезают из active snapshot.
- Никакого pending/approval состояния для новой revision нет.
- Прежние revisions сохраняются в истории snapshot/citations, но не подменяют актуальное содержимое.
- Operational block может временно запретить fetch/использование по техническим причинам; это не content review.

### 5.3. Один generic chunk против разных типов знаний

Обычный chunk подходит для текста PDF и описаний, но не должен быть единственным представлением изделия.

Нужно хранить canonical entity/fact/relation records. Для BM25/vector допускается строить их текстовые projections, но выдача должна возвращать исходный typed evidence object и его provenance.

### 5.4. Support Catalog не равен PDF full text

Support Catalog отвечает на вопрос «какой документ нужен и к чему он относится?». PDF text — отдельный answer-evidence channel.

PDF-ссылки из documents/certificates и Markdown body доверенных non-draft записей автоматически попадают в каталог и запускают fetch/extraction по configured trusted origin/path allowlist. Отдельного approval файла или его revision нет. Metadata-only match не доказывает содержание PDF; технически не извлечённый файл не представляется как text evidence.

### 5.5. Planner V3 не принимается автоматически

PR #12 показал 2/24 положительных blind outcomes при 16/16 отрицательных/неоднозначных. Не использовать его как готовый query planner. Начать с fan-out retrieval по релевантным каналам и явных evidence types. Новый planner — отдельная гипотеза с calibration и новым независимым evaluation.

## 6. Рекомендуемая стратегия интеграции

1. Сначала утвердить архитектуру и revision policy.
2. Провести read-only schema audit актуального выбранного commit Saturn-Main-Site.
3. Зафиксировать канонические contracts и mapping.
4. Реализовать три адаптера по отдельности на synthetic fixtures.
5. Объединить их в unified Knowledge Snapshot.
6. Только после допуска владельцем подключить ограниченный real pilot corpus.
7. Переиспользовать BM25/Qdrant/reranker и grounded answer application после selective port и отдельных тестов.
8. Выполнить site-specific retrieval и answer evaluation.
9. Только после quality gates переходить к API/UI и закрытому пилоту.

## 7. Запреты при интеграции

- Не сливать PR #13 целиком.
- Не rebase/merge PR #13 автоматически.
- Не переносить его README/HANDOFF/PROJECT_STATUS поверх актуальных файлов main.
- Не переносить PR #13 ADR-0011 под тем же номером; ADR-0011 main сохраняется.
- Не включать PR #12 V3 по умолчанию.
- Не переносить synthetic benchmark labels в site-specific datasets.
- Не менять frozen reports, START manifests и consumed datasets.
- Не включать реальные источники, cloud или deployment.
- Не писать в Saturn-Main-Site.

## 8. Условие закрытия матрицы

Матрица считается согласованной после подтверждения владельцем:
- selective reuse вместо полного merge PR #13;
- трёх отдельных adapters;
- canonical Entity/Fact/Relation model;
- доверенного source root без ручного content/relation/PDF approval;
- автоматической синхронизации и schema-drift handling;
- разделения Support metadata и PDF text evidence;
- отдельного cloud data-egress permission;
- запрета на автоматическое слияние PR #13 и PR #12.

