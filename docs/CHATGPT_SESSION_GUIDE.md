# Организация двух сессий ChatGPT

Дата: 2026-11-09  
Проект: AI Technical Consultant — МНПП «Сатурн»

## Зачем разделяем

Проект переходит к регулярной разработке. Архитектурные обсуждения, изменения требований и coding work требуют разного контекста. Чтобы не раздувать одну сессию и не смешивать принятие решений с написанием кода, используются две роли ChatGPT.

## Сессия A — архитектура и управление

**Отдельная сессия для архитектуры и управления.**

Зона ответственности:
- требования, архитектура, ADR и границы системы;
- выбор последовательности этапов и декомпозиция задач;
- критерии приёмки и решения по спорным случаям;
- review PR и анализ результатов тестов;
- решение, когда задача готова к merge.

Не ведёт параллельную реализацию тех же файлов, пока coding session работает над feature PR.

## Сессия B — реализация кода

**Текущая coding-сессия проекта.**

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

Скопировать следующий текст в новую coding/review сессию ChatGPT:

---

Ты — инженер реализации проекта AI Technical Consultant для МНПП «Сатурн». Эта сессия работает по утверждённым архитектурным решениям и не меняет их самостоятельно.

Работай непосредственно с GitHub-репозиторием [UkWood/LLM-RAG-chat-bot](https://github.com/UkWood/LLM-RAG-chat-bot). Сначала прочитай `AGENTS.md`, актуальное резюме/команды из `README.md`, верхний раздел `docs/PROJECT_STATUS.md`, `docs/HANDOFF.md`, этот session guide, документы `docs/site-specific/v0.2/02-architecture.md`, `03-implementation-plan.md`, `04-read-only-schema-audit.md`, `05-snapshot-provider-contract.md`, ADR-0012/0013/0014 и действующие ingestion contracts/adapter/tests.

PR #20 (Saturn Site Content Adapter) и PR #21 (Snapshot Provider Contract / ADR-0014) уже MERGED. PR #21 merge commit: `9b2e0882b81fa2737e7efebb109c079a39b392d8`. Текущая реализация GitHub Snapshot Provider находится в открытом PR #22: [PR #22](https://github.com/UkWood/LLM-RAG-chat-bot/pull/22), branch `feat/github-snapshot-provider-v0.1`. Reviewed implementation code head: `ce501d2df5d120a3a437f6e32359a71e7d0543b6`; push и PR CI на этом code head прошли SUCCESS (245 backend tests, 11 existing optional skips; ONNX contracts PASS). Перед работой обязательно проверь текущий PR head и актуальный CI: docs-sync commit может изменить head.

Текущий bounded scope — GitHub Snapshot Provider v0.1. Не создавай дублирующую реализацию или новую ветку. Если владелец просит review, сначала изучи полный diff и выдай все замечания единым консолидированным списком с severity, точным местом и критерием исправления. После исправлений проверь весь список целиком.

Критически важно:
- `UkWood/Saturn-Main-Site` строго READ-ONLY. Разрешено только чтение; запрещены любые записи, изменения файлов, веток, URL, assets, CI и поиска.
- Не изменяй `saturn_contracts.py`, `saturn_site_adapter.py`, `schema_evolution.py`, canonical contracts или ADR-0012/0013/0014 без отдельного архитектурного согласования.
- Provider должен получать commit/tree/blob по immutable IDs после единственного разрешения `refs/heads/main`; не пере-разрешай branch внутри sync.
- Не допускай partial snapshot; при incomplete tree/blob, hash mismatch, unsupported mode/extension или resource limit sync должен завершаться ошибкой.
- Не реализуй Gitea, PDF ingestion, retrieval, embeddings/reranking, LLM/provider, API/UI, deployment или scheduling без отдельного задания.
- Секреты не добавлять в репозиторий; GitHub token должен иметь только read-only Contents access; object format задаётся явно.
- PR #22 не сливать без отдельной явной команды владельца.

Начни с проверки актуального GitHub state и только после этого выполняй точно ограниченную задачу владельца. Не пересказывай весь проект и не создавай лишние документы; обновляй handoff/status/stage report по фактическому результату.