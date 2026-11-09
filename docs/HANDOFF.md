# Передача контекста — реализация кода

Дата: 2026-11-09  
Основной репозиторий: [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot)  
Текущий завершённый этап: Saturn Site Content Adapter, [PR #20](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20)  
Статус PR #20: **MERGED**  
Кодовый head PR: `9b36551adf61070426caa9250650bb32d638a66a`  
Merge commit в main: `361529963bd48772f0d9d478dfb3b963ec5a8d03`  
Base commit до PR #20: `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`

## 1. Текущий статус

- PR #17 и PR #18 приняты и слиты. ADR-0012/0013, канонические контракты и schema-evolution primitives находятся в main.
- PR #20 — trusted Saturn Site Content Adapter — слит в main 2026-11-09. Реализация адаптера входит в main через merge commit `361529963bd48772f0d9d478dfb3b963ec5a8d03`.
- Последний кодовый head PR #20: `9b36551adf61070426caa9250650bb32d638a66a`. PR-head GitHub Actions [run #232](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569426503) завершился SUCCESS; соответствующий push run [#231](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569421610) также SUCCESS.
- Проверка реализации: 212 тестов пройдены, 11 прежних optional skips; ONNX contracts PASS.
- Synthetic baseline не изменился: 10 документов, 44 chunks, 30 evaluation cases; lexical source-hit@5 — 0,85. Это прежняя synthetic evaluation, а не оценка качества нового адаптера.
- Адаптер остаётся pure/offline и принимает уже полученный immutable pinned snapshot. GitHub/Gitea Snapshot Provider, PDF download/parser, retrieval, LLM/provider, API/UI и deployment ещё не реализованы.
- Следующий bounded этап — проектирование provider-neutral Snapshot Provider contract. Он **не начат**; приступать к нему только после отдельной команды владельца.

## 2. Решения владельца — обязательны

- Stable trusted logical source ID: `UkWood/Saturn-Main-Site`, branch `main`. Snapshot Providers отображают свои физические GitHub/Gitea remotes и namespace на этот ID; адрес провайдера не входит в контракт адаптера.
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

## 5. Следующий bounded этап — Snapshot Provider (не начат)

После PR #20 следующий кандидат — provider-neutral read-only Snapshot Provider contract. Сначала требуется согласовать контракт и критерии проверки; реализацию провайдера в рамках этой задачи не начинать.

Контракт должен обеспечить:
1. Получение точного snapshot по закреплённому commit/tree.
2. Проверку commit/tree/blob identities и целостности bytes.
3. Сопоставление физического Git remote/namespace со стабильным trusted logical source ID.
4. Передачу неизменяемого `PinnedSiteSnapshot` в существующий pure/offline adapter.

После утверждения контракта можно реализовать GitHub Provider первым, а Gitea Provider — позднее как вторую реализацию того же интерфейса. При этом `saturn_site_adapter.py` не должен получать зависимости от GitHub/Gitea API, сети, clone, CI environment или deployment.

Любое изменение архитектуры или существующих contracts сначала выносится в отдельное обсуждение. Следующий этап не начинать без отдельной команды владельца.

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
3. Не начинать Snapshot Provider до отдельного согласования контракта и команды владельца.
4. При конфликте с утверждёнными требованиями остановиться и вынести вопрос в архитектурную сессию.

Для будущих изменений использовать отдельные feature branches и PR. Merge выполнять только после review и отдельной команды владельца.
