# Этап 2: offline ingestion на синтетических данных

Дата: 2026-11-04. Ветка feat/offline-ingestion. Статус: synthetic profile реализован, опубликован в PR и проверен локально/в удалённом CI; real ingestion не разрешён.

## Основание и результат

После поручения владельца «Сливай» [PR #1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/1) слит в main: 0cfe1748ca9c59ac44b8d04c538996bd9a65008b, CI [41798909615](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41798909615) success. Поручение «Продолжай» применено к следующему offline шагу, не к допуску реальных источников. Полный milestone M2 (этапы 2–5) ещё не завершён.

Добавлен отдельный ingestion package:

- Strict runtime registry v1: duplicate JSON keys, exact types/enums, approval provenance/UTC date, hashes, commit/path, URL и scopes; immutable SourceRecord.permits.
- Deny-before-read pipeline: UNKNOWN/pending/revoked пропускаются до filesystem I/O. Real approved records блокируются fixture runner; отдельный synthetic namespace/context. Один parser failure прерывает всю сборку.
- Read-only site adapter по schema commit 084d759487bfab6e111549c9b5469711ac5fc13e: Software/Category mapping, structured facts/units/status, heading/field provenance, целые Markdown tables и explicit relationships без вывода совместимости.
- Ссылки вложений — только pending candidates; родитель не разрешает документ. Ничего не скачивается.
- Local PDF adapter: pypdf worker с byte/page/text/CPU/RAM/time limits, реальные физические pages; отказ для encrypted, active/attached/empty/malformed PDF. Никакого OCR или исполнения действий/JS.
- Deterministic document/chunk/snapshot IDs; разные source approvals не сливаются по совпадению bytes. CLI выводит summary без corpus/index dumps.

Выход ingestion не подключён к M1 ответам. Произвольный parsed текст не считается проверенным evidence. M1 CLI/контракты не изменены. Runtime registry, site schema и synthetic fixtures — отдельные сущности, реальные production approvals не добавлены.

[Дизайн](../superpowers/specs/2026-11-04-offline-ingestion-design.md), [план](../superpowers/plans/2026-11-04-offline-ingestion.md), [ADR-0003](../decisions/0003-offline-ingestion.md).

## Фактические проверки

- RED: отсутствующие saturn_ai.ingestion, pipeline и pdf модули дали ожидаемые ModuleNotFoundError до реализации.
- Runtime policy: 6 тестов, включая 8 реальных pending кандидатов (все denied), hash/commit/scopes, duplicate keys, malformed types/approvals/paths/URLs.
- Site/pipeline: 10 тестов, включая draft, YAML aliases/tags/duplicate keys, metadata/code exclusion, entity mapping, units/table, relationship provenance, idempotence/different-source identity, deny-before-read, escaping symlink/hash drift.
- PDF: 5 тестов, включая физические pages 1/2 и units, malformed/empty/encrypted/active/page-limit, hash/policy before worker, timeout и независимый допуск PDF. PDF bytes генерируются тестами, реальные файлы не загружались.
- M1: все 20 прежних backend tests сохранены и проходят. Всего 41 backend test PASS.
- Чистый venv Python 3.12: установлены только PyYAML 6.0.3 и pypdf 6.10.0 из локальных wheels с --no-index --require-hashes. Backend suite в этом venv PASS. Reportlab/облачные ключи/GPU/модели не нужны.
- python3 scripts/check_project.py и python3 -m unittest discover -s tests -v: прежние проверки и 5 тестов PASS на финальной проверке.
- CLI: synthetic registry → 3 docs / 13 chunks, snapshot 712221fdb0bde4e0a426a26062a730fb511c99905f661c1f5ac153ca311383b8. Повторная сборка идентична. Real registry → 8 candidates / 0 permitted, без content I/O.
- CI расширен установкой hash-locked dependencies перед backend suite; тесты выполняются offline после установки. Dependency install сам требует package registry либо wheel cache.

Команда полного backend suite:

```bash
PYTHONPATH=backend/src work/ingestion-venv/bin/python -m unittest discover -s backend/tests -v
```

Создание venv и обычная установка описаны в README. Локальный work/ingestion-venv не коммитится и не гарантирован после snapshot.

## Независимое review

Первое review b20c364: 39 тестов PASS, два P2. Heading stack неверно сохранял родителей при skipped levels; code filtering неверно обрабатывал indented blocks и внешнюю ограду из четырёх backticks. Пробы воспроизведены RED. Исправлены level-aware heading stack, длина/синтаксис closing fence и исключение indented code. Добавлены два регрессионных теста с шестью subcases; suite 41 PASS. Повторное review подтвердило исходные fixes и выявило mixed space/tab indentation; дополнительный RED subcase воспроизвёл проблему, проверка отступа после expandtabs(4) её закрыла. Финальная suite 41 PASS.

## GitHub и происхождение

Base 0cfe174; commit 80da5bb — runtime policy, b20c364 — parser/pipeline/fixtures/CI. Review fixes: c0df98e. Последующие документация и публикация видны в Git/PR. API и git работают с sandbox network grant, исходный proxy сохранён, credentials не выводились.

Сайт прочитан только для проверки src/content.config.ts на pinned commit; его исходники, контент, CI, URL и assets не изменялись. Реестр config/knowledge/public-sources.json неизменён; SHA-256 raw registry 8441e6f5dad6f6f138e879960897f999da0f708dd8661abe02be2310effa229d. Учебный commit aaaa… и approval provenance явно вымышлены.

## Публикация и удалённый CI

[PR #2](https://github.com/UkWood/LLM-RAG-chat-bot/pull/2) создан в main, состояние при проверке OPEN. Commits: 80da5bb → b20c364 → c0df98e → 88c2924. Git push exit 0; PR API подтвердил head 88c29247a80638e64d1cd1fe740e73220b4defa1.

Push CI [41801220416](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41801220416) на 88c2924 завершён success. Jobs API подтвердил success каждого шага, включая hash-locked parser install, прежние 5 тестов и backend 41 tests. PR workflow [41801275165](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41801275165) запускается отдельно. Эти наблюдения сохранены последующим documentation-only commit; фактические checks последнего head смотреть в PR. Merge нового этапа не выполнялся.

## Ограничения и следующий шаг

Этап 2 подготовлен и проверен только на синтетических данных. Реальные ingestion/quality acceptance требуют exact source approvals, OS parser sandbox/egress и проверки корпуса инженером. Процессные resource limits не являются OS security sandbox. Сложные PDF tables/OCR и проверка актуальности источника не реализованы. Поддержан ограниченный набор content fields, не вся Astro schema; входы/выходы/сертификаты и словари требуют следующих adapters. JSON Schema artifact ещё не опубликован; strict validation реализована runtime кодом.

Следующий независимый шаг: согласованный immutable snapshot/index interface и локальный retrieval baseline (этап 3), продолжая synthetic profile. Подключение к генерации требует evidence/grounding этапа 5; реальный sample остаётся отдельным gate. UI/API, модели, cloud, Qdrant и deployment не реализованы.

## Последующее событие: merge PR #2

По поручению владельца PR #2 проверен и слит: 909072fe928f004729e6db95482bb5342f0e6e63, main CI 42062413579 success, 46 code tests PASS. GitHub merge API вернул 500; обычный merge/non-force push прошёл, API подтвердил merged=true. Сведения об открытом PR выше относятся к моменту исходной публикации.
