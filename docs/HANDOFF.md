# Передача контекста — реализация кода

Дата: 2026-11-09  
Текущая реализация: [PR #20](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20), ветка `feature/saturn-site-content-adapter`  
Основной репозиторий: [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot)  
Текущий main: \`223350c9f6f104b5b67aadd124bfc968f12f5dbf\`

## 1. Текущий статус

- PR #17 и PR #18 приняты и слиты. ADR-0012/0013, канонические контракты и schema-evolution primitives находятся в main.
- Текущий main: `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`.
- PR #20 открыт, не слит: [trusted Saturn Site Content Adapter](https://github.com/UkWood/LLM-RAG-chat-bot/pull/20).
- PR #20 реализует pure/offline адаптер для уже полученного pinned snapshot. GitHub snapshot provider, PDF, retrieval, LLM/API/UI и deployment ещё не реализованы.
- Финальный push CI PR #20 на commit `b73617ab176edb0a48aa2d24b176d6a18feefb49`: SUCCESS — 204 теста, 11 существующих optional skips; ONNX contracts SUCCESS.
- PR #20 ожидает review владельца. Merge не выполнялся.

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

## 3. Реализовано в PR #20 (ещё не в main)

Новый модуль: `backend/src/saturn_ai/ingestion/saturn_site_adapter.py`.

- Принимает immutable `PinnedSiteSnapshot`: trust root, branch, commit SHA, tree SHA и отсортированные файлы с Git blob SHA + исходными bytes. Blob SHA проверяется по точным байтам.
- Динамически обнаруживает Markdown collections под `src/content/<collection>/`; словари `src/data/*.yaml|yml` и `src/content.config.ts` включаются в manifest/fingerprints.
- `src/content.config.ts` только fingerprint-ится — Astro/TypeScript/JS не исполняются.
- Safe YAML: YAML 1.2 boolean semantics, запрет anchors/aliases/explicit tags, duplicate keys и non-string keys; ограничены размер, token count, depth и node count.
- Raw bytes, raw frontmatter text и Markdown body сохраняются. Неизвестные поля и вложенные значения становятся raw facts; неизвестные collections — `SiteContent`.
- Явные relations берутся только из текущей проверенной схемы. `pages.groups` остаётся navigation data.
- Используются PR #18 contracts: source revisions, schema inventory, dictionary fingerprints, deterministic sync manifest и file/schema diff.
- Ошибка записи диагностируется отдельно. Raw bytes остаются в package; package с error issues не допускается к promotion.

Тесты: `backend/tests/unit/test_saturn_site_adapter.py`; fixtures — `backend/tests/fixtures/saturn_site/`. Старые ingestion modules и synthetic/evaluation path не изменялись.

## 4. Важная граница с прежним ingestion

Существующие \`site.py\`, \`registry.py\`, \`pipeline.py\`, \`contracts.py\` обслуживают прежний synthetic/fixture ingestion path. В нём есть фиксированные collections и per-source approval contracts.

**Не удалять и не ослаблять эти approval gates глобально. Не пытаться подключить доверенный Saturn main через старый SourceRecord/Registry.** Новая Saturn-интеграция должна идти отдельным путём на основе \`saturn_contracts.py\` и собственных adapter contracts. Существующие synthetic tests и historical evaluation должны продолжать работать без регрессий.

## 5. Следующий bounded coding task после PR #20

После review и отдельной команды владельца на merge следующий отдельный этап — read-only GitHub snapshot provider, который получает точные commit/tree refs и передаёт адаптеру immutable snapshot.

Граница provider/adapter должна сохраниться:
- provider отвечает за GitHub read-only fetch и точную фиксацию commit/tree/blob identities;
- `saturn_site_adapter.py` остаётся pure/offline и не получает сетевых зависимостей;
- source-site writes, PDF fetching/parsing, retrieval, LLM/provider, API/UI и deployment остаются вне следующего этапа, пока отдельно не согласованы.

Если provider потребует изменения архитектуры или новых контрактов — остановиться и вынести конкретное предложение в архитектурную сессию.

## 6. Результат и проверка PR #20

- Fixtures покрывают шесть текущих collections, дополнительную неизвестную collection, draft/ordinary records, software/device, system/category, solution/section и declared relations.
- Проверены raw preservation, YAML rejection, CRLF body, unknown nested fields, arrays/order, add/update/delete, collection/field/type/dictionary drift и deterministic output.
- Финальный GitHub Actions run: [#205](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42531172049) — оба jobs SUCCESS.
- Offline verification: 204 tests, 11 optional skips. Synthetic baseline preflight: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 0.85 (существующая non-blocking baseline, без изменений).
- ONNX contracts: SUCCESS.
- Saturn-Main-Site не изменялся. PDF, LLM, provider, retrieval и deployment не подключались.
- PR #20 открыт и ожидает review; merge без отдельной команды владельца запрещён.

## 7. Разделение сессий и порядок работы

Эта сессия предназначена для реализации и проверки кода. Архитектурные решения, ADR и изменение scope согласуются в отдельной сессии «Saturn AI — Архитектура и управление».

При продолжении:
1. Проверить актуальный main и состояние PR #20.
2. Не повторять уже завершённую реализацию адаптера.
3. После review/merge продолжать только с bounded задачей read-only snapshot provider.
4. При конфликте с утверждёнными требованиями остановиться и вынести вопрос в архитектурную сессию.

PR создаётся в отдельной feature branch. Merge — только после review и отдельной команды владельца.
