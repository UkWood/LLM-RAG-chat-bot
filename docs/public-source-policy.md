# Реестр допуска PUBLIC-источников

[Реестр](../config/knowledge/public-sources.json) относится только к AI-проекту; его нельзя считать списком разрешённых файлов сайта. Сейчас это четыре проверенных кандидата Markdown и четыре не загруженных PDF-ссылки. Ничего не разрешено для ingestion или cloud автоматически.

## Состояния и обязательные поля

`visibility`: UNKNOWN/PUBLIC/INTERNAL. `approval_state`: pending/approved/revoked. Политика по умолчанию deny. UNKNOWN, pending, revoked и отсутствующее поле всегда запрещают доступ. В публичной системе INTERNAL запрещён и при local provider.

Для допуска владелец/назначенный ответственный проверяет именно указанную версию, публичную публикацию, актуальность и разрешённый способ использования. В отдельном изменении реестра заполняются:

- `visibility=PUBLIC`, `approval_state=approved`, `publication_verified=true`;
- `approved_content_sha256` — SHA-256 конкретных проверенных bytes; `observed_content_sha256` сам по себе не является допуском;
- `approval_id`, `approved_by`, `approved_at` — реальный provenance решения; не выдумывать имена и даты;
- `allowed_usage`: явно перечисленные `local_index`, `local_generate`, `cloud_generate`;
- `cloud_allowed=true` только если отдельно разрешён cloud; при этом `cloud_generate` обязан присутствовать в allowed_usage. Противоречивые комбинации не проходят validation.

У Git-источника дополнительно проверяются commit/path/hash и отсутствие draft. У external_document hash получают только после отдельно разрешённой загрузки, безопасного parsing и ручной проверки. PDF пока имеют `fetch_state=not_fetched` и не могут быть approved без hash. У каждого source — отдельный допуск; карточка не разрешает автоматически все её вложения.

Registry schema v1 описана здесь и в design document; исполняемый validator и JSON Schema — часть следующей реализации. До её появления этот JSON не используется как production access-control механизм. При реализации добавить strict schema: неизвестные поля/enum отклоняются, ID уникальны, hash 64 hex, даты валидны, source-kind поля согласованы.

## Порядок работы

1. Read-only discovery создаёт pending candidate с происхождением. Не загружать автоматически указанные PDF и не обходить каталоги файлового сервера.
2. Ответственный утверждает версию и scope использования; решение фиксируется review/approval record и ссылкой `approval_id`.
3. Индексатор проверяет exact hash/commit, publication и разрешение `local_index`; в chunks записывает source revision и policy revision.
4. Перед генерацией проверяется `local_generate` или сочетание cloud_allowed + `cloud_generate`, и privacy вопроса/истории. Источник с local-only scope не достигает внешнего provider.
5. Изменение bytes/commit переводит новую версию в pending; старое разрешение на неё не распространяется. Отзыв действует сразу через denylist, затем очищаются indexes/cache.

Хеши относятся к исходным bytes. Внешнему LLM передаются только разрешённые извлечённые фрагменты с provenance, без frontmatter, кода шаблонов, скриптов и служебных полей. Допуск не делает содержимое инструкцией для модели и не подтверждает техническую истинность каждого факта.

## Независимый путь для M1

До допуска реальных документов можно подготовить явно синтетический offline corpus с вымышленными учебными изделиями, пометкой test_only и FakeLLMProvider. Он не выдаётся за документацию Сатурна, не отправляется в cloud и не смешивается с PUBLIC corpus. Это позволяет проверить pipeline без ложного одобрения реальных источников.

## Проверка этой версии реестра

Проверены существование четырёх content paths в указанном read-only snapshot, их SHA-256, уникальность восьми source IDs и запрет всех pending entries. Содержимое PDF не проверялось. Hash drift, invalid approval и runtime enforcement будут проверяться тестами будущей реализации.
