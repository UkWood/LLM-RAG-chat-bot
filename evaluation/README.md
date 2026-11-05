# Evaluation baseline

`datasets/synthetic-v1.json` is a versioned, authored gold-label dataset for the synthetic offline profile. It contains 30 cases in the accepted category distribution: 20 calibration and 10 held_out, one held_out per category. Each expected fact points to an approved source and matching field/physical PDF page. Negative/clarification labels intentionally have no evidence.

The dataset is future evaluation input, not executable answer lookup. It must not be used to generate provider answers or tune on held_out cases. Updating gold labels/corpus changes revisions and requires review. M1 sentence fixtures are separate; these broader questions are not passed off as already supported by M1.

Current command validates corpus/hash/snapshot/labels only:

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
```

`report_kind=synthetic_baseline_preflight`, and retrieval/reranking/grounding explicitly equal not_run. `source_hit_at_5` is null. A successful preflight does not meet prototype Top-5/answer-quality acceptance. Real retrieval adapters and a scored runner are the next step. Source references and expected fact support are validated literally; semantic correctness of arbitrary gold labels still requires review.

Full local verification after locked install: `work/venv/bin/python scripts/verify_offline.py`. An optional `--report evaluation/reports/2026-11-05-baseline-preflight.json` saves the small reproducible metadata/label-validation report. It contains no source text/index dump or raw user questions. Actual later evaluation must report per-question outcomes, scores, quality metrics and measured provider/model revisions separately.
