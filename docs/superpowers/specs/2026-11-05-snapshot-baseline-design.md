# Snapshot contracts и synthetic evaluation baseline

Дата: 2026-11-05. Scope согласован владельцем: ближайший PR — snapshot-контракты и контрольный dataset, воспроизводимая проверка до подключения моделей. Основание: [критерии](../../acceptance/prototype-v1.md), [ADR-0004](../../decisions/0004-prototype-acceptance.md), этап 3 [roadmap](../plans/2026-11-03-ai-consultant-roadmap.md).

## Цель и подход

Связать immutable ingestion result с точным registry revision и явными policy metadata в индексируемом chunk. Подготовить 10 authored вымышленных документов (8 Markdown + 2 PDF) и 30 вопросов согласно согласованному распределению, сохранив факт/источник/страницу и ожидаемый answered/refused/clarification.

Инженерное решение: in-memory контракт публикации snapshot с двумя IndexDescriptor (dense/lexical) и атомарным pointer под lock. Descriptor — declaration coverage/config, не готовый индекс и не проверка реальных vectors/artifacts. Альтернатива немедленно устанавливать Qdrant/модели расширяет этот PR за согласованные границы. Persistence, настоящие index adapters и ranking относятся к следующему PR.

Snapshot содержит immutable documents и IndexedChunk wrappers с visibility, approval_state, usage, policy revision, source hash и locator. Builder повторно сверяет source/document/chunk provenance и exact policy; silent dropping разрешённых документов запрещён. Snapshot identity зависит от полного содержимого/metadata и registry, стабилен при перестановке входных records. При любом несоответствии сборка отклоняется. Test-only context сохраняется.

Catalog активирует только bundle с одинаковым snapshot и полным набором chunk IDs в обоих descriptors. Capture возвращает один immutable bundle. Failed promotion сохраняет предыдущий. Обновление/удаление — новая сборка, rollback меняет только corpus pointer. Runtime registry и append-only revocations отдельны; старый capture обязан повторно проходить текущую policy перед чтением/генерацией. Никаких cloud/provider/index сетевых вызовов.

## Dataset и preflight

Fixtures лежат отдельно от реального registry и M1; настоящие обозначения не получают вымышленных характеристик. PDFs — authored source fixtures, не corpus/index dumps, генерируются детерминированно из versioned page descriptions. Физические pages проверяются настоящим PDF adapter. Текст PDF учебный English/ASCII, вопросы русские; это не доказательство качества extraction русских PDF.

Versioned JSON labels: id, question, category, split, expected_status, must_answer/must_refuse, expected_sources, expected_facts и expected_evidence (source/text/field/page). Negative/clarification cases не содержат фиктивного evidence. Позитивные expected facts должны буквально поддерживаться разрешёнными parsed chunks и иметь согласованные source/page pointers. Отдельные calibration 20 и held_out 10, по одному held_out case каждой категории; held_out не используется для настройки будущих порогов.

Preflight валидирует структуру, hashes/revisions, категории/количество, непротиворечивость статусов и evidence labels. Он не запускает retrieval, не подбирает ответ по dataset, не генерирует псевдометрики. Отчёт явно retrieval/grounding=not_run и не закрывает source-hit@5 acceptance. Одна команда после locked install выполняет document checks, все unit/integration tests и preflight; малый безопасный отчёт counts/revisions/per-case label validation сохраняется в repo без raw корпусных dumps.

## Приёмка этого PR

Тесты на idempotence, tampered text/hash/provenance, missing/extra/duplicate docs/chunks, registry mismatch, mismatched/incomplete index descriptors, failed activation, read capture, deletion/update/rollback и неоткатываемые revocations. Dataset: exact distribution 30, поддержанные labels/pages, duplicate IDs/keys, contradictory expectations, real-source injection, missing facts и drift. Реальные sources/policy, M1 generation и сайт не меняются.
