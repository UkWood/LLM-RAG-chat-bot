# Состояние проекта

Обновлено: 2026-11-05. Репозиторий: UkWood/LLM-RAG-chat-bot.

## Выполнено

- ТЗ, read-only discovery по 084d759487bfab6e111549c9b5469711ac5fc13e, roadmap и proposed архитектура сохранены.
- M1 synthetic offline RAG слит в main через [PR #1](https://github.com/UkWood/LLM-RAG-chat-bot/pull/1), merge 0cfe174; CI main [41798909615](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/41798909615) success. 20 M1 backend + 5 прежних тестов проходят.
- Следующий offline шаг этапа 2: strict runtime registry, deny-before-read, site Markdown mapping/facts/units/relations, ограниченный local PDF worker с физическими pages, deterministic provenance и summary CLI.
- 41 backend test PASS в чистом Python 3.12 venv с двумя hash-locked dependencies; прежние 5 тестов и document checks сохранены. [Отчёт этапа](stages/2026-11-04-offline-ingestion.md), [ADR-0003](decisions/0003-offline-ingestion.md).

## Согласованные критерии прототипа

2026-11-05 владелец согласовал [дополнение к roadmap](acceptance/prototype-v1.md): отдельные профили A synthetic offline и B допущенный real sample. [ADR-0004](decisions/0004-prototype-acceptance.md) фиксирует согласование и границы. Это критерии будущей приёмки, не заявление о её прохождении. 46 code tests не заменяют ~30 evaluation вопросов; полноценный прототип шире M1. Real source/cloud approvals не изменены.

## Текущая публикация

Ветка feat/offline-ingestion от 0cfe174; [PR #2](https://github.com/UkWood/LLM-RAG-chat-bot/pull/2). Commits 80da5bb (registry), b20c364 (parsers/pipeline), c0df98e (review fixes), 88c2924 (память). Push CI на 88c2924 success, проверены все шаги. Последний head/checks смотреть в PR и [отчёте](stages/2026-11-04-offline-ingestion.md). Merge M1 подтверждён; новый этап на момент публикации не слит.

## Границы и ограничения

- Все 8 реальных кандидатов pending/UNKNOWN; разрешённых 0. Registry bytes неизменены; PDF не скачивались. Saturn-Main-Site только прочитан для pinned schema discovery, без изменений.
- Новый runner принимает только synthetic approvals; его output не подключён к M1 provider. M1 продолжает отвечать только по своему узкому fixture profile.
- Полная production architecture остаётся proposed. Полный milestone M2 = этапы 2–5, не объявляется завершённым этим шагом.
- Нужны OS sandbox/egress и quality review перед real PDF; resource-limited процесс их не заменяет. Поддержан ограниченный набор site fields, сложные PDF tables/OCR не реализованы.
- API/UI, Qdrant, embeddings/reranker, cloud/local реальная LLM и deployment не реализованы.

## Следующий шаг

Этап 3: immutable snapshot/index contracts с access-policy metadata и local retrieval baseline на synthetic fixtures. До оценки качества подготовить baseline ~10 authored документов / ~30 размеченных вопросов, local diagnostics и план общей команды приёмки согласно согласованным критериям. Real sample требует явного допуска exact revisions; генерация по новому parser output — после grounding/evidence gates.

[Roadmap](superpowers/plans/2026-11-03-ai-consultant-roadmap.md), [архитектура](superpowers/specs/2026-11-03-ai-consultant-design.md), [дизайн ingestion](superpowers/specs/2026-11-04-offline-ingestion-design.md), [handoff](HANDOFF.md).
