# Site-specific architecture v0.2 — approved baseline and audit addendum

Дата: 2026-11-08  
Статус базового пакета: **APPROVED by owner; merged in PR #16**  
Статус read-only mapping addendum: **OWNER REVIEW PENDING**.

## Назначение

Пакет v0.2 задаёт интеграцию Grounded RAG с утверждённой архитектурой технического консультанта МНПП «Сатурн».

Базовые документы v0.2 согласованы владельцем и слиты в main через PR #16. Read-only audit addendum уточняет фактическую схему и семантику данных, обнаруженные при проверке snapshot сайта.

## Базовые документы — утверждены

1. [Матрица интеграции PR #13 и v0.1](01-integration-matrix.md).
2. [Целевая архитектура v0.2](02-architecture.md).
3. [План реализации и критерии приёмки](03-implementation-plan.md).
4. [ADR-0012: интеграция знаний Сатурна](../../decisions/0012-saturn-knowledge-integration.md).

## Audit addendum — ожидает review

5. [Read-only schema audit and canonical mapping](04-read-only-schema-audit.md).
6. [Source data quality register](05-data-quality-register.md).
7. [ADR-0013: provenance and semantic status of relations](../../decisions/0013-saturn-relation-provenance.md).
8. [Stage report: read-only schema audit](../../stages/2026-11-08-saturn-read-only-schema-audit.md).

## Исходные документы v0.1

- [Site-specific README v0.1](../README.md)
- [Техническое задание v0.1](../01-technical-specification.md)
- [Архитектура v0.1](../02-architecture.md)
- [Карта источников](../03-source-inventory.md)
- [План реализации v0.1](../04-implementation-plan.md)
- [План испытаний и приёмки](../06-acceptance-plan.md)
- [ADR-0011: read-only адаптеры и границы поиска](../../decisions/0011-site-source-adapters-and-search-boundaries.md)

## Неприкосновенные ограничения

- UkWood/Saturn-Main-Site — строго READ-ONLY.
- Текущие поиски сайта /search/ и /service/search/ не изменять.
- Весь код, документы, индексы, тесты и решения AI-консультанта размещать только в UkWood/LLM-RAG-chat-bot.
- UNKNOWN, pending или revoked sources не индексировать и не передавать LLM.
- Допуск страницы не означает допуска связанного PDF.
- Новая версия источника не наследует approval предыдущей версии.
- Никаких реальных ingestion, cloud calls, deployment и merge без отдельного решения владельца.

## Текущая точка

- PR #16 merged: bf59284b4af9fa9d0a853595ba4fa31d89f53984.
- Source audit pinned to Saturn-Main-Site@084d759487bfab6e111549c9b5469711ac5fc13e.
- Mapping audit complete; owner approval of ADR-0013 and relation eligibility remains pending.
- No application code or real source ingestion has started.
