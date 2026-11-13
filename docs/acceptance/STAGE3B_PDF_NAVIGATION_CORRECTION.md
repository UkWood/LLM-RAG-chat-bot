# Stage 3B — Strict Inert PDF Navigation Compatibility Correction

Project: Saturn AI Technical Consultant (`UkWood/LLM-RAG-chat-bot`)
Baseline: `84d783331cc755e688a7f8637be13c297c07f43e`
Branch: `fix/stage3b-inert-pdf-navigation-compatibility`
Status: **implementation candidate, independent Acceptance pending; no merge authorization**.

## Architectural input

Session A accepted the separate real VA-01R value audit (2026-11-14): 3/3 `AUDITED`, 0 findings/errors, 187 physical pages, 215 `/Link` annotations, 213 `/Dest`, 2 `/URI`, 2 `/OpenAction`, all `/XYZ`. The value audit is the source for the *exact* allowlists below. The audit itself is not reproduced by synthetic fixtures.

## Navigation validation

Only these **exact field sets** are accepted. Object type checks use pypdf's concrete types rather than Python numeric duck-typing:

- **A**: `/BS`, `/Dest`, `/F`, `/Rect`, `/StructParent`, `/Subtype`; subtype `/Link`; `/BS` exactly `{/W: NumberObject(0)}`; `/F` exactly `NumberObject(4)`; `/StructParent` `NumberObject` in `[0, 2147483647]`.
- **B**: `/Border`, `/Dest`, `/Rect`, `/Subtype`, `/Type`; `/Type /Annot`, `/Subtype /Link`; `/Border` exactly `[NumberObject(0), NumberObject(0), NumberObject(0)]`.
- **C**: `/A`, `/Border`, `/Rect`, `/Subtype`, `/Type`; identical type/subtype/border constraints; `/A` exactly `{/Type /Action, /S /URI, /URI TextStringObject}`; URI text max 2048 UTF-8 bytes, absolute `http(s)` URL with valid hostname, no credentials, fragment or control characters. URI is not dereferenced or emitted.

`/Rect` is four finite numbers (NumberObject/FloatObject) with correct coordinate ordering. `/Dest` is only `[same-document indirect page reference, /XYZ, left, top, NumberObject(0)]`. `left` and `top` are null or finite numeric values in `[-1000000,1000000]`. `/OpenAction` is only this destination array. Page membership is validated against the same PdfReader's actual physical page indirect references without navigation. Unsupported keys/actions are rejected fail-closed. This does not introduce named destinations, outline extraction, remote GoTo, attachments, multimedia, or navigation-derived evidence.

Budgets, separate from and not increasing existing worker limits: 256 annotations/document; 64/page; 4096 navigation object visits; 4 consecutive indirect hops; depth 6; 16 dictionary keys; 64 array elements; 2048 URI bytes. Reject on limit violations. Worker continues to use `PdfReader(BytesIO(raw), strict=True)` with PDF/resource controls, and validates all navigation before extracting page text. POSIX subprocess isolation is **development-only, not an OS sandbox**.

## Parser identity / cache

`PARSER_VERSION = "saturn-pdf-pypdf-6.10.0/0.2.0"` in `external_document_extractor.py`. The existing adapter's immutable revision key includes the parser version and source bytes SHA-256; a changed parser identity therefore requires a new extraction even when PDF bytes are identical. Synthetic adapter regression included; no change to hash algorithm, physical-page provenance, source URL or owner attribution.

## Validation and acceptance matrix

- Local Python 3.13.5 / pypdf 5.9.0: Stage3B PN-01..10 and NN-01..24 plus additional subprocess scenarios. See `local-stage3b-navigation.log`. This is a *compatibility preflight* only.
- **Still mandatory:** `PYTHONPATH=backend/src python -m unittest discover -s backend/tests -v` and `python scripts/verify_offline.py` under Python 3.12 and **locked** `pypdf==6.10.0`; External Document Adapter/transport/subprocess and Stage 4A–5E regressions; GitHub Actions SUCCESS on exact PR head.
- **Still mandatory:** four original PDFs on the authorized Linux/WSL2 stand, verified against exact pinned bytes SHA-256, page counts 65/39/83/69, full standard Stage3B pipeline and provenance. `backend/tests/manual/verify_stage3b_real_pdfs.py` is a read-only worker-only preflight and **does not replace** the full pipeline proof or Session A review.
- Stage 5F is explicitly deferred to PR #32 after this correction passes Acceptance, is authorized to merge, is merged to `main`, and is integrated there. No PR #32 changes are part of this correction.

## Unresolved constraints

The final acceptance gate cannot be claimed without on-stand bytes and pinned environment. Any unexpected real PDF navigation structure requires a new Session A decision; do not relax allowlists or budgets. No merge or Stage 6 is authorized.
