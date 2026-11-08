# Правила AI Technical Consultant

## Начало работы

Прочитать README.md, docs/PROJECT_STATUS.md, roadmap и документ текущего этапа. Репозиторий — долговременная память проекта; важные решения не оставлять только в чате. Полные права владельца распространяются на UkWood/LLM-RAG-chat-bot; не запрашивать повторно разрешение на обычные изменения и публикацию в этом репозитории.

## Неприкосновенный сайт

UkWood/Saturn-Main-Site используется только read-only. Запрещены изменения исходников, CI, URL/assets, коммиты и push в него. Discovery фиксирует commit и происхождение сведений. Не переносить целиком сайт или служебные файлы в KB.

## Процесс и память

- Одна содержательная задача — небольшая ветка/commit; feature branch и PR при наличии GitHub API. Не переписывать историю и не применять force push без отдельной причины.
- ТЗ → дизайн/ADR → план → тесты/реализация → фактическая проверка → отчёт этапа → публикация. Не объявлять этап завершённым по одному успешному install/compile.
- В конце каждого этапа обновлять docs/PROJECT_STATUS.md и docs/stages/: результат, commits/PR, выполненные команды и исходы, ограничения, следующий шаг. Не выдавать pending approvals за полученные.
- ADR хранит существенные решения и их статус; планы — зависимости и критерии приёмки. Исправления решений сохранять с объяснением, не скрывать историю.
- GitHub CI обязателен для имеющихся проверок; тесты приложения добавлять вместе с кодом. CD — после появления реального deployable и целевой инфраструктуры, с проверками и защищёнными секретами.
- Если API GitHub недоступен, сохранить результаты Git push, явно записать ограничения PR/issues/checks; не заявлять, что удалённый CI прошёл без результата.

## Source trust и безопасность

- Для generic/legacy external sources и старого registry-пути действует default-deny: PUBLIC требует явного допуска exact revision/hash/scope; UNKNOWN/pending/revoked запрещены.
- **Исключение Saturn:** для `UkWood/Saturn-Main-Site@main` действует owner-approved trust root из ADR-0012/0013. Все non-draft site records, declared relations, dictionaries и прямые linked PDFs доверенные; ручной per-source/per-revision approval не применяется.
- Исключение Saturn не разрешает cloud egress. Внешний provider/data egress — отдельная runtime policy.
- Не подключать новый Saturn adapter к legacy `SourceRecord/Registry` и не удалять его approval checks глобально. Старый путь остаётся для synthetic/прочих generic sources.

Не коммитить secrets, .env, raw user logs, модели, corpus/index dumps. Без evidence — отказ; citations строит backend. Provider сменный; embeddings/reranking локальные. CI/dev не требуют GPU или облачных ключей.

## Среда

Облачная задача уже изолирована. Использовать существующий checkout; не создавать Git worktree без явного запроса пользователя. Процессы не переживают snapshot автоматически; команды запуска документировать при появлении сервисов.
