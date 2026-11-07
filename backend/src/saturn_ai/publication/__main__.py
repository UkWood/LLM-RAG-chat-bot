"""Operator refresh/status commands; never exposed as a user chat tool."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from .policy import PublicationPolicy
from .store import PublicationStore,atomic_json
from .refresh import RefreshController,lexical_index_check


def index_builder_for(model_dir):
    from ..evaluation.reranking import load_embedding
    from ..retrieval.lexical import BM25Index
    from ..retrieval.dense import QdrantIndex
    encoder,_=load_embedding(model_dir)
    def build(snapshot,directory):
        lexical=BM25Index(snapshot)
        dense=QdrantIndex(snapshot,encoder,path=directory/'dense')
        try:
            lexical.validate();dense.validate()
            atomic_json(directory/'index.json',dict(mode='hybrid',embedding=encoder.identity,
                lexical=asdict(lexical.descriptor),dense=asdict(dense.descriptor)))
        finally:dense.close()
    return build


def main(argv=None):
    parser=argparse.ArgumentParser(description='Refresh published text/PDF: daily or operator --force')
    parser.add_argument('--policy',type=Path,required=True);parser.add_argument('--store',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status');refresh=sub.add_parser('refresh')
    refresh.add_argument('--force',action='store_true')
    modes=refresh.add_mutually_exclusive_group(required=True)
    modes.add_argument('--model-dir',type=Path);modes.add_argument('--lexical-only',action='store_true')
    args=parser.parse_args(argv)
    try:
        data=json.loads(args.policy.read_text());data['pdf_origins']=tuple(data.get('pdf_origins',()))
        policy=PublicationPolicy(**data);store=PublicationStore(args.store,policy)
        if args.command=='status':result=store.state()
        else:
            if args.lexical_only:
                def build(snapshot,directory):
                    lexical_index_check(snapshot,directory)
                    atomic_json(directory/'index.json',dict(mode='lexical',snapshot_id=snapshot.snapshot_id))
            else:build=index_builder_for(args.model_dir)
            result=RefreshController(policy,store,index_builder=build).run(force=args.force)
        public={k:result.get(k) for k in ('status','last_success','last_attempt','source_count','chunk_count','error_type')}
        public['health']=store.health();print(json.dumps(public,ensure_ascii=False))
        return 2 if result.get('status')=='failed' else 0
    except (ValueError,OSError,TypeError,KeyError):
        print(json.dumps(dict(status='error',reason_code='publication_unavailable')));return 2

if __name__=='__main__':raise SystemExit(main())
