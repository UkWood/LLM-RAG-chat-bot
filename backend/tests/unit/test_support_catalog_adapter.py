"""Offline/contract tests for the independent Saturn Support Catalog Adapter."""
import dataclasses
import unittest
from pathlib import Path

from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot, adapt_snapshot, git_blob_sha1,
)
from saturn_ai.ingestion.support_catalog_adapter import (
    adapt_support_catalog, _markdown_links, _resolve_url,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "saturn_site"
SOURCE_COMMIT = "084d759487bfab6e111549c9b5469711ac5fc13e"
ORIGIN = "https://www.mnppsaturn.ru"
PRODUCT = "src/content/products/catalog-a.md"
SECOND = "src/content/products/catalog-b.md"
SYSTEM = "src/content/systems/catalog-system.md"


def files():
    result = {}
    for path in FIXTURE.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            result[path.relative_to(FIXTURE).as_posix()] = (git_blob_sha1(raw), raw)
    return result


def put(mapping, path, text):
    raw = text.encode("utf-8")
    mapping[path] = (git_blob_sha1(raw), raw)


def source(title="Catalog A", fields="", body="Body.", draft=False):
    return "---\ntitle: " + title + "\n" + ("draft: true\n" if draft else "") + fields + "---\n" + body + "\n"


def doc(title="A guide", kind="manual", url="/ftp/guide.pdf", version=None, date=None):
    extra = (", version: " + version if version else "") + (", date: " + date if date else "")
    return '{ title: "' + title + '", kind: ' + kind + ', url: "' + url + '"' + extra + " }"


def catalog(additions=None, removed=(), commit="a"*40):
    mapping = files()
    for path in removed:
        mapping.pop(path, None)
    for path, text in (additions or {}).items():
        put(mapping, path, text)
    snapshot = PinnedSiteSnapshot.from_mapping(
        commit_sha=commit, tree_sha="c"*40, files=mapping,
    )
    return adapt_support_catalog(adapt_snapshot(snapshot))


class SupportCatalogTests(unittest.TestCase):
    def test_product_documents(self):
        result = catalog({PRODUCT: source(fields="documents:\n  - " + doc(version="v2", date="2026-10-01") + "\n")})
        self.assertTrue(result.ready_for_promotion)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(len(result.pdf_candidates), 1)
        item = result.documents[0]
        self.assertEqual(item.title, "A guide")
        self.assertEqual(item.kind, "manual")
        self.assertEqual(item.version, "v2")
        self.assertEqual(item.date, "2026-10-01")
        self.assertTrue(item.url.endswith("/ftp/guide.pdf"))
        self.assertEqual(len(item.owner_entity_ids), 1)
        self.assertEqual(len(item.source_locators), 1)
        self.assertEqual(result.occurrences[0].field_path, "documents[0]")

    def test_system_documents(self):
        result = catalog({SYSTEM: source("Catalog system", "documents:\n - " + doc() + "\n")})
        self.assertEqual(len(result.documents), 1)
        self.assertIn("/systems/", result.occurrences[0].source_path)

    def test_product_certificates_and_scans(self):
        result = catalog({PRODUCT: source(fields="certificates:\n - " + doc("Approval", "certificate", "/ftp/approval.pdf") + '\n - { kind: scan, image: "/photos/scan.jpg" }\n')})
        self.assertEqual(len(result.documents), 2)
        self.assertEqual(len(result.pdf_candidates), 1)
        scan = next(x for x in result.documents if x.kind == "scan")
        self.assertEqual(scan.title, "scan.jpg")
        self.assertEqual(next(x for x in result.occurrences if x.kind == "scan").title, None)

    def test_markdown_inline_reference_and_html_links(self):
        body = ('# Downloads\n[One](/ftp/one.pdf)\n'
                '[Two][manual]\n[Three][]\n[shortcut]\n'
                '[manual]: /ftp/two.pdf\n[Three]: /ftp/three.pdf\n'
                '[shortcut]: /ftp/four.pdf\n'
                '<a class="doc" href="/ftp/five.PDF?q=1#page=3">Five</a>\n')
        result = catalog({PRODUCT: source(body=body)})
        self.assertEqual(len(result.pdf_candidates), 5)
        self.assertTrue(all(x.field_path.startswith("body:line=") for x in result.occurrences))
        self.assertTrue(all("heading=" in x.field_path for x in result.occurrences))
        self.assertTrue(result.ready_for_promotion)

    def test_markdown_all_non_draft_collections_including_unknown(self):
        additions = {
            "src/content/labs/catalog-lab.md": source("Lab", body="[Lab](/ftp/lab.pdf)"),
            "src/content/articles/catalog-article.md": source("Article", body="[A](/ftp/a.pdf)"),
            "src/content/news/catalog-news.md": source("News", body="[N](/ftp/n.pdf)"),
            "src/content/pages/catalog-page.md": source("Page", body="[P](/ftp/p.pdf)"),
            PRODUCT: source(body="[D](/ftp/d.pdf)"),
            SYSTEM: source("System", body="[S](/ftp/s.pdf)"),
        }
        result = catalog(additions)
        self.assertEqual(len(result.pdf_candidates), 6)
        self.assertEqual(len({x.owner_entity_id for x in result.occurrences}), 6)

    def test_draft_is_excluded_from_all_channels(self):
        result = catalog({PRODUCT: source(fields="documents:\n - " + doc() + "\n", body="[A](/ftp/a.pdf)", draft=True)})
        self.assertEqual(result.documents, ())
        self.assertEqual(result.pdf_candidates, ())

    def test_dedup_multiple_owners_and_provenance(self):
        block = "documents:\n - " + doc() + "\n"
        result = catalog({
            PRODUCT: source(fields=block, body="[Link](/ftp/guide.pdf)"),
            SECOND: source("Catalog B", fields=block),
            SYSTEM: source("Catalog System", fields=block),
        })
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(len(result.pdf_candidates), 1)
        self.assertEqual(len(result.documents[0].owner_entity_ids), 3)
        self.assertEqual(len(result.documents[0].source_locators), 4)
        self.assertEqual(len(result.occurrences), 4)
        self.assertEqual(len(set(result.documents[0].source_locators)), 4)
        self.assertEqual(len(result.pdf_candidates[0].source_revision_ids), 3)

    def test_conflicting_metadata_is_visible_and_blocks_promotion(self):
        result = catalog({
            PRODUCT: source(fields="documents:\n - " + doc(title="First", version="v1") + "\n"),
            SECOND: source("Catalog B", fields="documents:\n - " + doc(title="Second", version="v2") + "\n"),
        })
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(len(result.occurrences), 2)
        self.assertFalse(result.ready_for_promotion)
        self.assertGreaterEqual(len([x for x in result.issues if x.code == "conflicting_document_metadata"]), 2)
        self.assertEqual({x.title for x in result.occurrences}, {"First", "Second"})
        self.assertEqual({x.version for x in result.occurrences}, {"v1", "v2"})

    def test_absolute_root_and_relative_links(self):
        result = catalog({PRODUCT: source(
            fields="documents:\n - " + doc(url="https://WWW.MNPPSATURN.RU:443/ftp/guide.pdf#page=5") + "\n",
            body="[Relative](guide2.pdf)\n",
        )})
        self.assertEqual(len(result.pdf_candidates), 2)
        urls = {x.url for x in result.documents}
        self.assertIn(ORIGIN + "/ftp/guide.pdf", urls)
        self.assertIn(ORIGIN + "/products/catalog-a/guide2.pdf", urls)

    def test_percent_query_fragment_identity(self):
        result = catalog({PRODUCT: source(body=
            "[A](/ftp/re%20A.PDF?download=1#page=1)\n"
            "[B](/ftp/re%20A.PDF?download=1#page=2)\n"
            "[C](/ftp/re%20A.PDF?download=2)\n")})
        self.assertEqual(len(result.documents), 2)
        self.assertEqual(len(result.pdf_candidates), 2)
        self.assertEqual(len(result.occurrences), 3)
        first = next(x for x in result.pdf_candidates if "download=1" in x.resolved_url)
        self.assertEqual(len(first.source_locators), 2)
        self.assertEqual(len(first.raw_urls), 2)

    def test_pdf_selection_uses_path_not_kind(self):
        result = catalog({PRODUCT: source(fields=
            "documents:\n - " + doc("Program guide", "software", "/ftp/software.PdF?x=1") +
            "\n - " + doc("Compressed manual", "manual", "/ftp/manual.zip") + "\n")})
        self.assertEqual(len(result.documents), 2)
        self.assertEqual(len(result.pdf_candidates), 1)
        self.assertIn("software.PdF", result.pdf_candidates[0].resolved_url)

    def test_bad_url_and_wrong_types_are_diagnostics(self):
        result = catalog({PRODUCT: source(fields=
            "documents:\n - " + doc(url="javascript:evil.pdf") +
            "\n - { title: Missing, kind: manual }\n"
            " - { title: Broken, kind: manual, url: [invalid] }\n"
            " - 123\n")})
        self.assertFalse(result.ready_for_promotion)
        self.assertEqual(result.documents, ())
        self.assertIn("invalid_document_url", {x.code for x in result.issues})
        self.assertIn("missing_url", {x.code for x in result.issues})
        self.assertIn("malformed_document_entry", {x.code for x in result.issues})

    def test_invalid_collection_field_type_is_reported(self):
        result = catalog({SYSTEM: source("System", fields="documents: wrong\n")})
        self.assertFalse(result.ready_for_promotion)
        self.assertIn("invalid_document_field_type", {x.code for x in result.issues})

    def test_unsafe_schemes_credentials_and_encoded_traversal(self):
        for raw in ("http://example.com/a.pdf", "javascript:evil.pdf",
                    "https://user:secret@example.com/a.pdf",
                    "https://example.com/%2e%2e/a.pdf",
                    "//example.com/a.pdf", "/ftp/bad%QQ.pdf",
                    "https://example.com/a\\b.pdf"):
            with self.subTest(url=raw):
                with self.assertRaises(ValueError):
                    _resolve_url(raw, ORIGIN + "/products/x/", ORIGIN)

    def test_unresolvable_relative_url_is_diagnostic(self):
        result = catalog({"src/content/labs/lab-unrouted.md":
                          source("Lab", body="[Manual](relative.pdf)")})
        self.assertFalse(result.ready_for_promotion)
        self.assertIn("invalid_document_url", {x.code for x in result.issues})

    def test_code_fences_and_inline_code_are_not_links(self):
        tick = chr(96)
        body = (
            "Text file.pdf without link\n"
            + tick*3 + "md\n[hidden](/ftp/code.pdf)\n" + tick*3 + "\n"
            + "Inline " + tick + "[hidden](/ftp/inline.pdf)" + tick + "\n"
            + "~~~md\n[hidden](/ftp/fence.pdf)\n~~~\n"
            + "[visible](/ftp/real.pdf)\n"
        )
        result = catalog({PRODUCT: source(body=body)})
        self.assertEqual(len(result.pdf_candidates), 1)

    def test_incomplete_markdown_link_diagnostic(self):
        result = catalog({PRODUCT: source(body="[broken](/ftp/missing.pdf")})
        self.assertFalse(result.ready_for_promotion)
        self.assertIn("malformed_markdown_link", {x.code for x in result.issues})

    def test_update_delete_and_add_rebuild(self):
        original = catalog({PRODUCT: source(fields="documents:\n - " + doc() + "\n")})
        changed = catalog({PRODUCT: source(fields="documents:\n - " + doc(url="/ftp/new.pdf") + "\n"),
                           SECOND: source("Second", body="[S](/ftp/second.pdf)")}, commit="b"*40)
        self.assertEqual(len(original.documents), 1)
        self.assertEqual(len(changed.documents), 2)
        self.assertNotEqual(original.documents[0].document_id, changed.documents[0].document_id)
        deleted = catalog({SECOND: source("Second", body="[S](/ftp/second.pdf)")}, commit="c"*40)
        self.assertEqual(len(deleted.documents), 1)
        self.assertFalse(any("new.pdf" in x.url for x in deleted.documents))

    def test_add_and_remove_owner(self):
        block = "documents:\n - " + doc() + "\n"
        first = catalog({PRODUCT: source(fields=block)})
        second = catalog({PRODUCT: source(fields=block), SECOND: source("Second", fields=block)}, commit="b"*40)
        third = catalog({PRODUCT: source(fields=block)}, commit="c"*40)
        self.assertEqual([len(x.documents[0].owner_entity_ids) for x in (first, second, third)], [1, 2, 1])
        self.assertEqual(first.documents[0].document_id, second.documents[0].document_id)
        self.assertEqual(second.documents[0].document_id, third.documents[0].document_id)

    def test_stable_id_across_commits_and_determinism(self):
        additions = {PRODUCT: source(fields="documents:\n - " + doc() + "\n")}
        first = catalog(additions)
        again = catalog(additions)
        new_sha = catalog(additions, commit="f"*40)
        self.assertEqual(first, again)
        self.assertEqual(first.documents[0].document_id, new_sha.documents[0].document_id)
        self.assertNotEqual(first.documents[0].source_locators, new_sha.documents[0].source_locators)

    def test_exact_provenance_to_source_revision(self):
        result = catalog({PRODUCT: source(fields="documents:\n - " + doc() + "\n")})
        occurrence = result.occurrences[0]
        self.assertEqual(occurrence.source_path, PRODUCT)
        self.assertEqual(occurrence.source_locator, occurrence.source_revision_id + "#documents[0]")
        self.assertEqual(occurrence.raw_url, "/ftp/guide.pdf")
        self.assertEqual(occurrence.resolved_url, ORIGIN + "/ftp/guide.pdf")

    def test_metadata_update_does_not_change_document_id(self):
        a = catalog({PRODUCT: source(fields="documents:\n - " + doc(title="Old") + "\n")})
        b = catalog({PRODUCT: source(fields="documents:\n - " + doc(title="New") + "\n")}, commit="b"*40)
        self.assertEqual(a.documents[0].document_id, b.documents[0].document_id)
        self.assertNotEqual(a.documents[0].title, b.documents[0].title)

    def test_real_site_schema_samples_are_recognized(self):
        # Exact audited entries, extracted READ-ONLY from Saturn-Main-Site
        # @ 084d7594: src/content/products/fps.md and bsk-69.md.
        result = catalog({
            "src/content/products/fps.md": source("ФПС", fields=
                'documents:\n  - { title: "Фильтр питания ФПС. Руководство по эксплуатации", kind: manual, url: "/ftp/public/doc/fps/re%20FPS.pdf" }\n'),
            "src/content/products/bsk-69.md": source("БСК", fields=
                'documents:\n  - { title: "Техническое описание", kind: manual, url: "/ftp/public/doc/bsk/to%20bsk.pdf" }\n'
                'certificates:\n  - { kind: scan, image: "/photos/1863686720510304.jpg" }\n'),
        })
        self.assertTrue(result.ready_for_promotion)
        self.assertEqual(len(result.documents), 3)
        self.assertEqual(len(result.pdf_candidates), 2)
        self.assertEqual(sum(len(x.owner_entity_ids) for x in result.documents), 3)

    def test_upstream_fail_closed(self):
        result = catalog({PRODUCT: source(fields="documents: broken\n")})
        self.assertFalse(result.ready_for_promotion)

    def test_canonical_immutability_and_type_contract(self):
        result = catalog({PRODUCT: source(fields="documents:\n - " + doc() + "\n")})
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.documents[0].title = "Changed"
        with self.assertRaises(TypeError):
            adapt_support_catalog(None)


if __name__ == "__main__":
    unittest.main()
