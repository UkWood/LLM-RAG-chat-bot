"""Captured per-need search, deterministic bounded pool and one pair-scoring pass."""
from dataclasses import replace
import json
from time import perf_counter
from ..retrieval.contracts import passage_text
from ..retrieval.reranking import checked_scores,validate_pairs
from .v3_config import load_v3_config
from .evidence_v3 import validate_plan,validate_pool


def retrieve_v3(service,indexes,plan,question,scorer,*,mode='hybrid'):
    validate_plan(plan);cfg,_=load_v3_config();snapshot=indexes.snapshot;per_need=[]
    for need in plan.needs:
        query=need.entity_id.split('/')[-1].upper()+' '+cfg['descriptions'].get(need.predicate,'Именованная характеристика')+' '+need.selector
        if need.constraints.document_kind!='any':query+=' '+('руководство manual' if need.constraints.document_kind=='manual' else 'карточка')
        if need.constraints.representation=='markdown_table':query+=' таблица'
        trace=service._search(indexes,query,mode=mode,top_k=10)
        if trace.snapshot_id!=snapshot.snapshot_id:raise ValueError('Mixed captured V3 search')
        validate_pool(snapshot,trace.final);per_need.append(trace.final)
    allowed={c.chunk_id for c in service.catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
    pool=[];seen=set();all_ids={c.chunk_id for row in per_need for c in row if c.chunk_id in allowed}
    for rank in range(10):
        for row in per_need:
            if rank<len(row) and row[rank].chunk_id in allowed and row[rank].chunk_id not in seen and len(pool)<30:
                seen.add(row[rank].chunk_id);pool.append(replace(row[rank],rank=len(pool)+1,channel='need_pool'))
    pool=tuple(pool);mapping=validate_pool(snapshot,pool)
    passages=[passage_text(snapshot,mapping[c.chunk_id]) for c in pool];validate_pairs(question,passages)
    identity=json.loads(json.dumps(scorer.identity,allow_nan=False));start=perf_counter()
    scores=checked_scores(scorer.score_pairs(question,passages),len(pool)) if pool else []
    if scorer.identity!=identity:raise ValueError('Retrieval scorer identity drift')
    elapsed=perf_counter()-start
    allowed={c.chunk_id for c in service.catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
    ordered=sorted(((c,float(s)) for c,s in zip(pool,scores) if c.chunk_id in allowed),key=lambda pair:(-pair[1],pair[0].rank,pair[0].chunk_id))
    ranked=tuple(replace(c,score=score,rank=i,channel='need_reranker') for i,(c,score) in enumerate(ordered,1))
    return ranked,dict(search_count=len(per_need),per_need_ids=[[c.chunk_id for c in row] for row in per_need],
        pool_ids=[c.chunk_id for c in ranked],pool_trimmed=len(all_ids)>30,global_top5=[c.chunk_id for c in ranked[:5]],
        pairs_scored=len(passages),scoring_seconds=elapsed,scorer_identity=identity)
