# Состояние проекта

Обновлено: 2026-11-05. Репозиторий UkWood/LLM-RAG-chat-bot.

## Выполнено

- M1 synthetic offline RAG слит через PR #1, merge 0cfe174; CI success.
- Offline ingestion + согласованные prototype criteria слиты через [PR #2](https://github.com/UkWood/LLM-RAG-chat-bot/pull/2): merge 909072f, [main CI 42062413579](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42062413579) success. 46 прежних code tests сохранены.
- Новый этап 3a: immutable snapshot/policy payloads, source-byte/canonical extraction binding, dense/lexical descriptor coverage и process-local catalog с независимыми current policy/revocations.
- Подготовлены 10 authored synthetic документов (8 MD +2 PDF), 44 chunks и 30 gold-label questions; calibration 20/held_out 10. Отдельные expectations answered20/refused8/clarification2; реальные retrieval/answer outcomes ещё не измерены.
- Единая команда проверки: scripts/verify_offline.py. 5 прежних +60 backend tests PASS, preflight labels PASS; [безопасный отчёт](../evaluation/reports/2026-11-05-baseline-preflight.json). [Результаты этапа](stages/2026-11-05-snapshot-baseline.md), [ADR-0005](decisions/0005-snapshot-baseline.md).

## Согласованная приёмка и границы

[Prototype v1](acceptance/prototype-v1.md), ADR-0004 accepted: A synthetic offline / B отдельно допущенный реальный sample. M1 и code tests не равны полной приёмке. Dataset подготовлен, но metrics retrieval/reranking/grounding=not_run; source_hit_at_5=null. Полный M2 (этапы 2–5) не завершён.

Все 8 реальных кандидатов pending/UNKNOWN; разрешённых 0. Real registry bytes неизменны, PDF не загружались. Saturn-Main-Site read-only и не изменялся. Source receipts нового snapshot содержат только synthetic approved bytes в памяти; произвольный parsed text не подключён к M1 provider.

Полный ADR-0001 proposed. Persistence/multi-worker snapshots, реальные indexes/embeddings/reranker, scored retrieval, генерация по новому output, cloud/API/UI/deployment и OS parser sandbox для real corpus остаются будущими задачами.

## Текущая публикация

Ветка feat/snapshot-evaluation-baseline от main 909072f. Основные commits 7dead21, 80d5dc4, 1788198; fixes f4d22ea. [PR #3](https://github.com/UkWood/LLM-RAG-chat-bot/pull/3) открыт в main. Push CI на 29422fe success, locked install и unified verification подтверждены jobs API. Последний head/checks — в PR и отчёте этапа. PR #2 уже merged; новый этап не сливался.

## Следующий шаг

Local index adapters и реальный retrieval baseline на synthetic dataset. Затем fusion/reranking и evidence/grounding. Считать Top-5 по фактическим результатам; держать held_out отдельно от calibration. Real sample/cloud требуют явного допуска exact revisions и отдельных quality/privacy gates.

[Roadmap](superpowers/plans/2026-11-03-ai-consultant-roadmap.md), [snapshot design](superpowers/specs/2026-11-05-snapshot-baseline-design.md), [handoff](HANDOFF.md).
