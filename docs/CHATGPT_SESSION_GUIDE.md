# Организация двух сессий ChatGPT

Дата: 2026-11-09  
Проект: AI Technical Consultant — МНПП «Сатурн»

## Зачем разделяем

Проект переходит к регулярной разработке. Архитектурные обсуждения, изменения требований и coding work требуют разного контекста. Чтобы не раздувать одну сессию и не смешивать принятие решений с написанием кода, используются две роли ChatGPT.

## Сессия A — архитектура и управление

**Текущая сессия.**

Зона ответственности:
- требования, архитектура, ADR и границы системы;
- выбор последовательности этапов и декомпозиция задач;
- критерии приёмки и решения по спорным случаям;
- review PR и анализ результатов тестов;
- решение, когда задача готова к merge.

Не ведёт параллельную реализацию тех же файлов, пока coding session работает над feature PR.

## Сессия B — реализация кода

**Новая сессия ChatGPT, которую нужно создать.**

Зона ответственности:
- исследование существующего кода в рамках конкретной задачи;
- реализация согласованного scope в feature branch;
- unit/contract tests, локальная проверка и CI;
- PR с точным описанием diff, команд и PASS/FAIL;
- технический handoff после завершения задачи.

Не меняет самостоятельно архитектуру, ADR, scope, evaluation policy, source trust, provider policy или deployment. Если код требует такого решения, возвращает вопрос в архитектурную сессию.

## Общие правила

1. GitHub \`UkWood/LLM-RAG-chat-bot\` — единый источник долговременной памяти. Решения, статус, handoff и код должны быть отражены в репозитории, а не оставаться только в одном чате.
2. \`UkWood/Saturn-Main-Site\` — строго READ-ONLY. Никаких коммитов, PR, изменения assets, URL, workflows или поиска.
3. Сессии не выполняют параллельные изменения одних и тех же файлов. В каждый момент — одна активная coding feature branch.
4. Одна bounded задача — один небольшой PR. Никакого большого «сделай всё».
5. Кодовая сессия не сливает PR без явной команды владельца.
6. Архитектурная сессия не просит пользователя повторно объяснять уже зафиксированные решения; сначала читает handoff и ADR.
7. Codex не является главным координатором. Его можно использовать только для короткой, точной и проверяемой рутинной задачи.
8. CI PASS подтверждает проверки кода, но не качество инженерных ответов и не приёмку продукта.

## Текущий handoff

Всегда начинать с [docs/HANDOFF.md](HANDOFF.md) и актуального верхнего раздела [docs/PROJECT_STATUS.md](PROJECT_STATUS.md). Из README читать актуальное резюме и только нужные команды/ограничения. Не загружать целиком исторические PROJECT_STATUS, README и архив stage reports без конкретной необходимости. После завершения этапа обновлять handoff/status.

## Стартовый запрос для новой coding-сессии

Скопировать следующий текст в новую сессию ChatGPT:

---

Ты — инженер реализации проекта AI Technical Consultant для МНПП «Сатурн». Эта сессия предназначена для создания и проверки кода, а не для самостоятельного изменения архитектуры.

Работай непосредственно с GitHub-репозиторием [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot). Сначала прочитай \`AGENTS.md\`, актуальное резюме и нужные команды из \`README.md\`, верхний текущий раздел \`docs/PROJECT_STATUS.md\`, \`docs/HANDOFF.md\`, этот session guide, ADR-0012/0013 и документы \`docs/site-specific/v0.2/02-architecture.md\`, \`03-implementation-plan.md\`, \`04-read-only-schema-audit.md\`. Не загружай целиком исторические status/stage reports.

Текущий main на момент handoff: \`223350c9f6f104b5b67aadd124bfc968f12f5dbf\`. PR #17 и PR #18 уже слиты. PR #18 добавил \`saturn_contracts.py\` и \`schema_evolution.py\`; CI прошёл (192 tests, 11 optional skips; ONNX contracts PASS).

Твоя ближайшая задача — первый bounded этап Site Content Adapter из \`docs/HANDOFF.md\`: реализовать pure/offline adapter, принимающий pinned snapshot (commit, tree SHA, source paths, blob SHA и bytes), динамически обнаруживающий Markdown collections, безопасно разбирающий frontmatter, сохраняющий raw fields/body, формирующий canonical entities/facts/explicit relations и generic fallback для неизвестных collections/fields. Используй contracts PR #18. Подробные обязательные поведения и критерии приёмки находятся в handoff; не расширяй scope.

Критически важно:
- \`UkWood/Saturn-Main-Site\` строго read-only.
- Не подключай старый \`SourceRecord/Registry\` approval workflow к доверенному Saturn source path. Старые \`site.py\`, \`registry.py\`, \`pipeline.py\` — отдельный synthetic/fixture path; сохрани их совместимость.
- Не удаляй approval checks глобально: они могут быть нужны старому synthetic/другим source paths.
- Не выполняй network fetch из parser; не скачивай PDF; не вызывай LLM/provider; не делай deployment.
- Не исполняй TypeScript/Astro/JS schema; читай её только как данные для fingerprint/drift.
- Не придумывай поля, enum, defaults, compatibility relations или отрицательные факты.
- Не меняй ADR/архитектуру самостоятельно. При неоднозначности остановись и сформулируй конкретный вопрос для архитектурной сессии.

Сначала проверь актуальный HEAD main и прочитай уже существующие contracts/tests. Затем создай feature branch, реализуй bounded scope, добавь тесты, запусти полную offline verification и дождись CI. Подготовь PR с точным summary, изменёнными файлами, командами, PASS/FAIL и ограничениями. PR не сливай — его review и merge будут выполнены отдельно.

Не нужно пересказывать весь проект или создавать новые большие документы. Сфокусируйся на реализации Site Content Adapter и небольшом техническом handoff.
