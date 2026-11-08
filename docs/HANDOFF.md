# Передача контекста — реализация кода

Дата: 2026-11-09  
Основной репозиторий: [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot)  
Текущий main: \`223350c9f6f104b5b67aadd124bfc968f12f5dbf\`

## 1. Текущий статус

- PR #17: принят и слит. ADR-0012/0013 и архитектура доверенного источника/schema evolution согласованы.
- PR #18: принят и слит в main. Реализованы канонические контракты и pure schema-evolution primitives.
- CI PR #18: SUCCESS — 192 теста, 11 существующих optional skips; ONNX contracts SUCCESS.
- Следующий этап: Site Content Adapter. Реальный sync, PDF fetch, retrieval integration и deployment ещё не реализованы.

## 2. Решения владельца — обязательны

- Trust root: \`UkWood/Saturn-Main-Site\`, branch \`main\`.
- Все non-draft записи сайта, объявленные сайтом связи, справочники и прямые PDF-ссылки из documents/certificates или Markdown body доверенные. Ручная проверка/approval не нужна.
- \`draft: true\` исключается из публичного corpus.
- Сайт строго READ-ONLY: не менять его файлы, ветки, URL, assets, CI или поиск.
- Изменения сайта автоматически синхронизируются; commit/hash нужны для воспроизводимости и citations, а не approval.
- Новые поля/collections сохраняются как generic evidence; несовместимые типы не интерпретируются старым mapping, а дают drift report.
- PDF обрабатываются автоматически по доверенным ссылкам, но только с технической HTTPS host/path allowlist, SSRF/redirect и resource-limit защитой.
- Cloud data egress к внешней LLM — отдельное решение; source trust его не разрешает.
- ChatGPT — основная среда проектирования, реализации и review. Codex — только для ограниченных рутинных coding tasks по точному brief.

## 3. Реализовано в main

Новые модули PR #18:
- \`backend/src/saturn_ai/ingestion/saturn_contracts.py\` — immutable SiteSourceRevision, SiteEntity, SiteFact, SiteRelation, SupportDocument, PdfRevision, EvidenceUnit, schema and sync manifest contracts.
- \`backend/src/saturn_ai/ingestion/schema_evolution.py\` — observed schema inventory, collection/field/type/dictionary drift, file add/change/delete diff, deterministic manifest and sync plan.
- Tests: \`backend/tests/unit/test_saturn_contracts.py\`, \`backend/tests/unit/test_saturn_schema_evolution.py\`.

Это фундаментальные contracts, не полноценный adapter. Они не читают GitHub и не импортируют реальный сайт.

## 4. Важная граница с прежним ingestion

Существующие \`site.py\`, \`registry.py\`, \`pipeline.py\`, \`contracts.py\` обслуживают прежний synthetic/fixture ingestion path. В нём есть фиксированные collections и per-source approval contracts.

**Не удалять и не ослаблять эти approval gates глобально. Не пытаться подключить доверенный Saturn main через старый SourceRecord/Registry.** Новая Saturn-интеграция должна идти отдельным путём на основе \`saturn_contracts.py\` и собственных adapter contracts. Существующие synthetic tests и historical evaluation должны продолжать работать без регрессий.

## 5. Следующая bounded coding task

Реализовать первый вертикальный срез **Site Content Adapter**, который принимает уже полученный immutable/pinned snapshot (commit, tree SHA, path → bytes/blob SHA) и не выполняет сетевых запросов сам.

Обязательное поведение:
1. Динамически обнаруживать все Markdown files в \`src/content/<collection>/\`, не использовать статический allowlist коллекций.
2. Разбирать frontmatter безопасным YAML loader без исполнения Astro/TypeScript/JS; сохранять raw frontmatter и Markdown body без потерь.
3. Пропускать только записи с явным \`draft: true\`; отсутствующее поле не считать draft.
4. Известное текущее mapping брать из \`docs/site-specific/v0.2/04-read-only-schema-audit.md\`; новые collections → generic \`SiteContent\`.
5. Сохранять каждое поле как raw fact (включая неизвестные поля, массивы, порядок, единицы и qualifiers); не выдумывать defaults и отрицательные утверждения.
6. Применять только явно объявленные relation mappings. Не выводить совместимость из co-occurrence. \`pages.groups\` — навигационная структура, не состав инженерной системы.
7. Software — subtype products; \`systems.kind=category\` — Category; \`pages.kind=solution/section\` должны различаться.
8. Строить source revisions, schema inventory, dictionary fingerprints и deterministic sync manifest через contracts PR #18.
9. Parser должен быть pure/offline и детерминированным. Ошибка одной записи должна быть диагностирована; решение о fail/skip и атомарной публикации не должно приводить к потере raw data.
10. Не подключать PDF download/parser, retrieval, LLM/provider, API/UI или deployment в этом PR.

Первый PR может включать parser + mapping + fixtures/contract tests. Источник GitHub/read-only snapshot provider — отдельный следующий шаг, если он не помещается в небольшой reviewable PR.

## 6. Критерии приёмки следующего PR

- Unit fixtures покрывают все шесть текущих collections: products, systems, groups, articles, news, pages.
- Проверены Software, System/Category, Solution/SectionPage, draft/ordinary records.
- Неизвестная collection и неизвестные nested fields сохраняются.
- Проверены explicit relations и отсутствие ложной инженерной связи из navigation fields.
- Проверены add/update/delete и schema drift на входных pinned snapshots.
- Повторная обработка одинакового snapshot и версий adapter/mapping даёт идентичный canonical output.
- Нет network access, PDF fetch, provider calls и изменений Saturn-Main-Site.
- Все существующие tests + новые tests проходят; CI зелёный.
- PR описывает exact input SHA, файлы, команды, фактические результаты и ограничения.

## 7. Как работать в новой сессии

Новая сессия предназначена для **реализации кода**. Текущая сессия остаётся архитектурной и управляющей: здесь согласуются изменения модели, ADR, scope, критерии и принимаются результаты review.

Новая сессия должна прочитать:
1. \`AGENTS.md\`
2. \`README.md\`
3. \`docs/PROJECT_STATUS.md\`
4. этот файл
5. \`docs/CHATGPT_SESSION_GUIDE.md\`
6. \`docs/decisions/0012-saturn-knowledge-integration.md\` и \`0013-saturn-relation-provenance.md\`
7. \`docs/site-specific/v0.2/02-architecture.md\`, \`03-implementation-plan.md\`, \`04-read-only-schema-audit.md\`
8. два новых canonical modules и tests PR #18.

Не загружать весь исторический архив stage reports без конкретной необходимости. Не менять архитектуру/ADR самостоятельно. При конфликте реализации с утверждёнными решениями — остановиться и вынести короткий вопрос в архитектурную сессию.

PR создаётся в отдельной feature branch. Merge — только после review и отдельной команды владельца.
