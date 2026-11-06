# Evidence Gate Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans inline. Owner explicitly authorized next stage after PR7 merge; existing accepted roadmap/criteria preserved, routine scoped implementation choices recorded in spec.

Goal: conservative canonical evidence gate + offline extractive pipeline + honest unchanged evaluation.
Spec: [design](../specs/2026-11-06-evidence-gate-design.md).
Architecture: strict query plan → captured hybrid/rerank → typed canonical field gate → Fake provider → exact claim/citation/policy validation. Python3.12, existing locks, no new dependencies.

## Constraints and review focus

No real source approvals/cloud/site writes/model dumps; unchanged dataset/corpus/held_out. One entity/one field or manual lookup only; full grammar, no semantic inference. Provider only after local_index+local_generate policy; recheck before return. Partial list evidence/conflict must refuse. Provider omission or forged metadata must fail. Errors remain errors. Actual quality can fail and is preserved.

### Task1: plans and canonical gate

Files grounding/contracts.py, grounding/gate.py, tests/unit/test_evidence_gate.py.
Interfaces: QuestionPlan(entity_id,aspect), GateResult(state,reason,evidence_ids), plan_question(question,snapshot), evaluate_evidence(plan,snapshot,candidates,catalog).
- [x] RED tests strict grammar/unknown suffix/typo/mixed/injection, canonical full field sets/list coverage, malformed typed values, conflict, manual page and local_generate policy.
- [x] Implement exact schema-driven field selection and gate, no dataset dependency; targeted GREEN.
- [x] Full verifier and commit, ledger evidence.

### Task2: grounded application and canonical citations

Files grounding/application.py, grounding/__main__.py, retrieval/service.py captured rerank helper, tests/integration/test_grounded_pipeline.py.
Interfaces: GroundedConsultant(service,scorer,provider).answer(question)->GroundedResult; result status/gate/claims/sources/reason/snapshot. Captured helper keeps snapshot through rerank; GenerationRequest reused.
- [x] RED tests provider absent on failed gate, exact grounded claims, invented/omitted/duplicate text/IDs, canonical physical pages, revocation before/during generation and active publication, provider errors/offline guard/context budget.
- [x] Implement minimal captured flow, immutable internal canonical evidence, strict output validation, backend citations; GREEN.
- [x] Full suite and commit.

### Task3: actual evaluation and CLI/docs

Files evaluation/grounding.py, evaluation/__main__.py, tests/unit/test_grounding_evaluation.py, stage/status/handoff/ADR0008/README.
Interfaces run_grounding_evaluation(root,dataset,model_directory,reranker_directory)->report; stage grounding requires hybrid/pinned artifacts. Runtime reports contain no raw questions/context.
- [x] RED metric denominator/no-label-leak tests; implement status/false-refusal/citation/claim/evidence metrics with calibration/held_out and exact identities; GREEN.
- [x] Actual pretrained+Fake run on30cases, preserve unsupported-positive failures; no dataset/settings changes or tuning.
- [x] Two-profile full verifier, independent whole-branch review, RED→GREEN important fixes, publish feature PR and check actual CI. No automatic merge of new PR.
