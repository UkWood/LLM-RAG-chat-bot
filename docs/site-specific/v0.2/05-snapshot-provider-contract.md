# Snapshot Provider Contract v0.1

Date: 2026-11-09  
Status: **ACCEPTED — owner-approved architecture; provider implementation NOT STARTED**  
Repository: UkWood/LLM-RAG-chat-bot  
Related decisions: ADR-0012, ADR-0013, ADR-0014

## 1. Purpose and boundary

Snapshot Provider is the read-only boundary between a Git hosting service and the existing pure/offline Saturn Site Content Adapter.

Its only public responsibility is to obtain one complete, immutable source revision and return it as the existing PinnedSiteSnapshot contract. It does not parse Markdown, YAML, Astro or TypeScript; map domain entities; create canonical facts or relations; fetch external PDF URLs; extract PDF text; run retrieval; or call an LLM.

Approved sequence:
- GitHub REST API is the first transport implementation.
- Gitea REST API is a later implementation of the same provider-neutral contract.
- Both implementations produce the same logical source identity and PinnedSiteSnapshot shape.
- Provider-specific API, authentication, response decoding, rate-limit handling and server-version behavior remain inside the corresponding implementation.
- Site Content Adapter and canonical knowledge contracts do not depend on GitHub/Gitea SDKs, URLs, API response types, credentials, CI, clone operations or deployment.

This document defines the target contract only. It does not authorize provider implementation.

## 2. Stable source identity and physical remote binding

The trusted logical source is fixed:

| Field | Value |
|---|---|
| Logical source ID | UkWood/Saturn-Main-Site |
| Branch | main |
| Git ref | refs/heads/main |

Provider configuration maps one explicitly configured physical remote to this logical identity. The physical binding contains provider kind, trusted API origin, repository namespace/name and a reference to a read-only credential. It is configuration, not source identity.

The physical API URL, GitHub owner, Gitea organization/namespace, credential, token, provider name and server version must not replace the logical source ID in PinnedSiteSnapshot or canonical provenance.

The provider must not accept a repository URL, API endpoint, namespace or credential supplied by a user question or arbitrary runtime input. Only a preconfigured and allowlisted remote binding may be used.

A GitHub-to-Gitea migration changes the physical binding and provider implementation only. It does not change the logical source ID, canonical entity IDs, source meaning or Site Content Adapter interface.

## 3. Provider-neutral interface

The public interface is intentionally small:

- SnapshotProvider.fetch_snapshot() returns one PinnedSiteSnapshot for the configured trusted source and branch.
- A successful return means the complete selected file set for one exact commit/tree was obtained and every selected blob passed the required integrity checks.
- Any incomplete or unverifiable result raises a typed provider error. A partial PinnedSiteSnapshot is never returned as success.

The internal Git object transport needs equivalent operations for:
1. Resolving one configured ref to a commit object ID.
2. Reading the commit identified by that immutable object ID and obtaining its root tree object ID.
3. Enumerating a tree and its child trees by immutable tree object IDs.
4. Reading a blob by immutable blob object ID.
5. Determining the repository Git object format, or applying an explicitly configured and verified provider capability where the API does not expose it.

These are conceptual contracts, not a requirement to expose provider API types to the adapter. GitHubRestTransport and the future GiteaRestTransport implement them behind the provider boundary.

## 4. Pinning and trust model

### 4.1. One-time branch resolution

At the beginning of a sync, the provider resolves refs/heads/main once. The resulting commit object ID is the revision pin for the entire operation.

The provider then:
1. Reads the commit by that exact commit object ID.
2. Confirms that the returned commit identity matches the pinned ID.
3. Reads the root tree object ID from that commit.
4. Confirms that tree responses identify the exact requested tree object IDs.
5. Enumerates the complete tree and retrieves selected blobs only by object IDs found in that pinned tree.

After the initial ref resolution, every subsequent operation uses immutable commit, tree or blob object IDs. The provider must not re-resolve main, follow a moving branch, or perform a final HEAD recheck during the same sync.

If main moves while files are being fetched, the in-progress snapshot remains a snapshot of the originally pinned commit. This is expected and safe: a later sync resolves main again and obtains the newer revision. A retry caused by a transient API failure retries the same pinned object ID; it does not silently switch to a new commit.

### 4.2. What commit/tree verification means

The Git provider is the trusted authority for the mapping:

refs/heads/main → commit object ID → root tree object ID.

The provider checks identity consistency across ref, commit and tree responses and verifies that the selected tree traversal is complete. It does not claim independent cryptographic verification of commit or tree objects: the provider API supplies those object identities and tree entries, and this contract does not independently fetch and hash raw serialized commit/tree object bytes.

No claim of signature verification, commit authorship verification or independent tree-object authenticity is implied. Stronger independent verification would require a separate design that retrieves and validates the raw Git objects.

### 4.3. Complete tree enumeration

A successful snapshot requires a complete view of every tree path relevant to the selection policy.

- A recursive tree response marked truncated is not a complete result and must never be accepted as one.
- The provider may fall back to a complete non-recursive traversal, starting from the pinned root tree and following every child tree by its returned tree object ID.
- Every selected subtree must be enumerated to completion. A truncated, missing, inaccessible or otherwise unverifiable subtree makes the sync fail unless a complete fallback traversal succeeds.
- The provider must not infer missing entries, silently omit a subtree, or use a partial listing.
- Tree entries must be checked for path, type, mode, object ID and declared size where the API provides it.
- Symlinks and submodules inside selected source paths are unsupported and cause an explicit failure; they are not followed or treated as ordinary files.

The provider does not need to download or recursively enumerate unrelated binary asset directories merely to construct the Site Content Adapter snapshot.

## 5. Deterministic source-file selection

The provider fetches only the source files required by the current Site Content Adapter and its audited route/configuration dependencies.

| Source path | Selection rule | Purpose |
|---|---|---|
| src/content/** | Every tracked Markdown file with .md suffix, case-insensitive | All Markdown collections and records |
| src/data/** | Every tracked .yaml and .yml file, case-insensitive | Site dictionaries |
| src/content.config.ts | Exact file; required | Astro content schema fingerprint |
| src/pages/** | Every tracked regular file under the directory | Astro route inventory and route source dependencies |
| astro.config.mjs | Exact file; required | Production site origin and Astro configuration inputs |
| src/lib/url.ts | Exact file when present | URL/route helper dependency |
| src/lib/nav.ts | Exact file when present | Navigation route dependency |
| src/lib/service.ts | Exact file when present | Support catalog route dependency |

The existing adapter currently requires src/content.config.ts and astro.config.mjs. Their absence is a hard failure. Every selected file present in the pinned tree is mandatory for that sync: a missing blob, inaccessible object, decoding/truncation error or hash mismatch is a hard failure. A selected directory that is genuinely empty in the pinned tree is not an incomplete listing.

All selected files are sorted by repository-relative POSIX path before the immutable snapshot is constructed. New Markdown collections, new Markdown records, new YAML dictionaries and new files under src/pages are discovered from the pinned tree; the provider does not maintain a fixed list of collection names.

The selection policy is versioned independently from the Git provider. If a future adapter revision requires additional source paths, the policy and its tests must be updated explicitly. Files outside the selected paths are not implicitly included.

The provider does not mass-download images, photographs, diagrams, PDFs, fonts, video, public assets, generated output, package caches, old-site migration material, compiled search indexes or unrelated documentation. It does not execute Astro, JavaScript or TypeScript. The existing adapter remains responsible for parsing the selected source bytes and applying draft/schema semantics.

## 6. Git blob integrity and content hashes

### 6.1. Repository object format

Git object IDs are calculated using the hash format of the repository. The provider must establish that format from authoritative provider/repository capability information or an explicit trusted configuration verified against the provider. It must not choose an algorithm merely from a provider brand or infer the format solely from an object ID's string length.

For a blob with raw bytes B, the canonical Git object hash is calculated over:
- the ASCII object header: blob, one space, the decimal byte length of B, followed by a NUL byte;
- then the exact unmodified bytes B;
- using the repository's Git object hash algorithm (for example SHA-1 or SHA-256).

The locally calculated object ID must exactly equal the blob object ID obtained from the pinned tree. The check is performed on raw bytes, before text decoding, newline conversion, Unicode normalization or parsing.

### 6.2. Separate content SHA-256

The raw content SHA-256 is also calculated and retained as content provenance. It is the SHA-256 digest of B itself, without the Git object header.

The two values have different meanings:
- Git blob object ID verifies that exact bytes correspond to the blob object in the pinned Git tree, using the repository object format.
- Raw content SHA-256 is a content digest for storage, deduplication and provenance independent of the Git object header.

A raw content SHA-256 must never be substituted for a Git blob object ID.

### 6.3. Current canonical-contract compatibility

The existing PinnedSiteSnapshot, SiteFileRevision and SiteSourceRevision implementation currently validates 40-character SHA-1 commit/tree/blob IDs, and the current adapter independently recomputes Git blob SHA-1. The audited Saturn repository uses this SHA-1 contract.

Therefore, Snapshot Provider contract v0.1 may return a snapshot only when the repository object format is SHA-1 and all current canonical validators can represent the IDs. If the provider identifies another Git object format, it must fail closed with an explicit unsupported-object-format error. It must not truncate, recast or mislabel the object ID.

Supporting a SHA-256 Git object-format repository later requires a separately versioned, provider-neutral evolution of the canonical contracts and adapter verification (including commit, tree and blob IDs and an explicit object-format field). That evolution is not part of this docs-only stage. This limitation is about the current canonical data model, not about GitHub versus Gitea.

## 7. PDF documents are part of the knowledge corpus

PDFs remain a full and mandatory part of the target AI Technical Consultant knowledge corpus under ADR-0012 and ADR-0013. Their absence from the ordinary Git snapshot is a separation of responsibilities, not an exclusion from the product.

The normal document path is:
1. Support Catalog Adapter discovers document/certificate metadata and direct PDF links from non-draft site content, including Markdown body links, and preserves all owning site records and source locators.
2. External Document Adapter fetches the exact catalogued PDF through the configured trusted HTTPS host/path policy.
3. The PDF extraction pipeline records the original URL, raw PDF bytes SHA-256, extraction state, parser version, physical page count and page-level evidence.
4. Extracted PDF passages become answer evidence; catalog metadata remains a separate document-lookup evidence type.

SnapshotProvider.fetch_snapshot() does not fetch PDFs, does not discover PDF links, does not parse PDFs and does not bulk-download Git assets. This does not relax the requirement to ingest and index the trusted PDFs through their designated adapters.

### 7.1. Future PDFs stored as Git blobs

The architecture must allow a future Support Catalog record to identify a PDF stored in the trusted Git repository using a pinned logical source ID, commit SHA, repository path and expected blob object ID.

In that case, a future External Document Adapter or dedicated Git-backed document source may request that exact blob through the same provider-neutral read-only Git object transport. Before returning bytes, it must establish that the path resolves to the expected blob in the specified commit's tree and independently verify the Git blob object hash and raw content SHA-256.

This is a selective, document-specific retrieval path. It is not part of the ordinary site snapshot file-selection set, does not trigger a bulk asset download, does not bypass Support Catalog ownership/provenance, and does not move PDF parsing into Snapshot Provider. It is an architectural extension point only; no Git-backed PDF retrieval is implemented in this stage.

## 8. Failure and atomicity semantics

A provider operation is successful only when all required steps complete for one pinned commit/tree.

The provider must fail the sync for at least the following conditions:
- branch ref cannot be resolved at the start;
- ref, commit or tree identities disagree;
- complete tree enumeration cannot be established;
- a tree response is truncated and no complete fallback traversal succeeds;
- a selected required file or blob cannot be retrieved;
- selected blob type/mode is unsupported;
- Git blob object hash does not match the expected tree object ID;
- repository object format is unknown or unsupported by the current canonical contract;
- raw bytes are truncated, malformed or exceed configured limits;
- mandatory adapter input files are absent.

No partial or empty fallback snapshot may be returned for these failures. A failed sync must not replace the previously active Knowledge Snapshot. Retryable network/rate-limit errors may be retried with bounded backoff and provider guidance such as Retry-After, always using the same pinned object IDs. Authentication, authorization, integrity and unsupported-format failures are not converted into successful empty results.

## 9. Security and resource controls

Both provider implementations must enforce:
- HTTPS with certificate validation;
- a preconfigured API origin and repository allowlist;
- read-only credentials with minimum required repository-read permissions;
- secrets supplied through the runtime secret mechanism and never written to source files, snapshots, citations or logs;
- no user-controlled URL, endpoint, repository locator, ref or path;
- redirect restrictions that do not permit leaving the configured trusted API origin;
- strict validation of repository-relative paths and Git tree entry types/modes;
- finite limits for tree entries, selected file count, per-file bytes, aggregate bytes, traversal depth, request concurrency, API calls and total operation time;
- bounded retries and explicit handling of API rate limits;
- no execution of fetched source code and no shell/clone fallback in the REST implementation.

Limits must be configurable, finite and covered by tests. Exact numeric defaults are an implementation-stage decision based on the measured source tree and provider behavior; exceeding any configured hard limit fails the sync.

## 10. Provider conformance and acceptance criteria

The first implementation is GitHub REST. A future Gitea REST implementation must pass the same provider-neutral contract suite.

The implementation is acceptable only when tests prove:
1. The configured physical remote maps to the stable logical source ID.
2. The configured main ref is resolved once and pinned to one commit/tree.
3. After pinning, all reads use immutable object IDs; a branch move during download does not cause a ref re-resolution or mixed-revision snapshot.
4. Commit/tree response identities are consistent, and all selected tree paths are enumerated completely.
5. Truncated recursive listings are rejected or replaced by a complete non-recursive traversal.
6. The deterministic path policy includes every required adapter input and excludes unrelated binary assets.
7. Every selected blob is fetched by its tree object ID and independently checked with the repository's canonical Git object hash algorithm.
8. Raw content SHA-256 is calculated separately and retained by canonical provenance.
9. Missing required files, missing blobs, incomplete trees, hash mismatches, unknown object formats and resource-limit violations fail closed.
10. The returned immutable PinnedSiteSnapshot is accepted by the existing pure/offline Site Content Adapter without provider-specific dependencies.
11. GitHub and future Gitea implementations produce equivalent snapshots for the same logical source revision and path-selection policy.
12. PDF corpus requirements remain satisfied through Support Catalog Adapter and External Document Adapter; no PDF ingestion is added to the normal site snapshot path.

## 11. Explicit exclusions of v0.1

This contract stage does not implement GitHub or Gitea providers, PDF discovery/fetching/parsing, Git-backed PDF retrieval, schema/adapter changes, retrieval integration, embeddings, reranking, LLM/provider calls, API/UI, deployment, scheduling or production operations.

Any change to existing canonical contracts must be separately described and approved before implementation. Saturn-Main-Site remains strictly READ-ONLY.
