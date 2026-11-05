# Local retrieval baseline, этап 3b

Scope: продолжение согласованного roadmap после PR #3. [Prototype criteria](../../acceptance/prototype-v1.md), [snapshot contracts](2026-11-05-snapshot-baseline-design.md). Владелец подтвердил отсутствие local embedding checkpoint; нейросетевое качество нельзя заявлять или подменять deterministic vectors.

## Решение и варианты

Реализовать настоящий BM25 и embedded Qdrant local adapter на CPU, привязанные к одному immutable snapshot. BM25 измеряется на подготовленном dataset. Векторный adapter проверяется с явно test-only vectors; для настоящего semantic/hybrid evaluation нужен локальный ONNX checkpoint с pinned hashes/config. Автозагрузки модели/облачных embeddings нет. Альтернативы: ставить remote Qdrant/скачивать неопределённую модель или объявить hashing vectors semantic search — не подходят текущему offline scope и требованиям честной проверки качества.

BM25 tokenizer сохраняет technical designation целиком, casefold без слияния кириллицы/латиницы. Для score corpus text формируется из title, heading, текстового поля и зафиксированных schema-based bilingual field/document-type aliases. k1=1.2/b=0.75, top40 per channel, RRF k=60 фиксируются до evaluation; не подбираются по held_out. Scores не являются confidence. Никакого доступа retrieval code к gold labels.

Qdrant хранит vectors + проверяемые metadata snapshot/chunk/source/hash/policy, возвращаемый текст берётся из canonical snapshot. UUID point IDs deterministic. Размерность приходит от embedding config; vectors finite/shape/nonzero проверяются. Local mode без сети; persistent directory только runtime/work, в repo indexes не коммитятся. Двойной index set готов до публикации; coverage/config/реальные payloads сверяются, partial promotion не меняет активный pointer. Удаление/обновление — новый snapshot/index pair; runtime policy/revocations фильтруются до обоих поисков и повторно после, rollback policy не откатывает.

Допускается process-local catalog и индексы; это не multi-worker/durable production promotion. Проверка canonical snapshot может повторно парсить PDF; latency репортируется только как наблюдение текущего CPU, не SLA.

## Embedding boundary

Сменный Encoder protocol encode_documents/encode_query и identity/config revision/dimensions. CI test encoder не участвует в semantic quality report. Опциональный local ONNX adapter принимает только локальный каталог с model.onnx/tokenizer.json и manifest hashes, CPU execution, bounded batches/sequence length, configured query/passage prefixes, pooling и normalization. Никакого remote code или provider-specific API; файлы модели доверенные owner-provisioned artifacts, не пользовательские uploads. Реальная модель не выбрана и не проверена, benchmark/license/model-card остаются gate перед её использованием на real data.

## Evaluation и diagnostic mode

Dataset/corpus неизменны. Runner индексирует только corpus, передаёт retriever только question; labels применяет после search. Меряет primary chunk-top5 source-hit, all-expected-source coverage, supported evidence-hit@5, MRR по позитивным cases, отдельно calibration/held_out. Дополнительно document-deduplicated source rank может отображаться, но не подменяет chunk Top-5. Negative/clarification cases показывают найденных кандидатов, refusal/grounding не оцениваются этим этапом.

Default report lexical-only, dense/hybrid/reranking/grounding not_run без checkpoint. При real local model возможен отдельный hybrid report с artifact/model/config revisions; test encoders запрещены для такого отчёта. Нельзя объявлять source-hit@5=100% до фактического результата; если baseline не проходит target, сохранить failed cases и продолжить следующий этап без настройки на held_out. Diagnostic output — локальный opt-in, default reports содержат IDs/ranks/scores, без raw questions/context. Safe synthetic отчёт сохраняется в repo.

## Проверки

BM25 ranking/formula/no-match/ties/filtering/technical suffixes; Qdrant upsert/query/coverage/shape/malformed model outputs/reopen payload consistency; snapshot mismatch, partial activation, revocation mid-query и old capture after rollback; evaluator scores по реальным results, no expected-source injection, split denominators/negative cases и explicit unmeasured modes. M1 provider и реальные permissions не меняются.
