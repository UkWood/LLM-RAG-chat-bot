# ADR-0003: offline ingestion и отдельный runtime registry

Дата: 2026-11-04. Статус: implemented для synthetic-only этапа 2; полная production архитектура ADR-0001 остаётся proposed.

## Решение

Строгий runtime loader registry v1 принимает неизменяемые записи и проверяет exact hashes, source commit, provenance допуска, publication, visibility, scopes, URL/path и типы. Реальные pending кандидаты проходят schema validation и остаются запрещёнными. Это не подтверждение полномочий указанного approved_by: изменение production approvals остаётся обязанностью владельца.

Сборщик поддерживает только synthetic registry context, source IDs и inert PDF URLs; неизвестные/неразрешённые bytes не читаются. Выход отделён от M1 generation evidence: extractive копирование произвольного parsed text не объявляется grounding. Один сбой разрешённого parser прерывает всю сборку, immutable result не возвращает частично успешный snapshot.

Карточки: bounded PyYAML SafeLoader без aliases/tags/duplicate keys; mapping по схеме сайта на pinned 084d759487bfab6e111549c9b5469711ac5fc13e, прочитанной только для discovery. Structured facts сохраняют units/field paths, relationships сохраняют происхождение и не превращаются в вывод о совместимости. Текстовые таблицы Markdown не разрываются. PDF: pypdf в процессе с ресурсными лимитами, физические pages и fail-closed для encrypted/active/empty documents. Непроверенные таблицы PDF и OCR не поддерживаются как доказательные данные.

## Альтернативы и цена

Продолжать M1 sentence grammar — недостаточно для реальной модели контента. Downloader и разрешение существующих PDF без owner approvals — недопустимы. Выбран локальный fixture pipeline с двумя pinned dependencies и wheel hashes для Python 3.12/Linux x86_64. Другие платформы требуют расширения lock hashes и тестирования; M1 CLI по-прежнему stdlib-only.

Процессные лимиты не заменяют OS sandbox/egress для недоверенных файлов; настоящий ingestion остаётся выключенным. Нужны допуск exact real sample, parser sandbox, PDF quality/OCR review и runtime интеграция policy с будущим retrieval. Strict runtime validation реализована кодом, отдельная публикуемая JSON Schema остаётся дальнейшей задачей, не заявляется выполненной.
