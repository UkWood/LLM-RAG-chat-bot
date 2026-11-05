# Этап 3b: local indexes и измеренный lexical retrieval baseline

Дата: 2026-11-05. Ветка feat/local-retrieval-baseline. Scope: продолжить local index adapters и actual retrieval measurement; генерация/real sources не подключаются.

## Исходное состояние

PR #3 слит: be71efde2b7a3f572d790d416bf642f3a9798017, main [CI42089988455](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42089988455) success. Открытых PR перед началом нет. Подготовлены snapshot, corpus10docs/44chunks и gold dataset30cases. Владелец сообщил, что локальной embedding-модели нет. Это реальное ограничение neural measurement, не повод выдавать test vectors за semantic quality.

[Дизайн](../superpowers/specs/2026-11-05-local-retrieval-design.md), [план](../superpowers/plans/2026-11-05-local-retrieval.md), [ADR-0006](../decisions/0006-local-retrieval.md).

## Реализовано

- BM25, deterministic technical tokenization без слияния разных обозначений, schema-based bilingual metadata aliases, repeatable rankings/diagnostics.
- Actual qdrant-client1.20.0 embedded memory/path index: deterministic UUIDs, finite/shape/nonzero checks, verified config/coverage/payload/vectors, query-time policy filtering. SDK API сверена с official qdrant-client README tag v1.20.0.
- Process-local publication actual IndexSet, failed-promotion preservation, snapshot consistency, before/after query policy checks, runtime corruption rejection, Qdrant reopen, rank-only RRF.
- Optional local ONNX adapter: CPU mean pooling, prefixes, hashes, bounded batches/sequence length, no model downloads. Base/optional transitive dependencies hash-locked. Actual semantic checkpoint отсутствует; supported model family не выбрана.
- Measured evaluation CLI и opt-in diagnostics, per-channel scores/IDs, split denominators, separate source-hit/all-sources/evidence support/MRR. Retrieval получает только question, не expected sources/facts. Negative/clarification cases исключены из positive denominator; refusals не оцениваются.

## Фактические результаты

[Measured lexical report](../../evaluation/reports/2026-11-05-lexical-retrieval.json) отделён от [preflight](../../evaluation/reports/2026-11-05-baseline-preflight.json). Порядок Top-5 — первые пять chunks, не скрытая подмена на deduplicated documents.

| Показатель | Весь набор | Calibration | Held_out |
|---|---:|---:|---:|
| Positive questions | 20 | 14 | 6 |
| Source-hit@5 | 17/20 =85% | 14/14 =100% | 3/6 =50% |
| All expected sources@5 | 80% | 92.86% | 50% |
| Mean expected-source recall@5 | 82.5% | 96.43% | 50% |
| Mean gold-evidence recall@5 | 72.5% | 82.14% | 50% |
| MRR@5 | .701667 | .788095 | .5 |

Source-hit failures: q005, q013, q016. Gold evidence misses: q003, q005, q011, q013, q014, q016. Dataset/corpus/labels и исходная retrieval configuration не изменялись после held_out результата. Исправления численной стабильности и политики касаются correctness, не подгонки semantic behavior.

Source-hit target1.0 **не достигнут**. Dense/hybrid/reranking/grounding/refusal not_run в этом отчёте. Rank-only RRF протестирован с известными vectors, но neural quality не измерялось. Green code CI не означает quality acceptance.

Первое наблюдение CPU: build1.95s, query p50≈.485s/p95≈1.281s. Timing включает canonical snapshot/policy revalidation и зависит от среды/нагрузки; это не performance benchmark или SLA.

## Проверки

- RED: отсутствующие retrieval.lexical/embeddings/evaluation.retrieval modules до реализации.
- Qdrant actual query/filter/delete/corruption/reopen tests с known test vectors. Reopen выявил score delta≈6.7e-8 и нестабильные tied point IDs; fixed bounded all-allowed fetch + six-decimal tie sort. IDs/ranks стабильны, scores сравниваются с tolerance1e-6.
- Mid-query revoke RED: ranks surviving candidates начинались с3; fixed renumber перед RRF, GREEN. Failed new-snapshot promotion сохраняет прежний active IndexSet.
- Metric tests проверяют source-hit≠gold-fact hit, actual rank/MRR, multi-source recall, empty positive denominator, invalid result identity/NaN и отсутствие label injection в query.
- Чистое base venv установлено из hash lock с offline cache; unified verifier PASS (до optional regression). Отдельная установка optional lock успешна, CPUExecutionProvider доступен.
- Основной suite на final code: 5 project +83 backend discovered, из которых 3 optional-runtime проверки пропускаются без optional lock. В полном optional окружении все88 code tests выполнены и PASS (5 project +83 backend). Отдельный CI job запускает6 embedding-contract tests с реальным CPU runtime на authored numeric graphs, без языковой модели.
- Unified verifier включает весь suite, preflight и lexical measurement. --require-source-hit-target — отдельный quality gate, фактически проверен exit1 при85%; baseline correctness CI не объявляет target выполненным.

## Review и исправление

Независимое review5c1f2f2 нашло один блокирующий P2: ONNX external_data sidecar не был pinned и менял результат под неизменным manifest. Реальный CPU regression воспроизвёл RED. Fix812a2d2: запрет external tensors во всех protobuf messages до ORT, exact verified in-memory model/tokenizer bytes вместо filename reload. Actual embedded numeric inference, relative/absolute external graph rejection и file swap после hash check проходят. Проверяется single-file contract, не качество language embeddings.

## Публикация и память

Base be71efd;15197e7 — adapters/deps;5c1f2f2 — measured evaluation/diagnostics;812a2d2 — single-file ONNX fix. Финальные docs/PR/head/CI записываются после фактической публикации. Автоматический merge не выполняется. Raw model weights, index dumps, raw user logs и secrets не коммитились. Real registry и M1 app/provider неизменны; сайт не читался/не изменялся на этом шаге.

## Что остаётся

Для actual dense/hybrid quality требуется локальный trusted checkpoint + проверенные model-card/license/pooling. Предоставить model.onnx/tokenizer.json/manifest.json по documented schema; сеть/облачные embeddings не используются. До появления модели neural результаты остаются not_run.

Далее — neural benchmark и reranking с настройкой на calibration, independent evaluation, затем evidence/grounding и генерация. BM25 target failure не скрывать и не исправлять частными правилами под held_out. Real sample/cloud по-прежнему требуют отдельного exact approval/privacy gate. Server-Qdrant, durable dual-index promotion, multi-worker и SLA не реализованы. Полный M2/prototype acceptance не завершены.
