# План реализации AI Technical Consultant для Сатурна

Дата: 2026-11-09  
Статус: **ACCEPTED — implementation started under ADR-0012/0013**  
Основная среда архитектуры и контроля: ChatGPT. Codex — только ограниченные coding tasks.

## 1. Цель и границы

Создать независимого технического консультанта на основе доверенного содержимого UkWood/Saturn-Main-Site и PDF, на которые ссылается сайт.

- Сайт и его поиск остаются строго READ-ONLY.
- Весь код, индексы, конфигурация и тесты — только в UkWood/LLM-RAG-chat-bot.
- В MVP нет регистрации, пользовательской памяти, загрузки файлов, CRM, CMS или публичного widget.
- Доверие к источнику не означает автоматического разрешения отправлять его содержимое внешнему LLM: cloud egress согласуется отдельно.
- Отсутствующие тексты/иллюстрации на развивающемся сайте не трактуются как доказательство отсутствия функций.

## 2. Source sync и schema evolution

Каждый sync фиксирует exact main commit сайта и обнаруживает изменения content tree, Astro schema, dictionaries, routes и PDF links.

- Новые/изменённые записи и документы импортируются автоматически.
- Удалённые записи удаляются из активного snapshot.
- Новые простые поля и collections сохраняются в generic representation и доступны для поиска.
- Сложные/изменившие тип поля не интерпретируются старым typed mapping; adapter выдаёт drift report и требует технического обновления.
- Adapter/mapping/parser имеют версии; их изменения покрываются fixtures и contract tests.
- Новый snapshot проходит проверку целостности и публикуется атомарно.

## 3. Последовательность реализации

### Этап 1. Canonical contracts — COMPLETED (PR #18)

Добавлены immutable contracts: SiteSourceRevision, SiteEntity, SiteFact, SiteRelation, SupportDocument, PdfRevision, EvidenceUnit, schema inventory, drift events, file change set, sync manifest и sync plan. Provenance служит traceability, не approval. Старые synthetic contracts сохранены.

**PASS:** exact PR head CI SUCCESS — 192 offline tests (11 existing optional skips) + ONNX contracts. Merge commit: `223350c9f6f104b5b67aadd124bfc968f12f5dbf`. Stage report: [canonical contracts](../stages/2026-11-09-saturn-canonical-contracts.md).

### Этап 2. Site Content Adapter

Read-only импорт Markdown/frontmatter/YAML с динамическим discovery collections. Generic fallback для unknown collections/fields. System/Category distinction, Software subtype, все relations, specs и qualifiers.

**PASS:** fixtures для всех текущих collections; add/update/delete; новые поля/collections/dictionary values; schema fingerprint/drift report; неизвестные данные не теряются; повторный import одного snapshot детерминирован.

### Этап 3. Support Catalog и PDF Adapter

Автоматически собирать документы и certificates, сохранять всех owners, загружать trusted PDF links по configured host/path allowlist, hash и физические страницы.

**PASS:** несколько owners; дедупликация без потери metadata; изменение bytes запускает re-extraction; fetch/parser errors не превращаются в пустой документ; SSRF/redirect/size/time limits тестируются.

### Этап 4. Unified Snapshot и retrieval

Объединить structured facts/relations, site passages, support metadata и PDF passages. Сохранить отдельные каналы поиска и canonical evidence IDs. Переиспользовать BM25/Qdrant/RRF и оценивать reranker отдельно.

**PASS:** metadata-only match не доказывает PDF content; каждый candidate имеет source provenance; build воспроизводим; частичный build не становится active.

### Этап 5. Grounded answer и evaluation

Bounded question → retrieval → typed evidence → generation → backend verification → citations. Отдельно проверять field values, relations, units, qualifiers, physical PDF pages и completeness.

**PASS:** claims имеют evidence; backend формирует citations; ошибки инфраструктуры не маскируются под отказ; synthetic и real evaluation не смешиваются; независимая оценка answer quality проходит согласованные критерии.

### Этап 6. API и минимальный UI

FastAPI и простой интерфейс: одно поле ввода, ответ, ссылки на страницы/PDF, уточнения и ошибки. Production hosting и внешний provider — отдельные решения.

## 4. Правила разработки и приёмки

- Одна bounded задача — один небольшой reviewable PR.
- В каждом Codex brief: исходный SHA, разрешённые файлы, ожидаемое поведение, тесты, команды и PASS/FAIL.
- Codex не меняет архитектуру, site repo, frozen datasets, provider settings и deployment; не выполняет merge.
- Проверять diff, exact head SHA, CI и все tests. Green CI не является доказательством качества инженерных ответов.
- Merge выполняется только после review и явного разрешения владельца.
- Не создавать отдельный документ на каждый этап: решения — в ADR, текущая работа — в PROJECT_STATUS/HANDOFF, детали — в коде и тестах.

## 5. Ближайшая задача: Site Content Adapter

Реализовать отдельный pure/offline adapter, который принимает immutable pinned snapshot (repository/branch/commit/tree SHA + source paths/blob SHA/bytes) и строит canonical Saturn content package.

- Динамически обнаруживать все `src/content/<collection>/*.md`; не зашивать список collections.
- Safe YAML frontmatter parsing без исполнения Astro/TypeScript/JS.
- Сохранять исходный frontmatter и Markdown body; каждое поле, включая неизвестное, представлять как raw fact.
- Явно различать известные entity types и generic `SiteContent`; применять правила из read-only schema audit.
- Сохранять только source-declared relations с исходным predicate/field path; `pages.groups` — навигация, не состав системы.
- Строить schema inventory, dictionary fingerprints, file diffs и deterministic manifest через PR #18 contracts.
- Parser не выполняет сеть и не загружает PDF. Git snapshot provider, Support Catalog/PDF и retrieval — последующие отдельные этапы.

**PASS:** fixtures всех шести текущих collections; unknown collection/fields; draft behavior; nested values/specs/qualifiers; explicit relations; add/update/delete/schema drift; deterministic output; полный regression suite + CI; нулевые изменения Saturn-Main-Site.

Текущий coding handoff и критерии разделения двух ChatGPT-сессий: [HANDOFF.md](../HANDOFF.md), [CHATGPT_SESSION_GUIDE.md](../CHATGPT_SESSION_GUIDE.md).
