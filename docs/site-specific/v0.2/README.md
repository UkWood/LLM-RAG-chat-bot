# Site-specific architecture v0.2 — integration proposal

Дата: 2026-11-08  
Статус: **PROPOSED — требуется рассмотрение и утверждение владельцем**  
База: main 3cd6787db2fe00fd7cea49bce8a355a27f292bf0  
Связанная экспериментальная работа: PR #13, branch docs/grounded-rag-redesign  
Фундаментальная основа: site-specific v0.1, утверждённая владельцем и включённая в main через PR #14.

## Назначение

Пакет v0.2 определяет, как интегрировать экспериментальный Grounded RAG из PR #13 с утверждённой архитектурой технического консультанта МНПП «Сатурн».

Это архитектурные документы, а не разрешение на программирование, ingestion реальных источников, внешние LLM-вызовы, deployment или merge экспериментальных веток.

## Документы пакета

1. [Матрица интеграции PR #13 и v0.1](01-integration-matrix.md) — что уже существует, что можно переиспользовать, что требуется изменить или разработать.
2. [Целевая архитектура v0.2](02-architecture.md) — модель знаний, три адаптера источников, revision policy, unified snapshot, retrieval и grounded answer flow.
3. [План реализации и критерии приёмки](03-implementation-plan.md) — последовательность этапов, зависимости, gates и границы будущих coding tasks.
4. [ADR-0012: интеграция знаний Сатурна](../../decisions/0012-saturn-knowledge-integration.md) — предлагаемые архитектурные решения и явно отложенные решения.

## Исходные документы

- [Site-specific README v0.1](../README.md)
- [Техническое задание v0.1](../01-technical-specification.md)
- [Архитектура v0.1](../02-architecture.md)
- [Карта источников](../03-source-inventory.md)
- [План реализации v0.1](../04-implementation-plan.md)
- [План испытаний и приёмки](../06-acceptance-plan.md)
- [ADR-0011: read-only адаптеры и границы поиска](../../decisions/0011-site-source-adapters-and-search-boundaries.md)

## Текущая точка

- main остаётся на 3cd6787db2fe00fd7cea49bce8a355a27f292bf0.
- PR #13 остаётся Draft и не слит. Его head основан на прежнем main bb16530e5b9a4943abae5c1b0f526cb218f46b2d.
- PR #13 содержит полезные компоненты публикации и grounded RAG, но не реализует все три source adapters, требуемые v0.1.
- Human answer assessment PR #13 остаётся pending. 15/15 технически завершённых диагностических случаев и зелёный CI не являются оценкой правильности ответов.
- PR #12 Semantic Planner V3 не принимается как основа: его независимый blind quality gate завершился 2/24 положительных случаев и 16/16 отрицательных/неоднозначных.
- PR #15 с соглашением о совместной работе и handoff на момент подготовки этого пакета открыт, не слит.

## Неприкосновенные ограничения

- UkWood/Saturn-Main-Site — строго READ-ONLY. В рамках проекта запрещены любые записи в этот репозиторий: файлы, контент, assets, workflows, branches, commits, PR, settings и история.
- Текущие поиски сайта /search/ и /service/search/ не изменять и не заменять.
- Весь код, документы, индексы, тесты и решения AI-консультанта размещать только в UkWood/LLM-RAG-chat-bot.
- Источники UNKNOWN, pending или revoked не индексировать и не передавать LLM.
- Допуск страницы сайта не означает допуска связанного PDF.
- Новая версия источника не наследует approval предыдущей версии.
- Никаких реальных ingestion, cloud calls, production deployment и merge без отдельного решения владельца.
- Этот пакет не утверждает LLM provider, embedding model, reranker, OCR stack, API domain или инфраструктуру.

## Статус утверждения

До явного решения владельца все документы пакета имеют статус PROPOSED. Их публикация в отдельной docs-ветке и Draft PR предназначена для review; main не изменяется.
