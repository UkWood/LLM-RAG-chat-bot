# Site-specific architecture v0.2 — Saturn

Статус: **ACCEPTED**. Архитектурная основа утверждена PR #16; доверенная source policy и schema evolution уточнены владельцем 2026-11-09.

## Основные документы

1. [Integration matrix](01-integration-matrix.md) — выборочное переиспользование PR #13.
2. [Target architecture](02-architecture.md) — adapters, canonical model, retrieval и answer flow.
3. [Implementation plan](03-implementation-plan.md) — последовательность работ и критерии PASS.
4. [Source schema and adapter evolution](04-read-only-schema-audit.md) — фактическая схема сайта и правила обновления.
5. [ADR-0012](../../decisions/0012-saturn-knowledge-integration.md) — интеграция с существующим Grounded RAG.
6. [ADR-0013](../../decisions/0013-saturn-relation-provenance.md) — доверие к данным и эволюция адаптера.

## Неприкосновенные ограничения

- UkWood/Saturn-Main-Site — строго READ-ONLY.
- Все non-draft данные, связи и PDF-ссылки сайта считаются доверенными; ручное content approval не требуется.
- Каждая sync фиксирует commit/hash и версии адаптера для воспроизводимости.
- Изменения структуры обнаруживаются автоматически; unknown data не теряется.
- Cloud generation — отдельное решение о передаче данных provider, не проверка достоверности источника.
- Текущие /search/ и /service/search/ сайта не изменяются.
- Весь код и knowledge artifacts размещаются только в UkWood/LLM-RAG-chat-bot.
