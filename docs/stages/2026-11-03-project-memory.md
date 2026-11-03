# Этап: discovery, архитектура и долговременная память

Дата: 2026-11-03. Статус: опубликовано в main; локальные проверки пройдены, результат удалённого Actions пока не подтверждён.

## Результат

Сохранены исходное ТЗ, discovery по конкретному commit сайта, roadmap, design v0.1, proposed ADR-0001, правила PUBLIC и 8 pending-кандидатов. Независимый builder check архитектуры: `nothing important left`. Это не означает принятие дизайна владельцем или допуск реальных документов.

Добавлены README, AGENTS, PROJECT_STATUS, журнал этапов, issue/PR templates и GitHub Actions workflow. CI выполняет offline проверки ссылок/Markdown fences и инвариантов реестра; runtime validator и приложение не созданы. CD пока не включён: нет deployable, сервера и проверенного production-процесса.

## Проверки

- Предыдущая проверка: четыре observed SHA-256 соответствуют read-only commit сайта `084d759487bfab6e111549c9b5469711ac5fc13e`; 8 IDs уникальны; все permissions закрыты.
- `python scripts/check_project.py`: PASS, ссылки/Markdown fences и инварианты реестра.
- `python -m unittest discover -s tests -v`: 5 тестов PASS; негативные сценарии сохранены в репозитории и запускаются в CI.
- Негативные проверки: неразрешённый cloud, дубликат ID, approval без hash и path traversal должны отклоняться.
- Репозиторий сайта не изменялся; реальные PDF не скачивались.

## GitHub

`git ls-remote origin` успешен, remote refs отсутствуют: публикация будет первым коммитом репозитория. GitHub API (`gh api repos/UkWood/LLM-RAG-chat-bot`) вернул `Forbidden`; настройки через API, issues/PR и чтение результатов Actions пока недоступны. Полные права владельца не устраняют сетевые ограничения среды. Токены не извлекались и не запрашивались.

Первый commit: `0b199b3489da5565cace7ce1283beded132aca74` (`docs: establish project memory, architecture and offline CI`). `git push -u origin main` завершился с exit 0; `git ls-remote origin refs/heads/main` подтвердил тот же SHA. Исходное ТЗ сохранено без изменения текста, окончания строк нормализованы CRLF → LF.

[CI workflow](https://github.com/UkWood/LLM-RAG-chat-bot/actions/workflows/ci.yml) опубликован; результат удалённого запуска не прочитан из-за Forbidden от API. Branch protection, PR/issues и deployment не настроены через API; нельзя заявлять, что эти механизмы активированы.

Результаты последующих Git push и точные commits сохраняются в истории и отчётах. Нельзя утверждать успех удалённого CI без его фактического результата. Bootstrap публикуется в main; последующие продуктовые изменения — feature branches/PR, когда доступ к API позволяет это сделать.

## Дальше

M1 — синтетический CPU/offline вертикальный RAG с FakeLLMProvider. Реальные источники остаются pending до явного допуска. В конце этапа обновить статус, проверки и отчёт, опубликовать изменения в этом репозитории.
