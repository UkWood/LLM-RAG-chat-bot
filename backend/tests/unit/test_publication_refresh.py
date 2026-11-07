"""Refresh tests use real persistence and publication policy, controlled HTTP receipts."""
import tempfile
from pathlib import Path
import unittest
from saturn_ai.publication.policy import PublicationPolicy
from saturn_ai.publication.fetch import Fetched
from saturn_ai.publication.store import PublicationStore
from saturn_ai.publication.refresh import RefreshController

ROOT='https://example.invalid/site/'
class Site:
    def __init__(self):self.pages={ROOT:b'<main><a href="device/">Device</a></main>',ROOT+'device/':b'<main>Voltage 24 V.</main>'};self.failed=set()
    def __call__(self,url,kind):
        if url in self.failed:raise OSError('network unavailable')
        return Fetched(url,self.pages.get(url,b''),'text/html',200 if url in self.pages else 404)

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1000000.;self.policy=PublicationPolicy(ROOT);self.site=Site()
        self.store=PublicationStore(Path(self.temp.name),self.policy,clock=lambda:self.now)
        self.updater=RefreshController(self.policy,self.store,self.site)
    def test_daily_skip_and_admin_force_replace_same_url(self):
        self.assertEqual(self.updater.run()['status'],'completed')
        before=self.store.capture();self.now+=60
        self.assertEqual(self.updater.run()['status'],'skipped')
        self.site.pages[ROOT+'device/']=b'<main>Voltage 12 V.</main>'
        self.assertEqual(self.updater.run(force=True)['status'],'completed')
        after=self.store.capture();self.assertNotEqual(before.snapshot_id,after.snapshot_id)
        self.assertIn('12 V',' '.join(c.chunk.text for c in after.chunks))
        self.assertFalse(any(c.source_id==ROOT+'device/' for c in self.store.catalog().eligible_snapshot_chunks(before,'local_generate')))
        self.now+=86400;self.assertEqual(self.updater.run()['status'],'completed')
    def test_removed_link_removes_previous_document(self):
        self.updater.run();self.site.pages[ROOT]=b'<main>Current catalog.</main>'
        self.updater.run(force=True)
        self.assertNotIn(ROOT+'device/',self.store.current_versions())
    def test_fetch_failure_does_not_mean_delete_and_does_not_promote(self):
        self.updater.run();before=self.store.capture().snapshot_id
        self.site.failed.add(ROOT+'device/')
        self.assertEqual(self.updater.run(force=True)['status'],'failed')
        self.assertEqual(self.store.capture().snapshot_id,before)
        self.assertIn(ROOT+'device/',self.store.current_versions())
    def test_failed_index_build_blocks_observed_old_version_before_promotion(self):
        self.updater.run();before=self.store.capture();self.site.pages[ROOT+'device/']=b'<main>Voltage 48 V.</main>'
        def fail(snapshot,directory):raise ValueError('index build failed')
        updater=RefreshController(self.policy,self.store,self.site,index_builder=fail)
        self.assertEqual(updater.run(force=True)['status'],'failed')
        self.assertEqual(self.store.capture().snapshot_id,before.snapshot_id)
        allowed=self.store.catalog().eligible_snapshot_chunks(before,'local_generate')
        self.assertFalse(any(c.source_id==ROOT+'device/' for c in allowed))
    def test_concurrent_force_is_serialized_and_stale_data_is_denied(self):
        self.updater.run()
        with self.store.job_lock() as acquired:
            self.assertTrue(acquired)
            self.assertEqual(self.updater.run(force=True)['status'],'busy')
        self.now+=self.policy.max_age_seconds+1
        self.assertFalse(self.store.current_versions())
        self.assertEqual(self.store.health(),'stale')
    def test_corrupted_blob_does_not_load_as_evidence(self):
        self.updater.run();snapshot=self.store.capture()
        path=self.store.root/'blobs'/snapshot.sources[0].content_hash
        path.write_bytes(b'changed without receipt')
        with self.assertRaises(ValueError):self.store.capture()
    def test_untrusted_pdf_origin_never_fetched(self):
        self.site.pages[ROOT]=b'<main>Page <a href="https://localhost/a.pdf">PDF</a></main>'
        self.assertEqual(self.updater.run()['status'],'completed')
        self.assertEqual(len(self.store.capture().sources),1)

    def test_removed_link_denied_even_when_index_promotion_fails(self):
        self.updater.run();before=self.store.capture()
        self.site.pages[ROOT]=b'<main>New catalog without old device.</main>'
        def fail(snapshot,directory):raise ValueError('build failed')
        result=RefreshController(self.policy,self.store,self.site,index_builder=fail).run(force=True)
        self.assertEqual(result['status'],'failed')
        self.assertFalse(any(c.source_id==ROOT+'device/' for c in self.store.catalog().eligible_snapshot_chunks(before,'local_generate')))

    def test_confirmed_root_delete_denies_descendants_before_new_snapshot(self):
        self.updater.run();self.site.pages.pop(ROOT)
        self.assertEqual(self.updater.run(force=True)['status'],'failed')
        self.assertEqual(self.store.current_versions(),{})

    def test_next_calendar_day_does_not_skip_due_to_short_interval(self):
        self.updater.run();self.now+=86399
        self.assertEqual(self.updater.run()['status'],'completed')

    def test_private_resolved_destination_is_rejected_before_io(self):
        from saturn_ai.publication.fetch import PublicationFetcher
        resolver=lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))]
        fetch=PublicationFetcher(self.policy,resolver=resolver)
        with self.assertRaises(ValueError):fetch(ROOT,'page')

    def test_changed_publication_policy_can_be_rebuilt_without_loading_old_policy(self):
        self.updater.run()
        policy=PublicationPolicy(ROOT,cloud_allowed=True)
        store=PublicationStore(self.store.root,policy,clock=lambda:self.now)
        self.assertEqual(RefreshController(policy,store,self.site).run(force=True)['status'],'completed')
        snapshot=store.capture()
        self.assertTrue(store.catalog().eligible_snapshot_chunks(snapshot,'cloud_generate'))
