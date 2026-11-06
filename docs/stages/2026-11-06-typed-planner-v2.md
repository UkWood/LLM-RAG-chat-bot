# Typed planner V2 — 2026-11-06

Owner accepted design PR9 and explicitly requested implementation. Base main e0e44e54996b9f9e713899f7949746f27e33485b after PR8 merge. Branch feat/typed-planner-v2 includes the accepted design; feature PR will supersede docs-only PR9. This branch is not automatically merged.

## Implementation and boundaries

Immutable multi-need plans, orthogonal source scopes, canonical typed projections with literal spans/parser revisions/units/group completeness, all-needs evidence gate and separate backend references. Explicit designation/qualifier binding; whole-query consumption and conservative refusal. Manual anchor expansion limited1 total; evidence max5chunks/8000chars. One captured snapshot and atomic current index/generate permission intersection through publication. Mixed responses quote only factual needs; all-reference responses bypass Fake provider with the same policy checks. V1 remains default, v2 opt-in.

No new dependencies/models/real approvals/cloud/UI/deployment. Saturn-Main-Site strictly read-only. Existing E5 revision614241f622f53c4eeff9890bdc4f31cfecc418b3 and mmarco revision1427fd652930e4ba29e8149678df786c240d8825, local artifacts only in ignored work/. License declarations are not production clearance.

## Blind protocol and review

Independent fresh-context author read accepted capabilities and canonical synthetic KB/ingestion contracts only. Separate label reviewer corrected four IDs before implementation and confirmed final40cases/24positive/12refused/4clarification. Dataset SHA3889e584af3687ac6c686a3e80aeb172f429534f257d457c19ab5251469219e1. Implementer never opened the payload before final freeze/first START. Independent reviewer ran structural validation only, PASS40; did not run the candidate. Exact gold pointer arrays are conjunctive; equivalent canonical values can satisfy requirement correctness while strict pointer coverage stays separate.

Whole-branch independent preblind review found six Important defects: explicit interface qualifier discarded, metadata need dropped, shared source scope lost, open features treated as complete, dimensioned/fractional counts accepted, failed first attempt lacking outcome. Regression RED reproduced all six; fixes bind selectors before coordination, preserve requested references/source scopes, validate completeness/count grammar, retain error rows and persist invalid/partial outcomes after START. Additional pending-clause qualifier regression and per-projection parser/schema revision checks passed. No second blind attempt permitted by choosing a different freeze filename. Tests use custom/calibration fixtures, never blind contents.

## Commands

```bash
work/base-venv/bin/python scripts/verify_offline.py
work/venv/bin/python scripts/verify_offline.py
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage planner-calibration --mode hybrid --corpus fixtures/evaluation --dataset evaluation/datasets/synthetic-v1.json --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --planner-report work/planner-v2/calibration-reviewed.json
work/venv/bin/python scripts/freeze_planner_v2.py --dataset evaluation/datasets/planner-v2-blind.json --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --freeze work/planner-v2/freeze-final.json
PYTHONPATH=backend/src work/venv/bin/python -m saturn_ai.evaluation --stage planner-blind --mode hybrid --corpus fixtures/evaluation --dataset evaluation/datasets/planner-v2-blind.json --model-dir work/multilingual-e5-small --reranker-dir work/mmarco-reranker --freeze work/planner-v2/freeze-final.json --planner-report evaluation/reports/2026-11-06-planner-v2-first-blind.json --require-planner-target
```

Freeze requires clean committed tree; execution writes exclusive tracked START before reading the blind set, then saves all outcomes. Report contains IDs/metrics, not raw questions/answers/context logs. Quality flag exit1 means target unmet; setup/invalid experiment exit2. Never rerun or tune using this consumed set.

## Pre-freeze verification

Final code verification PASS:5 project +161 backend tests in both environments; base11 optional skips, optional0 skips. Both full verifier commands exited0 after final qualifier fix. Independent preblind review complete; all Important findings fixed RED→GREEN. Actual calibration: v1 positives8/14/status14/20; v2 positives14/14/status20/20, no v1-positive regressions, canonical output validity1.0. Strict pointer recall v1.428571/v2.714286 remains distinct from requirement correctness; reference-only outputs do not fabricate quotes. [Calibration report](../../evaluation/reports/2026-11-06-planner-v2-calibration.json). First blind result is pending at this commit; no blind quality claim. New quality target24/24positive+16/16negative/ambiguity; full prototype/real sample/natural-language entailment remain unaccepted.

Network recheck2026-11-06: both https://huggingface.co and https://us.aws.cdn.hf.co returned HTTP200 through the configured proxy. No new artifacts downloaded.
