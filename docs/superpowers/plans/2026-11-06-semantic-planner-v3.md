# Semantic Planner V3 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL superpowers:executing-plans, inline execution inherited. Owner explicitly approved PR11 design and implementation; do not request plan/method approval again.

**Goal:** bounded role-aware predicate proposals, need-directed retrieval and exact selected-group validation, with independently blinded comparison only if calibration qualifies.
**Architecture:** captured snapshot → complete roles/exact entities/scopes → deterministic or calibrated local predicate proposal → per-need hybrid pool → bounded complete-group selection → V3 pinned-binding gate → exact Fake quotes/backend references/current policy publication.
**Tech:** Python3.12, existing unittest/locks/ONNX/tokenizer/CPU bundles only.
**Spec:** [accepted design](../specs/2026-11-06-semantic-planner-design.md).

## Global Constraints

V1 default; V2 public behavior/config/projections unchanged. Question<=4000chars, entities<=3, needs<=4, evidence<=5chunks/8000chars, one same-retrieved-manual anchor. <=4hybrid queries,10candidates/need, pool<=30, <=80intent+30rerank pairs; catalogue<=20; selection<=10000states/200000transitions. No new models/deps/source/cloud approvals, no Saturn writes/worktrees. Fresh blind40 hidden before implementation; separate cal60; no old held_out/consumed-blind tuning. No new target-specific implicit relations. All unsupported operators/qualifiers reject, errors remain errors. Existing first reports immutable.

## Review Focus

- Character/token truncation/Unicode cannot silently discard an operator or designation suffix (Task2).
- Wrong predicate/selector/source scope cannot become a related true quotation (Tasks2/5).
- Complete selected group cannot be replaced by a different source/mixed partial groups (Task3).
- Pool trimming, finite budget exhaustion and same-manual anchor cannot bypass policy/evidence bounds (Tasks3/4).
- Calibration infeasibility must leave blind unopened; setup/scoring failure after START consumes it and persists outcomes (Task5).

## File structure/interfaces

New grounding/v3_contracts.py: RoleSpan(start,end,role), ClauseV3(entity_ids,phrase,phrase_span,constraints,selector,recognized), QueryPlanV3(needs,question_sha256,planner_revision,catalogue_revision,gate_schema_revision,roles), GroupOption(need_index,group_id,projection_ids,evidence_ids,reference=None), EvidenceSelectionV3(options,candidates,anchors=()), ResultV3 extending GroundedResultV2 with trace and schema_version3.
New grounding/roles_v3.py: parse_roles(question,snapshot)->tuple[ClauseV3,...]|GateResult. Preserve original spans and complete content consumption; strict finite structural grammar, semantic phrase spans never swallow operators/source/entity qualifiers.
New grounding/router_v3.py: catalogue(snapshot,projections,catalog)->tuple[IntentEntry,...]; plan_v3(question,snapshot,projections,router,settings)->QueryPlanV3|GateResult. IntentEntry(predicate,selector,description); Router.propose(phrase,entries,settings) validates identity/finite/token bounds and abstains. Config fixed grid score_min[-10,-5,-2,0,2,5,10],margin_min[.25,.5,1,2,4]; exact clauses bypass scoring, finite ties abstain. config/planner-v3.json/canonical catalogue descriptions freeze before first calibration.
New grounding/evidence_v3.py: options_for_need(need,index,snapshot,pool,catalog,projections)->tuple[GroupOption,...]|GateV2; select_v3(plan,snapshot,pool,catalog,projections,limits)->EvidenceSelectionV3|GateV2; evaluate_v3(plan,selection,snapshot,catalog,projections)->GateV2. Rebuild/validate EXACT selected canonical group and references, source/global conflicts and full eligible group rules; no V2 reselection.
New grounding/retrieval_v3.py: retrieve_v3(service,indexes,plan,question,scorer)->pool+trace; captured _search10/need, round-robin unique30/current-policy filter, actual score_pairs pool once; validate canonical candidates/finite ranks/identity.
New grounding/application_v3.py: GroundedConsultantV3.answer(question)->ResultV3, reusing exact provider/reference/citation/current-policy publication semantics. CLI explicit --planner-version v3; V1 remains default.
New evaluation/v3_dataset.py: validate_v3(raw,snapshot,profile)->cases for blind40/cal60, strict canonical evidence/metadata/complete requirements. New evaluation/planner_v3.py: calibration comparison and declared-grid selection; freeze/first blind using exclusive SHA START/failure artifact and normalized plan/output scoring; CLI stages v3-calibration/v3-blind.

## Task1: independent blind data, before candidate implementation

- [x] Fresh blind author receives capability-only brief and canonical fixture/ingestion contracts, never old data/reports/tests/candidate/catalogue/calibration. Produce evaluation/datasets/planner-v3-blind.json+manifest, profile planner_v3_blind, same requirement schema as V2. Groups8single_field+4multi_need+4source_scoped+4document_reference+4relationship_type+8mandatory_refusal+8ambiguous_invalid; statuses24answered12refused4clarification. Root reads only SHA/counts/manifest.
- [x] Separate fresh label reviewer checks semantic/canonical labels and non-disclosing normalized-question duplicate hashes vs old sets and new calibration; fixes before final dataset identity without exposing payload to root. Save reviewed provenance/hash. Root blind-stages dataset without printing payload.
- [x] Root authors separate NON-independent calibration60:36positives(12single/8multi/6scoped/4docs/6relations) +24negative(12mandatory/6clarification/6mixed). Complete typed gold/pointers from canonical KB; no blind content access. Validate after Task5; no independent claim.

## Task2: role/parser/router contracts and calibration-independent guards

- [x] RED tests unknown symbols, operator negation/modification/disjunction, designation suffix/typo, scope propagation/mixed unsupported clause, input limits; exact positive single/spec/refs/software purpose/config lookup and original span coverage.
- [x] Implement focused modules/contracts/config above. Router consumes only predicate-phrase role spans, not ignored arbitrary trailing words. Named specs exact eligible labels. No source values in descriptions. Identity/token-length checked before inference with verified tokenizer; refuse any would-truncate pair.
- [x] RED tests fake score ordering/ties/nonfinite/wrong length, explicit unknown qualifier vs semantic topic, no more20candidates or4phrases, exact recognition/no inference. GREEN targeted; commit.

## Task3: captured retrieval/complete options/locked gate

- [x] RED integration for captured publication/current revocation, per-need10/pool30/round-robin fairness, duplicate/source/rank tampering and scoring errors. Implement retrieve_v3 with existing service/encoder/scorer.
- [x] RED pure tests complete group vs mixed-source partials, conflict/malformed/open members, wrong entity/selector/scopes, selected option mutation, manual same-source anchor/limit and metadata forgery, group union5/8000 and deterministic state/transition caps. Implement options/selector/evaluate exact canonical reconstruction; GREEN; commit.

## Task4: application/explicit CLI

- [x] RED no generation before all needs, provider omission/fake quotes, mixed and all-reference path, before/during/after-generation revocation, captured snapshot, model/provider errors and trace count limits. Implement V3 with unchanged V1/V2 behavior; GREEN; commit.

## Task5: data/evaluation/calibration and one-shot experiment

- [x] RED validators on custom fixtures (never blind payload); exact plan requirements/scopes/selector comparison independent of quote validity, equivalent reference rubric, partial/error denominators, truncated input/errors not correct refusals. Implement comparison/evaluator; validate calibration and have reviewer validate blind structurally (no solver).
- [x] Freeze initial catalogue/grammar/grid/resource identities before first calibration. Save each general-rule code/config iteration, select highest fully-correct positive coverage among zero unsafe/canonical-valid/correct negative outcomes, no legacyV1-positive regression and strictly better than correctedV2 new-cal coverage. Finite grid above remains fixed.
- [x] Base+optional full verifiers and one independent whole-branch review, one Important fix pass RED→GREEN/full checks; no second reviewer loop.
- [ ] If no configuration qualifies: persist feasibility failure, leave blind hidden/unconsumed, no fake blind score; docs/PR/CI and stop experimental stage. If qualifies: exact clean commit/code+config+catalogue+models+calibration+dataset hash freeze, SHA-exclusive START before parsing, single V2/V3 run40cases, errors/partial outcomes persist. Target24/24+16/16, no unsafe/partial/leak; unmet stays failure. No post-blind tuning/replay.
- [ ] ADR/status/stage/handoff/README and concrete implementation PR+actual current-head CI. Close docs-only11 as superseded once accepted design included. No automatic merge new feature PR.

## Verification commands

PYTHONPATH=backend/src:backend/tests work/venv/bin/python -m unittest discover -s backend/tests -p 'test_v3*.py' -v
work/base-venv/bin/python scripts/verify_offline.py
work/venv/bin/python scripts/verify_offline.py
Use existing local work/multilingual-e5-small and work/mmarco-reranker only for actual calibration/frozen comparison. Reports contain IDs/metrics/provenance, not raw questions/context/answer logs.

Self-review: all spec sections mapped above; same EvidenceNeed/SourceConstraints/FactProjection and canonical references consumed throughout, explicit new locked selection avoids V2 reselection. Gate/provider publication boundaries unchanged; empirical semantic mapping risk remains, default V3 disabled.
