# Состояние проекта

Обновлено: 2026-11-04. Репозиторий: UkWood/LLM-RAG-chat-bot.

## Выполнено

- Сохранены ТЗ, read-only discovery сайта по 084d759487bfab6e111549c9b5469711ac5fc13e, roadmap, архитектура v0.1 и proposed ADR-0001.
- PUBLIC registry: 4 Markdown + 4 PDF кандидата; все pending/UNKNOWN, без допуска и cloud.
- Реализован synthetic-only offline M1: ingestion с hash/policy → in-memory index → entity/aspect retrieval → FakeLLMProvider → extractive grounding → backend citations/refusal. CLI и тесты не требуют GPU/сети/ключей.
- Проверки документации/реестра и backend suite включены в CI. Подробности и evidence: [отчёт M1](stages/2026-11-04-m1-offline-rag.md).
- GitHub API теперь доступен; получен актуальный main/handoff. Все три прежних CI запуска success подтверждены по API.

## Текущая публикация

Ветка feat/m1-offline-rag; первый продуктовый commit fd0598b. Финальный PR/CI фиксируется в отчёте после проверки. Изменения сайта отсутствуют.

## Ограничения

- M1 разрешён поручением владельца продолжить synthetic/offline разработку; полная архитектура остаётся proposed. Полную приёмку Phase 0 и допуск real sample не объявлять.
- Поддержаны два fixture intents с точным учебным обозначением; строгая грамматика фактов не заменяет реальный parser и quality evaluation.
- Реальные PDF не загружены; backend HTTP/API/UI, реальные модели, Qdrant и deployment не реализованы.

## Следующий шаг

M2: ingestion сайта/PDF, runtime registry validation и provenance. Реальные exact revisions должны получить явный допуск. Без допуска продолжать только synthetic tests/adapters.

[Дорожная карта](superpowers/plans/2026-11-03-ai-consultant-roadmap.md), [архитектура](superpowers/specs/2026-11-03-ai-consultant-design.md), [план M1](superpowers/plans/2026-11-04-m1-offline-rag.md), [handoff](HANDOFF.md).
