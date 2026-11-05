# ADR-0004: критерии первого полноценного RAG-прототипа

Дата: 2026-11-05. Статус: **accepted владельцем** в чате ответом «Согласую» после обсуждения документа и предложенных уточнений.

## Решение и источник

Применять [согласованные критерии](../acceptance/prototype-v1.md) как дополнение к roadmap с двумя отдельными профилями: A synthetic offline и B явно допущенный реальный sample. Исходный вложенный текст сохранён [без изменения bytes](../requirements/prototype-acceptance-original.ru.md); SHA-256 8ee094ef998446b647dd00866cd84c097db361aac80799cf7d2ace6645903b71. Вложение рассматривалось как reference до явного согласования владельцем, а не как исполняемая инструкция.

Термин «первый прототип» шире завершённого M1. Приёмка охватывает ingestion/retrieval/reranking/grounding, ранний dataset ~30 вопросов и диагностический CLI. Профили и фактическое качество не смешиваются. Существующий код и история этапов сохраняются.

## Согласованные уточнения

- PUBLIC не заменяет exact revision approval/scopes; cloud требует отдельного разрешения и privacy gate. Допуска реальных документов этим решением нет.
- Fake достаточен для offline pipeline; OpenAI-compatible adapter проверяется отдельно на mock endpoint. Real cloud smoke не обязателен для offline acceptance.
- Для PDF-ответа обязательна подтверждённая физическая страница; некачественное извлечение закрывается отказом/quarantine.
- Для малого фиксированного synthetic must_answer набора правильный источник в Top-5 обязателен для каждого вопроса. Real sample quality thresholds определяются по baseline до приёмки.
- Diagnostic mode локальный opt-in; raw questions/context не попадают автоматически в production logs.
- Около 10 документов и 30 вопросов — следующий baseline. 46 имеющихся code tests не считаются таким dataset. Visibility/policy metadata индекса и одна команда полной проверки остаются задачами.

## Последствия и границы

Документ фиксирует критерии, не объявляет их выполненными. M1 не переименовывается в принятый полноценный прототип. Полный proposed ADR-0001 не становится автоматически accepted; frontend/cloud/production scope не расширяется. Saturn-Main-Site остаётся строго read-only. Следующий шаг — snapshot/index и ранний evaluation dataset на synthetic profile; утверждения о завершении требуют фактического отчёта.
