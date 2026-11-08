# Старт новой сессии ChatGPT — AI Technical Consultant для МНПП «Сатурн»

Дата checkpoint: 2026-11-08  
Репозиторий: `UkWood/LLM-RAG-chat-bot`  
Текущий main: `3cd6787db2fe00fd7cea49bce8a355a27f292bf0`

Этот документ — короткая точка входа в проект. Перед работой сверить SHA и статусы PR с GitHub: сведения ниже отражают checkpoint на указанную дату.

## 1. Как организована работа

Основная работа ведётся в ChatGPT. ChatGPT — архитектор, аналитик, планировщик, координатор и reviewer. Codex — только исполнитель небольших, строго ограниченных coding tasks по подготовленному ChatGPT ТЗ. Владелец утверждает существенные решения, scope, merge и deployment.

Обязательные правила: [CHATGPT_WORKING_AGREEMENT.md](CHATGPT_WORKING_AGREEMENT.md).

Не поручать Codex открытые задачи вида «продолжи проект». Каждое поручение должно иметь исходный commit, точные разрешённые файлы, запреты, тесты, критерии приёмки и ожидаемый отчёт.

## 2. Цель продукта

Отдельный технический AI-консультант для сайта ООО «МНПП Сатурн». Приоритетная аудитория — инженер-проектировщик; дополнительная — технический специалист и руководитель заказчика.

Консультант должен отвечать по разрешённым материалам, показывать подтверждающие источники и страницы PDF, частично отвечать при наличии части evidence, задавать вопросы для уточнения пробелов и отказывать при недостатке подтверждений. Он не должен придумывать характеристики, совместимость, протоколы или отрицательные свойства.

Полная принятая основа: [site-specific documentation v0.1](site-specific/README.md).

## 3. Неприкосновенные ограничения

- Репозиторий `UkWood/Saturn-Main-Site` — строго read-only. Никаких изменений файлов, кода, контента, URL, assets, CI, веток, коммитов или истории.
- Существующие поиски сайта `/search/` и `/service/search/` сохраняются без изменений.
- Разработка консультанта ведётся только в `UkWood/LLM-RAG-chat-bot`.
- Первый корпус — ориентировочно 10 конкретно проверенных источников.
- Текущие 8 source candidates в `config/knowledge/public-sources.json` имеют `UNKNOWN/pending`; ни один не разрешён автоматически.
- Не выполнять реальный ingestion, cloud generation или production deployment до соответствующего допуска и решения владельца.
- Не считать synthetic evaluation доказательством качества на реальных материалах Сатурна.

## 4. Принятые документы

Начать с [docs/site-specific/README.md](site-specific/README.md), далее:
- [01 — Техническое задание](site-specific/01-technical-specification.md)
- [02 — Архитектура](site-specific/02-architecture.md)
- [03 — Карта источников и двух поисков](site-specific/03-source-inventory.md)
- [04 — План реализации](site-specific/04-implementation-plan.md)
- [05 — Вопросы для ИТ](site-specific/05-it-questionnaire.md)
- [06 — План испытаний и приёмки](site-specific/06-acceptance-plan.md)
- [ADR-0011 — границы источников](decisions/0011-site-source-adapters-and-search-boundaries.md)

Эти документы v0.1 утверждены владельцем и слиты в main через PR #14, merge commit `3cd6787`.

## 5. Фактическое состояние main

В main есть инженерная offline foundation: ingestion contracts, snapshots/policy, BM25, dense/Qdrant adapter, local reranker, evidence gate и evaluation tooling.

Последние измерения на synthetic corpus:
- lexical source-hit@5: 17/20;
- dense: 18/20;
- hybrid: 17/20;
- local reranker: 20/20 на том же небольшом synthetic наборе;
- bounded grounded pipeline: 8/20 положительных ответов, 10/10 обязательных отказов/уточнений.

Это разные стадии измерений, не единая метрика. Полная приёмка прототипа не пройдена. Не заявлять production readiness.

## 6. Незавершённые ветки — не часть main

### PR #13 — grounded RAG / publication pipeline

- Branch: `docs/grounded-rag-redesign`.
- Head на checkpoint: `24a8409b7d5fb65d9f5144019f87f5d1bc75df0c`.
- Draft, не слит.
- Последний точный head имел успешные push CI и PR CI (оба workflow завершились SUCCESS).
- Ветка включает общий publication pipeline для опубликованных HTML/PDF, existing retrieval reuse, provider и partial grounded answer flow.
- На 15 synthetic diagnostic cases oracle и end-to-end режимы выполнили по 15/15 случаев без infrastructure errors. Raw statuses в обоих режимах: answered 5, partial 6, needs_support 3, clarification 1.
- Human answer assessment двух режимов остаётся pending. Runtime status/self-verifier не являются оценкой правильности.
- Есть SHA-bound human review forms для каждого режима; поля должны быть заполнены человеком, не моделью.
- Ветка основана на старом main `bb16530e5b9a4943abae5c1b0f526cb218f46b2d`; после PR #14 main продвинулся. GitHub сообщал `mergeable=false`. Не merge/rebase автоматически.

**Архитектурный вопрос для следующей сессии:** PR #13 строит общий контур опубликованных HTML/PDF. Принятые site-specific документы требуют также отдельного structured adapter для Markdown/frontmatter/YAML словарей сайта и metadata adapter для Support catalog. Нужно сопоставить код PR #13 с утверждённой архитектурой, определить переиспользуемые модули и недостающие адаптеры. Не считать PR #13 полной реализацией site-specific архитектуры.

Основные материалы PR #13:
- [PR #13](https://github.com/UkWood/LLM-RAG-chat-bot/pull/13)
- [15-case response/evidence packet](https://github.com/UkWood/LLM-RAG-chat-bot/blob/docs/grounded-rag-redesign/docs/stages/2026-11-07-grounded-rag-budget4096-responses.md)
- [Operator runbook](https://github.com/UkWood/LLM-RAG-chat-bot/blob/docs/grounded-rag-redesign/docs/runbooks/grounded-rag-operator.md)
- [Grounded RAG implementation plan](https://github.com/UkWood/LLM-RAG-chat-bot/blob/docs/grounded-rag-redesign/docs/superpowers/plans/2026-11-07-grounded-rag-implementation.md)

### PR #12 — Semantic Planner V3

- Branch: `feat/semantic-planner-v3`.
- Head: `2ea295197fffebde354a1e843bac464503dd5724`.
- Draft, не слит.
- Независимая оценка: 2/24 полностью корректных положительных ответа и 16/16 корректных отказов/уточнений. Quality gate не пройден.
- Не включать V3 по умолчанию и не переносить его в main автоматически.
- [PR #12](https://github.com/UkWood/LLM-RAG-chat-bot/pull/12)

## 7. Рекомендуемая первая работа в новой сессии

Не начинать сразу с кодирования.

1. Проверить фактический main HEAD и актуальные состояния PR #13/#12.
2. Прочитать принятый site-specific пакет и правила совместной работы.
3. Сопоставить архитектуру и код PR #13 с site-specific требованиями: structured site content, Support catalog metadata, extracted PDF text, policy/revision handling, citations и refresh lifecycle.
4. Разделить reuse, gap и conflict. Подготовить архитектурное решение и план интеграции.
5. Отдельно организовать human review 15 synthetic cases PR #13, если владелец ещё не оценивал их. Не записывать grades по догадке.
6. Только после согласования архитектуры сформировать первый узкий coding task. Вероятный первый site-specific этап — read-only adapter и экспорт структурированных сущностей/фактов/связей из зафиксированного snapshot сайта, но его границы нужно уточнить после сравнения с PR #13.

## 8. Готовая инструкция для следующей сессии

Продолжаем проект AI Technical Consultant для МНПП «Сатурн». Считай `docs/SESSION_START.md` и `docs/CHATGPT_WORKING_AGREEMENT.md` актуальной точкой входа. Основная работа должна происходить здесь, в ChatGPT; Codex — только исполнитель ограниченных coding tasks по подготовленному ТЗ. Сначала проверь актуальное состояние GitHub и изучи принятые документы `docs/site-specific/`. Не изменяй `UkWood/Saturn-Main-Site` ни при каких обстоятельствах. Не сливай PR #13 или PR #12. Сначала сопоставь PR #13 с принятой site-specific архитектурой и подготовь предложение по интеграции; отдельно проверь статус human review 15 synthetic cases. Не начинай кодирование, пока не определены следующий этап, точные границы и критерии приёмки.
