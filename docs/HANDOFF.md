# Передача контекста — реализация кода

Дата: 2026-11-09  
Основной репозиторий: [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot)  
Текущий завершённый этап: Saturn Site Content Adapter, [PR #20](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20)  
Статус PR #20: **MERGED**  
Кодовый head PR: `9b36551adf61070426caa9250650bb32d638a66a`  
Merge commit в main: `361529963bd48772f0d9d478dfb3b963ec5a8d03`  
Base commit до PR #20: `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`

## 1. Текущий статус

- PR #20 — trusted Saturn Site Content Adapter — слит в main. Реализация и проверки описаны ниже.
- Snapshot Provider architecture contract v0.1 и ADR-0014 приняты владельцем и опубликованы в документационном PR #21: https://github.com/UkWood/LLM-RAG-chat-bot/pull/21. PR открыт, не слит.
- PR #21: branch docs-snapshot-provider-contract-2026-11-09; base c1840b071e077ae6019f1b9e7930c3aa15d08ef3.
- Current PR head `0f2a1226b757ae346d65b05df13be657e3581d35` passed PR-head CI [#42624653260](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624653260) and push CI [#42624644980](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624644980). Both runs completed `offline-checks` and `onnx-contracts` successfully on this exact head.
- Git REST API выбран основным транспортом: GitHub — первая реализация, Gitea — последующая реализация того же provider-neutral контракта.
- Provider один раз разрешает refs/heads/main, фиксирует commit/tree и далее читает только по immutable object IDs. Повторного обращения к moving branch в рамках sync нет.
- Provider доверен в отношении ref → commit → tree identity mapping и полноты перечисления дерева; независимая криптографическая проверка raw commit/tree objects не заявляется.
- Каждый выбранный blob проверяется по canonical Git object hash с учётом object format репозитория; raw content SHA-256 хранится отдельно. Текущие canonical contracts поддерживают SHA-1; другие object formats требуют отдельного изменения contracts/adapter.
- Обычный snapshot содержит только необходимые Markdown/YAML/schema/Astro route/config файлы; массовая загрузка бинарных assets исключена.
- PDF остаются обязательной частью корпуса и обрабатываются через Support Catalog Adapter и External Document Adapter. Будущий выборочный Git-blob путь зарезервирован, но не реализован.
- GitHub/Gitea Provider, PDF ingestion, Git-backed PDF retrieval, retrieval integration, LLM/provider, API/UI и deployment не реализованы.
- Saturn-Main-Site остаётся строго READ-ONLY.


## 2. Решения владельца — обязательны

- Stable trusted logical source ID: `UkWood/Saturn-Main-Site`, branch `main`. Snapshot Providers отображают свои физические GitHub/Gitea remotes и namespace на этот ID; адрес провайдера не входит в контракт адаптера.
- Snapshot Provider использует Git REST API: GitHub — первая реализация, Gitea — последующая реализация того же provider-neutral контракта.
- Gitea tree pagination and commit-SHA/tree-SHA behavior must pass version-specific conformance tests; unsupported behavior fails closed. src/pages route-source allowlist is `.astro` and `.ts`, other types create drift diagnostics.
- Gitea provider обязан обрабатывать `page`/`per_page` и сверять все страницы по `page`, tree `sha`, `total_count` и уникальности entries. Документация Gitea описывает входной `sha` как commit SHA, а текущий upstream код принимает commit или tree ID; прямой tree-SHA lookup проверяется на точной версии целевого сервера. При несовместимости — recursive pagination по закреплённому commit SHA, иначе явная ошибка.
- `refs/heads/main` разрешается один раз на sync. После pinning все операции выполняются только по immutable commit/tree/blob IDs; повторной проверки подвижной ветки в той же sync нет.
- Git provider является trust source для ref → commit → tree identity mapping и полноты tree enumeration. Независимая криптографическая проверка raw commit/tree objects не заявляется.
- Каждый выбранный blob проверяется по canonical Git object hash с учётом object format репозитория; raw content SHA-256 хранится отдельно. Текущие canonical contracts поддерживают SHA-1; другой формат требует отдельной versioned эволюции contracts/adapter.
- Snapshot ограничен Markdown collections, YAML dictionaries, content schema, Astro routes и утверждёнными route/config dependencies; unrelated binary assets не скачиваются массово. Для `src/pages/` поддерживаются только `.astro` и `.ts` (не `.d.ts`); неизвестное расширение вызывает route-source drift и fail-closed. Read-only baseline Saturn-Main-Site на commit `084d759487bfab6e111549c9b5469711ac5fc13e`: 23 файла, 19 `.astro`, 4 `.ts`.
- PDF остаются обязательной частью knowledge corpus: discovery/cataloguing — Support Catalog Adapter, fetch/extraction — External Document Adapter. Будущий selective Git-blob retrieval допускается по pinned commit/path/blob SHA, но сейчас не реализуется.
- Все non-draft записи сайта, объявленные сайтом связи, справочники и прямые PDF-ссылки из documents/certificates или Markdown body доверенные. Ручная проверка/approval не нужна.
- `draft: true` исключается из публичного corpus.
- Сайт строго READ-ONLY: не менять его файлы, ветки, URL, assets, CI или поиск.
- Изменения сайта автоматически синхронизируются; commit/hash нужны для воспроизводимости и citations, а не approval.
- Новые поля/collections сохраняются как generic evidence; несовместимые типы не интерпретируются старым mapping, а дают drift report.
- PDF обрабатываются автоматически по доверенным ссылкам, но только с технической HTTPS host/path allowlist, SSRF/redirect и resource-limit защитой.
- Cloud data egress к внешней LLM — отдельное решение; source trust его не разрешает.
- ChatGPT — основная среда проектирования, реализации и review. Codex — только для ограниченных рутинных coding tasks по точному brief.

## 3. Реализовано в PR #20 и включено в main

Новый модуль: `backend/src/saturn_ai/ingestion/saturn_site_adapter.py`.

- Принимает immutable `PinnedSiteSnapshot`: trust root, branch, commit SHA, tree SHA и отсортированные файлы с Git blob SHA + исходными bytes. Blob SHA проверяется по точным байтам.
- `PinnedSiteSnapshot.repository` — стабильный logical source ID (`UkWood/Saturn-Main-Site`), а не физический Git remote URL.
- Динамически обнаруживает Markdown collections под `src/content/<collection>/`; словари `src/data/*.yaml|yml` и `src/content.config.ts` включаются в manifest/fingerprints.
- `src/content.config.ts` только fingerprint-ится — Astro/TypeScript/JS не исполняются.
- Safe YAML: YAML 1.2 boolean semantics, запрет anchors/aliases/explicit tags, duplicate keys и non-string keys; ограничены размер, token count, depth и node count.
- Raw bytes, raw frontmatter text и Markdown body сохраняются. Неизвестные поля и вложенные значения становятся raw facts; неизвестные collections — `SiteContent`.
- Явные relations берутся только из проверенной схемы. `pages.groups` остаётся navigation data, а не инженерной связью.
- Для `systems.kind` при отсутствии поля применяется только объявленный в source schema default `system`; явное неизвестное значение остаётся generic `SiteContent` с warning. Для `pages.kind` отсутствие значения означает `Page`, известные `solution`/`section` отображаются явно, неизвестное значение остаётся generic `SiteContent`.
- Используются PR #18 contracts: source revisions, schema inventory, dictionary fingerprints, deterministic sync manifest и file/schema diff.
- Ошибка записи диагностируется отдельно. Raw bytes остаются в package; package с error issues не допускается к promotion.

### Review corrections, вошедшие в merge

- Canonical URLs строятся по реальным Astro routes и production `SITE_URL` fallback из `astro.config.mjs`; GitHub Pages preview values и provider URLs исключены.
- Проверенные маршруты: products, systems, groups, articles, news, pages и `pages/home` → `/`. Вложенные slugs без соответствующего catch-all route не получают предположительный URL.
- `src/pages/**`, `astro.config.mjs`, `src/content.config.ts`, `src/lib/url.ts`, `src/lib/nav.ts`, `src/lib/service.ts`, `src/data/nav.yaml` и `src/data/industries.yaml` включены в source revisions/manifest. Добавление, изменение и удаление route/config files отражается в drift report.
- `SiteSyncManifest.parser_version` участвует в snapshot identity; смена версии вызывает parser-version drift. Старые manifests и builder calls поддерживаются через явный unversioned marker.
- `SiteSourceRevision` сохраняет семантику raw source provenance; версия site parser находится в processing manifest согласно ADR-0013.

Тесты: `backend/tests/unit/test_saturn_site_adapter.py`; fixtures: `backend/tests/fixtures/saturn_site/`.

## 4. Граница с прежним ingestion

Существующие `site.py`, `registry.py`, `pipeline.py`, `contracts.py` обслуживают прежний synthetic/fixture ingestion path. В нём есть фиксированные collections и per-source approval contracts.

**Не удалять и не ослаблять эти approval gates глобально. Не подключать доверенный Saturn main через старый SourceRecord/Registry.** Новая Saturn-интеграция идёт отдельным путём на основе `saturn_contracts.py` и собственных adapter contracts. Существующие synthetic tests и historical evaluation должны продолжать работать без регрессий.

## 5. Snapshot Provider — архитектура принята; реализация не начата

Владелец утвердил provider-neutral Snapshot Provider contract v0.1 и ADR-0014. Документы находятся в открытом docs-only PR #21:

- [PR #21](https://github.com/UkWood/LLM-RAG-chat-bot/pull/21)
- [Snapshot Provider Contract](site-specific/v0.2/05-snapshot-provider-contract.md)
- [ADR-0014](decisions/0014-snapshot-provider-contract.md)
- [Stage report](stages/2026-11-09-snapshot-provider-contract.md)

Принятая последовательность: GitHub REST Provider первым; Gitea REST Provider позднее за тем же контрактом. Provider получает точный snapshot и передаёт существующий immutable PinnedSiteSnapshot в pure/offline adapter.

Ключевые ограничения: branch main разрешается один раз; после pinning все операции выполняются по immutable commit/tree/blob IDs; Git provider является trust source для ref/commit/tree identity mapping, но независимая криптографическая проверка raw commit/tree objects не заявляется; каждый blob проверяется по Git object hash согласно object format, а raw content SHA-256 сохраняется отдельно. Текущие canonical contracts поддерживают SHA-1 и fail closed для иных форматов до отдельного согласования их эволюции.

PDF остаются обязательной частью knowledge corpus. Обычный Git snapshot не загружает их: discovery/cataloguing — Support Catalog Adapter, fetch/extraction — External Document Adapter. На будущее предусмотрено выборочное получение PDF как Git blob по pinned commit/path/blob SHA, но оно не реализуется сейчас.

**Не начинать реализацию GitHub/Gitea Provider или PDF ingestion в рамках PR #21.** Для реализации потребуется отдельная команда владельца и отдельный bounded этап.


## 6. Результаты и проверка PR #20

- PR #20: **MERGED**.
- Кодовый head: `9b36551adf61070426caa9250650bb32d638a66a`.
- Merge commit: `361529963bd48772f0d9d478dfb3b963ec5a8d03`.
- PR-head GitHub Actions [run #232](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569426503): SUCCESS.
- Push GitHub Actions [run #231](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569421610): SUCCESS.
- Offline verification: 212 tests passed, 11 existing optional skips; ONNX contracts PASS.
- Synthetic baseline preflight: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 0.85. Это прежняя non-blocking synthetic baseline, не оценка качества адаптера.
- Saturn-Main-Site проверен read-only на commit `084d759487bfab6e111549c9b5469711ac5fc13`; изменений в нём не было.
- ADR-0012 и ADR-0013 не изменялись.

## 7. Разделение сессий и порядок работы

Эта сессия предназначена для реализации и проверки кода. Архитектурные решения, ADR и изменение scope согласуются в отдельной сессии «Saturn AI — Архитектура и управление».

При продолжении:
1. Проверить актуальный main и не повторять уже завершённую реализацию адаптера.
2. Считать PR #20 завершённым и слитым; не возвращаться к его review/merge.
3. Считать архитектурный контракт Snapshot Provider утверждённым, но не начинать реализацию GitHub/Gitea Provider или PDF ingestion без отдельной команды владельца.
4. При конфликте с утверждёнными требованиями остановиться и вынести вопрос в архитектурную сессию.

Для будущих изменений использовать отдельные feature branches и PR. Merge выполнять только после review и отдельной команды владельца.
