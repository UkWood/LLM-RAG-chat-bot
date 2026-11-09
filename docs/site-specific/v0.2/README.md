# Site-specific architecture v0.2 — Saturn

Статус: **ACCEPTED**. Архитектурная основа утверждена PR #16; доверенная source policy и schema evolution уточнены владельцем 2026-11-09.

## Основные документы

1. [Integration matrix](01-integration-matrix.md) — выборочное переиспользование PR #13.
2. [Target architecture](02-architecture.md) — adapters, canonical model, retrieval и answer flow.
3. [Implementation plan](03-implementation-plan.md) — последовательность работ и критерии PASS.
4. [Source schema and adapter evolution](04-read-only-schema-audit.md) — фактическая схема сайта и правила обновления.
5. [Snapshot Provider Contract](05-snapshot-provider-contract.md) — provider-neutral REST contract, pinning, tree completeness, blob integrity and PDF boundary.
6. [ADR-0012](../../decisions/0012-saturn-knowledge-integration.md) — интеграция с существующим Grounded RAG.
7. [ADR-0013](../../decisions/0013-saturn-relation-provenance.md) — доверие к данным и эволюция адаптера.
8. [ADR-0014](../../decisions/0014-snapshot-provider-contract.md) — Git REST transport, trust boundary and Snapshot Provider decision.

## Неприкосновенные ограничения

- UkWood/Saturn-Main-Site — строго READ-ONLY.
- Все non-draft данные, связи и PDF-ссылки сайта считаются доверенными; ручное content approval не требуется.
- Каждая sync фиксирует commit/hash и версии адаптера для воспроизводимости.
- Snapshot Provider использует Git REST: GitHub первым, Gitea позднее; main разрешается один раз, затем используются только immutable object IDs.
- PDF остаются обязательной частью корпуса и обрабатываются через Support Catalog Adapter и External Document Adapter, отдельно от обычного Git snapshot.
- Изменения структуры обнаруживаются автоматически; unknown data не теряется.
- Cloud generation — отдельное решение о передаче данных provider, не проверка достоверности источника.
- Текущие /search/ и /service/search/ сайта не изменяются.
- Весь код и knowledge artifacts размещаются только в UkWood/LLM-RAG-chat-bot.
