# GitHub Snapshot Provider v0.1 — implementation

Date: 2026-11-09  
Status: **PR #22 OPEN; implementation code head CI SUCCESS; not merged**  
Repository: UkWood/LLM-RAG-chat-bot  
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/22  
Branch: `feat/github-snapshot-provider-v0.1`  
Base main: `9b2e0882b81fa2737e7efebb109c079a39b392d8`  
Reviewed implementation code head: `ce501d2df5d120a3a437f6e32359a71e7d0543b6`

## Objective

Implement the first working GitHub REST Snapshot Provider for the trusted Saturn site. The provider must resolve the moving branch once, pin an immutable revision, obtain a complete and verified source snapshot, and return the existing `PinnedSiteSnapshot` to the unchanged pure/offline Saturn Site Content Adapter.

## Implementation

### Provider boundary and revision pinning

- Added `backend/src/saturn_ai/ingestion/snapshot_provider.py` with provider-neutral `SnapshotProvider` Protocol.
- Added `backend/src/saturn_ai/ingestion/github_snapshot_provider.py` with `GitHubSnapshotProvider`.
- Physical repository and API origin are fixed: `UkWood/Saturn-Main-Site` and `https://api.github.com`. The returned canonical identity remains the logical source ID `UkWood/Saturn-Main-Site`; physical remote details do not enter canonical models.
- `refs/heads/main` is resolved exactly once. The returned object must be a commit. Commit SHA and root tree SHA are validated; subsequent calls use only pinned commit/tree/blob IDs.
- No final branch recheck or fallback to a newer commit occurs if `main` moves during a sync.

### Complete Git tree enumeration

- The provider first requests the recursive tree for the pinned root tree SHA.
- If GitHub returns `truncated=true`, the partial recursive listing is discarded. The provider starts a complete non-recursive traversal from the pinned root tree SHA and follows every child tree by its immutable tree SHA.
- Any truncated non-recursive subtree fails the sync; the provider never returns a partial inventory.
- Tree responses are checked against requested tree SHA. Entries are checked for safe paths, unique paths, parent-directory consistency, supported Git object type/mode, valid SHA-1 IDs, declared sizes and configured depth/count limits.

### Deterministic source selection

Selection follows `docs/site-specific/v0.2/05-snapshot-provider-contract.md`:
- Every `.md` file under `src/content/` (case-insensitive extension).
- Every `.yaml`/`.yml` file under `src/data/` (case-insensitive extension).
- Required `src/content.config.ts` and `astro.config.mjs`.
- Every regular `.astro` and `.ts` file under `src/pages/`, excluding `.d.ts`; any other regular file under `src/pages/` raises `RouteSourceDriftError` and fails closed.
- Optional `src/lib/url.ts`, `src/lib/nav.ts` and `src/lib/service.ts` when present.
- Selected symlinks/submodules are rejected. Unrelated binary assets, PDFs, images, fonts and videos are not downloaded.
- Selected paths are sorted by repository-relative POSIX path before snapshot construction.

### Blob integrity and snapshot construction

- Each selected blob is requested by the pinned blob SHA.
- GitHub API base64 content is decoded strictly; API SHA, tree/API declared sizes, decoded byte count and canonical Git blob SHA-1 are verified.
- Raw content SHA-256 is calculated separately from the Git object hash. Exact original bytes are preserved in `SnapshotFile`.
- The provider returns the existing immutable `PinnedSiteSnapshot`. Its files are accepted by `adapt_snapshot()` without modifying the adapter or canonical contracts.
- Any missing blob, invalid encoding, size/hash mismatch or resource-limit breach raises an error; no partial snapshot is returned.

### Security and resource controls

- Standard-library HTTPS transport uses the default TLS certificate/hostname verification context and refuses redirects.
- API origin and repository are fixed in code; API calls are GET-only. No arbitrary URL from tree/blob responses is followed.
- Runtime configuration is read from environment: `SATURN_GITHUB_TOKEN` and explicit `SATURN_GITHUB_OBJECT_FORMAT=sha1`. The token must have read-only Contents access. Token is excluded from config repr and never included in provider error messages.
- GitHub repository metadata did not expose an `object_format` field during the read-only audit. SHA-1 is therefore explicit trusted configuration, not inferred from object ID length; every selected blob is then verified using the canonical SHA-1 object hash.
- Bounded request timeout, total operation timeout, retry attempts/delay, API request count, response size, tree entry count/depth, selected file count, per-file bytes and total snapshot bytes are enforced.
- Network/HTTP errors, authentication, rate limits, missing objects, malformed responses, base64 errors, tree truncation, unsupported object modes and hash mismatches fail explicitly.

## Read-only source audit

`UkWood/Saturn-Main-Site` was read only. The current `main` tree at commit `084d759487bfab6e111549c9b5469711ac5fc13e` was inspected through Git tree metadata:
- Recursive tree: `truncated=false`, 1,119 entries.
- Files selected by the approved policy: 477.
- Total selected declared bytes: 2,233,425; largest selected file: 32,186 bytes.
- `src/pages/`: 23 regular files — 19 `.astro`, 4 `.ts`; no route-source drift.
- Both required files are present.

This was a metadata-only read-only audit, not a live execution of the new provider. No files, branches, URLs, assets, CI or search settings in `Saturn-Main-Site` were changed.

## Tests and CI

Added `backend/tests/unit/test_github_snapshot_provider.py` with 33 offline tests. Coverage includes:
- successful snapshot and adapter compatibility;
- one-time branch pinning and branch movement during blob retrieval;
- complete recursive tree, truncated recursive fallback and truncated non-recursive failure;
- tree identity, duplicate paths, missing parent directories, object modes and path depth;
- deterministic source selection, required files and route-source drift;
- symlink/submodule handling;
- blob SHA-1, raw SHA-256, base64 decoding, size checks and missing blobs;
- authorization, rate limits, bounded retry, network/partial-read failures and redirect rejection;
- response/resource limits, operation timeout, no partial result and explicit object-format configuration.

Implementation code head `ce501d2df5d120a3a437f6e32359a71e7d0543b6`:
- Push workflow [#42696950473](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42696950473): `offline-checks` and `onnx-contracts` — **SUCCESS**.
- PR workflow [#42696961675](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42696961675): `offline-checks` and `onnx-contracts` — **SUCCESS**.
- Offline verification: **245 backend tests passed, 11 existing optional skips**; project-level checks passed.
- Synthetic baseline unchanged: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 = 0.85. This is a regression/control measurement, not a quality claim for the new provider.

No new dependencies were added.

## Files changed

Implementation:
- `backend/src/saturn_ai/ingestion/snapshot_provider.py`
- `backend/src/saturn_ai/ingestion/github_snapshot_provider.py`
- `backend/tests/unit/test_github_snapshot_provider.py`

Documentation synchronization:
- `README.md`
- `docs/HANDOFF.md`
- `docs/PROJECT_STATUS.md`
- `docs/CHATGPT_SESSION_GUIDE.md`
- `docs/stages/README.md`
- `docs/stages/2026-11-09-snapshot-provider-contract.md` (final PR #21 merge result added while preserving its initial OPEN review state)
- this stage report

## Exclusions and known limitations

- No Gitea provider, PDF download/parser, Git-backed PDF retrieval, Support Catalog Adapter, retrieval integration, embeddings, reranking, LLM/provider, API/UI, deployment or production scheduling.
- No changes to `saturn_contracts.py`, `saturn_site_adapter.py`, `schema_evolution.py`, ADR-0012/0013/0014 or canonical contracts.
- Live provider smoke test and runtime wiring were not performed. Mock HTTP transport is used for CI; production credentials were not introduced.
- Only the GitHub JSON blob response with supported base64 encoding is accepted. Any unsupported response encoding fails closed; raw-media fallback is not implemented in v0.1.
- GitHub provider supports the current SHA-1-only canonical contracts. A different Git object format requires a separately approved canonical-contract evolution.
- PR #22 is **OPEN and NOT MERGED**. The current PR head and its checks must be revalidated before review/merge. Merge requires a separate explicit owner instruction.