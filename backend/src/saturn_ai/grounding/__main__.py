"""Explicit local synthetic grounded CLI. No model downloads or cloud provider."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from ..evaluation.reranking import load_embedding
from ..retrieval.reranker_model import load_semantic_reranker
from ..ingestion.registry import load_registry
from ..ingestion.pipeline import build_fixture
from ..snapshots import build_snapshot,SnapshotCatalog
from ..retrieval.lexical import BM25Index
from ..retrieval.dense import QdrantIndex
from ..retrieval.service import RetrievalService,IndexSet
from ..providers import FakeLLMProvider
from .application import GroundedConsultant


def main():
    parser=argparse.ArgumentParser(description='Synthetic local grounded answer with offline fake provider')
    for name in ('corpus','model-dir','reranker-dir'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--query',required=True)
    args=parser.parse_args();dense=None
    try:
        encoder,_=load_embedding(args.model_dir);scorer,_=load_semantic_reranker(args.reranker_dir)
        registry=load_registry((args.corpus/'registry.json').read_bytes())
        snapshot=build_snapshot(build_fixture(args.corpus,registry,registry.source_snapshot),registry)
        dense=QdrantIndex(snapshot,encoder);service=RetrievalService(SnapshotCatalog(registry))
        service.publish(IndexSet(snapshot,BM25Index(snapshot),dense))
        result=GroundedConsultant(service,scorer,FakeLLMProvider()).answer(args.query)
        print(json.dumps(asdict(result),ensure_ascii=False,indent=2))
        return 1 if result.status=='error' else 0
    except (ValueError,OSError,RecursionError):parser.exit(2,'Local grounded pipeline setup rejected.\n')
    finally:
        if dense:dense.close()


if __name__=='__main__':raise SystemExit(main())
