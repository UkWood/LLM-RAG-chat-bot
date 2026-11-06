# Bounded evidence gate / extractive grounded pipeline — 2026-11-06

Owner requested check/merge PR7 and execute next roadmap stage. PR7 clean bed222e, all4 push/PR checks success, no blocking comments/reviews; merged861871b609f76ecad065e4b635e86ec3638b2cc8. New implementation branch feat/evidence-gate, no automatic merge of this branch. Existing accepted prototype criteria govern; new design records bounded implementation choices, not new source/cloud approvals.

## Implemented

Strict full-question plan: one exact canonical entity + structured field power/interfaces/protocols/temperature/status or approved manual lookup. Unknown/near designations refuse/clarify without guessing; mixed/negated/instruction questions fail closed. Scope deliberately omits arbitrary body/diagnostic/multi-entity semantic reasoning. No application import of dataset or expected facts.

Gate resolves canonical facts in one captured immutable snapshot; requires current local_index AND local_generate, complete field value sets (list members are not conflicting scalar sources), typed value grammar, no conflicting field sets, max5chunks/8000chars. Duplicate identical sources do not add proof. Malformed members fail closed rather than disappearing from completeness. Manual citation requires separately approved PDF with actual physical page, not pending link inheritance; oversize page cannot reach provider.

Capture reused through planning/rerank/gate/provider/citations, even if active index changes. Recheck current policy before/after provider and before output; revocation cannot be rolled back by corpus snapshot. Only offline/test provider. FakeLLMProvider reuses existing GenerationRequest/Claim contract; complete unique exact canonical quotations required. Invented emitted IDs/text and omissions/duplicates fail validation; provider-local request mutation cannot rewrite canonical support; provider-owned Claim objects are not reused in result. URLs/title/hash/document IDs/heading/physical pages from canonical registry/snapshot only. Existing M1 unaffected, no real provider enabled. Infrastructure errors are status=error, never no_evidence.

## Actual unchanged quality run

Pinned E5 + mmarco pair reranker from previous stage (same identities/bundles); Fake provider verbatim-v1. Corpus10docs44chunks/dataset30cases unchanged. No grammar or aliases tuned after evaluation, no source/site changes. Report: [2026-11-06-grounding.json](../../evaluation/reports/2026-11-06-grounding.json).

| Metric | All | Calibration | Held-out |
|---|---|---|---|
| Positive answered |8/20|8/14|0/6|
| Proper refusal |8/8|5/5|3/3|
| Proper clarification |2/2|1/1|1/1|
| Expected status accuracy |.60|.70|.40|
| Expected evidence recall |.30|.428571|0|
| Emitted verbatim claim support |1.0|1.0|not applicable|
| Emitted canonical citation validity |1.0|1.0|not applicable|

No infrastructure errors or unsupported emitted quotations. Overall false refusal.50, false clarification.10 on positive denominator20. Unsupported/multi-entity questions account for12 missed positives. Two answered manual lookups cite valid approved physical pages but do not cover gold-labeled page/title evidence; they remain evidence-coverage failures rather than being reclassified as success. Failed IDs q003,q005,q009,q010,q011,q012,q013,q014,q015,q016,q017,q018,q019,q028 preserved. This is NOT full stage5/prototype quality acceptance; prior retrieval source-hit20/20 is not answer coverage20/20.

Exact quotation validation proves support for bounded extractive claims, not arbitrary natural-language entailment. Correct refusals do not compensate for unanswered positives. Real LLM safety/quality, free engineering advice, real sample and production remain NOT_RUN. Do not change held_out or grammar to patch these cases; planner expansion needs its own design/calibration/fresh evaluation.

## Commands

After existing hash-locked optional installation/local artifact preparation:

```bash
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.grounding --corpus fixtures/evaluation --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --query 'Какие интерфейсы у EDU-410?'
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage grounding --mode hybrid --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json
work/base-venv/bin/python scripts/verify_offline.py
work/venv/bin/python scripts/verify_offline.py --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --grounding-report work/evidence-gate/postfix-grounding.json --require-grounding-target
```

Last command intentionally returns1 for measured grounding target failure; code-test status is separate. Default verifier uses no pretrained models/network after install. Reports contain IDs/reasons/metrics/pages, not raw question/context/answer logs. Model artifacts/venvs and transient logs only ignored work/. No new dependencies. ORT emitted telemetry persistence warning as in previous stages; inference completed and telemetry is disabled in loader.

## TDD and scope rulings

Missing gate/application/evaluator modules first RED; implementation GREEN. Gate tests cover malformed approved facts, missing/partial fields, duplicate/conflicting source value sets, unknown suffix/typo/injection grammar, PDF page and generate scope. Integrations cover invented/omitted/duplicate claims, canonical text mutation, before/during-generation revocation, publication race, provider errors and offline guard. Metric tests distinguish errors from correct refusal and validate canonical page/URL rather than trusting an existing source ID; runner spy sees only question strings.

Additional boundary RED reproduced two issues: a9000char page initially passed gate (application already enforced budget), and malformed interface list member could be filtered away before completeness check. Fix gate-level page budget and quarantine malformed eligible field;7 gate tests PASS. No corpus/dataset edit or model-score threshold introduced.

Ruling: narrow structured grammar is an explicit implementation choice, not claimed complete natural understanding. Cost: measured false refusals/clarifications, especially held_out0/6; keep failures. Ledger/manual command logs under work/evidence-gate because skill helpers not installed locally, no worktree per AGENTS.md. Existing source/cloud approvals unchanged; Saturn-Main-Site not modified.

Final verification, independent review and publication evidence appended after actual completion. Next: broader planner/evidence coverage through calibration, not cloud provider or UI masking current quality failure.

## Independent review

Reviewer ran19 targeted tests independently and confirmed honest disclosure of narrow grammar, held_out0/6 and manual gold-evidence misses. Important finding reproduced: separate local_index/local_generate catalog calls could combine grants from different policy revisions where neither revision granted both. New atomic multi-scope API evaluates the intersection under one current-policy/revocation lock; gate and every provider/publication check use it. Deterministic RED reproduced gate false sufficiency and answered results at both before/after-provider boundaries; GREEN recorded after fix. Existing single-scope retrieval API remains compatible.

Two documentation findings addressed: README opening now reflects measured bounded grounding; request-tamper guarantee narrowed to canonical output integrity. Mutating provider-local question/source metadata is not generally detected when returned canonical quotations remain valid; this is not an arbitrary Python-provider sandbox. Such mutation cannot rewrite canonical emitted evidence/citations. No added free-language entailment guarantee.

Main after PR7 merge: [CI42169517262](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42169517262) on861871b verified SUCCESS. Review regression gate8+application9tests PASS after atomic scope fix; expected quality gate failure remains explicit, not presented as a code-test failure.

## Final local code verification

After atomic policy fix: base verifier5project+133backend PASS (11optional skips), optional verifier5+133PASS without skips; lexical17/20 unchanged. Targeted gate8/application9/evaluator4 (21total) PASS; policy-race gate and both provider boundary tests observed RED before fix and GREEN after it. Grounded CLI actual local model smoke answered interfaces with2canonical claims/citations. Full optional command also executes actual grounded quality and intentionally returns1 if target unmet; final model replay result recorded separately. No code/quality acceptance is inferred from doc checks or install alone.

## Публикация

[PR #8](https://github.com/UkWood/LLM-RAG-chat-bot/pull/8), branch feat/evidence-gate, implementation commitf01ca77. PR открыт, НЕ слит; предыдущий PR7 merged861871b и main CI42169517262 SUCCESS. Текущие actual push/PR checks доступны в PR8; не выводить CI success из локальных тестов и не считать green CI quality acceptance.

Финальный actual replay после атомарного policy fix совпал с saved report по metrics/cases/model/snapshot/dataset identities. Единая optional команда завершилась strict_grounding_exit=1 именно из-за targetFalse, после133PASS backend tests; base verifier exit0. Ограниченная grammar/held_out0/6/false refusals не скрываются. Реальные source approvals/cloud/Saturn-Main-Site не менялись.
