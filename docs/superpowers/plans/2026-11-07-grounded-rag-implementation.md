# Grounded RAG and publication updates — implementation plan

> For agentic workers: use superpowers:executing-plans, inline method inherited. Owner explicitly requested applying the discussed design; implement without another plan/method approval. Existing checkout only, no worktrees. One final independent whole-branch review.

**Goal:** ordinary question → existing hybrid/reranker → ready API LLM → checked complete/partial answer with backend citations and support questions; daily/manual updates of published text and linked PDFs.
**Architecture:** immutable generic publication snapshots and live eligibility policy adapt to existing search primitives without weakening synthetic contracts. Bounded generation and verification use an interchangeable OpenAI-compatible client; a separate updater publishes checked sources atomically.
**Tech:** Python3.12, stdlib HTTP/HTML/SQLite-or-JSON persistence/file locking, existing pypdf/Qdrant/ONNX dependencies; no new model training/framework/dependency.
**Spec:** [accepted design](../specs/2026-11-07-grounded-rag-redesign-design.md), including owner automatic-update/daily/manual/taxonomy-independent and ready-model clarifications.

## Global constraints

- Saturn-Main-Site strictly read-only; published HTML/PDF only, not development repository/drafts. No deployment/merge automatically.
- Source scope/provenance remains explicit; admit new versions by owner-authorized automatic policy, not invented per-version manual approvals. External PDFs require trusted-page link and permitted public destination; no arbitrary chat URLs.
- Legacy synthetic snapshot/provider/grounding contracts and consumed benchmarks stay unchanged; explicit new CLI path, no reuse of V3 code/datasets as tuning.
- Ready LLM only, model/base/key configuration; API credentials never in logs/Git/chat. No real model-quality claim from mocks. First candidate experiment model ID supplied by owner: deepseek-v4.1-flash-1017, endpoint/key still needed.
- Max4000question chars, search40/channel, pool30, rerank30, context5chunks/8000chars; one generation+one verification, no self-rewrite loop.
- Partial verified claims survive other gaps/revocations; unsupported facts never become negative capability assertions. Backend adds concrete questions plus «Для уточнения свяжитесь с поддержкой компании».
- Automatic once per24hours + operator force command; serialized jobs; current policy rejects deleted/replaced versions during refresh/in-flight responses. Never publish partial failed index build.
- First scope CLI; systemd daily timer artifact, not installed/running in this workspace. No invented admin web API/UI.

## Review focus

- Malicious source links/redirects and PDF parser isolation cannot expose local/private files or secrets.
- A true quote from another entity or a wrong unit/condition cannot be treated as proof merely because it exists.
- Daily edit/delete/replacement, failed refresh and in-flight generation must not silently serve revoked versions.
- Malformed/partial model JSON and provider errors must stay errors, not successful lack-of-evidence responses.
- Taxonomy/field names and punctuation cannot become hidden prerequisites to retrieval; human evaluation remains distinct from self-verification.

## Files/interfaces

publication/policy.py: PublicationPolicy(site_root,pdf_origins,...); checked public URLs and scope identity.
publication/extract.py + pdf_worker.py: PublishedSource.from_bytes(url,content,media_type,...) → canonical text/pages, exact raw hash; HTML main text independent of frontmatter and OS-isolated PDF extraction.
publication/snapshot.py: PublishedSnapshot(sources,policy_revision) with immutable IndexedChunks, validated identity; PublishedCatalog/current eligibility interface.
retrieval/validation.py + existing lexical/dense/service/contracts: dispatch accepted snapshot types, preserving old validation and search behavior.
publication/store.py + refresh.py + fetch.py: PublicationStore.capture()/eligible()/status(), atomic blob/manifest/state persistence, serialized refresh(policy,store,fetcher,force=False), controlled crawler.
rag/contracts.py + provider.py: immutable draft/verified response records, configured OpenAICompatibleClient.complete(system,user)->dict.
rag/application.py + __main__.py: Consultant.answer(question), schema/quote/value checks, verification and backend rendering, CLI.
evaluation/rag_diagnostic.py: diagnostic fixture loading, separate retrieval/oracle/end-to-end modes; human-review recording, model-quality NOT_RUN without configured runtime.
config/publication-policy.example.json, .env.example, deploy/refresh.service+timer, tests, docs/current status.

## Task1 — accepted direction and generic publication ingestion

- [x] Mark design/ADR accepted for bounded implementation; retain pending runtime inputs and historical quality failures. Commit accepted spec+plan.
- [x] RED unit tests: HTML content with changed category keys/nav/quotes still yields same technical text, safe source scope, source receipts, PDF isolation failure quarantines. Expected missing publication module/failing assertions.
- [x] Implement PublicationPolicy URL scope, bounded HTML/PDF parsing and PublishedSnapshot. Preserve original bytes/hashes/canonical metadata; generic entity identity derives from source, not product taxonomy.
- [x] RED generic snapshot adapters and legacy-invalid snapshot cases; add validation dispatch to existing indexes/service and plain passage representation. GREEN focused publication+retrieval contracts; commit.

## Task2 — durable refresh and daily/manual operation

- [x] RED tests edit/add/delete, PDF same-URL replacement/link removal, redirect/private target, failed fetch distinct from delete, two concurrent jobs, failed index promotion, stale/active-policy semantics.
- [x] Implement bounded HTTPS fetcher with validated redirects and configured public source origins; updater crawler and durable atomic store. Save version blobs/manifest outside Git; current deny policy separate from active snapshot; protect paths/hashes on load.
- [x] Implement due/force/status operator CLI and daily systemd example with explicit timezone/configuration. Filesystem/operator access is admin boundary; no public refresh endpoint. No service installation.
- [x] GREEN unit+integration refresh scenarios, one actual PDF sandbox capability probe; commit. If sandbox unavailable, PDFs quarantine with explicit status, never pretend parsed.

## Task3 — generic ready-model provider

- [x] RED local mock HTTP tests: configured model/path/auth, no redirects/credential leak, timeout/429/5xx, truncated/duplicate/malformed JSON, invalid config, bounded outputs.
- [x] Implement strict OpenAI-compatible chat client (existing HTTP dependency or stdlib), independent of retrieval and no provider/model hardcode. Documentation from actual provider before live integration; key only env.
- [x] GREEN mock provider contracts; .env.example with placeholders and model chosen only via configuration; commit.

## Task4 — ordinary RAG with partial grounded responses

- [ ] RED tests: original natural question reaches search unchanged; two supported facts plus missing fact gives partial with support question; none supported gives no factual answer; malformed model output stays error; invented quote/number/citation rejected; source revoked during generation removes only dependent claims; all-source revoke produces support outcome; provider policy boundary.
- [ ] Implement one captured search/rerank, bounded evidence, generation draft with exact quote pointers, deterministic checks, one semantic verification pass, final current-policy checks and backend-only citations/contact rendering. JSON values/IDs/cardinality are strictly validated; self-verification is not a truth guarantee.
- [ ] CLI configured provider + local bundles, explicit trusted-operator public-question/cloud flags before remote calls. No raw-question logs/history-as-evidence; unchanged legacy entrypoints.
- [ ] GREEN focused tests and CLI mocks; commit.

## Task5 — small diagnostic and usable operator documentation

- [ ] Author15new exposed diagnostic questions (5full/4partial/3missing/2ambiguous/1conflict) and synthetic ordinary-text fixtures, before any model tuning; expected facts/gaps/evidence are human-reviewable, no intent schema.
- [ ] Add retrieval-only, oracle-context+generator/checker, full-path runs. Record IDs/metrics/source/model identities; no raw production logs. Human grading separate from model self-check; real quality NOT_RUN if endpoint/key is absent.
- [ ] Run configured real-provider compatibility smoke with a public synthetic prompt only if owner-supplied runtime is ready; then diagnostic only within actual admitted scope. If missing, persist concrete blocker and complete independent code/tests without another surrogate planner.
- [ ] Operator docs cover source scope, daily/manual command, model API settings, PDF/OCR/size limits and quarantine, last-success/staleness, actual deployment not started. Add meaningful full-flow tests; commit.

## Task6 — one final review, verification and publication

- [ ] One fresh whole-branch reviewer; re-grade findings; one Critical/Important fix pass RED→GREEN, minor limitations disclosed. No repeated reviewer loop.
- [ ] Run final base+ONNX verify_offline once per final source; repeat only after relevant failures/changes. Docs checker+whitespace check. Old quality reports remain immutable.
- [ ] Update ADR/status/handoff/stage/README with actual code, tests, live-call/diagnostic results or explicit NOT_RUN blocker. Update existing PR13 title/body around final implementation (avoid another docs/implementation PR cycle), push and verify exact-head offline/ONNX CI. No automatic merge/deploy.

Self-review: tasks1→2 share PublishedSource/PublishedSnapshot/store eligibility; tasks1→4 use existing IndexSet/RetrievalService with strict snapshot dispatch; tasks3→4 share complete(system,user)->dict; task5 uses the same application and separately injected oracle context. Scope is one first CLI implementation with three independently testable components, not a production migration. New real-policy pathway is explicit and does not weaken legacy synthetic validation.


Checkpoint2026-11-07: Tasks1–3 implemented/targeted GREEN. Task4 core application and smoke command GREEN, full runtime/ask CLI incomplete. Tasks5–6 not done. Owner requested environment transition after configuring future runtime key/variables; continue from [handoff](../../handoffs/2026-11-07-grounded-rag-environment.md), no repeated design/method approval. No live API/model-quality measurement yet.
