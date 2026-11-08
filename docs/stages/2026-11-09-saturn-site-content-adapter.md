# Site Content Adapter — first vertical slice

Date: 2026-11-09  
Status: PR #20 open, not merged  
Repository: `UkWood/LLM-RAG-chat-bot`  
Base: `main` at `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`  
Branch: `feature/saturn-site-content-adapter`  
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/20

## Scope

Implemented only the pure/offline content adapter. It accepts a caller-supplied immutable snapshot with repository/branch, commit SHA, tree SHA and source paths containing Git blob SHA + exact bytes. It does not access GitHub or Saturn-Main-Site over the network.

The source schema was inspected read-only at Saturn-Main-Site revision `084d759487bfab6e111549c9b5469711ac5fc13`. No files or refs in that repository were changed.

## Implementation

- Added `backend/src/saturn_ai/ingestion/saturn_site_adapter.py`.
- Added immutable snapshot input types and exact Git blob SHA verification.
- Dynamically discovers Markdown collections under `src/content/<collection>/`.
- Fingerprints `src/content.config.ts` without executing TypeScript/Astro.
- Safely parses Markdown frontmatter and YAML dictionaries with bounded input, token, depth and node limits; rejects aliases, anchors, explicit tags, duplicate keys and non-string mapping keys.
- Preserves exact raw Markdown source bytes, raw frontmatter text and body. Unknown frontmatter fields and nested values are retained as raw facts.
- Excludes only records whose parsed `draft` value is the boolean `true`.
- Maps current entity subtypes and explicit source-declared relations. Missing `systems.kind` uses the source-declared `system` default; an explicit unknown discriminator remains generic with a warning. The `pages.groups` navigation tree is not projected as an engineering relation.
- Builds source revisions, schema inventory, dictionary fingerprints, deterministic manifest and add/update/delete + schema-drift plan using the existing Saturn contracts.
- Per-record parse errors are retained as diagnostics with raw bytes. A package containing errors is not eligible for promotion.

Test file: `backend/tests/unit/test_saturn_site_adapter.py`. Test fixtures: `backend/tests/fixtures/saturn_site/`.

## Verification

Implementation commit tested by CI: `51fb616d0c5d368f0452cab1fe6f1d07f3c78408`. Handoff/status documentation commits followed; the latest PR head must also have green checks before merge.

GitHub Actions PR-head [run #214](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42531823934): **SUCCESS**.

- Offline verification: 204 tests passed, 11 existing optional skips.
- ONNX contracts: SUCCESS.
- Synthetic baseline preflight: 10 documents, 44 chunks, 30 cases.
- Existing lexical source-hit@5 remains 0.85 overall; this non-blocking baseline was not changed by the adapter.

## Explicit exclusions

- No GitHub snapshot provider; caller supplies the pinned snapshot.
- No PDF download/parser, retrieval integration, LLM/provider, API/UI or deployment.
- No use of the legacy SourceRecord/Registry approval workflow.
- No changes to existing synthetic ingestion/evaluation, canonical contracts or ADRs.
- No modifications to Saturn-Main-Site.

## Next step

Review PR #20. After owner approval and merge, the next bounded implementation stage can be the read-only pinned GitHub snapshot provider. Any architecture/contract change must first be discussed in the separate architecture session.
