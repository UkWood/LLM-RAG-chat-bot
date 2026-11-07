"""Published text is evidence; mutable website taxonomy is not a parser contract."""
import unittest
from dataclasses import replace

from saturn_ai.publication.policy import PublicationPolicy
from saturn_ai.publication.extract import PublishedSource
from saturn_ai.publication.snapshot import PublishedSnapshot, PublishedCatalog
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService, IndexSet

ROOT='https://example.invalid/site/'
HTML=b'<html><title>Pump A</title><nav>obsolete category</nav><main><h1>Pump A</h1><p>Supply: 24 V.</p><table><tr><th>Port</th><th>Count</th></tr><tr><td>USB</td><td>2</td></tr></table><a href="guide.pdf">Manual</a></main></html>'

def source(content=HTML,url=ROOT+'pump/'):
    return PublishedSource(url,content,'text/html')

class PublicationTests(unittest.TestCase):
    def test_generic_text_ignores_taxonomy_and_keeps_table_values(self):
        first=source();second=source(HTML.replace(b'obsolete category',b'new grouping'))
        self.assertEqual(first.pages,second.pages)
        text=' '.join(t for _,t in first.pages)
        self.assertIn('Supply: 24 V.',text)
        self.assertIn('USB | 2',text)
        self.assertNotIn('obsolete category',text)
        self.assertIn(ROOT+'pump/guide.pdf',first.links)

    def test_source_scope_cannot_escape_published_site_or_pdf_origins(self):
        policy=PublicationPolicy(ROOT,('https://docs.example.invalid',))
        self.assertTrue(policy.allows_page(ROOT+'new-category/device'))
        self.assertFalse(policy.allows_page('https://example.invalid/site-other/'))
        self.assertTrue(policy.allows_pdf('https://docs.example.invalid/a.pdf'))
        for bad in ('https://127.0.0.1/site/','https://localhost/site/','https://example.invalid/site/%2e%2e/private', 'file:///tmp/a.pdf'):
            with self.subTest(url=bad),self.assertRaises(ValueError):PublicationPolicy(bad)
        self.assertFalse(policy.allows_pdf('https://unlisted.invalid/a.pdf'))

    def test_original_natural_question_reaches_existing_search(self):
        snap=PublishedSnapshot((source(),),'policy-a')
        catalog=PublishedCatalog(lambda:{s.url:s.content_hash for s in snap.sources})
        service=RetrievalService(catalog);service.publish(IndexSet(snap,BM25Index(snap)))
        result=service.search('Какое Supply у «Pump A»?',mode='lexical')
        self.assertTrue(result.final)
        self.assertEqual(result.final[0].source_id,ROOT+'pump/')
        self.assertIn('24 V',snap.chunks[0].chunk.text)
        self.assertFalse(catalog.eligible_snapshot_chunks(snap,'cloud_generate'))

    def test_new_version_and_live_revocation_invalidate_old_chunks(self):
        old=PublishedSnapshot((source(),),'policy-a')
        changed=PublishedSnapshot((source(HTML.replace(b'24 V',b'12 V')),),'policy-a')
        current={ROOT+'pump/':old.sources[0].content_hash}
        catalog=PublishedCatalog(lambda:dict(current))
        self.assertTrue(catalog.eligible_snapshot_chunks(old,'local_generate'))
        current[ROOT+'pump/']=changed.sources[0].content_hash
        self.assertFalse(catalog.eligible_snapshot_chunks(old,'local_generate'))
        self.assertTrue(catalog.eligible_snapshot_chunks(changed,'local_generate'))
        current.clear();self.assertFalse(catalog.eligible_snapshot_chunks(changed,'local_index'))

    def test_tampered_snapshot_and_unparsed_pdf_do_not_become_evidence(self):
        snap=PublishedSnapshot((source(),),'policy-a')
        bad=replace(snap,chunks=())
        with self.assertRaises(ValueError):BM25Index(bad)
        with self.assertRaises(ValueError):PublishedSource(ROOT+'a.pdf',b'not a PDF','application/pdf')
