# Этап 2: offline ingestion на синтетических данных

Основание: следующий шаг после M1, [roadmap](../plans/2026-11-03-ai-consultant-roadmap.md), [PUBLIC policy](../../public-source-policy.md). Поручение «Продолжай» разрешает следующий независимый offline шаг, не допуск реальных источников и не production rollout.

## Цель и границы

Проверить ingestion policy, metadata/provenance, структурированные характеристики и PDF pages до установки индексов/моделей. M1 CLI остаётся ограниченным и независимым. Новый ingestion result не становится evidence для свободных ответов автоматически. Полный milestone M2 включает этапы 2–5; этот шаг не завершает M2.

## Подходы

Выбран локальный byte-based pipeline на authored synthetic fixtures: тот же формат registry v1 валидируется для реальных pending кандидатов, однако исполняемая сборка требует test-only контекст и synthetic source IDs/URLs. Альтернатива — downloader реальных PDF — преждевременна без exact approvals и sandbox/egress. Развивать M1 sentence parser нецелесообразно: он не отражает frontmatter/site schema или PDF pages.

Инженерное решение: PyYAML SafeLoader со строгими duplicate/alias ограничениями для frontmatter, pypdf для локальных PDF. Версии/хеши фиксируются; тесты без сети/GPU/ключей после установки пакетов. PDF parser запускается в отдельном процессе с CPU/RAM/time/page/byte/text лимитами. Это обработка доверенных authored fixtures; OS sandbox без сети для недоверенных PDF остаётся gate перед real ingestion.

## Контракты

Registry immutable records, strict keys/enums/booleans/dates/hash/locator; exact approved bytes и usage нужны перед parsing. UNKNOWN/pending/revoked пропускаются без чтения content. Site input дополнительно bound к commit/path; внешние документы имеют отдельную запись и fetched hash. Никогда не наследовать approval страницы на документ. Содержимое approval records не является доказательством полномочий подписанта: production registry остаётся owner-managed.

Документ хранит source/document IDs, content hash, parser revision, title/entity type/version, source commit/path. Chunks — heading path, физическая страница для PDF, provenance field path, units и text hash. IDs deterministic; повторное ingestion идемпотентно. Dedupe не объединяет разные source approvals. Ошибка любого разрешённого документа прерывает сборку, частичный результат не возвращается.

Site adapter следует src/content.config.ts по commit 084d759487bfab6e111549c9b5469711ac5fc13e (read-only): products + software group → Software; systems.kind=category → Category; normalized relationships сохраняют исходный field path, не выводят совместимость. В text попадают только разрешённые structured content fields и Markdown body sections; служебный frontmatter/code/HTML исключены, неподдерживаемый контент закрывается. Таблица Markdown сохраняется целиком вместе с заголовками/единицами. PDF extraction — одна физическая страница на chunk; сканы/пустые страницы, encrypted/active/attachments/malformed PDF отклоняются. Сложные таблицы и OCR требуют отдельного quality profile.

## Проверка и ограничения

Тесты: deny-before-read, hash/commit drift, strict schema, draft, software/category, units/tables, relationship provenance, idempotence, same-bytes different source IDs, malformed parser, PDF physical pages, empty/encrypted/active PDF и limits. CLI build-summary показывает counts/IDs, без raw corpus/index dumps. Реальный pending registry даёт ноль разрешённых sources. Никаких cloud calls, сайта mutations или допуска реальных источников.
