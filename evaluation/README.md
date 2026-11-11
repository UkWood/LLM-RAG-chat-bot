## PR #31 — Stage 5E 0.1.1 corrected evaluator (independent-review cycle)

The first `saturn-grounding-calibration-v0.1.json` gold **and first v0.1 report** are immutable. The corrected scorer uses its own versioned `0.1.1` rubric/report: need/owner-qualified source binding, exact passage substrings, pinned bundle diagnostics and separate source-unsupported/off-question/extra-text metrics with explicit denominators. These changes may alter metrics while retaining the original gold; never relabel the first measurement.

Additional `saturn_controlled.py` cases deliberately inject policy restriction, technical error and a **simulated** conflict into three openly authored synthetic questions. Those outputs must be labeled `synthetic_controlled_fault_injection` and remain separate from actual calibration and any real/independent blind results.

```sh
PYTHONPATH=backend/src python -m saturn_ai.evaluation.saturn_grounding --profile calibration --dataset evaluation/datasets/saturn-grounding-calibration-v0.1.json --report /tmp/calibration-corrected.json
PYTHONPATH=backend/src python -m saturn_ai.evaluation.saturn_controlled
```

Blind completion now requires bound experiment/code/bundle/dataset/case IDs, report status/citation metrics consistency, and durable exclusive START/COMPLETE receipts. The test suite exercises only synthetic **open-case copies**; no actual blind dataset has run (`NOT_RUN`).

---
## Saturn Grounding Evaluation v0.1 (Stage 5E, 2026-11-11)

**Distinct from legacy evaluation.** The new source-backed Saturn pipeline uses `SaturnAnswerResult` and an independent scorer, not legacy synthetic `GroundedResult` or planner-v2 datasets. Frozen open 28-case source-backed synthetic corpus: `datasets/saturn-grounding-calibration-v0.1.json`, original measured output: `reports/saturn-grounding-calibration-v0.1.json`. Original source code SHA, snapshot/corpus/dataset/config identities and exact denominators are recorded in the report and [Stage 5E engineering report](../docs/stages/2026-11-11-saturn-grounding-evaluation.md).

```bash
PYTHONPATH=backend/src python -m saturn_ai.evaluation.saturn_grounding --profile calibration --dataset evaluation/datasets/saturn-grounding-calibration-v0.1.json --report /tmp/saturn-grounding-calibration.json
```

First actual open calibration: 28/28 correct, positive 17/17, citations 24/24; open fixture and deterministic Fake provider only, not blind/real sample. A future independent blind requires separately authored gold, approved 40-case distribution/thresholds, freeze and a *single* first-run receipt. Until then `independent_blind_evaluation=NOT_RUN`; never treat green CI or open calibration as product acceptance. Historical frozen datasets and reports below are unchanged.

---

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

Historical baseline: no checkpoint was available on 2026-11-05. The pinned E5 candidate experiment on 2026-11-06 is documented in [the stage report](../docs/stages/2026-11-06-model-preparation.md); it does not select a production model. The optional CI job exercises a tiny authored numeric ONNX graph only: it proves CPU/runtime/hash/sidecar contracts, not language embeddings. No model weights are downloaded or committed. Query/passage formatting, license and pooling must be checked against the chosen model card before a real model benchmark.

Local diagnostics: `PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.retrieval --corpus fixtures/evaluation --query 'Какие интерфейсы у EDU-410?' --mode lexical`. `--show-text` explicitly displays approved synthetic snippets locally; default diagnostics/report contain IDs/ranks/scores only, no raw questions/context. No answer is generated.

## Explicit model preparation

Install the hash-locked optional profile first. Obtain trusted model/tokenizer/card/license evidence separately; inference and the importer never download. Use a reviewed versioned profile (the E5 experiment profile is `config/embeddings/multilingual-e5-small.profile.json`):

```bash
work/venv/bin/python scripts/prepare_local_embedding.py --profile config/embeddings/multilingual-e5-small.profile.json --model work/model-source/model.onnx --tokenizer work/model-source/tokenizer.json --model-card work/model-source/README.md --license work/model-source/LICENSE.declaration --destination work/multilingual-e5-small
```

`--license` preserves evidence reviewed by the operator; `license_id` is an operator assertion, not proof of a legal grant. For this candidate the upstream repository supplies only card metadata `license: mit`, no standalone LICENSE: the exact declaration line is retained, with the complete card separately hashed. This is a local candidate experiment, not production/redistribution clearance. Review the exact source and scope before other uses. The destination must be new, is published atomically, and contains manifest/provenance/card/license/smoke receipts. Runtime-contract numeric bundles cannot enter semantic evaluation. Artifacts stay in ignored `work/` and must be restored after a fresh environment.

For measured runs use the existing evaluation command with `--mode dense` or `--mode hybrid`, `--model-dir work/multilingual-e5-small`; redirect stdout to the corresponding report. CPU smoke is not a semantic quality result. Dataset, corpus, aliases and ranking settings are frozen for these runs.

## Local reranking experiment (2026-11-06)

The accepted stage4 implementation uses the existing frozen hybrid pool,30 unique chunks, then a separately pinned local single-logit cross-encoder and top5. No query/passages/E5 prefixes are invented by the reranker; canonical passages and current source policy are checked before/after CPU scoring. No generation/evidence-sufficiency decision happens here.

Install the same hash-locked optional ONNX profile. Obtain reviewed files separately using the exact revision in `config/rerankers/mmarco-minilm.profile.json`. The official card declares Apache-2.0, with no standalone LICENSE in its listing: preserve the exact `license: apache-2.0` line as declaration evidence, the complete card separately, and do not infer redistribution/legal clearance.

```bash
work/venv/bin/python scripts/prepare_local_reranker.py --profile config/rerankers/mmarco-minilm.profile.json --model work/reranker-source/onnx_model.onnx --tokenizer work/reranker-source/tokenizer.json --model-card work/reranker-source/README.md --license work/reranker-source/LICENSE.declaration --destination work/mmarco-reranker
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage reranking --mode hybrid --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.retrieval --mode hybrid --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --corpus fixtures/evaluation --query 'Какие интерфейсы у EDU-410?'
```

The importer publishes only to a new destination atomically; errors preserve existing destinations and clean staging. Pair tokenizer is bounded512tokens/longest_first, batches<=8, query<=4000chars, passage<=20000chars,<=30pairs; output must be finite [batch,1] raw logits with identity activation. It reuses verified-byte single-file graph loading, not embedding pooling. Prepared runtime_contract graphs cannot enter semantic evaluation.

[Measured reranking report](reports/2026-11-06-reranking.json): source-hit20/20, all-source/evidence recall1.0, MRR.916667, binary evidence nDCG.867586; baseline hybrid17/20, nDCG.629721. nDCG uses binary canonical source/field/page/text relevance; ideal DCG counts all relevant chunks in snapshot, not only pool hits. Pool source coverage@30=1.0. Calibration14/14 and held_out6/6 passed source-hit, with no tuning or label leakage. Negatives remain unscored for refusal. `--require-source-hit-target` is available for the reranking stage; the default unified verifier still checks the unchanged lexical baseline17/20 and does not claim full prototype acceptance.

Pretrained weights/tokenizer/card/bundles remain in ignored work/; restore them explicitly after environment replacement. CI exercises authored numeric graphs only. Full grounding/refusal/engineering-answer quality is NOT_RUN. See [stage report](../docs/stages/2026-11-06-local-reranking.md) for provenance, review, commands and limitations.

## Grounded pipeline (bounded stage5)

The local offline application connects a captured snapshot/reranker to a strict field/manual evidence gate, FakeLLMProvider and exact canonical claim/citation validation. It supports one entity/one structured aspect or manual lookup; mixed/free-text/multi-entity questions may refuse or clarify. This is deliberately conservative and not full prototype acceptance.

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.grounding --corpus fixtures/evaluation --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --query 'Какие интерфейсы у EDU-410?'
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage grounding --mode hybrid --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
work/venv/bin/python scripts/verify_offline.py --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --grounding-report work/grounding.json --require-grounding-target
```

The final command runs all code checks + unchanged lexical evaluation + actual grounded quality, after explicit locked optional install and local artifact preparation. It returns1 when the grounded target is unmet; this is a measured quality failure even if code tests pass. Default verifier still needs no pretrained models/network after install. Stage CLI `--require-grounding-target` provides the same explicit quality gate; do not combine it with lexical `--require-source-hit-target` to hide differing criteria.

[Actual report](reports/2026-11-06-grounding.json):8/20 positives answered, proper refusal8/8, clarification2/2, overall status accuracy.6, expected-evidence recall.3. Held_out positive answer0/6; false-refusal/false-clarification rates.5/.1 overall. Emitted claims have exact canonical quote support and citations valid1.0 (separate denominators, absent claims are not scored as perfect). No grammar/labels/corpus changes after this result. Report stores IDs/reasons/metrics/pages, no raw question/context/answer logs. Free-language entailment/engineering consultation/real sample NOT_RUN. [Stage report](../docs/stages/2026-11-06-evidence-gate.md) and [ADR0008](../docs/decisions/0008-evidence-gate.md) state remaining limits.

New distinct 0.1.1 measured artifacts: [corrected open calibration](reports/saturn-grounding-calibration-review-v0.1.1.json) and [3-case controlled injected-fault report](reports/saturn-grounding-controlled-review-v0.1.1.json). Code SHA in both is `bad73187f6e3dca187636ae5cea4cbca0c69dded`, while the original first report remains on its earlier code SHA. Corrected report: positive 17/17, total 28/28, 24/24 citations, no source-unsupported/off-question/extra text; controlled case results are intentionally all failures. CI enforces original Gold/report Git blob identities.
