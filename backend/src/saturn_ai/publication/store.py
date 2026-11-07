"""Owner-private durable receipts, live policy and atomic snapshot publication."""
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import time
from .extract import PublishedSource
from .snapshot import PublishedSnapshot,PublishedCatalog


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.pending-')
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,ensure_ascii=False,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)


class PublicationStore:
    def __init__(self,root,policy,*,clock=time.time):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.policy=policy;self.clock=clock
    def state(self):
        path=self.root/'state.json'
        if not path.exists():return dict(status='uninitialized',allowed={},active=None,last_success=None,last_attempt=None)
        value=json.loads(path.read_text())
        if not isinstance(value,dict) or not isinstance(value.get('allowed'),dict):raise ValueError('Invalid publication state')
        return value
    def write_state(self,value):atomic_json(self.root/'state.json',value)
    @contextmanager
    def job_lock(self):
        with (self.root/'refresh.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:yield False;return
            try:yield True
            finally:fcntl.flock(lock,fcntl.LOCK_UN)
    def health(self):
        state=self.state();last=state.get('last_success')
        if not state.get('active') or last is None:return 'uninitialized'
        return 'stale' if self.clock()-last>self.policy.max_age_seconds else 'ready'
    def current_versions(self):
        state=self.state();last=state.get('last_success')
        if (not state.get('active') or last is None or self.clock()-last>self.policy.max_age_seconds
                or state.get('policy_revision')!=self.policy.revision):return {}
        versions=state['allowed'];links=state.get('links',{});aliases=state.get('aliases',{})
        seen=set();queue=[aliases.get(self.policy.site_root,self.policy.site_root)]
        while queue:
            url=queue.pop()
            if url in seen or url not in versions or not (self.policy.allows_page(url) or self.policy.allows_pdf(url)):continue
            seen.add(url)
            for link in links.get(url,[]):queue.append(aliases.get(link,link))
        return {url:versions[url] for url in seen}
    def catalog(self):return PublishedCatalog(self.current_versions,cloud_allowed=self.policy.cloud_allowed)
    def _manifest(self,*,allow_policy_change=False):
        active=self.state().get('active')
        if not active:raise LookupError('No published snapshot')
        if not re.fullmatch('[0-9a-f]{64}',active):raise ValueError('Invalid active snapshot identity')
        manifest=json.loads((self.root/'versions'/active/'manifest.json').read_text())
        if manifest.get('snapshot_id')!=active or (not allow_policy_change and manifest.get('policy_revision')!=self.policy.revision):
            raise ValueError('Publication policy/snapshot mismatch')
        return manifest
    def aliases(self):
        try:return {r['requested_url']:r['url'] for r in self._manifest(allow_policy_change=True)['sources']}
        except LookupError:return {}
    def observe(self,url,content_hash,*,requested_url=None,aliases=None):
        state=self.state();previous=(aliases or {}).get(requested_url)
        if previous and previous!=url:state['allowed'].pop(previous,None)
        graph=state.setdefault('links',{})
        if state['allowed'].get(url)!=content_hash or content_hash is None:graph[url]=[]
        if content_hash is None:state['allowed'].pop(url,None)
        else:state['allowed'][url]=content_hash
        state.setdefault('aliases',{})[requested_url or url]=url
        self.write_state(state)
    def observe_links(self,source):
        state=self.state();state.setdefault('links',{})[source.url]=list(source.links);self.write_state(state)
    def capture(self):
        manifest=self._manifest();sources=[];metadata={}
        for item in manifest['sources']:
            digest=item['sha256']
            if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid blob hash')
            content=(self.root/'blobs'/digest).read_bytes()
            if sha256(content).hexdigest()!=digest:raise ValueError('Publication receipt changed')
            source=PublishedSource(item['url'],content,item['media_type'])
            allowed=self.policy.allows_pdf if source.media_type=='application/pdf' else self.policy.allows_page
            if not allowed(source.url) or not allowed(item['requested_url']):raise ValueError('Source outside policy')
            sources.append(source);metadata[source.url]=item
        mapping={s.url:s for s in sources}
        for source in sources:
            item=metadata[source.url];parent=item['discovered_from']
            if parent is None:
                if item['requested_url']!=self.policy.site_root or source.media_type!='text/html':raise ValueError('Missing publication root')
            elif (parent not in mapping or mapping[parent].media_type!='text/html'
                  or item['requested_url'] not in mapping[parent].links):raise ValueError('Missing trusted publication link')
        snapshot=PublishedSnapshot(tuple(sources),self.policy.revision)
        if snapshot.snapshot_id!=manifest['snapshot_id']:raise ValueError('Derived publication changed')
        return snapshot
    def publish(self,snapshot,receipts,index_builder):
        directory=self.root/'versions'/snapshot.snapshot_id;directory.mkdir(parents=True,exist_ok=True)
        blobs=self.root/'blobs';blobs.mkdir(exist_ok=True)
        items=[]
        for source in snapshot.sources:
            path=blobs/source.content_hash
            if not path.exists():
                with path.open('xb') as output:output.write(source.content);output.flush();os.fsync(output.fileno())
            elif sha256(path.read_bytes()).hexdigest()!=source.content_hash:raise ValueError('Existing blob changed')
            items.append(dict(url=source.url,sha256=source.content_hash,media_type=source.media_type,**receipts[source.url]))
        index_builder(snapshot,directory)
        manifest=dict(snapshot_id=snapshot.snapshot_id,policy_revision=self.policy.revision,sources=items)
        atomic_json(directory/'manifest.json',manifest)
        state=self.state();state.update(active=snapshot.snapshot_id,allowed={s.url:s.content_hash for s in snapshot.sources},
            status='completed',last_success=self.clock(),error_type=None,source_count=len(snapshot.sources),chunk_count=len(snapshot.chunks),
            links={s.url:list(s.links) for s in snapshot.sources},aliases={r['requested_url']:url for url,r in receipts.items()})
        self.write_state(state)
        return state
