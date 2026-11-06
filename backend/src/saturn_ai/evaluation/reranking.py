"""Separate measured reranking experiment. Labels are used only after retrieval."""
from dataclasses import asdict, replace
from importlib.metadata import version
from math import log2, ceil
from pathlib import Path
from statistics import median
from time import perf_counter

from ..ingestion.registry import load_registry
from ..ingestion.pipeline import build_fixture
from ..snapshots import build_snapshot, SnapshotCatalog
from ..retrieval.embeddings import LocalONNXEncoder
from ..retrieval.model_preparation import read_model_provenance
from ..retrieval.reranker_model import load_semantic_reranker
from ..retrieval.contracts import SearchTrace, REPRESENTATION_VERSION
from ..retrieval.lexical import BM25Index
from ..retrieval.dense import QdrantIndex
from ..retrieval.service import RetrievalService, IndexSet
from .dataset import validate_dataset
from .retrieval import score_case, aggregate


def evidence_ndcg(case,snapshot,final):
    # Reuse actual identity/uniqueness/rank/score and top5 validation.
    if not case.must_answer:
        score_case(case,snapshot,SearchTrace(snapshot.snapshot_id,'reranked',(),(),tuple(final)))
        return None
    relevant={c.chunk_id for c in snapshot.chunks if any(
        c.source_id==ev.source_id and c.chunk.field_path==ev.field_path
        and c.chunk.page_start==ev.page and ev.text in c.chunk.text for ev in case.expected_evidence)}
    if not relevant:raise ValueError('Positive nDCG requires gold-supported chunks')
    score_case(case,snapshot,SearchTrace(snapshot.snapshot_id,'reranked',(),(),tuple(final)))
    dcg=sum(1/log2(rank+1) for rank,c in enumerate(final,1) if c.chunk_id in relevant)
    idcg=sum(1/log2(rank+1) for rank in range(1,min(5,len(relevant))+1))
    return dcg/idcg


def pool_metrics(case,candidates):
    if not case.must_answer:return dict(oracle_source_hit_at_30=None,expected_source_coverage_at_30=None)
    expected=set(case.expected_sources);found=expected&{c.source_id for c in candidates}
    return dict(oracle_source_hit_at_30=bool(found),expected_source_coverage_at_30=len(found)/len(expected))


def load_embedding(directory):
    before=read_model_provenance(directory)
    encoder=LocalONNXEncoder(directory)
    after=read_model_provenance(directory,identity=encoder.identity)
    if before!=after:raise ValueError('Embedding bundle changed during loading')
    if encoder.identity['kind']!='local_onnx':raise ValueError('Real embedding checkpoint required')
    return encoder,after


def _aggregate(rows):
    result=aggregate(rows);positive=[r for r in rows if r['scored_positive']]
    for key in ('evidence_ndcg_at_5','oracle_source_hit_at_30','expected_source_coverage_at_30'):
        result[key]=sum(r[key] for r in positive)/len(positive) if positive else None
    return result


def _latency(values):
    return dict(p50=round(median(values),6),p95=round(sorted(values)[ceil(.95*len(values))-1],6))


def run_reranking_evaluation(root:Path,dataset_path:Path,model_directory:Path,reranker_directory:Path):
    scorer,reranker_provenance=load_semantic_reranker(reranker_directory)
    encoder,embedding_provenance=load_embedding(model_directory)
    registry=load_registry((root/'registry.json').read_bytes())
    snapshot=build_snapshot(build_fixture(root,registry,registry.source_snapshot),registry)
    dataset=validate_dataset(dataset_path.read_bytes(),snapshot)
    started=perf_counter();lexical=BM25Index(snapshot);dense=QdrantIndex(snapshot,encoder)
    try:
        service=RetrievalService(SnapshotCatalog(registry));service.publish(IndexSet(snapshot,lexical,dense))
        index_build=perf_counter()-started
        rows=[];baseline_rows=[];latencies=[];scoring_latencies=[]
        for case in dataset.cases:
            tick=perf_counter()
            trace=service.rerank(case.question,scorer,mode='hybrid')
            latencies.append(perf_counter()-tick);scoring_latencies.append(trace.scoring_seconds)
            # Gold scoring starts only after the complete reranking call.
            oracle=pool_metrics(case,trace.input_candidates)
            baseline=score_case(case,snapshot,trace.baseline)
            baseline.update(evidence_ndcg_at_5=evidence_ndcg(case,snapshot,trace.baseline.final),**oracle)
            baseline_rows.append(baseline)
            reranked=SearchTrace(snapshot.snapshot_id,'hybrid',trace.baseline.lexical,trace.baseline.dense,trace.final)
            row=score_case(case,snapshot,reranked)
            row.update(evidence_ndcg_at_5=evidence_ndcg(case,snapshot,trace.final),**oracle,
                       baseline=baseline,input_top30=[asdict(c) for c in trace.input_candidates],
                       scored_survivors=[asdict(c) for c in trace.scored])
            rows.append(row)
        def by_split(items):
            return {split:_aggregate(items if split=='all' else [r for r in items if r['split']==split])
                    for split in ('all','calibration','held_out')}
        metrics=by_split(rows)
        def provenance_id(provenance):
            return {key:provenance[key] for key in ('bundle_id','model_card_sha256','license_sha256')}
        return dict(report_kind='synthetic_reranking_evaluation',schema_version=1,test_only=True,mode='hybrid',
            snapshot_id=snapshot.snapshot_id,registry_revision=registry.revision,dataset_revision=dataset.revision,
            document_count=len(snapshot.documents),chunk_count=len(snapshot.chunks),case_count=len(rows),
            embedding=encoder.identity,reranker=scorer.identity,embedding_provenance=provenance_id(embedding_provenance),
            reranker_provenance=provenance_id(reranker_provenance),
            frozen_configuration=dict(bm25_k1=1.2,bm25_b=.75,representation=REPRESENTATION_VERSION,channel_limit=40,
                rrf_k=60,dense_tie_round_decimals=6,pool_limit=30,final_limit=5,pair_batch_limit=8,
                truncation='longest_first',activation='identity',
                tie_break='descending raw logit, incoming rank, chunk_id',
                ndcg_relevance='binary canonical source/field/page/text; IDCG all relevant snapshot chunks',
                lexical_configuration_hash=lexical.descriptor.configuration_hash,
                dense_configuration_hash=dense.descriptor.configuration_hash),
            software={name:version(name) for name in ('numpy','qdrant-client','onnx','onnxruntime','tokenizers')},
            quality_evaluation=dict(lexical='measured',dense='measured',hybrid='measured',reranking='measured',
                                    grounding='not_run',refusal='not_run'),
            baseline_metrics=by_split(baseline_rows),metrics=metrics,source_hit_target=1.0,
            source_hit_target_met=metrics['all']['source_hit_at_5']==1.0,
            failed_source_hit_case_ids=[r['case_id'] for r in rows if r['scored_positive'] and not r['source_hit_at_5']],
            failed_gold_evidence_case_ids=[r['case_id'] for r in rows if r['scored_positive'] and r['gold_evidence_recall_at_5']<1.0],
            timing_seconds=dict(index_build=round(index_build,6),full_query=_latency(latencies),pair_scoring=_latency(scoring_latencies),
                note='single CPU process including canonical policy revalidation; baseline reuses same pool; no SLA'),
            ram_measurement='not_measured',cases=rows)
    finally:dense.close()
