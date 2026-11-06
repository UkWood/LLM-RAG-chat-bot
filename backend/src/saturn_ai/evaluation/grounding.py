"""Answer/refusal measurement; gold labels never enter the grounded application."""
from importlib.metadata import version
from time import perf_counter
from ..domain import Claim
from ..grounding.contracts import GroundedCitation,GroundedResult
from ..grounding.application import GroundedConsultant
from ..providers import FakeLLMProvider
from ..ingestion.registry import load_registry
from ..ingestion.pipeline import build_fixture
from ..snapshots import build_snapshot,SnapshotCatalog
from ..retrieval.lexical import BM25Index
from ..retrieval.dense import QdrantIndex
from ..retrieval.service import RetrievalService,IndexSet
from ..retrieval.reranker_model import load_semantic_reranker
from .reranking import load_embedding,_latency
from .dataset import validate_dataset


def score_grounded_result(case,snapshot,result):
    if (not isinstance(result,GroundedResult) or result.snapshot_id!=snapshot.snapshot_id
            or result.status not in ('answered','refused','clarification','error')):
        raise ValueError('Invalid grounded result identity/status')
    mapping={c.chunk_id:c for c in snapshot.chunks};records={r.source_id:r for r in snapshot.registry.entries}
    supported=set();count=0
    for claim in result.claims:
        if (isinstance(claim,Claim) and type(claim.chunk_id) is str and claim.chunk_id in mapping
                and claim.text==mapping[claim.chunk_id].chunk.text):
            c=mapping[claim.chunk_id];r=records[c.source_id]
            if r.permits('local_generate',c.source_hash,c.source_commit) and r.permits('local_index',c.source_hash,c.source_commit):
                supported.add(claim.chunk_id);count+=1
    if len(supported)!=len(result.claims):count=len(supported) if len(supported)<len(result.claims) else count
    citation_valid=None
    if result.status=='answered':
        citation_valid=bool(result.claims) and len(result.sources)==len(result.claims)
        claim_ids=[c.chunk_id for c in result.claims if isinstance(c,Claim)]
        source_ids=[]
        for citation in result.sources:
            if not isinstance(citation,GroundedCitation) or citation.chunk_id not in mapping:
                citation_valid=False;continue
            c=mapping[citation.chunk_id];r=records[c.source_id]
            expected=GroundedCitation(c.chunk_id,c.source_id,r.title,r.url or r.canonical_path,c.chunk.document_id,
                c.source_hash,c.source_commit,c.chunk.heading_path,c.chunk.page_start,c.chunk.page_end)
            if citation!=expected:citation_valid=False
            source_ids.append(citation.chunk_id)
        citation_valid=bool(citation_valid and len(set(claim_ids))==len(claim_ids) and source_ids==claim_ids)
    recall=None
    if case.must_answer:
        coverage=sum(any(mapping[cid].source_id==e.source_id and mapping[cid].chunk.field_path==e.field_path
                         and mapping[cid].chunk.page_start==e.page and e.text in mapping[cid].chunk.text for cid in supported)
                     for e in case.expected_evidence) if result.status=='answered' else 0
        recall=coverage/len(case.expected_evidence)
    return dict(case_id=case.id,split=case.split,category=case.category,expected_status=case.expected_status,
        must_answer=case.must_answer,must_refuse=case.must_refuse,status=result.status,gate_state=result.gate_state,
        reason_code=result.reason_code,status_correct=result.status==case.expected_status,
        expected_evidence_recall=recall,claim_count=len(result.claims),supported_claim_count=count,
        citation_valid=citation_valid,evidence_ids=[c.chunk_id for c in result.claims],
        source_ids=[c.source_id for c in result.sources],
        citation_pages=[dict(chunk_id=c.chunk_id,page_start=c.page_start,page_end=c.page_end) for c in result.sources])


def aggregate_grounding(rows):
    positives=[r for r in rows if r['must_answer']];refusals=[r for r in rows if r['must_refuse']]
    clarifications=[r for r in rows if r['expected_status']=='clarification'];answered=[r for r in rows if r['status']=='answered']
    def rate(items,predicate):return sum(predicate(r) for r in items)/len(items) if items else None
    claims=sum(r['claim_count'] for r in rows);supported=sum(r['supported_claim_count'] for r in rows)
    return dict(case_count=len(rows),positive_cases=len(positives),must_refuse_cases=len(refusals),
        clarification_cases=len(clarifications),answered_cases=len(answered),errors=sum(r['status']=='error' for r in rows),
        expected_status_accuracy=rate(rows,lambda r:r['status_correct']),
        positive_answer_rate=rate(positives,lambda r:r['status']=='answered'),
        false_refusal_rate=rate(positives,lambda r:r['status']=='refused'),
        false_clarification_rate=rate(positives,lambda r:r['status']=='clarification'),
        proper_refusal_rate=rate(refusals,lambda r:r['status']=='refused'),
        proper_clarification_rate=rate(clarifications,lambda r:r['status']=='clarification'),
        mean_expected_evidence_recall=sum(r['expected_evidence_recall'] for r in positives)/len(positives) if positives else None,
        verbatim_claim_support_rate=supported/claims if claims else None,
        canonical_citation_validity=rate(answered,lambda r:r['citation_valid']),
        unsupported_claim_count=claims-supported)


def run_grounding_evaluation(root,dataset_path,model_directory,reranker_directory):
    scorer,reranker_provenance=load_semantic_reranker(reranker_directory)
    encoder,embedding_provenance=load_embedding(model_directory)
    registry=load_registry((root/'registry.json').read_bytes());snapshot=build_snapshot(build_fixture(root,registry,registry.source_snapshot),registry)
    dataset=validate_dataset(dataset_path.read_bytes(),snapshot)
    started=perf_counter();lexical=BM25Index(snapshot);dense=QdrantIndex(snapshot,encoder)
    try:
        service=RetrievalService(SnapshotCatalog(registry));service.publish(IndexSet(snapshot,lexical,dense))
        index_build=perf_counter()-started;provider=FakeLLMProvider();app=GroundedConsultant(service,scorer,provider)
        rows=[];latencies=[]
        for case in dataset.cases:
            calls=len(provider.calls);tick=perf_counter()
            result=app.answer(case.question)
            latencies.append(perf_counter()-tick)
            # Only the question enters app. All gold data is applied after response.
            row=score_grounded_result(case,snapshot,result);row['provider_called']=len(provider.calls)>calls;rows.append(row)
        metrics={split:aggregate_grounding(rows if split=='all' else [r for r in rows if r['split']==split])
                 for split in ('all','calibration','held_out')}
        all_metrics=metrics['all']
        target_met=all(all_metrics[k]==1.0 for k in ('expected_status_accuracy','positive_answer_rate',
             'mean_expected_evidence_recall','verbatim_claim_support_rate','canonical_citation_validity'))
        def provenance(p):return {k:p[k] for k in ('bundle_id','model_card_sha256','license_sha256')}
        return dict(report_kind='synthetic_grounding_evaluation',schema_version=1,test_only=True,
            snapshot_id=snapshot.snapshot_id,registry_revision=registry.revision,dataset_revision=dataset.revision,
            document_count=len(snapshot.documents),chunk_count=len(snapshot.chunks),case_count=len(rows),
            embedding=encoder.identity,reranker=scorer.identity,embedding_provenance=provenance(embedding_provenance),
            reranker_provenance=provenance(reranker_provenance),provider=dict(kind='offline_fake',revision='verbatim-v1'),
            frozen_configuration=dict(mode='hybrid',channel_limit=40,rrf_k=60,pool_limit=30,top_k=5,
                grammar='single-entity-structured-field-or-manual-v1',evidence_max_chars=8000,claim_support='exact canonical quote'),
            quality_evaluation=dict(grounded_pipeline='measured',refusal='measured_on_synthetic',
                canonical_citations='measured',verbatim_claim_support='measured',natural_language_entailment='not_run',
                free_engineering_consultation='not_run',real_sample='not_run'),metrics=metrics,
            grounding_target_met=target_met,full_prototype_accepted=False,
            failed_case_ids=[r['case_id'] for r in rows if not r['status_correct'] or (r['must_answer'] and r['expected_evidence_recall']<1.0)],
            software={n:version(n) for n in ('numpy','qdrant-client','onnx','onnxruntime','tokenizers')},
            timing_seconds=dict(index_build=round(index_build,6),query=_latency(latencies),note='single CPU process; no SLA'),cases=rows)
    finally:dense.close()
