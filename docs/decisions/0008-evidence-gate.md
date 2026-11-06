# ADR-0008: canonical extractive evidence gate

Status: accepted bounded implementation under owner request to execute roadmap stage5 after merging PR7. Full prototype/production acceptance is not granted.

Use strict full-question planning for a single exact entity and a structured field (power/interfaces/protocols/temperature/status) or approved manual lookup. Ambiguous one-edit designations require clarification; no silent correction or model-score sufficiency. Gate requires current local_index AND local_generate, complete canonical field sets, typed values, no conflicts and bounded evidence. Malformed members cannot be discarded to make a partial list look complete.

Keep one captured snapshot throughout reranking/gate/generation/citations. Only offline test provider enabled, reuse FakeLLMProvider; provider claims must exactly quote each selected canonical evidence chunk once. Backend builds URLs/hash/document IDs/headings/physical pages from registry/snapshot, never from model metadata. Recheck policy before and after generation and before output. Infrastructure errors remain errors. Existing M1 unchanged, no cloud/site/real sources/new dependencies.

[Actual frozen synthetic assessment](../../evaluation/reports/2026-11-06-grounding.json):8/20 positive answers, refusals8/8, clarifications2/2, status accuracy.6, expected-evidence recall.3; emitted verbatim claims/citations valid1.0,0unsupported. Held_out positive0/6. The narrow grammar is insufficient for full prototype acceptance; green code tests or correct refusals do not cure false refusals. Do not tune on failed held_out questions. A broader semantic/planning stage needs separate calibration/fresh evaluation and design; it is not silently enabled here.

Exact quote support is not universal natural-language entailment. Fake provider cannot establish safety/quality of real LLMs. Full engineering consultation, real sample/source approvals and cloud integration remain disabled. Source-hit20/20 from prior retrieval stage is not answer coverage20/20.
