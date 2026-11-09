# Site Content Adapter — first vertical slice

Date: 2026-11-09  
Status: **PR #20 MERGED**  
Repository: `UkWood/LLM-RAG-chat-bot`  
Base before merge: `main` at `934c65e2bc11adf4c2b0b0e3b30717a02d7bb26e`  
Implementation branch: `feature/saturn-site-content-adapter`  
Implementation head: `9b36551adf61070426caa9250650bb32d638a66a`  
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/20  
Merge commit: `361529963bd48772f0d9d478dfb3b963ec5a8d03`  
Merged at: 2026-11-09 06:35:47 UTC

## Scope

Implemented only the pure/offline content adapter. It accepts a caller-supplied immutable snapshot with repository/branch, commit SHA, tree SHA and source paths containing Git blob SHA + exact bytes. It does not access GitHub or Saturn-Main-Site over the network.

The source schema was inspected read-only at Saturn-Main-Site revision `084d759487bfab6e111549c9b5469711ac5fc13`. No files or refs in that repository were changed.

## Implementation

- Added `backend/src/saturn_ai/ingestion/saturn_site_adapter.py`.
- Added immutable snapshot input types and exact Git blob SHA verification.
- `PinnedSiteSnapshot.repository` is the stable logical source ID (`UkWood/Saturn-Main-Site`), not a physical Git remote URL.
- Dynamically discovers Markdown collections under `src/content/<collection>/`.
- Fingerprints `src/content.config.ts` without executing TypeScript/Astro.
- Safely parses Markdown frontmatter and YAML dictionaries with bounded input, token, depth and node limits; rejects aliases, anchors, explicit tags, duplicate keys and non-string mapping keys.
- Preserves exact raw Markdown source bytes, raw frontmatter text and body. Unknown frontmatter fields and nested values are retained as raw facts.
- Excludes only records whose parsed `draft` value is the boolean `true`.
- Maps current entity subtypes and explicit source-declared relations. Missing `systems.kind` uses the source-declared `system` default; an explicit unknown discriminator remains generic with a warning. The `pages.groups` navigation tree is not projected as an engineering relation.
- Builds source revisions, schema inventory, dictionary fingerprints, deterministic manifest and add/update/delete + schema-drift plan using the existing Saturn contracts.
- Per-record parse errors are retained as diagnostics with raw bytes. A package containing errors is not eligible for promotion.

Test file: `backend/tests/unit/test_saturn_site_adapter.py`. Test fixtures: `backend/tests/fixtures/saturn_site/`.

## Review corrections included in the merged PR

- Canonical origin comes from the checked-in production `SITE_URL` fallback in `astro.config.mjs`; the adapter ignores GitHub Pages preview environment overrides and `BASE_PATH`.
- Verified routes: products, systems, groups, articles, news, root pages and `pages/home` → `/`. Unknown collections have no canonical URL; nested slugs without a catch-all route are not guessed.
- Route/config sources are included in source revisions and manifest: `src/pages/**`, `astro.config.mjs`, `src/content.config.ts`, `src/lib/url.ts`, `src/lib/nav.ts`, `src/lib/service.ts`, `src/data/nav.yaml`, `src/data/industries.yaml`. Add/change/delete produces route drift.
- Parser version is part of manifest and snapshot identity; parser changes produce drift. Legacy manifests and old builder calls use `saturn-site-parser/unversioned`.
- Missing `pages.kind` maps to `Page`; known `solution`/`section` map to their types; unknown explicit values remain generic `SiteContent` with warning and preserved raw facts.
- `SiteSourceRevision` remains raw source provenance. ADR-0013's PDF parser version stays on PDF extraction provenance; the site parser version belongs to `SiteSyncManifest`.

## Verification

Implementation head: `9b36551adf61070426caa9250650bb32d638a66a`.

GitHub Actions PR-head [run #232](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569426503): **SUCCESS**.

Matching push [run #231](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42569421610): **SUCCESS**.

- Offline verification: 212 tests passed, 11 existing optional skips.
- ONNX contracts: SUCCESS.
- Synthetic baseline preflight: 10 documents, 44 chunks, 30 cases.
- Existing lexical source-hit@5 remains 0.85 overall; this non-blocking baseline was not changed by the adapter and is not an adapter quality metric.

## Merge record

PR #20 was merged into `main` on 2026-11-09 at 06:35:47 UTC. Merge commit: `361529963bd48772f0d9d478dfb3b963ec5a8d03`. The implementation branch and PR are historical references; there is no open PR #20 work remaining.

## Explicit exclusions

- No GitHub/Gitea Snapshot Provider; caller supplies the pinned snapshot. Future providers map physical remotes to the stable logical source ID and emit the same `PinnedSiteSnapshot`.
- No PDF download/parser, retrieval integration, LLM/provider, API/UI or deployment.
- No use of the legacy SourceRecord/Registry approval workflow.
- No changes to existing synthetic ingestion/evaluation or ADRs. `SiteSyncManifest` was extended compatibly with parser version; legacy manifests/build calls remain supported.
- No modifications to Saturn-Main-Site.

## Next step — not started

The next bounded stage is to define and approve a provider-neutral read-only Snapshot Provider contract. It must verify exact commit/tree/blob identities, map physical Git remotes to the stable logical source ID and emit the existing `PinnedSiteSnapshot` contract.

Only after that contract is approved should the first provider implementation (GitHub) be started; Gitea can later implement the same contract. This stage has not started and is not included in PR #20. Any architecture/contract change must first be discussed in the separate architecture session.
