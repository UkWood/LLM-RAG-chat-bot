# ADR-0006: local retrieval adapters и честный lexical baseline

Дата: 2026-11-05. Статус: implemented в bounded synthetic profile. Владелец поручил продолжать roadmap и подтвердил отсутствие local embedding checkpoint.

## Решение

Использовать настоящий Qdrant SDK1.20.0 local mode (CPU, memory/path) и независимый BM25 по одному проверенному snapshot. Remote server/ports/cloud embeddings не включаются. BM25 k1=1.2/b=.75, technical-token spelling, schema-based bilingual field aliases, top40 и RRF k60 фиксированы до measurement. Retrieval code не читает evaluation/gold labels. Алгоритмические/model benchmark решения production уровня не приняты.

Actual Qdrant artifacts проверяются: snapshot/config/dimensions, точный набор point IDs, payload hashes/policy и vectors. Текст возвращается из canonical snapshot, не из model-generated metadata. Новая IndexSet публикуется process-local atomic pointer только после проверок; explicit lexical-only набор не выдаётся за готовый dual index. Policy/revocations проверяются до обоих каналов и после query; survivors получают новые последовательные ranks до RRF. Source rollback не меняет runtime policy.

Qdrant float32 serialization показала ~6.7e-8 score drift и нестабильный cutoff равных points при reopen. Для bounded local profile (до10000chunks) выбирается полный разрешённый набор, затем six-decimal tie key + chunk ID; raw scores сохраняются. Это цена детерминированного tie ordering, не production throughput решение.

## Neural boundary

Encoder сменный. Known CI vectors проверяют реальные Qdrant операции, но не semantic quality. Optional CPU ONNX profile принимает local pinned single-file model/tokenizer/manifest с mean pooling/prefixes/dimensions. Файлы модели должны быть trusted owner-provisioned, не user uploads; model card/license/pooling проверяются до real benchmark. Автозагрузки моделей нет; BGE/Qwen/E5 не объявлены production выбором.

Review выявило: unpinned ONNX external_data sidecar менял inference под тем же manifest. Фикс: protobuf traversal запрещает external-data tensors до runtime; runtime/tokenizer получают те же immutable bytes, которые прошли hash check, без повторного чтения filename. Optional CI использует только authored numeric graph, в том числе relative/absolute sidecar и hash/load file-swap regression. Это не language-model quality test.

## Measurement и последствия

Frozen BM25: source-hit@5=17/20=.85, calibration14/14, held_out3/6; all-source success .8, mean expected-source recall .825, mean gold-evidence recall .725, MRR .7016667. Failed q005/q013/q016 остаются в report. После результата held_out corpus/labels/aliases/config не подгонялись.

Dense/hybrid/reranking/grounding/refusal=not_run. Цель source-hit1.0 и полная prototype acceptance не пройдены. Green code CI доказывает корректность операций/отчётов; --require-source-hit-target отдельно даёт exit1 при quality failure. Следующий quality шаг требует локального checkpoint; inference-contract CI его не заменяет.

Persistence проверена только для Qdrant local reopen. BM25 и active pointer process-local; durable/multi-worker coordinated promotion не реализована. Наблюдаемые latency включают canonical policy revalidation и не являются SLA. Реальные источники/cloud и Saturn-Main-Site не меняются, ADR-0001 proposed.

## Experiment update 2026-11-06

Pinned E5 candidate prepared; dense18/20, hybrid17/20 actual synthetic source-hit@5. Mean pooling/prefixes checked against pinned card; MIT declaration metadata only, no standalone LICENSE/legal clearance. This supersedes historical neural not_run above for dense/hybrid only. No production model selection. [Evidence](../stages/2026-11-06-model-preparation.md).
