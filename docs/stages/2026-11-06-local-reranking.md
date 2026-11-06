# Local reranking — stage4, 2026-11-06

Owner accepted design PR #6 and explicitly authorized implementation. Base main92e7022 (PR #5 merged), main CI42166311910 success. Design PR #6 remains open; implementation branch inherits its documentation and acceptance. No automatic merge.

## Result

Working separate bounded CPU pair reranker + actual pretrained experiment. Frozen corpus10docs44chunks/dataset30cases/20positive labels; no aliases/settings/labels/corpus edits. No Saturn-Main-Site access/writes, real registry8pending/UNKNOWN unchanged. No provider/grounding/refusal measurements or source/cloud approvals.

| Metric | Hybrid baseline | Hybrid + reranker |
|---|---|---|
| Source-hit@5 |17/20=.85|20/20=1.0|
| All expected sources |.80|1.0|
| Gold evidence recall |.725|1.0|
| MRR@5 |.758333|.916667|
| Binary evidence nDCG@5 |.629721|.867586|
| Calibration source-hit |13/14|14/14|
| Held-out source-hit |4/6|6/6|

Candidate-pool oracle source-hit and expected-source coverage@30=1.0. No failed source/evidence cases after reranking. Negative10cases not scored as refusal. Rank metrics are not answer correctness. This passes the source-hit retrieval target on this small synthetic set only; full chatbot acceptance remains open. nDCG relevance is canonical source/field/physical page/text support; IDCG counts all relevant snapshot chunks, not only retrieved pool. Labels scored after rerank, never used as model inputs.

[Measured report](../../evaluation/reports/2026-11-06-reranking.json). Fixed top30/final5,batch8,max512/longest_first, BM25k1=1.2/b=.75,per-channel40/RRF60 unchanged. CPU p50 full query1.826487s,p952.166960s; pair scoring1.004003s/1.270742s. Includes canonical policy validation, baseline reuses same pool, single process, not SLA. RAM not_measured. No threshold/model selection based on held_out.

## Official candidate and provenance

Explicit operator acquisition via pinned official resolve URLs, no runtime downloads. cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 revision1427fd652930e4ba29e8149678df786c240d8825: README/config/tokenizer config/tokenizer.json/onnx/model.onnx. Card/config match earlier discovery bytes; pair formatting without E5 prefixes, pad1,max512,Identity activation,logits[batch,1]. Single-file470883696bytes weights passed recursive external-data rejection + real CPU pair smoke. No conversion/quantization/tuning. E5 identity same as prior report.

Official card metadata declares Apache-2.0, no standalone LICENSE in listing. Exact declaration line preserved as LICENSE evidence, full card separately; operator assertion is not legal/redistribution clearance. Candidate is local experimental, not production selection. Artifacts/venvs under ignored work/ only.

- bundle_id: `efc61040651012b14c58e4f111a70ead71e6d39b5944e1b069a3bb6d28421aaf`
- model_sha256: `3e9a03ed1e966f7c5288dd4230e3d6a9bf5e3a170a06f1f4241c5bca12c6487c`
- tokenizer_sha256: `62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626`
- model_card_sha256: `474736a65d6393a060119a8dc304563af67af4d8d86ccfee4a05dd0df107fc11`
- license_sha256: `5e05dfca6eeba9772cf92c589149b62c0fd75573469b8801649008df8f8e8f5f`

## Implementation and reproducibility

Reranker protocol, separate RerankTrace and captured service helper preserve baseline search. Canonical membership/identity/uniqueness checked; current policy before/after inference; scorer cannot invent source IDs/text. Complete index replacement during query uses original capture; revocation during inference suppresses survivors. Wrong scalar count/shape/NaN/Inf or adapter failure rejects, no fallback or refusal fabrication.

Separate strict pair profile/manifest/preparation: bounded regular file reads, exact hashes/immutable runtime bytes via existing single-file loader, pair CPU smoke/determinism, atomic Linux renameat2 no-replace and cleanup. Read-only identity exposed as copy; complete bundle swaps fail before semantic benchmark. Numeric graph tests exercise actual ORT but remain runtime_contract; they do not assert language quality.

Commands after locked optional install:

```bash
PYTHONPATH=backend/src work/venv/bin/python -m unittest discover -s backend/tests -p 'test_rerank*.py' -v
work/base-venv/bin/python scripts/verify_offline.py
work/venv/bin/python scripts/verify_offline.py
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage reranking --mode hybrid --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

See evaluation/README.md for explicit preparation/diagnostic CLI. Numeric pair tokenization/truncation/shape/external-data/hash-load-swap, directory collision/cleanup/provenance replacement, canonical policy/revocation/capture, nDCG/oracle and no-label-leak tests added through RED→GREEN. Intermediate bugs: manual512token expected sum corrected2552; positive empty-gold guard moved before legacy division after reproduced ZeroDivisionError. Neither changes retrieval settings. ORT telemetry-ID persistence warning observed; runtime disables telemetry and inference completed. Actual dependencies unchanged.

Validation/review/publication results recorded after their actual runs. Next stage: evidence gate/grounded pipeline with FakeLLMProvider; do not use score thresholds as truth or allow pending real materials. ADR-0007 records bounded decision.

## Фактическая проверка перед review

После реализации: base verifier5project+111backend PASS (11optional skips), optional verifier5+111PASS без skips. Targeted reranking8, pair-model6, evaluator4tests PASS; positive empty-gold regression GREEN после исправления. Verifier включает actual lexical17/20 и preflight, без pretrained downloads. Diagnostic CLI проверен на официальных локальных bundles, выдаёт IDs/ranks/scores, answer_evaluation=not_run и без raw text по умолчанию. Exact dataset/snapshot identities совпали с предыдущим report. `git diff --check` clean; tracked models/work/index dumps отсутствуют.
