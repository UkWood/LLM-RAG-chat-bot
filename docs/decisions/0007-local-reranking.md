# ADR-0007: bounded local reranking

Status: accepted bounded implementation following owner-approved [design](../superpowers/specs/2026-11-06-local-reranking-design.md). Full production architecture ADR-0001 remains proposed.

## Context and decision

Frozen E5 hybrid achieved source-hit17/20; its top30 pool contains expected sources for all positives. Add a separate local CPU single-logit pair scorer after hybrid RRF, not embedding mean pooling or heuristic label lookup. Capture one IndexSet; resolve text from its canonical snapshot; check current policy before and after scorer. Errors are explicit with no fallback. Sort raw descending logit, incoming rank,chunk ID; final5. Model score is not confidence or evidence sufficiency.

Use explicit immutable hashes/profile/card/license evidence and atomic new directory preparation. Runtime uses exact verified bytes, rejects external-data tensors, and reports identity-bound provenance; complete bundle replacement during load is rejected. Numeric runtime-contract bundles cannot supply semantic reports. No inference downloads/new dependencies; locked optional CPU profile is sufficient.

Actual candidate: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 at1427fd652930e4ba29e8149678df786c240d8825. Card declares Apache-2.0, ru/multilingual and pair logits; declaration evidence is not standalone license/legal clearance. This selects a local experiment, not production/redistribution rights.

## Consequences and evidence

[Actual unchanged synthetic run](../../evaluation/reports/2026-11-06-reranking.json): source-hit20/20, all-source/evidence coverage1.0, MRR.916667,nDCG.867586; hybrid baseline17/20 and nDCG.629721 in same run. Positive source-hit calibration14/14,held_out6/6; no tuning. CPU single-process latency measured, not SLA. Numeric CI verifies contracts only. Current lexical default preserved; no new generator/API/cloud access or real source approvals.

Retrieval criterion passes this small frozen synthetic set; grounded answers/refusal/injection defense/real sample and full prototype acceptance remain unmeasured. Next bounded stage5 must evaluate sufficient/insufficient/ambiguous/conflict evidence and claim support independently of reranker scores. Saturn-Main-Site remains read-only.
