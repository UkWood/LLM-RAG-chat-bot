"""Open synthetic diagnosis; retrieval scores are distinct from pending human assessment."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from ..publication.extract import PublishedSource
from ..publication.snapshot import PublishedSnapshot,PublishedCatalog
from ..rag.application import Consultant
from ..rag.provider import strict_json,OpenAICompatibleClient,ProviderSettings

ROOT_URL='https://example.invalid/rag-diagnostic/'


def load_fixture(root,dataset_path):
    root=Path(root);raw=Path(dataset_path).read_bytes();data=strict_json(raw)
    if (not isinstance(data,dict) or data.get('schema_version')!=1
            or data.get('scope')!='public_synthetic_open_diagnostic' or not isinstance(data.get('cases'),list)):
        raise ValueError('Invalid diagnostic scope')
    sources=tuple(PublishedSource(ROOT_URL+p.name,p.read_bytes(),'text/html') for p in sorted(root.glob('*.html')))
    snapshot=PublishedSnapshot(sources,'public-synthetic-diagnostic-v1')
    seen=set();cases=[]
    for case in data['cases']:
        if (not isinstance(case,dict) or set(case)!={'id','kind','question','evidence','gaps'}
                or not isinstance(case['id'],str) or case['id'] in seen
                or case['kind'] not in ('full','partial','missing','ambiguous','conflict')
                or not isinstance(case['question'],str) or not 1<=len(case['question'])<=4000
                or not isinstance(case['evidence'],list) or not isinstance(case['gaps'],list)):
            raise ValueError('Invalid diagnostic case')
        seen.add(case['id']);ids=[]
        for evidence in case['evidence']:
            if (not isinstance(evidence,dict) or set(evidence)!={'source','quote'}
                    or not isinstance(evidence['source'],str) or not isinstance(evidence['quote'],str) or not evidence['quote']):
                raise ValueError('Invalid gold pointer')
            found=[c.chunk_id for c in snapshot.chunks if c.source_id==ROOT_URL+evidence['source'] and evidence['quote'] in c.chunk.text]
            if not found:raise ValueError('Gold excerpt not in canonical fixture')
            ids.extend(found)
        ids=tuple(dict.fromkeys(ids))
        if len(ids)>5 or sum(len(c.chunk.text) for c in snapshot.chunks if c.chunk_id in ids)>8000:
            raise ValueError('Oracle exceeds runtime context budget')
        cases.append(dict(case,oracle_ids=ids))
    if Counter(c['kind'] for c in cases)!=dict(full=5,partial=4,missing=3,ambiguous=2,conflict=1):
        raise ValueError('Diagnostic requires frozen 15-case distribution')
    return snapshot,dict(data,cases=cases,dataset_sha256=sha256(raw).hexdigest())


def run_diagnostic(app,dataset,mode,*,public_questions=False):
    if mode not in ('retrieval','oracle','end-to-end'):raise ValueError('Unknown diagnostic mode')
    snapshot=app.service.capture().snapshot;mapping={c.chunk_id:c for c in snapshot.chunks};rows=[]
    failed=False
    for case in dataset['cases']:
        row=dict(case_id=case['id'],kind=case['kind'])
        if failed:
            rows.append(dict(row,status='not_run',reason_code='earlier_infrastructure_error'));continue
        if mode=='retrieval':
            trace=app.service.rerank(case['question'],app.scorer,mode=app.mode)
            pool=tuple(c.chunk_id for c in trace.input_candidates)
            ids=[];length=0
            for c in trace.final:
                text=mapping[c.chunk_id].chunk.text
                if length+len(text)<=8000:ids.append(c.chunk_id);length+=len(text)
            def recall(selected):
                evidence=case['evidence']
                return sum(any(mapping[cid].source_id==ROOT_URL+e['source'] and e['quote'] in mapping[cid].chunk.text
                    for cid in selected) for e in evidence)/len(evidence) if evidence else None
            row.update(pool_ids=pool,context_ids=ids,pool_gold_quote_recall=recall(pool),gold_quote_recall=recall(ids))
        else:
            # Expected facts/gaps never enter generation. Oracle only chooses canonical context IDs.
            answer=app.answer(case['question'],public_question=public_questions,
                context_ids=case['oracle_ids'] if mode=='oracle' else None)
            row['answer']=answer.to_dict()
            if answer.status=='error':
                row['infrastructure_error']=answer.reason_code;failed=True
        rows.append(row)
    recalls=[r['gold_quote_recall'] for r in rows if r.get('gold_quote_recall') is not None]
    return dict(report_kind='public_synthetic_open_rag_diagnostic',schema_version=1,mode=mode,test_only=True,
        identities=dict(snapshot_id=snapshot.snapshot_id,dataset_sha256=dataset['dataset_sha256'],
            provider=app.provider.identity if mode!='retrieval' else None,
            embedding=app.service.capture().dense.encoder.identity if app.service.capture().dense else None,
            reranker=app.scorer.identity if mode!='oracle' else None),
        case_count=len(rows),fixture_review=dataset.get('fixture_review','pending_human'),human_review='pending',
        generation_quality='not_run' if mode=='retrieval' else 'pending_human_review',
        mean_gold_quote_recall=sum(recalls)/len(recalls) if recalls else None,
        infrastructure_errors=sum('infrastructure_error' in r for r in rows),cases=rows)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',required=True,choices=['retrieval','oracle','end-to-end'])
    for name in ('fixture-root','dataset','report'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('model-dir','reranker-dir'):parser.add_argument('--'+name,type=Path)
    for name in ('reviewed-fixtures','allow-cloud','public-questions'):parser.add_argument('--'+name,action='store_true')
    args=parser.parse_args(argv);dense=None
    # No config/body/exception text enters reports. Each invocation is explicit; no live retries.
    report=dict(report_kind='public_synthetic_open_rag_diagnostic',mode=args.mode,status='not_run',
        generation_quality='not_run',human_review='pending',reason_code='diagnostic_setup_required')
    code=2
    try:
        snapshot,dataset=load_fixture(args.fixture_root,args.dataset)
        if args.mode!='retrieval' and not args.reviewed_fixtures:
            report['reason_code']='fixture_review_required'
            raise ValueError()
        provider=None
        if args.mode!='retrieval':
            report['reason_code']='provider_configuration_required'
            provider=OpenAICompatibleClient(ProviderSettings.from_env())
            if provider.remote and not (args.allow_cloud and args.public_questions):
                report['reason_code']='cloud_operator_flags_required'
                raise ValueError()
            dataset=dict(dataset,fixture_review='operator_attested')
        report['reason_code']='diagnostic_setup_required'
        from ..retrieval.lexical import BM25Index
        from ..retrieval.service import RetrievalService,IndexSet
        service=RetrievalService(PublishedCatalog(lambda:{s.url:s.content_hash for s in snapshot.sources},
            cloud_allowed=args.allow_cloud))
        scorer=None
        if args.mode!='oracle':
            report['reason_code']='local_models_required'
            if args.model_dir is None or args.reranker_dir is None:raise ValueError()
            from .reranking import load_embedding
            from ..retrieval.reranker_model import load_semantic_reranker
            from ..retrieval.dense import QdrantIndex
            encoder,_=load_embedding(args.model_dir);scorer,_=load_semantic_reranker(args.reranker_dir)
            dense=QdrantIndex(snapshot,encoder)
            report['reason_code']='diagnostic_setup_required'
        service.publish(IndexSet(snapshot,BM25Index(snapshot),dense))
        app=Consultant(service,scorer,provider)
        report=run_diagnostic(app,dataset,args.mode,public_questions=args.public_questions)
        report['status']='measured' if args.mode=='retrieval' else 'awaiting_human_review'
        code=2 if report['infrastructure_errors'] else 0
    except (ValueError,OSError,TypeError,KeyError):
        # Safe fixed reason; provider configuration and local paths can contain sensitive text.
        pass
    finally:
        if dense:dense.close()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report.get(k) for k in ('status','mode','case_count','generation_quality','human_review','reason_code')},ensure_ascii=False))
    return code

if __name__=='__main__':raise SystemExit(main())
