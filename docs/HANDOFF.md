# Передача контекста — реализация кода

Дата: 2026-11-09  
Текущая реализация: [PR #20](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20), ветка `feature/saturn-site-content-adapter`  
Основной репозиторий: [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot)  
Текущий main: \`934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e\`

## 1. Текущий статус

- PR #17 и PR #18 приняты и слиты. ADR-0012/0013, канонические контракты и schema-evolution primitives находятся в main.
- Текущий main: `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`.
- PR #20 открыт, не слит: [trusted Saturn Site Content Adapter](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20).
- PR #20 реализует pure/offline адаптер для уже полученного pinned snapshot. GitHub snapshot provider, PDF, retrieval, LLM/API/UI и deployment ещё не реализованы.
- Проверенный кодовый head `76cef265b7ebc73e7f1a4848e6bbd3d02478ad66` прошёл PR-head CI [#230](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42568802924): SUCCESS — 212 тестов, 11 существующих optional skips; ONNX contracts SUCCESS.
- После кодового commit обновляются только status/handoff документы. Перед merge проверять checks актуального PR head.
- PR #20 ожидает review владельца. Merge не выполнялся.

## 2. Решения владельца — обязательны

- Stable trusted logical source ID: `UkWood/Saturn-Main-Site`, branch `main`. Snapshot Providers map their physical GitHub/Gitea remotes to this ID; provider addresses are not part of the adapter contract.
- Все non-draft записи сайта, объявленные сайтом связи, справочники и прямые PDF-ссылки из documents/certificates или Markdown body доверенные. Ручная проверка/approval не нужна.
- \`draft: true\` исключается из публичного corpus.
- Сайт строго READ-ONLY: не менять его файлы, ветки, URL, assets, CI или поиск.
- Изменения сайта автоматически синхронизируются; commit/hash нужны для воспроизводимости и citations, а не approval.
- Новые поля/collections сохраняются как generic evidence; несовместимые типы не интерпретируются старым mapping, а дают drift report.
- PDF обрабатываются автоматически по доверенным ссылкам, но только с технической HTTPS host/path allowlist, SSRF/redirect и resource-limit защитой.
- Cloud data egress к внешней LLM — отдельное решение; source trust его не разрешает.
- ChatGPT — основная среда проектирования, реализации и review. Codex — только для ограниченных рутинных coding tasks по точному brief.

## 3. Реализовано в PR #20 (ещё не в main)

Новый модуль: `backend/src/saturn_ai/ingestion/saturn_site_adapter.py`.

- Принимает immutable `PinnedSiteSnapshot`: trust root, branch, commit SHA, tree SHA и отсортированные файлы с Git blob SHA + исходными bytes. Blob SHA проверяется по точным байтам.
- Динамически обнаруживает Markdown collections под `src/content/<collection>/`; словари `src/data/*.yaml|yml` и `src/content.config.ts` включаются в manifest/fingerprints.
- `src/content.config.ts` только fingerprint-ится — Astro/TypeScript/JS не исполняются.
- Safe YAML: YAML 1.2 boolean semantics, запрет anchors/aliases/explicit tags, duplicate keys и non-string keys; ограничены размер, token count, depth и node count.
- Raw bytes, raw frontmatter text и Markdown body сохраняются. Неизвестные поля и вложенные значения становятся raw facts; неизвестные collections — `SiteContent`.
- Явные relations берутся только из текущей проверенной схемы. `pages.groups` остаётся navigation data.
- Для `systems.kind` при отсутствии поля применяется только объявленный в source schema default `system`; явное неизвестное значение остаётся generic `SiteContent` с warning. `pages.kind` default не имеет.
- Используются PR #18 contracts: source revisions, schema inventory, dictionary fingerprints, deterministic sync manifest и file/schema diff.
- Ошибка записи диагностируется отдельно. Raw bytes остаются в package; package с error issues не допускается к promotion.

Тесты: `backend/tests/unit/test_saturn_site_adapter.py`; fixtures — `backend/tests/fixtures/saturn_site/`. Старые ingestion modules и synthetic/evaluation path не изменялись.

### Review corrections in PR #20

- Canonical URLs derive from the checked-in public `SITE_URL` fallback in `astro.config.mjs`; GitHub Pages `SITE_URL`/`BASE_PATH` overrides and provider URLs are not used.
- Actual Astro routes are verified for products, systems, groups, articles, news and pages; `pages/home` maps to `/`. Nested slugs without a matching catch-all route have no guessed canonical URL.
- `src/pages/**`, `astro.config.mjs`, `src/content.config.ts`, `src/lib/url.ts`, `src/lib/nav.ts`, `src/lib/service.ts`, `src/data/nav.yaml` and `src/data/industries.yaml` are included in source revisions/manifest. Route add/change/delete is reported as drift.
- `SiteSyncManifest.parser_version` participates in snapshot identity. Legacy manifests and builder calls remain compatible through an explicit unversioned marker. Current parser/mapping versions are 0.2.0.
- Unknown explicit `pages.kind` values map to `SiteContent` with warning; missing kind maps to `Page`. Raw frontmatter and facts retain the original value.
- `SiteSourceRevision` remains raw source provenance; site parser version is a processing-manifest field, consistent with ADR-0013.

## 4. Важная граница с прежним ingestion

Существующие \`site.py\`, \`registry.py\`, \`pipeline.py\`, \`contracts.py\` обслуживают прежний synthetic/fixture ingestion path. В нём есть фиксированные collections и per-source approval contracts.

**Не удалять и не ослаблять эти approval gates глобально. Не пытаться подключить доверенный Saturn main через старый SourceRecord/Registry.** Новая Saturn-интеграция должна идти отдельным путём на основе \`saturn_contracts.py\` и собственных adapter contracts. Существующие synthetic tests и historical evaluation должны продолжать работать без регрессий.

## 5. Следующий bounded coding task после PR #20

После review и отдельной команды владельца на merge — provider-neutral Snapshot Provider stage. Текущий GitHub provider и будущий Gitea provider должны выдавать один и тот же `PinnedSiteSnapshot`; конфигурация каждого provider отображает физический remote/namespace на стабильный trusted logical source ID.

`saturn_site_adapter.py` остаётся pure/offline. GitHub/Gitea API, network, clone, provider environment, source-site writes, PDF, retrieval, LLM/provider, API/UI и deployment не входят в этот PR.

Если provider потребует изменения архитектуры или новых контрактов — остановиться и вынести конкретное предложение в архитектурную сессию.

## 6. Результат и проверка PR #20

- PR-head CI [#230](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42568802924): SUCCESS — 212 tests, 11 existing optional skips; ONNX contracts PASS.
- Проверены canonical URL для известных collections, pages/home, публичный домен, GitHub Pages base-path exclusion, slug encoding и nested slugs.
- Проверены route source add/change/delete, parser version identity/drift, legacy manifest compatibility и pages.kind discriminator.
- Synthetic baseline preflight: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 0.85 (существующая non-blocking baseline).
- Saturn-Main-Site проверен read-only на commit `084d759487bfab6e111549c9b5469711ac5fc13`; изменений в нём не было.
- PR #20 открыт; merge без отдельной команды владельца запрещён.

## 7. Разделение сессий и порядок работы

Эта сессия предназначена для реализации и проверки кода. Архитектурные решения, ADR и изменение scope согласуются в отдельной сессии «Saturn AI — Архитектура и управление».

При продолжении:
1. Проверить актуальный main и состояние PR #20.
2. Не повторять уже завершённую реализацию адаптера.
3. После review/merge продолжать только с bounded задачей read-only snapshot provider.
4. При конфликте с утверждёнными требованиями остановиться и вынести вопрос в архитектурную сессию.

PR создаётся в отдельной feature branch. Merge — только после review и отдельной команды владельца.
