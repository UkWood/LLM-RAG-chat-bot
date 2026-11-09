# Snapshot Provider Contract — architecture decision

Date: 2026-11-09  
Status: **PR #21 OPEN; CI SUCCESS; documentation-only architecture change**  
Repository: UkWood/LLM-RAG-chat-bot  
Base: main at c1840b071e077ae6019f1b9e7930c3aa15d08ef3  
PR: https://github.com/UkWood/LLM-RAG-chat-bot/pull/21  
Branch: docs-snapshot-provider-contract-2026-11-09

## Scope

Document the owner-approved provider-neutral Snapshot Provider contract after the Saturn Site Content Adapter merge (PR #20).

This stage covers architecture and documentation only. It does not implement a GitHub/Gitea provider, PDF ingestion, Git-backed PDF retrieval, or any runtime integration.

## Owner-approved decisions

- Git REST API is the primary transport.
- GitHub REST API is the first provider implementation; Gitea REST API is a later implementation of the same provider-neutral contract.
- The trusted logical source ID remains UkWood/Saturn-Main-Site on branch main. Physical remote/provider details are mapped through trusted configuration and do not enter the canonical adapter boundary.
- The provider resolves refs/heads/main once, pins the returned commit and tree, and performs all subsequent reads by immutable object IDs. It does not re-resolve or recheck the moving branch during that sync.
- The Git provider is trusted for ref → commit → tree identity mapping. Commit/tree identity consistency and complete tree enumeration are required, but no independent cryptographic verification of raw commit/tree objects is claimed.
- Each selected blob is independently verified against the canonical Git blob object hash using the repository object format. Raw content SHA-256 is stored separately.
- The current canonical snapshot/adapter implementation supports SHA-1 object IDs. Other formats fail closed until a separately approved canonical-contract and adapter evolution.
- Only Markdown collections, YAML dictionaries, content schema, Astro routes and audited route/configuration dependencies are selected. Unrelated binary assets are not bulk-downloaded.
- GitHub recursive truncation and Gitea pagination are handled according to provider-specific semantics. Gitea pages must be fully collected and cross-checked against page, tree SHA and total_count; direct tree-SHA lookup is version-tested, with recursive pinned-commit pagination as the safe fallback.
- Under src/pages/, only `.astro` and `.ts` route-source files (excluding `.d.ts`) are selected. Unknown file types are reported as route-source drift and fail closed rather than being downloaded or silently skipped. The audited source baseline is 23 files: 19 `.astro`, 4 `.ts`.
- Any incomplete tree, truncation/pagination inconsistency without a complete fallback, missing required file/blob, hash mismatch, unsupported object mode/format or hard-limit violation fails the sync.
- HTTPS, trusted endpoint allowlists, read-only credentials, secret protection and finite resource limits are mandatory.
- Provider-specific GitHub/Gitea behavior stays behind the provider boundary. The Site Content Adapter and canonical contracts do not depend on the Git service.

## PDF boundary

PDF remains a full and mandatory part of the AI Technical Consultant knowledge corpus under ADR-0012 and ADR-0013.

The ordinary site snapshot does not fetch PDFs. Support Catalog Adapter discovers and catalogues trusted document references and owners; External Document Adapter fetches and extracts PDF content and page-level evidence.

The design reserves a future selective Git-blob retrieval path when a PDF is stored in Git/Gitea and its exact logical source ID, commit, path and blob SHA are available. Such retrieval must prove path/blob membership in the pinned commit and independently verify the blob hash and raw content SHA-256. It remains outside the ordinary site snapshot and is not implemented here.

## Documents

- Provider contract: docs/site-specific/v0.2/05-snapshot-provider-contract.md
- ADR-0014: docs/decisions/0014-snapshot-provider-contract.md
- Existing source trust and PDF requirements: ADR-0012 and ADR-0013
- Existing adapter contract and implementation: backend/src/saturn_ai/ingestion/saturn_contracts.py and backend/src/saturn_ai/ingestion/saturn_site_adapter.py

## Verification and exclusions

This is a documentation-only architecture stage. No source code, dependencies, tests, runtime configuration, credentials, source website files or deployment settings are changed.

PR #21 is open and not merged.

Current PR head: `0f2a1226b757ae346d65b05df13be657e3581d35`.

- PR-head run [#42624653260](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624653260): **SUCCESS**.
- Matching push run [#42624644980](https://github.com/UkWood/LLM-RAG-chat-bot/actions/runs/42624644980): **SUCCESS**.
- Both runs completed jobs `offline-checks` and `onnx-contracts` successfully on the exact current PR head.

The current documentation revision has therefore passed both required CI workflows. No provider implementation or PDF ingestion is authorized by this stage.
