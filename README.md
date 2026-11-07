# AI Technical Consultant — МНПП «Сатурн»

Отдельный технический консультант: ответы только по разрешённым материалам с источниками и отказом при недостатке доказательств. Статический интерфейс Astro, отдельный FastAPI backend, локальная KB и сменный LLM provider.

**Стадия:** M1/ingestion/snapshot baseline слиты в main. Добавлены local indexes и measured BM25: Top-5 source hit17/20=85%; lexical target100% пока не пройден. Actual E5 experiment: dense18/20=90%, hybrid17/20=85%; Actual local reranker достиг20/20 и evidence recall100% на том же synthetic наборе; bounded grounded pipeline измерен:8/20 положительных ответов, обязательные отказ/уточнение10/10; grounding target не пройден. Реальные источники пока не допущены к индексации/облачной отправке. Полная production-архитектура остаётся proposed.

**Новое выбранное направление:** обычный RAG с подтверждёнными частичными ответами и вопросами к поддержке при пробелах. [Подробный дизайн](docs/superpowers/specs/2026-11-07-grounded-rag-redesign-design.md) принят; реализация в работе. [Рабочая точка перехода в новую среду](docs/handoffs/2026-11-07-grounded-rag-environment.md). Это не приёмка качества.

Новый operator путь: [runbook](docs/runbooks/grounded-rag-operator.md), `python -m saturn_ai.rag ask` с persisted hybrid store/local bundles и готовой API LLM. Открытая synthetic диагностика: [fixtures](fixtures/rag-diagnostic/README.md),15вопросов; actual retrieval gold quote recall1.0 для12evidence-bearing cases,3missing recall=null. AITunnel public synthetic API smoke **compatible** (HTTP/JSON contract only); human fixture review подтверждён. Oracle15/15 выполнен, end-to-end остановлен на d03 (`pipeline_unavailable`, остальные12NOT_RUN); human answer review pending, качество не принято. [Фактические ответы](docs/stages/2026-11-07-grounded-rag-first-responses.md). Ничего не развёрнуто.

[Текущий checkpoint для новой среды с LLM variables](docs/handoffs/2026-11-07-grounded-rag-llm-transition.md).

## Память проекта

- [Продолжение в новой сессии](docs/HANDOFF.md)

- [Текущее состояние и следующий шаг](docs/PROJECT_STATUS.md)
- [Согласованные критерии прототипа: offline / real sample](docs/acceptance/prototype-v1.md)
- [Дорожная карта](docs/superpowers/plans/2026-11-03-ai-consultant-roadmap.md)
- [Архитектура](docs/superpowers/specs/2026-11-03-ai-consultant-design.md)
- [Решения ADR](docs/decisions/0001-rag-boundaries.md)
- [Discovery сайта](docs/discovery/2026-11-03-site-audit.md)
- [Исходное ТЗ](docs/requirements/original-brief.ru.md)
- [Допуск PUBLIC](docs/public-source-policy.md) и [реестр](config/knowledge/public-sources.json)
- [Журнал этапов](docs/stages/README.md)
- [Правила работы](AGENTS.md)

Репозиторий `UkWood/Saturn-Main-Site` — **только чтение**, без изменений файлов, CI, адресов и assets. Все результаты AI хранятся в этом репозитории. Чат не заменяет документацию и Git-историю.

## Проверка текущего этапа

```bash
python3 -m venv work/venv
work/venv/bin/python -m pip install --require-hashes -r backend/requirements.lock
work/venv/bin/python scripts/verify_offline.py
```

Тесты выполняются на CPU без сети, ключей и моделей после установки закреплённых parser dependencies (PyYAML/pypdf). Lock с wheel hashes рассчитан на Python 3.12/Linux x86_64; установка требует package registry либо локального wheel cache. M1 CLI и прежние проверки остаются stdlib-only. CI устанавливает эти dependencies и запускает все проверки на push/PR.

## Offline CLI M1

Из корня checkout:

```bash
PYTHONPATH=backend/src python3 -m saturn_ai --corpus fixtures/synthetic 'Какие интерфейсы у DEMO-100?'
PYTHONPATH=backend/src python3 -m saturn_ai --corpus fixtures/synthetic 'Найдите руководство DEMO-100'
PYTHONPATH=backend/src python3 -m saturn_ai --corpus fixtures/synthetic 'Интерфейсы DEMO-999?'
```

Первый запрос возвращает вымышленный учебный RS-485 с source ID, heading, hash и chunk ID. Второй находит синтетическое руководство; URL example.invalid обозначает учебный источник, не реальный PDF. Третий возвращает refused/unknown_entity без sources и вызова provider. Все результаты test_only=true.

Принимаются полные формулировки из примеров: «[Какие] интерфейсы [у] DEMO-100» и «[Найдите] руководство [для/на] DEMO-100» (регистр не важен, конечный знак вопроса необязателен). Смешанные и отрицательные запросы закрываются отказом. Поддержаны только точное обозначение одного учебного изделия и intents «интерфейсы»/«руководство». Parser принимает строгую грамматику synthetic facts; свободные консультации и качество реальных моделей этим не проверяются. Corpus загружается и индексируется в память при запуске, без постоянного index dump. [План M1](docs/superpowers/plans/2026-11-04-m1-offline-rag.md), [отчёт](docs/stages/2026-11-04-m1-offline-rag.md), [фикстуры и ограничения](fixtures/synthetic/README.md).

API/UI, реальные модели, PDF ingestion, Docker deployment и CD остаются следующими этапами. Текущий CLI не является production сервисом.

## Offline ingestion, этап 2

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.ingestion --registry config/knowledge/public-sources.json
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.ingestion --registry fixtures/ingestion/registry.json --fixture-root fixtures/ingestion --source-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

Первая команда валидирует 8 реальных pending кандидатов: разрешённых источников 0, content не читается. Вторая собирает 3 вымышленных карточки в память и выводит только counts/IDs: 3 документа, 13 chunks. Источники/approval provenance исключительно учебные. Ссылки документов становятся отдельными pending candidates, без загрузки и наследования допуска карточки.

PDF-проверки генерируют отдельные authored файлы в памяти, проверяют физические страницы, ошибки и лимиты. Parser output не подключён к M1 ответам; качество произвольных таблиц/PDF и инженерных консультаций не заявляется. Процессные лимиты не заменяют OS sandbox для недоверенных файлов; real ingestion выключен.

[Дизайн](docs/superpowers/specs/2026-11-04-offline-ingestion-design.md), [план](docs/superpowers/plans/2026-11-04-offline-ingestion.md), [ADR-0003](docs/decisions/0003-offline-ingestion.md), [отчёт](docs/stages/2026-11-04-offline-ingestion.md).

## Snapshot и evaluation baseline

```bash
work/venv/bin/python scripts/verify_offline.py --report evaluation/reports/2026-11-05-baseline-preflight.json
```

После отдельного locked install команда выполняет все project/backend tests и проверяет corpus/snapshot/gold labels. Это текущая единая offline проверка, а не полная приёмка качества прототипа. Результат: 10 вымышленных документов, 44 chunks, 30 размеченных вопросов; retrieval/reranking/grounding имеют not_run, source_hit_at_5=null.

Snapshot хранит явные policy metadata, проверяет original bytes и полный canonical parser output; in-memory catalog отделяет corpus rollback от runtime revocations. Декларации dense/lexical coverage не являются готовыми индексами. Нет persistence/multi-worker или модели поиска; новые данные не подключены к M1 ответам.

[Dataset и ограничения](evaluation/README.md), [authored fixtures](fixtures/evaluation/README.md), [ADR-0005](docs/decisions/0005-snapshot-baseline.md), [отчёт этапа 3a](docs/stages/2026-11-05-snapshot-baseline.md).

## Локальный поиск и измеренная проверка

Обновите окружение через `pip install --require-hashes -r backend/requirements.lock` (Python3.12). Единая команда по-прежнему `work/venv/bin/python scripts/verify_offline.py`: code tests + preflight + actual lexical evaluation. Кодовая проверка и quality gate различаются: `--require-source-hit-target` возвращает nonzero при недостижении100%.

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.retrieval --corpus fixtures/evaluation --query 'Какие интерфейсы у EDU-410?' --mode lexical
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage retrieval --mode lexical --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

Qdrant SDK local CPU memory/path проверен с контрольными vectors; это не semantic benchmark. Optional `backend/requirements-onnx.lock` и local single-file checkpoint позволяют отдельный dense/hybrid run, checkpoint кандидата подготовлен в эксперименте 2026-11-06 (см. отчёт ниже). Auto downloads нет. Runtime contracts на numeric ONNX graph проверяются отдельным CI job.

[Измеренный report](evaluation/reports/2026-11-05-lexical-retrieval.json): source-hit17/20, calibration14/14, held_out3/6; corpus/labels/aliases не подгонялись после результата. Dense/hybrid/reranking/grounding/refusal not_run. Диагностика показывает IDs/ranks/scores, `--show-text` включает approved synthetic snippets только локально. Ожидания dataset не используются как ответы.

[Evaluation/модельный manifest и команды](evaluation/README.md), [пример manifest](config/embeddings/local-onnx.example.json), [ADR-0006](docs/decisions/0006-local-retrieval.md), [отчёт этапа3b](docs/stages/2026-11-05-local-retrieval.md).

[Подготовка E5 и actual dense/hybrid experiment](docs/stages/2026-11-06-model-preparation.md). Это измерение synthetic retrieval, не приёмка grounded chatbot и не production model selection.

[Local reranking: реализация, actual benchmark и ограничения](docs/stages/2026-11-06-local-reranking.md). Retrieval target на synthetic наборе пройден; это не приёмка grounded chatbot.

[Bounded evidence gate и extractive grounded pipeline](docs/stages/2026-11-06-evidence-gate.md):8/20 positives answered, обязательные отказ/уточнение10/10, claims/citations1.0 для выданных ответов. Grounding target и полная prototype acceptance НЕ пройдены; source-hit20/20 не означает answer coverage20/20.

## Opt-in typed planner V2

V2 adds bounded multi-need plans, canonical table/spec/relation projections and separate backend metadata references. V1 remains default. No new approvals, provider or dependencies. [Design](docs/superpowers/specs/2026-11-06-planner-expansion-design.md), [stage/protocol/results](docs/stages/2026-11-06-typed-planner-v2.md). Synthetic code checks are separate from blind quality acceptance.

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.grounding --planner-version v2 --corpus fixtures/evaluation --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --query 'Питание и интерфейсы EDU-410?'
```

Requires the existing explicitly prepared local bundles; no automatic downloads. V2 emits schema_version=2 with requirement bindings and backend references; engineering claims remain exact canonical quotations. Unsupported clauses/qualifiers or incomplete evidence refuse the entire request. This is bounded structured interpretation, not general engineering advice. The fresh blind benchmark is single-use after freeze; follow the stage commands, never rerun it as routine CI.

First frozen40case blind assessment: V2 fully correct8/24 positives and14/16 negative/ambiguity outcomes; V1 0/24 and12/16. V2 emitted support/canonical validity1.0, but the24/24+16/16 quality gate FAILED. Prototype not accepted. No post-result tuning; this set is now exposed regression evidence. Calibration14/14 positives is not blind generalization.

Post-review corrective revision rejects `нет`, unsupported literal Modbus/TCP/RTU qualifiers and modification requests outside supported lookup bindings instead of discarding them. Unqualified protocol questions remain supported. The first blind score above is historical for frozen7bc6f11, not a measurement of this corrected runtime: independent quality NOT_RUN, prototype not accepted. Dataset/START/report unchanged, no blind rerun. [Corrective stage report](docs/stages/2026-11-06-planner-v2-corrections.md).
