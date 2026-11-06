# Local reranking — проект следующего bounded этапа

Дата: 2026-11-06. Статус: **accepted владельцем в чате 2026-11-06; реализация разрешена**. Это уточнение этапа4 принятого roadmap, не реализация и не закрытие приёмки.

## Основание и результат

PR #5 merged в main `92e70223c579d10dfc785263d24a23d92940c6c1`; main CI42166311910 success. Actual unchanged synthetic retrieval: BM25 source-hit17/20, E5 dense18/20, hybrid17/20. Цель100% не достигнута. Reranking/grounding/refusal пока NOT_RUN. Existing service отдаёт до40 кандидатов, после policy-filtered BM25/dense/RRF; текст хранится только в canonical snapshot. Embedding mean-pooling adapter нельзя использовать как cross-encoder: он возвращает vectors, а reranker — scalar relevance для пары query/passage.

Цель: сменный локальный CPU pair scorer → policy-safe reranking не более30 кандидатов → top5 и отдельное реальное сравнение baseline/reranked. Никаких ответов, LLM, cloud, UI/API, допуска реальных sources или изменений Saturn-Main-Site. Evidence gate/claim support остаются следующим этапом5. Search score не является confidence или доказательством ответа.

## Рассмотренные подходы

1. **Выбранная roadmap архитектура, предлагаемая конкретизация:** отдельный ONNX cross-encoder после RRF. Переиспользует locked optional dependencies, local-only runtime, bounded verified artifacts; позволяет независимо измерить изменение ranking. Стоимость — CPU pair inference и отдельная идентичность checkpoint.
2. Лексические правила вместо модели: дешевле, но дублируют BM25 и не выполняют model reranking. Допустимы только как явно названный baseline, не замена neural quality.
3. Одновременно строить reranker, entity resolution, evidence gate и генерацию: скрывает причину изменений и смешивает этапы4/5. Отложено. Cloud reranker исключён требованием локальных моделей.

Пункт1 следует существующему roadmap; параметры ниже — предложение исполнителя, не отдельное утверждение владельца. Веса конкретной модели не объявлены выбранными для production.

## Candidate discovery (read-only)

Официальный `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, immutable revision `1427fd652930e4ba29e8149678df786c240d8825`. Проверены только README.md/config.json/tokenizer_config.json через pinned resolve URLs. Card перечисляет ru/multilingual, license apache-2.0, обучение на переведённом MMARCO; tree содержит onnx/model.onnx и tokenizer.json. Config: XLMRobertaForSequenceClassification, single label/logit, default activation Identity, pad_id1; tokenizer max_length512. Правильная подача — tokenizer пары (query, passage), без E5 prefixes. Размер/weights hashes/output graph и отсутствие external_data **не проверены**. Полного LICENSE в listing нет; card declaration не является юридическим заключением.

Почему кандидат: лёгкий multilingual аналог, прямо предусмотренный архитектурой. BGE multilingual можно сравнить позже на тех же правилах calibration; качество русского инженерного текста не выводится из card. Сеть нужна только отдельному operator acquisition; runtime никогда не скачивает. Если pretrained single-file graph не соответствует контракту, записать precise blocker, не конвертировать/подменять модель молча.

## Контракты

### Reranker и immutable bundle

`Reranker.score_pairs(query: str, passages: list[str]) -> list[float]`, read-only JSON identity. Exactly один finite scalar на input passage в исходном порядке; длина списка проверяется. Empty passages → [] без inference; invalid query/oversize/unsupported input → явная ошибка. Max query4000chars, passage20000chars, max30pairs, batching<=8, max512tokens с зафиксированной pair truncation longest_first. Tie ordering: descending score, затем incoming rank, затем chunk ID; numeric rounding не добавляется без воспроизводимого основания.

LocalONNXReranker использует отдельную schema manifest: kind=local_onnx_pair_scorer, schema_version, model_id/revision40hex, model/tokenizer/card/license SHA256, output_name, max_length, pad_id, activation=identity, purpose semantic_candidate/runtime_contract, source/review reference. Никакого pooling/dimensions как у embedding manifest. Поддерживается только single-logit output [batch,1]; другие формы отклоняются, без угадывания класса/activation. Scores — raw logits, не вероятность. Input names/types строго из input_ids/attention_mask/token_type_ids с int64/int32. Информация о реальной форме graph проверяется до benchmark, config не заменяет smoke.

Preparation: explicit paths/profile → bounded regular file reads → staging → exact hashes → recursive external-data rejection → ORT CPU из тех же immutable verified bytes → pair smoke (shape/finite/repeatability) → atomic no-replace new directory. Existing destination/соседние файлы не изменяются; failure cleans staging. Leaf symlinks, oversized, empty, corrupt, malformed/duplicate-key metadata отвергаются. Parent storage trusted/operator-controlled; importer не OS sandbox для untrusted uploads. Reuse low-level verified-byte/runtime validation без ослабления embedding contracts; не делать глобальный refactor без необходимости.

Card/license evidence pinned, license_id — reviewed operator assertion. Semantic benchmark требует prepared semantic_candidate, полный provenance сверяется с identity после загрузки и сравнивается с первым read; complete bundle swap отклоняется. Numeric CI graphs только runtime_contract и не допускаются к measured semantic report.

### Policy-safe orchestration

Добавить отдельный метод/service rerank для captured IndexSet, сохранив existing search поведение и SearchTrace для baseline. Передавать только canonical passages из snapshot, взятого тем же capture, а не доверять text/source metadata от scorer. Candidate input строится внутри service из существующего поиска (top30); не принимать произвольные IDs/тексты от пользователя.

Перед pair scorer повторить current local_index policy на captured snapshot; excluded chunks не достигают модели. После inference — ещё одна policy-проверка, затем упорядочение survivors и переиндексация ranks. Старый snapshot может законно обслужить in-flight запрос, если текущая policy его допускает; запретить mixing new active index с captured snapshot. Revocation во время scorer исключает результат. Проверить candidate identity/source/snapshot, дубликаты и canonical membership до scoring. Если числу scores не соответствует input, shape/finite invalid или adapter raises — явная ошибка без silent lexical fallback, без fabricated refusal и частичного результата.

Отдельный RerankTrace хранит snapshot_id/mode, input candidates (до30), scored survivors и final top5, reranker identity/config. Не менять meaning baseline channel scores. Не менять registry/visibility/approval, не создавать context sources из scorer output. Trace без сырых вопросов/текста; локальный --show-text может брать только одобренные synthetic snippets из captured snapshot.

## Evaluation

Existing dataset30cases/corpus10docs44chunks, aliases, BM25k1=1.2/b=.75, per-channel40/RRF60 frozen. Reranker stage input top30, final chunk top5; baseline report сохраняется отдельно. Во время этой реализации параметры заранее фиксируются, tuning не выполняется. Expected labels попадают только в scoring после retrieval/rerank; не передаются pair scorer и не меняют passages. Негативы не входят в positive denominator и не считаются refusal.

Report отдельный report_kind/schema, exact snapshot/dataset/embedding/reranker/provenance/config/software identities; calibration/held_out/all; per-case baseline + reranked IDs/ranks/raw scores. Primary source-hit@5, all-source success, expected-source/evidence recall и MRR@5 совместимы с текущим runner. Добавить binary chunk-evidence nDCG@5: relevance1 только при совпадении canonical source/field/physical page и фактического expected evidence text; IDCG строится по всем relevant chunks snapshot (не по returned pool), duplicate chunk IDs запрещены. Это размеченная binary relevance, не градуированная экспертная оценка. Нулевой gold set для positive → validation failure, negative metric=null. Фиксировать candidate-pool oracle source coverage@30, чтобы отделить missed retrieval от плохого rerank. Для baseline nDCG использовать тот же scoring на том же corpus, не переписывать старые отчёты.

Timing: pair scoring отдельно и full query latency p50/p95, index build отдельно. Single CPU process measured, не SLA; RAM measure только по фактической поддерживаемой методике, иначе not_measured. No raw questions/context/model vectors in Git; только безопасные IDs/metrics. Test encoders/scorers не выдают себя за semantic model.

Actual experiment после source/card/config/weights validation: frozen hybrid(E5)+candidate reranker. Цель source-hit1.0 прежняя; quality-target unmet → сохранять failure cases и NOT accepted, а не чинить held_out. Если candidate хуже baseline — опубликовать результат как есть, не включать по умолчанию и не переключаться по held_out. Reranking smoke/green code CI не закрывают model quality или chatbot acceptance.

## Проверки и последовательность будущей реализации

1. Тесты scorer contract и rank integration RED, затем minimal implementation GREEN: deterministic ordering, duplicate/wrong IDs, malformed score count/shape/NaN/Inf, empty pool, top limits, unknown mode; scorer receives only canonical approved passages.
2. Regression concurrent active publication/revocation перед и во время scorer; current denylist нельзя откатить snapshot rollback. Ошибки не становятся no_evidence.
3. Separate pinned ONNX pair adapter/import CLI: numeric graph genuine CPU inference, pair-tokenization/padding/truncation, immutable bytes/file-swap/external-data rejection/atomic collision/cleanup. Runtime_contract guard and complete bundle-swap regression.
4. Hand-computed source/MRR/nDCG tests (including multiple fields/pages, missing pool candidate and duplicate evidence matches); actual evaluation runner no-label-leak test; no fabricated neural metrics.
5. Locked base+optional full verifier, optional CI numeric contracts без pretrained download; unchanged lexical baseline expected17/20. Actual pinned candidate benchmark отдельно с operator artifacts вне Git.
6. Independent whole-branch review и RED→GREEN fixes; ADR/stage/status/handoff; feature PR и фактический CI. PR green не является merge; merge отдельно по указанию владельца.

Это пока порядок и критерии, **не утверждённый implementation plan**. После принятия дизайна составить детальный task plan с exact files/commands/tests и выполнить TDD. Ранее существующее право обычных commits/push/PR сохраняется; source/cloud approvals этим документом не выдаются.

## Критерий окончания этапа

Рабочий bounded local rerank с policy/identity контрактами; tests/actual CI; actual pretrained report с pinning либо precise blocker/NOT_RUN. Grounding/refusal/engineering answer quality остаются NOT_RUN до отдельного этапа5. Полная prototype acceptance не пройдена независимо от code CI.
