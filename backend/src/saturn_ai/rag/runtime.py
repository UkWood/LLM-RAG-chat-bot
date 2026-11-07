"""Load one checked publication/index capture; the updater remains a separate process."""
from dataclasses import asdict,dataclass
from .application import Consultant
from .provider import strict_json


@dataclass
class Runtime:
    app: Consultant
    dense: object

    def __enter__(self):return self
    def __exit__(self,*args):self.dense.close()


def load_runtime(store,model_dir,reranker_dir,provider):
    from ..evaluation.reranking import load_embedding
    from ..retrieval.reranker_model import load_semantic_reranker
    from ..retrieval.lexical import BM25Index
    from ..retrieval.dense import QdrantIndex
    from ..retrieval.service import RetrievalService,IndexSet
    if store.health()!='ready':raise ValueError('Publication is not current')
    snapshot=store.capture()
    directory=store.root/'versions'/snapshot.snapshot_id
    saved=strict_json((directory/'index.json').read_bytes())
    encoder,_=load_embedding(model_dir)
    scorer,_=load_semantic_reranker(reranker_dir)
    lexical=BM25Index(snapshot)
    # Compare JSON-normalized descriptors (tuple coverage is stored as a JSON array).
    import json
    normalized=lambda value:json.loads(json.dumps(value,allow_nan=False))
    if (not isinstance(saved,dict) or set(saved)!={'mode','embedding','lexical','dense'}
            or saved['mode']!='hybrid' or saved['embedding']!=normalized(encoder.identity)
            or saved['lexical']!=normalized(asdict(lexical.descriptor))):
        raise ValueError('Saved index identity mismatch')
    if not (directory/'dense').is_dir():raise ValueError('Persisted dense index missing')
    dense=QdrantIndex(snapshot,encoder,path=directory/'dense',require_existing=True)
    try:
        if saved['dense']!=normalized(asdict(dense.descriptor)):raise ValueError('Saved dense identity mismatch')
        service=RetrievalService(store.catalog());service.publish(IndexSet(snapshot,lexical,dense))
        # Date belongs to this capture, not a later updater publication.
        manifest_state=store.state()
        if manifest_state.get('active')!=snapshot.snapshot_id:raise ValueError('Publication changed while loading')
        as_of=manifest_state['last_success']
        app=Consultant(service,scorer,provider,as_of=lambda:as_of,health=store.health)
        return Runtime(app,dense)
    except BaseException:
        dense.close();raise
