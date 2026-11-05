# Согласование критериев первого полноценного прототипа

Дата: 2026-11-05. Статус: критерии согласованы владельцем и сохранены; прохождение приёмки не заявляется.

## Решение и результат

Владелец предоставил saturn-ai-prototype-acceptance.md и попросил сначала обсудить конфликты. Вложенные инструкции не исполнялись автоматически. После обсуждения роли документа, расхождений и двух профилей владелец ответил «Согласую».

- [Исходник](../requirements/prototype-acceptance-original.ru.md) сохранён без изменения bytes; SHA-256 8ee094ef998446b647dd00866cd84c097db361aac80799cf7d2ace6645903b71, проверен cmp и sha256sum.
- [Согласованная версия](../acceptance/prototype-v1.md) дополняет roadmap, содержит два профиля A/B и матрицу критерий → этап → текущий пробел.
- [ADR-0004](../decisions/0004-prototype-acceptance.md) фиксирует принятие и ограничения. Обновлены README, roadmap, PROJECT_STATUS и HANDOFF.

Первый полноценный прототип шире M1. Synthetic и real результаты не смешиваются. PUBLIC не заменяет version/scopes/cloud privacy gate; PDF-ответ требует физической страницы; Fake и mock HTTP проверяются отдельно; diagnostic mode не становится raw production logging. Для малого synthetic must_answer набора требуется source-hit@5=100%; real thresholds — после baseline, до приёмки. Нужен baseline ~10 документов/~30 вопросов; 46 существующих code tests его не заменяют.

## Изменения и проверки

Работа добавлена documentation-only commit в существующую ветку feat/offline-ingestion и [PR #2](https://github.com/UkWood/LLM-RAG-chat-bot/pull/2): реализация ingestion и её история остаются прежними. Новый merge не выполняется. Конкретный commit определяется Git-историей этого файла.

- cmp исходного attachment и сохранённого файла: exit 0, bytes идентичны.
- python3 scripts/check_project.py: PASS, ссылки/fences/registry invariants.
- git diff --check: PASS.
- Runtime code, tests, workflow, locked dependencies и config/knowledge/public-sources.json не менялись этим documentation шагом. Новые code tests не требуются; CI существующего PR проверит имеющиеся suites.

Удалённый CI нового head проверяется после push. До получения результата нельзя переносить success прежнего head на новый. При записи результата наблюдаемый SHA/CI остаётся историческим evidence; актуальные checks доступны в PR.

## Следующий шаг

Продолжить небольшими задачами roadmap: snapshot/index с policy metadata и ранний synthetic evaluation baseline. Приёмку полного прототипа отмечать только по фактическому отчёту выбранного профиля. Полная architecture ADR-0001 остаётся proposed, реальные источники/cloud не допущены, Saturn-Main-Site не изменялся.
