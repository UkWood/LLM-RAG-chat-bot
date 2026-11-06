# Состояние проекта

## Актуально: local reranking implementation — 2026-11-06

Owner approved design PR #6 and implementation. New bounded stage4 implemented after main92e7022: separate CPU pair scorer, canonical/policy-safe captured rerank and explicit atomic local preparation. Official mmarco-MiniLM revision1427fd652930e4ba29e8149678df786c240d8825 experiment: source-hit20/20, all-source/gold evidence1.0, MRR.916667,nDCG.867586; baseline hybrid17/20,nDCG.629721. Frozen data/settings; no held_out tuning. Retrieval target passes this small synthetic set only. Grounding/refusal/answer quality NOT_RUN, full prototype NOT accepted.

[Stage report](stages/2026-11-06-local-reranking.md), [accepted design](superpowers/specs/2026-11-06-local-reranking-design.md), [implementation plan](superpowers/plans/2026-11-06-local-reranking.md), [ADR-0007](decisions/0007-local-reranking.md). Prior proposed/open state below is historical. Weights/card/tokenizer only work/; explicit restoration required after environment replacement. License card Apache-2.0 declaration only, not production legal clearance. Next stage5 evidence gate/grounded pipeline; real sources pending, cloud disabled, Saturn-Main-Site READ-ONLY. Actual verification/review/publication follow in stage report; never infer merge from green CI.


## Текущий статус — 2026-11-06, после merge PR #5

PR #5 merged: main `92e70223c579d10dfc785263d24a23d92940c6c1`, main CI42166311910 success. Подготовка E5 и actual dense/hybrid measurements опубликованы; источник правды — [отчёт](stages/2026-11-06-model-preparation.md). Исторические упоминания open PR #5/no checkpoint ниже относятся к предыдущим переходам.

Следующий bounded этап4: [local reranking design](superpowers/specs/2026-11-06-local-reranking-design.md), статус proposed. Изучены card/config лёгкого multilingual cross-encoder; pretrained reranker не получен и не выполнялся. До implementation нужен детальный план после принятия дизайна. Evidence gate/grounding/refusal — отдельный этап5. [Результат проектирования](stages/2026-11-06-local-reranking-design.md).


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

## Публикация 2026-11-06

Commit b653014162b72b589eebd543a370a637f1dba92c опубликован в feat/embedding-model-preparation. [PR #5](https://github.com/UkWood/LLM-RAG-chat-bot/pull/5) открыт, не слит. [Push CI42165522960](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42165522960) на b653014 завершился success в обоих jobs, включая actual numeric preparation/swap tests. PR-event CI42165549055 на момент фиксации ещё in_progress; не считать его проверенным. Эта запись — отдельный docs commit, его CI следует проверять отдельно.

Публикация дизайна: [PR #6](https://github.com/UkWood/LLM-RAG-chat-bot/pull/6), branch feat/local-reranking-design, исходный commit55958ed. PR открыт, не принят/не слит; implementation не начата. CI проверять на текущем head PR, не выводить success из статуса предыдущих запусков.

## Публикация stage4

[PR #7](https://github.com/UkWood/LLM-RAG-chat-bot/pull/7), feat/local-reranking, implementation/fix commit2463ab0. PR открыт, НЕ слит. Design PR #6 закрыт как superseded: его accepted design и документация включены в #7; это не merge #6.

После review fix официальный pretrained benchmark повторён: metrics/baseline_metrics, все per-case ranks/raw scores и pinned identities точно совпали с committed report. Первоначальные timing measurements сохранены, повтор не используется для tuning. Full final base5+112PASS(skips11),optional5+112PASS(0 skips). Независимый review завершён, Important defect исправлен RED→GREEN, deferred product minors нет.

CI при публикации: push42168512725 и PR42168537774 на2463ab0 in_progress; это наблюдение, не заявление success. Проверять текущий head/actual checks в PR перед merge; новый docs commit проверяется отдельно. No automatic merge. Следующий отдельный stage5 — evidence gate/grounded pipeline, с собственным design/plan/quality gates.

Verified remote CI: [push42168613444](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42168613444) на d03a95d74535822f800b9cf02918eee7a7a863fe завершился SUCCESS, offline-checks и onnx-contracts (включая новые actual CPU pair contracts) оба success. Это CI реализации; данная запись — отдельный docs commit, его status проверять по текущему head PR #7. PR остаётся open/unmerged.
