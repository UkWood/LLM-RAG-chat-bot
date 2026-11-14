# Stage 3B — Trusted Source Ingestion Compatibility

Project: Saturn AI Technical Consultant (`UkWood/LLM-RAG-chat-bot`)
Branch: `fix/stage3b-inert-pdf-navigation-compatibility`
Status: **implementation in Draft PR #33, independent real-corpus Acceptance pending; NO MERGE**.

## Architecture decision (Session A, 2026-11-14)

Trusted `Saturn-Main-Site` and official PDF bytes are authoritative *source material*. A PDF must not be rejected merely because of an unfamiliar `/Link`, `/Border`, `/BS`, `/OpenAction`, `/URI`, `/Names`, `/AA`, `/Outlines` or form annotation. The earlier A/B/C strict navigation allowlist was superseded.

PDF navigation is **not** a RAG input. `external_pdf_worker.py` no longer traverses, executes, validates or emits navigation/action dictionaries. It extracts only `pypdf` text from the actual physical pages using `PdfReader(BytesIO(raw), strict=True)`. Embedded JavaScript, Launch, remote GoTo, URI and other actions are neither executed nor converted to evidence, retrieval sources or citations. Unsupported document syntax that `pypdf` itself cannot decode still fails closed with a parser diagnostic.

**Preserved protective controls:** the existing POSIX development subprocess, bounded PDF bytes, physical pages, per-page/total text, decoded per-page and total streams, CPU/RAM/wall-time, bounded parent stdout and child termination, encrypted-PDF rejection, and atomic no-partial-publication behavior. No navigation-specific annotation budget remains on the extraction path. The subprocess is **not a production OS sandbox**.

### PDF revision and provenance

`PARSER_VERSION = "saturn-pdf-pypdf-6.10.0/0.3.0"`. The External Document Adapter keys immutable revision identity by original document ID, original URL, source-byte SHA-256 and parser version, so the `0.2.0` cache cannot masquerade as a `0.3.0` extraction. Physical page provenance is retained; no original PDF data or URLs are modified.

## Change B — Support Catalog metadata variants

`CATALOG_VERSION = "saturn-support-catalog/0.2.0"`.

If one canonical document URL appears with different `title` or `kind` values across trusted pages, the catalog preserves **all original** `CatalogOccurrence` records and their source paths, field paths, owner associations, revisions and raw URLs. It emits `conflicting_document_metadata` with severity **warning**, not a blocking error. Presentation title/kind use a deterministic sorted selection, not an exclusive source claim.

Ambiguous `version` and `date` remain **errors**; malformed URLs, missing source revisions/owners and invalid upstream structures remain blocking. No document ID, canonical URL or provenance algorithm is rewritten. The existing Stage 4B single-document search record includes all source-declared title/kind variants from `DocumentMatch.occurrences`; no duplicate PDF, document or synthetic evidence is created.

Stage 4A independently reconstructs and validates the declared catalog policy version. The historical synthetic Stage 5E fixture explicitly uses catalog `0.1.0` and PDF parser `0.1.0`, preserving old semantics and byte-for-byte frozen calibration identity; production defaults are `0.2.0` and `0.3.0`. No frozen calibration artifacts were changed.

## Verification

GitHub Actions under Python 3.12 / locked `pypdf==6.10.0` must pass `offline-checks`, `onnx-contracts`, `saturn-evaluator-targeted`, and `saturn-calibration` on the **exact final PR head**. The offline suite includes PDF compatibility cases (A/B/C, normal destinations, inert active actions, >64/page and >256/document annotations), resource/security rejection cases, document/owner/URL provenance, catalog title/kind/version/date conflict cases, Stage 4A/4B/5A–5E, and frozen calibration reproduction.

## Real Linux/WSL2 acceptance (not yet demonstrated by CI)

Run the read-only `backend/tests/manual/verify_stage3b_real_pdfs.py` against four independently SHA-verified original PDFs, expected physical pages 65/39/83/69. Then run `backend/tests/manual/verify_stage3b_real_adapter.py` with the actual Saturn-Main-Site pinned Git snapshot (commit `084d759487bfab6e111549c9b5469711ac5fc13e`, tree `a5297822bf3a5e071b10cc1dca553481c1b84d47`). The **unfiltered** catalog should report 229 PDF candidates, 11 known descriptive title/kind conflicts as warnings, and no errors, subject to any additional real diagnostics. Four-document extraction must use only exact real catalog URLs and locally SHA-verified original bytes through real `adapt_external_documents()` and the real subprocess extractor.

Report **separately** global catalog readiness/issue counts, selected four-document adapter readiness and full-corpus extraction readiness. No scoped projection may delete or suppress catalog issues. An absent real document is `UNCOVERED`, never fabricated.

The successful four-PDF acceptance does **not** prove extraction of the full 229-document corpus. Full Stage 5F belongs to experimental PR #32 **only after** independent Acceptance, explicit authorization and merge of this Stage 3B correction into main.

**STRICTLY READ ONLY site and original PDFs. No PR #32 changes. No Merge. No Stage 6.**
