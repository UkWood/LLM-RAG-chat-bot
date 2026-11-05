# Evaluation baseline

`datasets/synthetic-v1.json` is a versioned, authored gold-label dataset for the synthetic offline profile. It contains 30 cases in the accepted category distribution: 20 calibration and 10 held_out, one held_out per category. Each expected fact points to an approved source and matching field/physical PDF page. Negative/clarification labels intentionally have no evidence.

The dataset is future evaluation input, not executable answer lookup. It must not be used to generate provider answers or tune on held_out cases. Updating gold labels/corpus changes revisions and requires review. M1 sentence fixtures are separate; these broader questions are not passed off as already supported by M1.

Current command validates corpus/hash/snapshot/labels only:

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

`report_kind=synthetic_baseline_preflight`, and retrieval/reranking/grounding explicitly equal not_run. `source_hit_at_5` is null. A successful preflight does not meet prototype Top-5/answer-quality acceptance. Real retrieval adapters and a scored runner are the next step. Source references and expected fact support are validated literally; semantic correctness of arbitrary gold labels still requires review.

Full local verification after locked install: `work/venv/bin/python scripts/verify_offline.py`. An optional `--report evaluation/reports/2026-11-05-baseline-preflight.json` saves the small reproducible metadata/label-validation report. It contains no source text/index dump or raw user questions. Actual later evaluation must report per-question outcomes, scores, quality metrics and measured provider/model revisions separately.

## Measured lexical retrieval (stage 3b)

After updating the hash-locked base environment:

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage retrieval --mode lexical --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

The measured report is `reports/2026-11-05-lexical-retrieval.json`, distinct from the older preflight report. Frozen BM25 source-hit@5: 17/20=.85, calibration14/14, held_out3/6. All-source success .80, mean gold-evidence recall .725, MRR .7016667. Target1.0 is **not met**. Failed source-hit cases q005/q013/q016 remain in the report; corpus, gold labels and retrieval configuration were not tuned after this held_out result.

Primary source-hit uses the first five **chunks**, not a substituted document-deduplicated ranking. Gold-evidence recall additionally checks source, field, physical page and matching fact text; a hit on the right document alone is weaker. Negative/clarification cases show candidates but are excluded from the positive denominator. Refusal/answer behavior is not measured.

Default lexical evaluation does not construct fake dense results: dense/hybrid/reranking/grounding/refusal stay not_run. Passing code CI is not prototype quality acceptance. Add `--require-source-hit-target` to the evaluation CLI or unified verifier for an explicit nonzero exit when source-hit@5<1.0.

## Optional local neural profile

Install `backend/requirements-onnx.lock` into the chosen CPU venv. Supply a trusted, owner-provisioned local directory containing `model.onnx`, `tokenizer.json`, `manifest.json`; see config/embeddings/local-onnx.example.json for the schema. Placeholder hashes/dimensions/prefixes/pad/output name must be replaced with values from the exact model; the example selects no production model. Only single-file embedded weights and mean pooling are supported. External-data tensors are rejected recursively, and the runtime consumes the exact verified bytes. Never use arbitrary user-uploaded models.

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage retrieval --mode hybrid --model-dir work/local-embedding-model --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

No checkpoint is currently available (confirmed by the owner). Actual neural quality is therefore unmeasured. The optional CI job exercises a tiny authored numeric ONNX graph only: it proves CPU/runtime/hash/sidecar contracts, not language embeddings. No model weights are downloaded or committed. Query/passage formatting, license and pooling must be checked against the chosen model card before a real model benchmark.

Local diagnostics: `PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.retrieval --corpus fixtures/evaluation --query 'Какие интерфейсы у EDU-410?' --mode lexical`. `--show-text` explicitly displays approved synthetic snippets locally; default diagnostics/report contain IDs/ranks/scores only, no raw questions/context. No answer is generated.
