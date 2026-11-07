# Semantic Planner V3 experiment — 2026-11-06

Owner explicitly approved detailed design PR11 and requested implementation. Base mainbb16530 (PR10 merged, mainCI42256501265 SUCCESS). [Accepted design](../superpowers/specs/2026-11-06-semantic-planner-design.md), [implementation plan](../superpowers/plans/2026-11-06-semantic-planner-v3.md), [ADR0010](../decisions/0010-semantic-planner.md). Inline execution in the existing isolated checkout, no worktrees or repeated approval. V1 remains default, corrected V2 unchanged, V3 explicit opt-in. No new dependencies/models/source/cloud permission; Saturn-Main-Site strictly read-only.

## Data independence

Fresh-context author and independent semantic/source/capability reviewer prepared NEW40cases before ANY candidate implementation. Final blind SHA6f48fdbad02761fac30c1950e3a9f8c3a0b77ed0fbc3eb5c854a1315fb23dbe0,25589bytes,24answered12refused4clarification; original8/4/4/4/4/8/8 groups. One quote normalization and one same-quota positive replacement for a baseline source-capability gap occurred during authoring, before code. Implementer saw only hash/counts/manifest/validation outcomes, never blind text/labels. Reviewer checked25evidence needs,6typed refs,27canonical pointers, no remaining gaps. Nondisclosing normalized-question dedup vs old30/oldblind40/newcal60:zero collisions. A supplemental baseline capability schema had no values/questions/candidate grammar; only reviewer accessed it. Author did not inspect it or candidate code.

Root authored exposed NON-independent calibration60 from canonical KB:36positives(12single,8multi,6source-scoped,4docref,6relation/type),18refusals6clarifications. Both profiles structurally validated (blind validator executed by independent reviewer only after labels froze, no solver/inference). Old datasets/first reports untouched; no old held_out/consumed-blind tuning. New blind remains hidden/unconsumed until feasibility+review+exact freeze/exclusive START, or stays hidden if infeasible.

## Implemented boundary

Role spans preserve original character offsets and full content consumption; invisible symbols, negation/modification/disjunction, unsupported selectors and mixed topics reject before proposal. Source/entity/predicate/lookup bindings are explicit, not a global ignored-context list. Ambiguous scope attachment clarifies. Exact complete lookup constructions may bypass scoring; other noun topic spans use pinned local mmarco catalogue proposals. Catalogue keys are enum predicate/canonical selector, no source values/expected facts. Exact ambiguous spec labels clarify; malformed values retain their known label so the gate quarantines the fact instead of routing to another spec.

Verified tokenizer measures full untruncated pairs before intent inference; existing reranking behavior stays compatible. Logits are relevance, not semantic proof. Fixed score grid[-10,-5,-2,0,2,5,10] and margin[.25,.5,1,2,4], catalogue<=20,<=4phrases/80intent pairs. Only multiple credible labels may produce semantic ambiguity; a single low-margin credible label refuses. Unknown semantics may still misroute; this is empirical risk, not universal language understanding.

Captured hybrid queries10/need, deterministic round-robin unique30, one original-question rerank30; total<=110pairs/4queries. Whole canonical group options, full-source conflict/malformed/partial rules and deterministic bounded cover(10000states/200000transitions). Exact pinned option fingerprint checked by V3 gate; it never reselects a different group. Same existing projection schema/current atomic index+generate intersection; max5chunks/8000chars/one same-retrieved-manual anchor. Fake exact complete quotes/backend references checked before/after generation and before publication, including all-reference bypass. No provider call for partial/unsupported requests; infrastructure errors remain errors.

## Calibration and first-run protocol

Record source/runtime/config/model/data identities BEFORE actual calibration. Evaluate35 fixed-grid abstention configurations from actual permissive proposal scores and outputs; grammar/catalogue may iterate only on exposed calibration with audit. Projected grid results are not35 full model runs or a speed benchmark. Fully replay the chosen configuration, require identical status/requirement/output outcomes, zero unsafe/errors, valid canonical output, correct negative/ambiguity outcomes, no V1-positive regression on legacy calibration and strict fully-correct coverage gain over corrected V2 on new calibration. Report actual selected replay cold/warm latency and pair counts separately.

If infeasible, publish feasibility failure with independent quality NOT_RUN and blind unconsumed. If feasible, clean exact commit+runtime/config/model/calibration/author SHA freeze then exclusive dataset-SHA START before parsing/model setup; single correctedV2/V3 comparison40cases. Setup/scoring failure consumes set and persists invalid/partial outcome. No second freeze filename or post-result tuning. Acceptance24/24positive+16/16negative/ambiguity, no unsafe/partial/policy/citation error; smaller result stays failure. Even a synthetic pass does not grant production/real-sample/default enablement.

## Verification checkpoint

TDD initial missing modules RED, then concrete operator/Unicode/modifier/multihead/declaration/scope/token/selector and locked-group counterexamples RED→GREEN. Core22tests PASS before evaluator additions. Evaluator/custom temporary freeze/CLI contract tests and full base/optional verifiers are in progress; actual semantic calibration/fresh blind result not yet measured at this checkpoint. Final review, actual outcomes, publication and CI are appended after completion. No numeric graph test is reported as model quality.

## Resume, calibration iteration 1 and final review — 2026-11-07

Restored clean branch f90a83c after the usage-limit interruption; local bundles remained available. Both huggingface.co and us.aws.cdn.hf.co returned HTTP200 through the normal environment network. No download or Saturn mutation.

[First actual calibration](../../evaluation/reports/2026-11-07-planner-v3-calibration-iteration-1.json) on committed f90a83c did **not qualify** any of the35 fixed-grid settings. The permissive probe achieved34/36 fully-correct positives and24/24 negative outcomes, but one answered plan was wrong and legacy V1-positive q008/q018 regressed. These are exposed, non-independent calibration outcomes, not blind quality. No selected configuration, freeze or V3 START was created.

Calibration-only diagnosis justified a general finite declaration lookup and narrowly bound synthetic entity/manual training descriptors. Separately, authoring audit found cal036 omitted the explicit USB selector although both question and canonical evidence require USB: its exposed gold selector changed from empty to `interface=usb`; question, evidence, status and quotas are unchanged. Original failed report/source/data identity is retained. The blind dataset/manifest and all old datasets/reports remain unchanged; question-based dedup remains valid.

Independent fresh-context whole-branch review found three Important issues: typed-lookup residual content, overbroad noun-stem exact recognition, and dangling/alternate designation separators. All three received failing regression tests before the fix, then targeted GREEN. No second reviewer loop. Two Minor findings deferred: relevance preference sums option minima and prunes alternative bindings with the same evidence union; saved diagnostics omit per-need retrieval/pool/selection coverage. They limit preference/diagnosis, not complete canonical sufficiency or policy. Full verifiers and a second actual calibration are next; fresh blind remains hidden and unconsumed.

A further implementer audit before any blind attempt found the legacy regression check could accept an unrelated true quotation. It now grades the unchanged V1-supported requirement against original gold-defined canonical complete facts and equivalent canonical manual references, both during grid qualification and selected replay. A custom regression rejects the wrong interface quote for a power question while accepting equivalent complete power evidence from the table and a correct manual reference (8 evaluator tests PASS). The [374cad5 calibration report](../../evaluation/reports/2026-11-07-planner-v3-calibration-before-legacy-grader.json) is retained as a superseded diagnostic, **not a valid blind qualification**: its application result cannot substitute for the corrected legacy evaluator. Fresh calibration and full checks of the corrected evaluator follow; V3 START still absent.

## Qualified calibration and verification — 2026-11-07

[Corrected calibration report](../../evaluation/reports/2026-11-07-planner-v3-calibration.json), source `e792e1373516e5bc4dba7b7b5ed0b4ef280cf82a`, runtime SHA `cc0c271bb5cb2eebc69c88c7b076535bbbd4dcc182135743c513bd3d02a47a14`: **feasible=true**, selected replay matches. Selected score_min=-2.0, margin_min=1.0 from the unchanged35-setting grid. V3 fully correct35/36 positives and24/24 negative/ambiguity; unsafe0, errors0, canonical output validity1.0. Corrected V2 on the same exposed data20/36 and24/24, with1 wrong answered binding. Eight gold-correct V1-positive legacy cases retained without regression under complete-fact/manual-reference equivalence. This is NON-independent calibration, not an independent quality claim.

Selected actual replay setup24.27s, warm p50=2.40s/p95=3.54s on this shared CPU environment; no SLA or35-full-run claim. General-rule and evaluator audit history above remains visible. Blind payload/manifest unchanged, root has never opened the payload; no V3 START at this checkpoint.

Final source verification: `work/base-venv/bin/python scripts/verify_offline.py` and `work/venv/bin/python scripts/verify_offline.py`:5project+206backend PASS in both (base12optional skips/ONNX0). Existing lexical baseline17/20 remains an expected measured target failure. Independent whole-branch review and Important fix pass completed; two Minor limitations above remain. [Implementation PR12](https://github.com/UkWood/LLM-RAG-chat-bot/pull/12) is draft/unmerged; docs-only11 closed as superseded without merge. Next: exact clean freeze and the single first blind attempt, then result/CI publication. No runtime/config/grader tuning after that first result.

## First independent blind outcome — target FAILED, 2026-11-07

[Immutable first report](../../evaluation/reports/2026-11-07-planner-v3-first-blind.json), [exclusive START](../../evaluation/experiments/6f48fdbad02761fac30c1950e3a9f8c3a0b77ed0fbc3eb5c854a1315fb23dbe0.START.json). Exact freeze `f0144f7945c5d22e87325fefc85491f2eabc4d88`, runtime SHA `cc0c271bb5cb2eebc69c88c7b076535bbbd4dcc182135743c513bd3d02a47a14`, dataset SHA `6f48fdbad02761fac30c1950e3a9f8c3a0b77ed0fbc3eb5c854a1315fb23dbe0`, selected -2.0/1.0. START persisted2026-11-07T00:43:27.689388Z before model setup and payload parsing. Implementer never inspected blind questions before freeze; final reviewer never opened them.

Valid completed experiment:80system runs/40cases, unexecuted0, errors0. CLI with `--require-planner-target` returned1 because the quality target was not met. No rerun, data relabeling or runtime/config/grader change after the first result.

| Measured outcome | Corrected V2 | V3 |
| --- | ---: | ---: |
| Fully correct positive answers | 4/24 | 2/24 |
| Correct refusal/clarification | 16/16 | 16/16 |
| All fully correct outcomes | 20/40 | 18/40 |
| Wrong answered bindings / unsafe answers | 0 | 0 |
| Runtime errors | 0 | 0 |
| Emitted canonical validity / verbatim support | 1.0 / 1.0 | 1.0 / 1.0 |

V3 positives:2/8single-field;0/4multi-need,0/4source-scoped,0/4document-reference,0/4relationship/type. It falsely refused20positive cases and asked clarification for2. Failure reason counts:8unknown_predicate,7unsupported_qualifier,4unsupported_symbol,1unknown_entity,1ambiguous_predicate,1ambiguous_entity. This measures severe coverage failure; it does not establish universal safety from16negative examples. Corrected V2's4/24 is a new measurement on this dataset, not the historical old8/24 result.

The35/36calibration gain did not generalize; V3 performed worse than V2 on this independent set. The24/24+16/16target and full prototype acceptance remain FALSE. Latency medians in this report are dominated by early refusals and do not show a useful answer-speed gain. Preserve V1 default and explicit experimental V3 opt-in. Next is a separate redesign of language/role/predicate coverage with fresh independent evaluation before any new quality claim; this consumed dataset must not become a tuning set.

[PR12](https://github.com/UkWood/LLM-RAG-chat-bot/pull/12) remains draft/unmerged to make the failed quality result explicit. Accepted design and audit are retained, docs-only11 closed as superseded without merge. Two deferred Minor findings remain exactly as documented: relevance preference/tie pruning and missing per-need retrieval diagnostics. No new model/dependency/source/cloud permission; Saturn-Main-Site unchanged/read-only. Final publication/CI evidence follows separately.

Commands: final base/ONNX `scripts/verify_offline.py` both5project+206backend PASS; `scripts/check_project.py` and `git diff --check` PASS. Actual calibration used `--stage v3-calibration --mode hybrid --require-feasibility`, existing `work/multilingual-e5-small` + `work/mmarco-reranker`. Freeze used `scripts/freeze_planner_v3.py`; first comparison used `--stage v3-blind --freeze work/planner-v3/freeze-final.json --planner-report evaluation/reports/2026-11-07-planner-v3-first-blind.json --require-planner-target`. The numeric CI contracts are separate from these semantic measurements.
