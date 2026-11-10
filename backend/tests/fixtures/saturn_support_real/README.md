# Exact source-derived Saturn Support Catalog fixtures

All eight files under this directory are **unmodified bytes** copied via read-only GitHub Git API from `UkWood/Saturn-Main-Site`, commit `084d759487bfab6e111549c9b5469711ac5fc13e`, tree `a5297822bf3a5e071b10cc1dca553481c1b84d47` (2026-11-10). The Git blob SHA-1s were verified at import time and are independently asserted in `test_cr03_exact_source_derived_fixture_integration`.

| Source path | Exact Git blob SHA-1 |
|---|---|
| `src/content/products/fps.md` | `4bf3c1de3bca10ec4d9203f789a602f878d83ab1` |
| `src/content/products/bsk-69.md` | `c1db8a1733db672b66d8da272fdec63eacd08cf4` |
| `src/content/products/archtool.md` | `a05995ce25bc27762dae307da0490e9cad053f5d` |
| `src/content/pages/spisok-podderzhivaemogo-oborudovaniya.md` | `1106958ac9a3fe175c531fe7a49fd65a122f40d3` |
| `astro.config.mjs` | `58b013ab2bc00eb5718ee036ab351354d06d84da` |
| `src/content.config.ts` | `2eaa0913798b9301314e9bdcbeb2b8318417ae13` |
| `src/pages/products/[slug].astro` | `a3c47da9d6a35583a2fd6284aabf5ff9993a9555` |
| `src/pages/[slug].astro` | `48ddec0a5b3acae61146d7a3dbf50a7361d745e4` |

The two route source files and Astro configuration are exact upstream fixtures, **not executed**, and provide the adapter's canonical URL provenance. This is deliberately a curated, partial `PinnedSiteSnapshot` for an offline integration test, not a complete source checkout or production sync. The test confirms documents, PDF candidates, owner linkage, IDs, revisions, line/field locators and absence of network calls. No PDFs, binaries, user data, model files or site mutation are involved.
