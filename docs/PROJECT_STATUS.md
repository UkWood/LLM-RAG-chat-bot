# Состояние проекта

## Продолжение 2026-11-06: actual checkpoint и измерение

Предыдущий сетевой blocker снят: runtime policy unrestricted/enforced, huggingface.co и us.aws.cdn.hf.co вернули HTTP200 через штатный proxy. Получен официальный intfloat/multilingual-e5-small revision614241f622f53c4eeff9890bdc4f31cfecc418b3; CPU smoke прошёл, artifacts только в ignored work/. Model card декларирует MIT; отдельного LICENSE нет, сохранена точная строка декларации, это не production legal clearance.

На неизменных 10docs/44chunks/30cases: dense source-hit@5=18/20 (calibration12/14, held_out6/6), hybrid17/20 (13/14,4/6), BM25 baseline17/20 (14/14,3/6). Цель100% не пройдена. Reranking/grounding/refusal NOT_RUN; M1 generator не менялся. Не подгонять held_out. Следующий шаг — отдельный план reranking/evidence gate и calibration-only улучшений; реальные источники по-прежнему pending/UNKNOWN, Saturn-Main-Site только чтение.

Проверки: base verifier 5 project +93 backend tests, 6 optional skips; optional verifier 5+93 без skips. Десять targeted preparation tests PASS; canonical URL regression RED→GREEN. Обновлён optional CI. Отчёт: [model preparation](stages/2026-11-06-model-preparation.md). Публикация/CI фиксируются ниже по фактическому результату. Прежние блокеры и сведения о PR #4 ниже исторические (PR #4 merged a1093fb).


## Промежуточная передача 2026-11-06

PR #4 слит в main a1093fb, CI42097546595 success. Ветка feat/embedding-model-preparation содержит незавершённую подготовку локального embedding bundle; 8 целевых тестов PASS, полный suite/review/CI/PR ещё впереди. Реальная модель не получена, dense/hybrid quality NOT_RUN. Владелец обновил разрешение huggingface.co, но активная среда осталась на прежней политике и CONNECT403; продолжение в новой среде описано в [HANDOFF](HANDOFF.md). Сведения о PR #4 ниже относятся к прошлой публикации.

Обновлено:2026-11-05. Репозиторий UkWood/LLM-RAG-chat-bot.

## Выполнено

- PR #1/#2/#3 слиты. Main до текущего этапа be71efd, [CI42089988455](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42089988455) success. Snapshot contracts +10 synthetic docs/30 gold cases доступны в main.
- Новый этап3b: настоящий local BM25, embedded Qdrant memory/path adapter, policy-filtered publication/search/RRF и diagnostics; optional pinned single-file CPU ONNX adapter без model downloads.
- [Measured lexical baseline](../evaluation/reports/2026-11-05-lexical-retrieval.json): source-hit@5=17/20=85%, calibration14/14, held_out3/6. All-source success80%, gold-evidence recall72.5%, MRR≈.701667. Source-hit failures q005/q013/q016 сохранены. Target100% не пройден, held_out не подгонялся.
- Measured runner отделён от preflight; gold labels применяются после search, negatives не портят positive denominator. Unified verification включает code tests/preflight и lexical report.
- Independent review external ONNX sidecar hole воспроизведён и закрыт canonical single-file validation + pinned bytes loading. Optional CI проверяет actual numeric graph inference/security contracts, не язык/семантику.

## Неизмеренное и ограничения

Владелец подтвердил отсутствие local embedding checkpoint. Dense/hybrid/reranking/grounding/refusal в quality report=not_run. Qdrant test vectors не подменяют model quality. Lexical code CI green не означает приёмку прототипа. [Согласованные критерии](acceptance/prototype-v1.md) и ADR-0004 действуют, полный M2 не завершён.

Индексы/active publication process-local; Qdrant reopen проверен, но server/distributed/durable coordinated promotion и SLA отсутствуют. Raw source receipts только в памяти, output не подключён к M1 provider. Реальные sources (8 pending/UNKNOWN), registry bytes и Saturn-Main-Site не менялись. Cloud/API/UI/deployment не реализованы; ADR-0001 proposed.

## Текущая публикация

Ветка feat/local-retrieval-baseline от be71efd. Commits15197e7,5c1f2f2,812a2d2. [PR #4](https://github.com/UkWood/LLM-RAG-chat-bot/pull/4) открыт, push CI42094770037 на95eb0b0 success в обоих jobs (основной+optional ONNX). Последний head/checks и evidence в [отчёте этапа](stages/2026-11-05-local-retrieval.md). Новый этап не слит.

## Следующий шаг

Получить/подготовить trusted local embedding checkpoint с exact hashes/manifest и корректным pooling/prefixes по model card; выполнить actual dense/hybrid benchmark на текущем corpus. Затем reranking/grounding. Пока модели нет, можно развивать проверяемые adapters/контракты и evaluation, не заявляя semantic quality и не подгоняя held_out.

[Roadmap](superpowers/plans/2026-11-03-ai-consultant-roadmap.md), [local retrieval design](superpowers/specs/2026-11-05-local-retrieval-design.md), [ADR-0006](decisions/0006-local-retrieval.md), [handoff](HANDOFF.md).
