# Planner V2 corrections after merge review — 2026-11-06

Owner requested continuing after PR10 merge was blocked by two independently reproduced Important defects. This corrects existing accepted whole-query/refusal behavior, not a new planning capability. A final independent review also identified dropped modification intent; its fix is included below. Previous conditional request to merge applies after verified fixes/review/current-head CI; quality acceptance is separate. Saturn-Main-Site remains strictly read-only.

## Root causes and fixes

`нет` was accepted as generic context and absent from the negation rejection. The authored synthetic question `У EDU-410 нет питания?` became a positive power need and returned a canonical voltage quote. Explicitly reject this negation before planning, remove it from context; mixed requests also refuse before provider generation.

Modbus/TCP/RTU were accepted as generic context with no typed selector. `Какой протокол TCP у EDU-410?` returned Modbus RTU; the reverse RTU request for EDU-420 returned Modbus TCP. Remove these protocol literals from context so unsupported qualification rejects the whole request. This deliberately refuses matching explicit qualifiers too: typed protocol selection is not implemented in this bounded revision. Unqualified protocol questions still quote the correct canonical value. No change to gate/projections/evaluator/config, V1 default or source permissions.

The final reviewer additionally reproduced `Можно ли поменять питание EDU-410?` and `Измени питание EDU-410?` returning a static voltage answer. Global modification/configuration verb context is now removed. Such words are consumed only in supported software/address lookups or configuration-interface lookups: infinitive modification needs a software/address/which-program binding; verbal configuration needs an explicit through/over-which-interface lookup, while nominal interface-of-configuration requests remain allowed. Imperatives, possibility/modification requests, and generic how-to configuration reject before generation. This preserves the existing calibration software-address and configuration-interface questions without implementing modification instructions.

## Evidence

TDD RED: planner/application cases reproduced dropped negation (2tests,5failed assertions/subtests), protocol qualification (3tests,16failed assertions/subtests). GREEN: negation2tests and protocol3tests, including positive unqualified protocol controls. Regressions cover case normalization, mixed predicates/entities, deferred subject/predicate clauses, protocol family and transport, and no claims/sources/references/provider call for refused questions. Final-review modification2tests reproduced16failed assertions/subtests, then GREEN. An additional RED case for `Какой интерфейс настроить EDU-410?` prevented confusing which interface to modify with through which interface to configure; GREEN after binding the configuration preposition. Final targeted planner+modification13tests PASS. Full suites/calibration rerun after this final fix. Existing canonical synthetic fixture and test scorer only; no blind payload or label used.

Full base/optional verification and calibration commands:

```bash
work/base-venv/bin/python scripts/verify_offline.py
work/venv/bin/python scripts/verify_offline.py
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage planner-calibration --mode hybrid --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --planner-report work/planner-v2/corrective-calibration.json
```

[Actual corrective calibration report](../../evaluation/reports/2026-11-06-planner-v2-corrective-calibration.json): V1 positives8/14/status14/20, V2 positives14/14/status20/20, no old-positive regressions. Canonical output validity1.0, strict pointer recall V1.428571/V2.714286. Only legacy calibration20cases executed; no exposed held_out or consumed blind evaluation. Final base and optional full verifier commands both exited0 after all review fixes:5project+168backend tests, base11optional skips and optional0. Independent final review and its single RED→GREEN fix pass are complete; no unresolved Critical/Important findings from that review. Current-head remote CI and merge outcome are pending at this checkpoint and must be verified in PR10.

## Frozen experiment applicability

First blind freeze7bc6f118e820fc5d4f648fb22997ad65d9e1c99c and its first report/START/dataset remain byte-for-byte unchanged. Historical V2 result8/24positive+14/16negative, quality target FALSE; it measures only the frozen runtime. The merge-review counterexamples show that zero unsafe answers on those40cases is not a guarantee for other questions.

The corrected runtime changes after that experiment. Its independent quality is **NOT_RUN**, and the old experiment is **not applicable to the corrected revision**. No blind rerun/relabeling/score improvement is claimed. Preserve the consumed set as exposed historical regression evidence; a new generalization claim requires a fresh independently authored/reviewed set, exact new freeze and first-run protocol. Calibration/test success does not grant prototype acceptance. V1 remains default, V2 opt-in; full prototype/real sample/cloud/production still unaccepted.

[PR10](https://github.com/UkWood/LLM-RAG-chat-bot/pull/10), [original frozen report](../../evaluation/reports/2026-11-06-planner-v2-first-blind.json), [plan addendum](../superpowers/plans/2026-11-06-typed-planner-v2.md), [ADR0009](../decisions/0009-typed-planner-v2.md).

## Independent review

Fresh-context whole-branch review confirmed both original fixes and policy/provenance/default boundaries; targeted31tests PASS. It found one additional Important unsupported-modification interpretation, fixed in the single review fix pass with RED→GREEN regressions above. No Critical or Minor findings. No second blind or review-driven benchmark run. Reviewer declined to judge independent quality (NOT_RUN), full verifier/calibration/CI (root responsibility), and real-source/production acceptance (outside this offline scope); root accepts those rulings without treating them as acceptance.
