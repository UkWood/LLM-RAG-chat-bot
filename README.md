# AI Technical Consultant — МНПП «Сатурн»

Отдельный технический консультант: ответы только по разрешённым материалам с источниками и отказом при недостатке доказательств. Статический интерфейс Astro, отдельный FastAPI backend, локальная KB и сменный LLM provider.

**Стадия:** M1 слит в main; добавлен следующий offline шаг — runtime registry и ingestion синтетических карточек/PDF. Реальные источники пока не допущены к индексации/облачной отправке. Полная production-архитектура остаётся proposed.

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
python3 scripts/check_project.py
python3 -m unittest discover -s tests -v
python3 -m venv work/venv
work/venv/bin/python -m pip install --require-hashes -r backend/requirements.lock
PYTHONPATH=backend/src work/venv/bin/python -m unittest discover -s backend/tests -v
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
