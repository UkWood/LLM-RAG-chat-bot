# Stage report: canonical Saturn source contracts

Дата: 2026-11-09  
Статус: **COMPLETED — PR #18 merged**

## Scope

Первый программный этап после принятия ADR-0012/0013: канонические контракты Saturn source/evidence и pure schema-evolution primitives. Live site sync, PDF download, retrieval и generation в scope не входили.

## Реализация

PR #18: https://github.com/UkWood/LLM-RAG-chat-bot/pull/18  
Merge commit: \`223350c9f6f104b5b67aadd124bfc968f12f5dbf\`

Добавлены:
- \`backend/src/saturn_ai/ingestion/saturn_contracts.py\`;
- \`backend/src/saturn_ai/ingestion/schema_evolution.py\`;
- \`backend/tests/unit/test_saturn_contracts.py\`;
- \`backend/tests/unit/test_saturn_schema_evolution.py\`.

Контракты фиксируют source revisions, entities, raw/normalized facts, explicit relations, SupportDocument owners, PDF revisions, page-addressable evidence, schema inventory/drift и deterministic sync manifest.

## Проверка

GitHub Actions для exact PR head \`e13dc85b82c79d4696d483c4ef3bb3704500fc73\`:
- offline checks: SUCCESS;
- 192 tests run, 11 existing optional skips, no failures;
- ONNX contracts: SUCCESS.

Synthetic lexical evaluation осталась отдельной исторической метрикой и не является проверкой качества Saturn adapter. Новые модули не подключены к реальному сайту.

## Ограничения

- Нет GitHub/site snapshot client.
- Нет импорта реальных Saturn Markdown records.
- Нет Support Catalog crawler/link collector или PDF fetch/parser integration.
- Нет index/retrieval/generation integration.
- Нет cloud/provider call или deployment.
- Legacy synthetic ingestion path не менялся.

## Следующий этап

Site Content Adapter: pure/offline parsing of a pinned source snapshot; dynamic collections; safe YAML frontmatter; preservation of raw fields/body; known semantic mapping plus generic fallback; explicit relations; deterministic manifest. Требования и разделение сессий — в \`docs/HANDOFF.md\` и \`docs/CHATGPT_SESSION_GUIDE.md\`.
