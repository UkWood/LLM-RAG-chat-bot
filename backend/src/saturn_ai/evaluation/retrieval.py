"""Measured retrieval only. Gold labels score results, never construct query/context."""
from dataclasses import asdict
from importlib.metadata import version
from math import isfinite, ceil
from pathlib import Path
from statistics import median
from time import perf_counter

from ..ingestion.pipeline import build_fixture
from ..ingestion.registry import load_registry
from ..snapshots import build_snapshot, SnapshotCatalog
from ..retrieval.lexical import BM25Index
from ..retrieval.dense import QdrantIndex
from ..retrieval.embeddings import LocalONNXEncoder
from ..retrieval.model_preparation import read_model_provenance
from ..retrieval.service import RetrievalService, IndexSet
from ..retrieval.contracts import Candidate, REPRESENTATION_VERSION
from .dataset import validate_dataset


def score_case(case, snapshot, trace):
    if trace.snapshot_id != snapshot.snapshot_id or len(trace.final) > 5:
        raise ValueError('Result snapshot/Top-5 mismatch')
    mapping = {c.chunk_id:c for c in snapshot.chunks}
    for candidates in (trace.lexical, trace.dense, trace.final):
        seen = set()
        for position, result in enumerate(candidates, 1):
            if (not isinstance(result, Candidate) or result.chunk_id not in mapping or result.chunk_id in seen
                    or result.source_id != mapping[result.chunk_id].source_id or result.snapshot_id != snapshot.snapshot_id
                    or not isfinite(result.score) or type(result.rank) is not int or result.rank != position):
                raise ValueError('Invalid result identity/rank/score')
            seen.add(result.chunk_id)
    metrics = dict(source_hit_at_5=None, all_expected_sources_at_5=None, expected_source_recall_at_5=None,
                   gold_evidence_recall_at_5=None, reciprocal_rank_at_5=None)
    if case.must_answer:
        returned = {c.source_id for c in trace.final}
        expected = set(case.expected_sources)
        hit = expected & returned
        supported = sum(any(mapping[result.chunk_id].source_id == ev.source_id
                            and mapping[result.chunk_id].chunk.field_path == ev.field_path
                            and mapping[result.chunk_id].chunk.page_start == ev.page
                            and ev.text in mapping[result.chunk_id].chunk.text for result in trace.final)
                        for ev in case.expected_evidence)
        reciprocal = next((1/rank for rank, c in enumerate(trace.final,1) if c.source_id in expected),0.0)
        metrics.update(source_hit_at_5=bool(hit), all_expected_sources_at_5=expected <= returned,
                       expected_source_recall_at_5=len(hit)/len(expected),
                       gold_evidence_recall_at_5=supported/len(case.expected_evidence), reciprocal_rank_at_5=reciprocal)
    def compact(results):
        return [dict(asdict(result),score=round(result.score,12)) for result in results[:5]]
    return dict(case_id=case.id,split=case.split,category=case.category,expected_status=case.expected_status,
                scored_positive=case.must_answer,answer_evaluation='not_run',**metrics,
                lexical_top5=compact(trace.lexical),dense_top5=compact(trace.dense),final_top5=compact(trace.final))


def aggregate(rows):
    positive=[row for row in rows if row['scored_positive']]
    def mean(key):return sum(row[key] for row in positive)/len(positive) if positive else None
    return dict(case_count=len(rows),positive_cases=len(positive),
                source_hit_at_5=mean('source_hit_at_5'),all_expected_sources_at_5=mean('all_expected_sources_at_5'),
                mean_expected_source_recall_at_5=mean('expected_source_recall_at_5'),
                mean_gold_evidence_recall_at_5=mean('gold_evidence_recall_at_5'),mrr_at_5=mean('reciprocal_rank_at_5'))


def run_retrieval_evaluation(root: Path,dataset_path: Path,*,mode='lexical',model_directory: Path|None=None):
    if mode not in ('lexical','dense','hybrid') or (mode=='lexical' and model_directory is not None):
        raise ValueError('Invalid explicit model/mode selection')
    encoder=None
    provenance=None
    if mode!='lexical':
        if model_directory is None:
            raise ValueError('Real local checkpoint required for dense/hybrid evaluation')
        provenance=read_model_provenance(model_directory,require_semantic=True)
        encoder=LocalONNXEncoder(model_directory)
        loaded_provenance=read_model_provenance(model_directory,require_semantic=True,identity=encoder.identity)
        if loaded_provenance!=provenance:
            raise ValueError('Model bundle changed during loading')
        provenance=loaded_provenance
        if encoder.identity.get('kind')!='local_onnx':
            raise ValueError('Test encoders cannot measure semantic quality')
    registry=load_registry((root/'registry.json').read_bytes())
    snapshot=build_snapshot(build_fixture(root,registry,registry.source_snapshot),registry)
    dataset=validate_dataset(dataset_path.read_bytes(),snapshot)
    started=perf_counter()
    lexical=BM25Index(snapshot)
    dense=QdrantIndex(snapshot,encoder) if encoder is not None else None
    service=RetrievalService(SnapshotCatalog(registry))
    try:
        service.publish(IndexSet(snapshot,lexical,dense))
        build_seconds=perf_counter()-started
        rows,latencies=[],[]
        for case in dataset.cases:
            tick=perf_counter()
            # Only question reaches retrieval. Labels are used below, after search.
            trace=service.search(case.question,mode=mode,top_k=5)
            latencies.append(perf_counter()-tick)
            rows.append(score_case(case,snapshot,trace))
        metrics={split:aggregate(rows if split=='all' else [row for row in rows if row['split']==split])
                 for split in ('all','calibration','held_out')}
        return dict(report_kind='synthetic_retrieval_evaluation',schema_version=1,test_only=True,mode=mode,
                    snapshot_id=snapshot.snapshot_id,registry_revision=registry.revision,dataset_revision=dataset.revision,
                    document_count=len(snapshot.documents),chunk_count=len(snapshot.chunks),case_count=len(rows),
                    frozen_configuration=dict(bm25_k1=1.2,bm25_b=0.75,representation=REPRESENTATION_VERSION,
                        channel_limit=40,rrf_k=60,dense_tie_round_decimals=6,
                        lexical_configuration_hash=lexical.descriptor.configuration_hash,
                        dense_configuration_hash=dense.descriptor.configuration_hash if dense else None),
                    embedding=encoder.identity if encoder else None,
                    model_provenance={key:provenance[key] for key in ('bundle_id','model_card_sha256','license_sha256')} if provenance else None,
                    software=dict(qdrant_client=version('qdrant-client'),numpy=version('numpy')),
                    quality_evaluation=dict(lexical='measured' if mode!='dense' else 'not_run',
                        dense='measured' if encoder else 'not_run',hybrid='measured' if mode=='hybrid' else 'not_run',
                        reranking='not_run',grounding='not_run',refusal='not_run'),
                    metrics=metrics,source_hit_target=1.0,
                    source_hit_target_met=metrics['all']['source_hit_at_5']==1.0,
                    failed_source_hit_case_ids=[r['case_id'] for r in rows if r['scored_positive'] and not r['source_hit_at_5']],
                    failed_gold_evidence_case_ids=[r['case_id'] for r in rows if r['scored_positive'] and r['gold_evidence_recall_at_5']<1.0],
                    timing_seconds=dict(index_build=round(build_seconds,6),query_p50=round(median(latencies),6),
                                        query_p95=round(sorted(latencies)[ceil(0.95*len(latencies))-1],6),
                                        note='single CPU process; includes canonical policy validation; no SLA'),cases=rows)
    finally:
        if dense:dense.close()
