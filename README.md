# AI Technical Consultant — МНПП «Сатурн»

Отдельный технический консультант: ответы только по разрешённым материалам с источниками и отказом при недостатке доказательств. Статический интерфейс Astro, отдельный FastAPI backend, локальная KB и сменный LLM provider.

**Стадия:** discovery и проект архитектуры подготовлены; реализация RAG ещё не начата. Реальные источники пока не допущены к индексации/облачной отправке.

## Память проекта

- [Текущее состояние и следующий шаг](docs/PROJECT_STATUS.md)
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
```

Проверка использует только Python standard library, без GPU, ключей, сети и загрузки моделей. CI запускает её на push/PR. Это проверка документации и реестра, а не тест готового RAG.

Backend/UI, Docker deployment и CD появятся вместе с соответствующими проверенными этапами; сейчас артефакта приложения для deployment нет.
