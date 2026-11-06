# Этап4: проект local reranking — 2026-11-06

Статус: дизайн proposed; implementation/evaluation НЕ выполнялись. Продолжение после merged PR #5 (main92e7022, main CI42166311910 success). Изменения только в документации, real registry/corpus/dataset и Saturn-Main-Site не менялись.

[Предлагаемый дизайн](../superpowers/specs/2026-11-06-local-reranking-design.md) уточняет принятую архитектуру: hybrid RRF top30 → локальный CPU pair scorer → top5 с canonical text и policy recheck до/после inference. Evidence gate/генерация отдельно, этап5. ONNX vector pooling adapter не подменяет reranker.

Сопоставлены существующие RetrievalService/search traces, actual evaluation, accepted prototype criteria и roadmap. Предложены separate pair manifest/preparation, immutable provenance guard, bounded scoring, explicit failure/no fallback и unchanged synthetic benchmark с binary evidence nDCG@5. Parameters предложены до измерения, без настройки на held_out.

Read-only source discovery: официальный HF API и pinned README/config/tokenizer config кандидата cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 revision1427fd652930e4ba29e8149678df786c240d8825. Подтверждены declared ru/multilingual, Apache-2.0 card declaration, pair scoring, single label/identity activation, tokenizer512/pad1 и наличие ONNX path в tree. Weights не скачивались, hashes/CPU/semantic quality NOT_RUN. Полного LICENSE в listing нет, metadata не legal clearance.

Pinned source hashes:

- README.md `474736a65d6393a060119a8dc304563af67af4d8d86ccfee4a05dd0df107fc11`
- config.json `cc2cfe51aa3fd759d21d21acf5dfd6994aa67a3c9210636d22e143699d336c77`
- tokenizer_config.json `e7fbfbfa6347b4e414c1cee50d142e2c2f9a895dad68b068ae83a8b564c3837e`

Выбор лёгкой модели — предложение исполнителя, не production model selection или заявление о качестве. Отдельный candidate benchmark может не улучшить17/20 hybrid. В этом случае честно сохранить результат и failed cases, не включать по умолчанию.

Проверки текущей документационной работы: `python3 scripts/check_project.py`, `git diff --check`; outcome фиксируется перед публикацией. Application tests не заменены этим этапом и не заявляются как заново выполненные. Следующий шаг — принятие дизайна и detailed implementation plan/TDD, затем actual experiment и independent review/CI. Старые права на обычную публикацию сохраняются; этот proposed doc не даёт source/cloud approvals.

Independent builder check: существенных вопросов, мешающих планированию, не найдено; design согласуется с retrieval/acceptance contracts. `scripts/check_project.py` PASS,5 project tests PASS, `git diff --check` clean. Это проверка proposed documentation, не reranker implementation или model benchmark.

Публикация дизайна: [PR #6](https://github.com/UkWood/LLM-RAG-chat-bot/pull/6), branch feat/local-reranking-design, исходный commit55958ed. PR открыт, не принят/не слит; implementation не начата. CI проверять на текущем head PR, не выводить success из статуса предыдущих запусков.
