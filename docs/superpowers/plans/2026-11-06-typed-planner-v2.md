# Typed Planner V2 Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, inline. Owner accepted PR9 design and explicitly requested implementation; no repeated execution-method/plan approval.

Goal: typed complete multi-need planner, exact canonical projections/references, frozen blind comparison.
Spec: [accepted design](../specs/2026-11-06-planner-expansion-design.md).
Architecture: captured snapshot → strict compositional plan → versioned projections → all-needs canonical gate → Fake quotes/backend references → atomic policy publication.
Tech: Python3.12/existing locks/unittest, no new dependencies/models. Existing models only actual comparison. No worktrees per AGENTS.

## Constraints

Query<=4000chars, entities<=3, needs<=4, evidence<=5chunks/8000chars. Source document kind and representation are independent constraints. No default switch from v1, no dataset/corpus/parser changes, no new approvals/cloud/site writes. Old calibration only may tune; legacy exposed held_out is regression, not independent generalization. Blind set withheld until exact commit freeze; after first result no tuning on it.

## Review focus

- Table row/header/units and statement subject binding cannot answer with wrong entity/right source (Task2 tests).
- Set members are not scalar conflicts; partial/unknown enumeration cannot establish completeness (Task2 tests).
- Every need/source constraint must be covered, not one supported substring of mixed/negated question (Tasks2/3 tests).
- Metadata references/one same-manual anchor cannot invent quotes or approve another source (Task3 tests).
- Atomic current multi-scope permission/revocation and captured snapshot apply also to all-reference responses (Task3 tests).

### Task1: independent blind authoring/review, before implementation

Files evaluation/datasets/planner-v2-blind.json, planner-v2-blind.manifest.json (root reads manifest only).
- [x] Fresh author reads ONLY canonical KB, approved capability spec and current ingestion/snapshot modules, not old datasets/reports/tests or candidate code. Author40cases:24positive (8single field/spec,4multi-need,4source-scoped,4document-ref,4relationship/type),8mandatory_refusal,8ambiguous_invalid (4clarification,4refused). See author schema in task dispatch; semantic gold evidence is canonical source/field/page/text or typed ref.
- [x] Fresh label reviewer validates canonical hashes/support, distribution, semantic outcomes and independence without revealing text/labels to root. Fix before freeze, then manifest SHA/counts/version; root commit blindly stages files, never prints payload.
- [x] Record identity/provenance in manifest and ledger; authoring fixture, not real approval.

### Task2: v2 contracts, projections, compositional parsing

Files grounding/v2_contracts.py, projections.py, planner_v2.py, config/planner-v2.json; tests/unit/test_planner_v2.py (root-authored calibration/custom only).
Interfaces SourceConstraints(document_kind,representation); EvidenceNeed(entity_id,predicate,selector='',constraints=...); QueryPlanV2(needs,question_sha256,config_revision); CanonicalSpan(chunk_id,start,end,role); FactProjection(entity_id,predicate,value,source_id,spans,unit,group_id,cardinality,complete,representation); build_projections(snapshot)->tuple; plan_v2(question,snapshot,projections)->QueryPlanV2|GateResult.
- [x] RED tests schema field/spec/table literal spans, wrong-row/unit trap, valid list/group, statement purpose/composition/config-interface, unquotable metadata hints, malformed/open-list rejection.
- [x] Implement deterministic versioned projections with canonical spans; no synthetic model facts. Typed metadata refs separate.
- [x] RED plan tests whole-query consumption, single/multi needs/entities, source/representation conjunction, unsupported/negated/trailing/missing entity and typo clarification; implement explicit clause grammar using schema aliases/calibration only. GREEN targeted; commit.

### Task3: complete gate/application/reference results

Files grounding/gate_v2.py, application_v2.py; tests/integration/test_planner_v2_pipeline.py.
Interfaces GateV2(state,reason,evidence_ids,bindings,anchor_ids); GroundedResultV2(status,...claims,sources,references,plan,bindings,schema_version=2); TypedReference(kind,entity_id,source_id,value,title,url,document_id,content_hash,anchor_chunk_id,page).
- [x] RED tests need completeness, source scope mismatch, complete set conflict/partial union, malformed projection, canonical cell spans, request mixed refs+quotes, wrong metadata, provider omission/fake claim, budget/current policy/capture/ref-only revocation.
- [x] Implement all-or-nothing gate over top5 plus explicit same retrieved-manual anchor, validated against same canonical snapshot. Provider only canonical quote subset; backend refs exact canonical metadata, all-reference bypass with identical policy checks. v1 untouched/default unchanged. GREEN/full verifier; commit.

### Task4: blinded evaluator, CLI, freeze and first actual comparison

Files evaluation/planner_v2.py, evaluation/blind_dataset.py, evaluation/__main__.py, grounding/__main__.py; tests/unit/test_planner_v2_evaluation.py; docs/ADR/stage/status.
- [x] RED tests data validation (test-local custom synthetic cases, never blind contents), proper denominators, exact requirement/source/quote/ref equivalence across v1/v2, missing-third-need and metadata mismatch, no labels passed to app; GREEN.
- [ ] Base+optional full verifier; legacy CALIBRATION ONLY actual comparison/tuning, no reading old held_out or blind. Freeze final code/config/calibration at exact commit +config/projection hashes and write freeze manifest BEFORE blind run.
- [ ] Independent whole-branch review before blind, important fixes RED→GREEN +full suite, then final freeze. First blind evaluation once after logged START, do not inspect questions/labels before it. Save all40 cases/metrics/errors including unmet target. New target24/24 positives+16/16negative/ambiguity, no unsafe claims/invalid citations, complete needs for each answered. v1/v2 same rubric/artifacts/config.
- [ ] After result no planner/config changes; if bug invalidates experiment mark consumed/invalid and require fresh set for new independence. Final quality report not baseline relabeling. Publish feature PR +actual CI, docs/handoff; no auto merge.
