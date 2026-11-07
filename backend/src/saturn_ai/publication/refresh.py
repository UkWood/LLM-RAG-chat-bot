"""One daily/manual job; crawling and atomic promotion are not a chat tool."""
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from .extract import PublishedSource
from .fetch import PublicationFetcher
from .snapshot import PublishedSnapshot


def lexical_index_check(snapshot,directory):
    from ..retrieval.lexical import BM25Index
    BM25Index(snapshot).validate()


class RefreshController:
    def __init__(self,policy,store,fetcher=None,*,index_builder=lexical_index_check):
        self.policy=policy;self.store=store;self.fetcher=fetcher or PublicationFetcher(policy);self.index_builder=index_builder
    def run(self,*,force=False):
        with self.store.job_lock() as acquired:
            if not acquired:return dict(status='busy')
            state=self.store.state();last=state.get('last_attempt')
            zone=ZoneInfo(self.policy.refresh_timezone)
            if (not force and state.get('policy_revision')==self.policy.revision and last is not None
                    and datetime.fromtimestamp(last,zone).date()==datetime.fromtimestamp(self.store.clock(),zone).date()):
                return dict(status='skipped')
            aliases=self.store.aliases();state.update(status='running',last_attempt=self.store.clock(),error_type=None,policy_revision=self.policy.revision)
            self.store.write_state(state)
            try:
                queue=[(self.policy.site_root,'page',None)];seen=set();sources={};receipts={};pages=pdfs=total=0
                while queue:
                    requested,kind,parent=queue.pop(0)
                    if requested in seen:continue
                    seen.add(requested)
                    allowed=self.policy.allows_pdf if kind=='pdf' else self.policy.allows_page
                    if not allowed(requested):continue
                    pages+=kind=='page';pdfs+=kind=='pdf'
                    if pages>self.policy.max_pages or pdfs>self.policy.max_pdfs:raise ValueError('Publication crawl budget exhausted')
                    fetched=self.fetcher(requested,kind)
                    if not allowed(fetched.url):raise ValueError('Fetched destination outside scope')
                    if fetched.status in (404,410):
                        self.store.observe(fetched.url,None,requested_url=requested,aliases=aliases)
                        if requested==self.policy.site_root:raise ValueError('Publication root unavailable')
                        continue
                    if fetched.status!=200:raise ValueError('Unexpected source status')
                    total+=len(fetched.content)
                    if total>100_000_000:raise ValueError('Publication byte budget exhausted')
                    digest=sha256(fetched.content).hexdigest()
                    self.store.observe(fetched.url,digest,requested_url=requested,aliases=aliases)
                    source=PublishedSource(fetched.url,fetched.content,fetched.media_type)
                    self.store.observe_links(source)
                    if fetched.url in sources:continue
                    sources[source.url]=source;receipts[source.url]=dict(requested_url=requested,discovered_from=parent)
                    if kind=='page':
                        for link in source.links:
                            if self.policy.allows_pdf(link):queue.append((link,'pdf',source.url))
                            elif self.policy.allows_page(link):queue.append((link,'page',source.url))
                snapshot=PublishedSnapshot(tuple(sources.values()),self.policy.revision)
                return self.store.publish(snapshot,receipts,self.index_builder)
            except Exception as exc:
                state=self.store.state();state.update(status='failed',error_type=type(exc).__name__)
                self.store.write_state(state)
                return dict(status='failed',error_type=type(exc).__name__,last_success=state.get('last_success'))
