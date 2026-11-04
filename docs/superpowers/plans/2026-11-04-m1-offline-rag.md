# M1 offline RAG — implementation plan

> Execution: superpowers:executing-plans; implementation in this isolated checkout.

**Goal:** synthetic-only CPU/offline ingestion → in-memory retrieval → fake claims → validated citations/refusal.
**Architecture:** immutable typed records; explicit test-only manifest with exact byte hashes; exact entity + supported intent gate; extractive claim validation. Backend owns citation metadata.
**Tech stack:** Python 3.12 standard library and unittest; no runtime dependencies or network.
**Spec:** [architecture](../specs/2026-11-03-ai-consultant-design.md), milestone 1 of [roadmap](2026-11-03-ai-consultant-roadmap.md).

## Scope and decisions

The owner's 2026-11-04 instruction explicitly authorizes continuing synthetic M1. It does not approve the entire proposed production architecture or real source registry. No new architecture choice requiring owner input is necessary for this bounded milestone.

Use dataclasses with runtime validation for this dependency-free slice; production Pydantic/API contracts remain future work. Corpus fixtures are authored fictional examples, never Saturn specifications or production corpus dumps. Markdown sections represent one complete fact each; supported intents are interfaces and manual lookup only. Conservative exact designation matching and explicit aspect matching avoid a similarity threshold presented as confidence. No semantic retrieval claims.

## Global constraints

- Synthetic/test_only, local-only and FakeLLMProvider only; no cloud capability.
- PUBLIC + approved + hash match + local_index/local_generate required even for fixtures.
- INTERNAL/UNKNOWN/pending/revoked fail closed. Recheck policy before provider and result.
- No frontend, models, PDF downloader, services, Qdrant or modifications to Saturn-Main-Site.

## Review focus

Hash drift and manifest path escape; unsupported aspect with known device; invented/ambiguous designation; forged claim with valid chunk ID; policy revocation during generation.

### Task 1: vertical slice

Files: backend/src/saturn_ai/{domain,knowledge,providers,application,__main__}.py; backend/tests/integration/test_vertical_slice.py; fixtures/synthetic/.
Interfaces: load_snapshot(Path) -> Snapshot; Consultant(snapshot, provider).answer(str) -> AnswerResult; FakeLLMProvider.generate(GenerationRequest) -> tuple[Claim, ...].

- [x] Write integration tests for fact/source provenance, document lookup, absent evidence, invented entity, user/document injection, INTERNAL isolation, hash/path rejection, forged claims, unsupported aspect, ambiguity, revocation and provider failure.
- [x] Run PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v; observe missing implementation.
- [x] Implement strict synthetic loader, immutable in-memory index, deterministic gate, fake provider, extractive claim validation and backend citations.
- [x] Repeat tests; inspect CLI JSON for one answer and one refusal; commit code/tests/fixtures.

### Task 2: CI and durable handoff

Files: .github/workflows/ci.yml, README.md, docs/{PROJECT_STATUS,HANDOFF}.md, docs/stages/2026-11-04-m1-offline-rag.md.

- [x] Add backend unittest command to existing CI; preserve previous checks.
- [x] Update status, decisions, limitations and exact verification commands; review diff.
- [ ] Push feature branch, create PR, inspect actual Actions results; record PR and CI evidence.
