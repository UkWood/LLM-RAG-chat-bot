# Подготовка модели и actual retrieval — 2026-11-06

База: merged PR #4 a1093fb, ранее проверенный main CI42097546595 success. Продолжена feat/embedding-model-preparation с WIP2a13a29. Saturn-Main-Site не читался и не изменялся; real registry и synthetic corpus/dataset не менялись.

## Получение и provenance

Runtime unrestricted/enforced; оба запрошенных домена HTTP200. Первые curl без network grant не соединялись с proxy; после штатного network grant доступ подтверждён. Proxy/TLS не обходились. Отдельный операторский curl получил официальный API и закреплённые resolve URLs для README.md/config.json/1_Pooling/config.json/onnx/config.json/onnx/tokenizer_config.json/onnx/model.onnx/onnx/tokenizer.json на revision614241f622f53c4eeff9890bdc4f31cfecc418b3. Никаких auto downloads из runtime.

Официальная card/config подтверждают mean pooling + normalization, 384dimensions, 512tokens, pad0, query/passage prefixes. Graph выдаёт last_hidden_state; single-file CPU smoke прошёл. Это кандидат, не production selection. Repository tree не содержит LICENSE: exact card declaration `license: mit` сохранена как evidence, full card отдельно. License ID — утверждение оператора на основании metadata, не доказательство legal grant/redistribution rights. Для production нужна отдельная проверка. Ошибочный первоначальный импорт полного card как LICENSE превысил лимит256KB, был отклонён без publication; после явного извлечения exact declaration line импорт прошёл.

Pinned hashes (реальные bytes):

- bundle_id: `b037950bfc55dd03c486eed833478030c40f6b9f4284b701ee5334ae5a885f66`
- model_sha256: `ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665`
- tokenizer_sha256: `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`
- model_card_sha256: `0038de97aee16258cecbad7ffda4b4febd6953e747a00e0ddbc8e6ed241e9c1c`
- license_sha256: `79f2b3590cfbc769c76ab167c95bd04e0b0d321e18434042cf44dcc6a7258d0f`

## Измерение

Существующий unchanged runner, ranking/aliases/corpus/labels не менялись. 30cases, positive denominator20; отрицательные не оцениваются как refusals.

| Mode | Source-hit@5 | Calibration | Held-out | Gold evidence recall | MRR@5 |
|---|---|---|---|---|---|
| BM25 baseline |17/20|14/14|3/6|.725|.701667|
| Dense E5 |18/20|12/14|6/6|.800|.833333|
| Hybrid RRF |17/20|13/14|4/6|.725|.758333|

Dense failures q017/q018; hybrid q005/q013/q017. Не tuning на held_out. All-source success dense.85, hybrid.80. Ни один режим не прошёл source-hit1.0. Reranking/grounding/refusal NOT_RUN. Это synthetic retrieval эксперимент, не оценка engineering answers/реального corpus.

[Dense report](../../evaluation/reports/2026-11-06-dense-retrieval.json), [hybrid report](../../evaluation/reports/2026-11-06-hybrid-retrieval.json).

## Реализация и проверки

Explicit local importer наследует WIP: bounded reads, immutable profile/hashes, single-file graph validation, CPU smoke/determinism, atomic Linux renameat2 no-replace, error cleanup. Numeric runtime_contract purpose запрещён semantic evaluator. Review source URL выявил normalized control characters: отдельный тест сначала дал2FAIL, точное сравнение canonical raw URL дало9PASS (до финального review). Бывший invalid-profile тест мог проходить из-за invalid placeholder graph; новый тест вызывает validation напрямую.

Команды из корня после locked install (Python3.12):

```bash
work/base-venv/bin/python scripts/verify_offline.py
work/venv/bin/python scripts/verify_offline.py
PYTHONPATH=backend/src work/venv/bin/python -m unittest discover -s backend/tests -p test_model_preparation.py -v
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage retrieval --mode dense --model-dir work/multilingual-e5-small --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage retrieval --mode hybrid --model-dir work/multilingual-e5-small --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

Base:5 project+93 backend tests PASS,6optional skipped. Optional:5+93 PASS без skips; targeted10PASS. Verifier также выполнил preflight и actual lexical report85%. ORT предупреждал о невозможности сохранить telemetry device ID; inference/тесты завершились успешно, runtime отключает telemetry. CLI/profile instructions в evaluation/README.md. Веса/card/tokenizer/venvs остаются в work/, не Git. Локальный ledger в work/model-preparation-plan/progress.md; scripts skills отсутствуют в checkout, учёт выполнен вручную. Следующая среда требует восстановления artifacts отдельно.

## Следующий шаг

Fresh review + PR/actual CI; затем отдельный bounded этап reranking/evidence/grounding с calibration-only решениями. Никаких автоматических approvals реальных sources, cloud calls или merge. Полная prototype acceptance не пройдена.

## Independent review

Reviewer проверил весь branch от a1093fb; important: полная замена bundle между первым provenance read и encoder load смешивала provenance A/embedding B. Воспроизведено reviewer и regression с двумя реальными prepared numeric bundles; RED: changed bundle достиг indexing. Fix: сравнить оба полных provenance и отклонить замену до indexing, удержать identity-bound result. GREEN:10 targeted tests; полный suite повторён после fix. Numeric fixtures здесь проверяют race contract, не semantic quality.

Rulings: raw URL должен точно совпадать с canonical URL (нормализация URL-парсером не является provenance). License metadata допускает только данный local candidate experiment, не legal clearance. Ledger ведётся вручную в work/ вместо недоступных helper scripts. Стоимость ошибочных решений: ложный отказ нестандартному URL, непроверенные redistribution rights, отсутствие helper enforcement соответственно.

Review ruling: противоречащая opening status README оценена как important для достоверности текущего статуса, исправлена на actual18/20 dense и17/20 hybrid. Deferred minors нет.
