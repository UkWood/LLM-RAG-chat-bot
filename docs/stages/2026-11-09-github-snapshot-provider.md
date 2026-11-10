# GitHub Snapshot Provider v0.1 — implementation

Date: 2026-11-09  
Status: **PR #22 OPEN; consolidated review corrections implemented; awaiting independent re-review, not merged**  
Repository: UkWood/LLM-RAG-chat-bot  
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/22  
Branch: `feat/github-snapshot-provider-v0.1`  
Base main: `9b2e0882b81fa2737e7efebb109c079a39b392d8`  
Original implementation code head: `ce501d2df5d120a3a437f6e32359a71e7d0543b6`  
Corrective code head: `27b64b439b699bef396122c395cf091fb60735f0`

## Consolidated Acceptance Review corrections — 2026-11-10

**Review outcome:** Four issues corrected in the existing PR #22 branch, preserving ADR-0014 and the SHA-1-only canonical snapshot boundary. The PR remains **OPEN, NOT MERGED**.

| # | Severity | Change | Verification |
|---|---|---|---|
| 1 | BLOCKER | A GitHub non-recursive tree request is now exactly `GET /git/trees/{sha}`; the `recursive` query parameter is absent. | Exact URL regression + recursive-truncation fallback to child tree SHA paths |
| 2 | BLOCKER | Guard `src`, `src/content`, `src/data`, `src/pages`, `src/lib` and every descendant under content/data/pages against symlinks, gitlinks and source-directory replacement. | Source collection gitlink, data symlink, pages gitlink, nested content symlink in normal/fallback modes; unrelated asset symlink remains allowed |
| 3 | IMPORTANT | Selective fallback traverses only `src`, `src/content/**`, `src/data/**`, `src/pages/**` and the top-level `src/lib` dependency directory. No fixed collection/dictionary/route filename list. | Large unrelated `public/**` and archive trees are never requested, even when configured to return `truncated=true`; new nested Markdown, YAML dictionary and Astro route are discovered |
| 4 | MINOR | Strict `ref == "refs/heads/main"` check before trusting the commit object. | Wrong and absent `ref` fail closed after one request |

The complete non-recursive traversal still checks tree SHA identity, non-truncated responses, path hierarchy, object modes/types, count and depth limits, and selected blob integrity. No unsupported symlink/gitlink is followed and no partial snapshot is returned.

### Direct GitHub REST semantics verification

Read-only GitHub REST requests against Saturn-Main-Site pinned commit `084d759487bfab6e111549c9b5469711ac5fc13e` and root tree `a5297822bf3a5e071b10cc1dca553481c1b84d47`:

- `/git/trees/{sha}` returned **16** immediate root entries with no nested path.
- `/git/trees/{sha}?recursive=0` returned **1,119** entries with nested paths.
- `/git/trees/{sha}?recursive=1` returned **1,119** entries with nested paths.
- Pinned child-tree requests without `recursive` returned immediate-only entries: `src` **9**, `src/content` **6**, `src/content/products` **292**. Each returned the requested tree SHA and `truncated=false`.

The above direct API check verifies the original defect and the corrected request semantics. It is **not** a claim that the provider was executed end-to-end with live credentials.

### RED → GREEN regression evidence

- Test-only RED commit: `491f14fe1e926958d8d934113a014398a76b2140`.
- RED push job: [run #42774670369](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42774670369), `offline-checks` **FAILURE**, **254 tests, 12 failing assertions, 11 existing optional skips**. Reproduced all four review findings. ONNX contracts remained SUCCESS.
- Corrective implementation code commit: `27b64b439b699bef396122c395cf091fb60735f0`.
- GREEN PR job: [run #42774964424](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42774964424), `offline-checks` and `onnx-contracts` **SUCCESS**, **254 tests passed, 11 optional skips**.
- Existing synthetic baseline unchanged: 10 documents, 44 chunks, 30 cases; lexical source-hit@5 0.85. This is a historical regression measurement, not site-provider quality.
- Nine new provider test methods were added, bringing the provider-specific count from 33 to **42**. The test fixture now models non-recursive URLs exactly and models source-directory gitlinks/symlinks without impossible descendants.
- A final strengthening of the test fixture expands the irrelevant public/archive case to 320 binary/archive files in over 300 directories and checks the nested symlink on both recursive and fallback paths. Final head CI must verify this documentation/test revision.

### Reproducible test commands

From a complete checkout with Python 3.12 and locked dependencies:

```bash
python -m pip install --require-hashes -r backend/requirements.lock
PYTHONPATH=backend/src python -m unittest discover -s backend/tests/unit -p test_github_snapshot_provider.py -v
python scripts/verify_offline.py
python -m pip install --require-hashes -r backend/requirements-onnx.lock
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -p test_embeddings.py -v
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -p test_model_preparation.py -v
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -p 'test_rerank*.py' -v
```

The assistant runtime had no checkout/network access to GitHub via the local shell; the full tests were actually run by GitHub Actions using the commands in `.github/workflows/ci.yml`. No local execution is claimed. Final corrected PR-head workflow outcomes must be checked by exact SHA before review.

### Unchanged boundaries

No changes to `PinnedSiteSnapshot`, `saturn_site_adapter.py`, `saturn_contracts.py`, `schema_evolution.py`, ADR-0012/0013/0014, provider-neutral protocol, legacy ingestion or read-only Saturn site. No Git clone/CLI fallback, no new dependency, no Gitea/PDF/retrieval/LLM/runtime deployment.

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

Originally added `backend/tests/unit/test_github_snapshot_provider.py` with 33 offline tests. Consolidated review adds nine methods (42 total). Coverage includes:
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