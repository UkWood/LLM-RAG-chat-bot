"""Immutable publication snapshots and current policy, separate from synthetic schema."""
from dataclasses import dataclass,field,asdict
from hashlib import sha256
import json
from types import SimpleNamespace
from ..ingestion.contracts import Document,make_chunk,identifier
from ..snapshots import IndexedChunk
from .extract import PublishedSource


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


@dataclass(frozen=True)
class PublishedSnapshot:
    sources: tuple
    policy_revision: str
    chunks: tuple=field(default=())
    snapshot_id: str=field(default='')
    documents: tuple=field(default=())
    registry: object=field(default=None,compare=False)
    _seal: str=field(default='',repr=False)
    test_only: bool=False

    def __post_init__(self):
        # replace() retains the original seal and is validated rather than rebuilt.
        if self._seal:return
        if (not isinstance(self.sources,tuple) or not self.policy_revision or any(not isinstance(s,PublishedSource) for s in self.sources)
                or len({s.url for s in self.sources})!=len(self.sources)):raise ValueError('Invalid publication sources')
        documents=[];records=[]
        for source in sorted(self.sources,key=lambda s:s.url):
            docid=identifier('published-text-v1',source.url,source.content_hash)
            chunks=[]
            for page,text in source.pages:
                for start in range(0,len(text),1500):
                    part=text[start:start+1500].strip()
                    if part:chunks.append(make_chunk(docid,source.url,part,(),'body',page))
            documents.append(Document(docid,source.url,source.content_hash,'published-text-v1',source.title,
                source.url,'Document',None,source.url,tuple(chunks)))
            records.append(SimpleNamespace(source_id=source.url,document_type='pdf' if source.media_type=='application/pdf' else 'page'))
        sid=digest([self.policy_revision,[(s.url,s.content_hash) for s in sorted(self.sources,key=lambda s:s.url)],
            [asdict(d) for d in documents]])
        indexed=tuple(IndexedChunk(c,sid,self.policy_revision,d.content_hash,None,d.locator,d.title,
            'PUBLIC','approved',('local_index','local_generate')) for d in documents for c in d.chunks)
        object.__setattr__(self,'snapshot_id',sid);object.__setattr__(self,'documents',tuple(documents))
        object.__setattr__(self,'chunks',indexed);object.__setattr__(self,'registry',SimpleNamespace(revision=self.policy_revision,entries=tuple(records)))
        object.__setattr__(self,'_seal',self._fingerprint())

    def _fingerprint(self):
        return digest([self.snapshot_id,self.policy_revision,[asdict(d) for d in self.documents],
            [asdict(c) for c in self.chunks],[(s.url,s.content_hash,sha256(s.content).hexdigest()) for s in self.sources]])

    def validate(self):
        if self._seal!=self._fingerprint() or self.registry.revision!=self.policy_revision:
            raise ValueError('Publication snapshot changed')
        return self


class PublishedCatalog:
    def __init__(self,current_versions,*,cloud_allowed=False):
        self.current_versions=current_versions;self.cloud_allowed=cloud_allowed
    def eligible_snapshot_chunks(self,snapshot,usage):
        return self.eligible_snapshot_chunks_for_usages(snapshot,(usage,))
    def eligible_snapshot_chunks_for_usages(self,snapshot,usages):
        snapshot.validate()
        if not usages or any(u not in ('local_index','local_generate','cloud_generate') for u in usages):raise ValueError('Invalid usage')
        if 'cloud_generate' in usages and not self.cloud_allowed:return ()
        versions=self.current_versions()
        return tuple(c for c in snapshot.chunks if versions.get(c.source_id)==c.source_hash)
