# Authored synthetic evaluation corpus v1

Ten fictional documents: eight Markdown cards/articles/table/system descriptions and two three-page English PDF manuals. All EDU designations, values and approvals are authored test material, not Saturn products or owner approval of real documents. Commit bbbb… is a synthetic identity. URLs example.invalid are inert; 192.0.2.42 is a documentation-only address.

The registry pins source bytes and explicit local scopes. The two small PDFs are original source fixtures, not scraped company files, corpus extracts or index dumps. `manuals.json` records their authored pages; `scripts/generate_synthetic_pdfs.py` reproduces the bytes using locked pypdf. It does not change registry hashes or evaluation labels. Regenerate PDFs deliberately and update hashes/revisions in a reviewed change if pages change.

All ten documents have positive evidence labels in evaluation/datasets/synthetic-v1.json. The troubleshooting article includes an untrusted instruction inside a code block for a document-injection case; the relevant supported diagnostic fact is separate. The snapshot/dataset preflight validates label support, not an LLM's resistance to arbitrary injection.

PDF text is English/ASCII with Russian questions elsewhere in the corpus; these fixtures do not evaluate Cyrillic PDF extraction, OCR or complex PDF tables. Markdown includes a units table. Negative cases include missing facts, invented variants, out-of-domain queries and two typo cases requiring clarification.
