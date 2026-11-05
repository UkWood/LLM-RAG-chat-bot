# Offline ingestion fixtures

Authored fictional teaching cards only. DEMO-300, DEMO-SOFT and the category are not Saturn products. The all-`a` commit is a synthetic identity, never a real site commit. Approval provenance explicitly says synthetic-test-author-not-owner; it does not approve any real document.

`registry.json` uses registry v1 with `registry_status=synthetic_test_only`. The runner rejects approved real source IDs and external URLs, skips denied entries before reading bytes, and never downloads candidate document links. The linked manual stays pending; PDF tests generate their own small text PDFs in memory with a separate exact-hash record.

Only source schema observations (not site content) inform these examples. No site files, real PDF bytes, persistent indexes or corpus dumps are included. Ingestion output is separate from M1 evidence; arbitrary extracted prose is not considered a grounded answer.
