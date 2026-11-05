"""Local opt-in query diagnostics. No provider calls or answer generation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from ..ingestion.registry import load_registry
from ..ingestion.pipeline import build_fixture
from ..snapshots import build_snapshot, SnapshotCatalog
from .lexical import BM25Index
from .dense import QdrantIndex
from .embeddings import LocalONNXEncoder
from .service import RetrievalService, IndexSet


def main():
    parser=argparse.ArgumentParser(description='Local synthetic retrieval diagnostics; no generated answer')
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--query',required=True)
    parser.add_argument('--mode',choices=['lexical','dense','hybrid'],default='lexical')
    parser.add_argument('--model-dir',type=Path)
    parser.add_argument('--index-dir',type=Path)
    parser.add_argument('--top-k',type=int,default=5)
    parser.add_argument('--show-text',action='store_true',help='Explicit local output of approved synthetic text')
    args=parser.parse_args();dense=None
    try:
        if args.mode=='lexical' and (args.model_dir or args.index_dir):
            raise ValueError('Lexical mode does not use neural model/index directory')
        if args.mode!='lexical' and args.model_dir is None:
            raise ValueError('Local checkpoint required')
        registry=load_registry((args.corpus/'registry.json').read_bytes())
        snapshot=build_snapshot(build_fixture(args.corpus,registry,registry.source_snapshot),registry)
        lexical=BM25Index(snapshot)
        if args.model_dir:
            dense=QdrantIndex(snapshot,LocalONNXEncoder(args.model_dir),path=args.index_dir)
        service=RetrievalService(SnapshotCatalog(registry));service.publish(IndexSet(snapshot,lexical,dense))
        trace=service.search(args.query,mode=args.mode,top_k=args.top_k)
        output=asdict(trace);output['answer_evaluation']='not_run';output['reranking']='not_run'
        if args.show_text:
            by_id={c.chunk_id:c for c in snapshot.chunks}
            output['approved_synthetic_text']={c.chunk_id:by_id[c.chunk_id].chunk.text for c in trace.final}
        print(json.dumps(output,ensure_ascii=False,indent=2))
    except (ValueError,OSError,RecursionError):
        parser.exit(2,'Local synthetic retrieval rejected.\n')
    finally:
        if dense:dense.close()


if __name__=='__main__':main()
