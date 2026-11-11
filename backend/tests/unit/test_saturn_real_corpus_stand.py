"""Offline contract checks for the opt-in real corpus integration stand.

These are intentionally NOT real source or model-quality measurements.
"""
from pathlib import Path
import unittest

from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot, adapt_snapshot, git_blob_sha1,
)
from saturn_ai.ingestion.support_catalog_adapter import adapt_support_catalog
from saturn_ai.real_corpus_stand import (
    RealCorpusIntegrityError, prepare_real_stand, real_pdf_policy,
    select_pdf_catalog, select_site_snapshot,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "saturn_site"
COMMIT = "a" * 40
CONTENT = "src/content/products/device-x.md"


def verified_fixture(*, add_documents=False):
    mapping = {}
    for file in FIXTURE.rglob("*"):
        if not file.is_file():
            continue
        path = file.relative_to(FIXTURE).as_posix()
        raw = file.read_bytes()
        if path == CONTENT and add_documents:
            raw = raw.replace(
                b"---\n# Device X",
                b"documents:\n"
                b"  - {title: Test guide, kind: manual, url: /ftp/guide.pdf}\n"
                b"  - {title: Other guide, kind: manual, url: /ftp/other.pdf}\n"
                b"---\n# Device X",
            )
        mapping[path] = (git_blob_sha1(raw), raw)
    return PinnedSiteSnapshot.from_mapping(
        commit_sha=COMMIT, tree_sha="c" * 40, files=mapping)


class RealCorpusStandContractTests(unittest.TestCase):
    def test_subset_retains_verified_git_files_and_omits_unselected_content(self):
        full = verified_fixture()
        sample = select_site_snapshot(
            full, expected_commit=COMMIT, content_paths=(CONTENT,))
        paths = {x.path for x in sample.files}
        self.assertEqual(sample.commit_sha, full.commit_sha)
        self.assertEqual(sample.tree_sha, full.tree_sha)
        self.assertIn(CONTENT, paths)
        self.assertIn("astro.config.mjs", paths)
        self.assertIn("src/content.config.ts", paths)
        self.assertNotIn("src/content/products/device-y.md", paths)
        original = {x.path: x for x in full.files}
        for file in sample.files:
            self.assertIs(file, original[file.path])
            self.assertEqual(file.blob_sha, git_blob_sha1(file.content))
        self.assertTrue(adapt_snapshot(sample).ready_for_promotion)

    def test_source_revision_and_missing_source_fail_closed(self):
        full = verified_fixture()
        with self.assertRaisesRegex(RealCorpusIntegrityError, "source_commit_mismatch"):
            select_site_snapshot(full, expected_commit="b" * 40,
                                 content_paths=(CONTENT,))
        with self.assertRaisesRegex(RealCorpusIntegrityError, "missing_verified"):
            select_site_snapshot(full, expected_commit=COMMIT,
                                 content_paths=("src/content/products/nope.md",))
        with self.assertRaisesRegex(RealCorpusIntegrityError, "unsafe_sample_path"):
            select_site_snapshot(full, expected_commit=COMMIT,
                                 content_paths=("../secrets.md",))

    def test_explicit_pdf_selection_does_not_keep_unselected_documents(self):
        full = verified_fixture(add_documents=True)
        site = adapt_snapshot(select_site_snapshot(
            full, expected_commit=COMMIT, content_paths=(CONTENT,)))
        catalog = adapt_support_catalog(site)
        self.assertTrue(catalog.ready_for_promotion)
        self.assertEqual(len(catalog.pdf_candidates), 2)
        sample = select_pdf_catalog(catalog, pdf_paths=("/ftp/guide.pdf",))
        self.assertEqual(len(sample.documents), 1)
        self.assertEqual(len(sample.pdf_candidates), 1)
        self.assertEqual(len(sample.occurrences), 1)
        self.assertTrue(sample.ready_for_promotion)
        self.assertTrue(sample.pdf_candidates[0].resolved_url.endswith("/ftp/guide.pdf"))
        self.assertFalse(any("other.pdf" in x.resolved_url for x in sample.pdf_candidates))
        with self.assertRaisesRegex(RealCorpusIntegrityError, "missing_or_ambiguous"):
            select_pdf_catalog(catalog, pdf_paths=("/ftp/missing.pdf",))
        with self.assertRaisesRegex(RealCorpusIntegrityError, "unsafe_pdf"):
            select_pdf_catalog(catalog, pdf_paths=("/private/guide.pdf",))

    def test_pdf_policy_is_explicit_allowlist_with_request_cap(self):
        policy = real_pdf_policy()
        self.assertEqual(policy.allowed_hosts, ("www.mnppsaturn.ru",))
        self.assertEqual(policy.allowed_path_prefixes, ("/ftp",))
        self.assertEqual(policy.max_requests, 4)
        self.assertEqual(policy.max_attempts, 1)

    def test_development_worker_must_be_explicitly_enabled(self):
        class NoNetwork:
            def fetch_snapshot(self):
                raise AssertionError("No network before opt in")
        with self.assertRaisesRegex(RealCorpusIntegrityError, "opt_in_required"):
            prepare_real_stand(provider=NoNetwork(),
                               enable_development_pdf_worker=False)


if __name__ == "__main__":
    unittest.main()
