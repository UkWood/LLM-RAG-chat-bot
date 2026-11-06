"""Typed requirement and canonical output scoring. Labels applied AFTER application output."""
from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import perf_counter
from ..domain import Claim
from ..grounding.contracts import GroundedCitation
from ..grounding.v2_contracts import GroundedResultV2
from ..grounding.projections import build_projections,projection_id,document_kind,norm,selector_matches
from ..grounding.gate_v2 import canonical_reference
from ..grounding.v2_config import load_config


def _scope(p,need,snapshot):
    doc=next(d for d in snapshot.documents if d.source_id==p.source_id)
    record=next(r for r in snapshot.registry.entries if r.source_id==p.source_id)
    return (need['document_kind']=='any' or document_kind(doc,record)==need['document_kind']) and (
        need['representation']=='any' or p.representation==need['representation'])



def _reference_scope(source_id,kind,need,snapshot):
    doc=next(d for d in snapshot.documents if d.source_id==source_id)
    record=next(r for r in snapshot.registry.entries if r.source_id==source_id)
    representation='quoted_statement' if kind=='document' else 'structured_field'
    return (need['document_kind']=='any' or document_kind(doc,record)==need['document_kind']) and (
        need['representation']=='any' or representation==need['representation'])


def _match(p,need,snapshot):
    return (p.entity_id==need['entity_id'] and p.predicate==need['predicate']
            and selector_matches(p,norm(need.get('selector',''))) and p.valid and _scope(p,need,snapshot))


def _output_integrity(result,snapshot):
    mapping={c.chunk_id:c for c in snapshot.chunks};records={r.source_id:r for r in snapshot.registry.entries}
    supported=set();claim_count=len(result.claims);valid=True
    for claim in result.claims:
        if (not isinstance(claim,Claim) or type(claim.chunk_id) is not str or claim.chunk_id not in mapping
                or type(claim.text) is not str or claim.text!=mapping[claim.chunk_id].chunk.text):
            valid=False;continue
        c=mapping[claim.chunk_id];r=records[c.source_id]
        if not all(r.permits(u,c.source_hash,c.source_commit) for u in ('local_index','local_generate')):valid=False;continue
        if claim.chunk_id in supported:valid=False
        supported.add(claim.chunk_id)
    cites={}
    for citation in result.sources:
        if not isinstance(citation,GroundedCitation) or citation.chunk_id not in mapping:valid=False;continue
        c=mapping[citation.chunk_id];r=records[c.source_id]
        expected=GroundedCitation(c.chunk_id,c.source_id,r.title,r.url or r.canonical_path,c.chunk.document_id,
            c.source_hash,c.source_commit,c.chunk.heading_path,c.chunk.page_start,c.chunk.page_end)
        if citation!=expected or citation.chunk_id in cites:valid=False
        if not all(r.permits(u,c.source_hash,c.source_commit) for u in ('local_index','local_generate')):valid=False
        cites[citation.chunk_id]=citation
    if not supported<=set(cites):valid=False
    refs=[]
    for ref in getattr(result,'references',()):
        try:
            if canonical_reference(ref.kind,ref.entity_id,ref.source_id,ref.anchor_chunk_id,snapshot)!=ref:valid=False
            if ref.anchor_chunk_id not in cites:valid=False
            refs.append(ref)
        except (ValueError,KeyError,AttributeError):valid=False
    if result.status=='answered' and not (result.claims or refs):valid=False
    if result.status!='answered' and (result.claims or result.sources or refs):valid=False
    return valid,supported,cites,refs,claim_count


def score_v2_case(case,snapshot,result):
    if (result.snapshot_id!=snapshot.snapshot_id and not (result.status=='error' and result.snapshot_id=='')) or result.status not in ('answered','refused','clarification','error'):
        raise ValueError('Comparison result identity/status mismatch')
    valid,supported,cites,refs,claim_count=_output_integrity(result,snapshot)
    projections=build_projections(snapshot);by_id={projection_id(p):p for p in projections}
    mapping={c.chunk_id:c for c in snapshot.chunks};docs={d.source_id:d for d in snapshot.documents}
    records={r.source_id:r for r in snapshot.registry.entries}
    available=[];binding_valid=True
    if isinstance(result,GroundedResultV2) and result.status=='answered':
        if result.plan is None or len(result.bindings)!=len(result.plan.needs):binding_valid=False
        else:
            indexes=set()
            for binding in result.bindings:
                if binding.need_index in indexes or not 0<=binding.need_index<len(result.plan.needs):binding_valid=False;continue
                indexes.add(binding.need_index);need=result.plan.needs[binding.need_index]
                for pid in binding.projection_ids:
                    p=by_id.get(pid)
                    if (p is None or p.entity_id!=need.entity_id or p.predicate!=need.predicate or not selector_matches(p,need.selector)
                            or not _scope(p,dict(document_kind=need.constraints.document_kind,representation=need.constraints.representation),snapshot)
                            or not p.valid or not {s.chunk_id for s in p.spans if s.role=='value'}<=supported):
                        binding_valid=False;continue
                    available.append(p)
                if binding.reference is not None:
                    ref=binding.reference
                    expected_pred='document_reference' if ref.kind=='document' else 'entity_type'
                    if (ref not in refs or ref.entity_id!=need.entity_id or need.predicate!=expected_pred
                            or not _reference_scope(ref.source_id,ref.kind,dict(document_kind=need.constraints.document_kind,representation=need.constraints.representation),snapshot)):
                        binding_valid=False
            if indexes!=set(range(len(result.plan.needs))):binding_valid=False
    else:
        available=[p for p in projections if p.valid and {s.chunk_id for s in p.spans if s.role=='value'}<=supported]
    needs=case.get('requirements',[]);correct=[];gold_total=0;gold_hit=0
    for need in needs:
        evidence=need.get('evidence',[]);ref=need.get('reference')
        for e in evidence:
            gold_total+=1
            if any(mapping[cid].source_id==e['source_id'] and mapping[cid].chunk.field_path==e['field_path']
                   and mapping[cid].chunk.page_start==e['page'] and e['text'] in mapping[cid].chunk.text for cid in supported):gold_hit+=1
        if ref is not None:
            matched=False
            for r in refs:
                if (r.kind==ref['kind'] and r.entity_id==need['entity_id'] and r.source_id==ref['source_id'] and r.value==ref['value'] and _reference_scope(r.source_id,r.kind,need,snapshot)):matched=True
            if ref['kind']=='document' and not isinstance(result,GroundedResultV2):
                # Same document-reference rubric for v1 actual canonical manual citations.
                for citation in cites.values():
                    if (citation.source_id==ref['source_id'] and records[citation.source_id].document_type=='manual'
                            and entity_id_normalized(docs[citation.source_id])==need['entity_id']
                            and citation.title==ref['value'] and _reference_scope(citation.source_id,'document',need,snapshot)):matched=True
            correct.append(bool(matched and valid and binding_valid));continue
        gold_projections=[p for p in projections if _match(p,need,snapshot) and any(
            mapping[s.chunk_id].source_id==e['source_id'] and mapping[s.chunk_id].chunk.field_path==e['field_path']
            and mapping[s.chunk_id].chunk.page_start==e['page'] and e['text'] in mapping[s.chunk_id].chunk.text
            for s in p.spans for e in evidence)]
        def complete(p):return p.complete or (need['representation']=='markdown_table' and p.complete_for_source)
        complete_groups={}
        for p in projections:
            if _match(p,need,snapshot) and complete(p):complete_groups.setdefault(p.group_id,set()).add((p.value,p.unit))
        group_ids={p.group_id for p in gold_projections}
        gold_values={(p.value,p.unit) for p in projections if p.group_id in group_ids and p.valid}
        sets=list(complete_groups.values())
        expected=sets[0] if sets and all(v==sets[0] for v in sets) else set()
        if not gold_values<=expected:expected=set()
        returned={(p.value,p.unit) for p in available if _match(p,need,snapshot) and complete(p)}
        correct.append(bool(expected and returned==expected and valid and binding_valid))
    answered=result.status=='answered'
    fully=bool(result.status==case['expected_status'] and valid and binding_valid and
               (not answered or needs and all(correct)))
    return dict(case_id=case['id'],group=case.get('group','legacy'),expected_status=case['expected_status'],status=result.status,
        reason_code=result.reason_code,fully_correct=fully,status_correct=result.status==case['expected_status'],
        requirement_count=len(needs),correct_requirements=sum(correct),requirement_coverage=sum(correct)/len(needs) if needs else None,
        gold_pointer_coverage=gold_hit/gold_total if gold_total else None,claim_count=claim_count,supported_claim_count=len(supported),
        canonical_output_valid=valid and binding_valid,unsafe_answer=answered and not fully,
        evidence_ids=list(supported),reference_sources=[r.source_id for r in refs])


def entity_id_normalized(doc):return doc.entity_id.removeprefix('synthetic:')


def aggregate_v2(rows):
    positive=[r for r in rows if r['expected_status']=='answered'];negative=[r for r in rows if r['expected_status']!='answered']
    def rate(items,fn):return sum(fn(r) for r in items)/len(items) if items else None
    claims=sum(r['claim_count'] for r in rows);supported=sum(r['supported_claim_count'] for r in rows)
    return dict(case_count=len(rows),positive_cases=len(positive),negative_cases=len(negative),errors=sum(r['status']=='error' for r in rows),
        fully_correct_rate=rate(rows,lambda r:r['fully_correct']),positive_fully_correct=rate(positive,lambda r:r['fully_correct']),
        negative_fully_correct=rate(negative,lambda r:r['fully_correct']),positive_answer_rate=rate(positive,lambda r:r['status']=='answered'),
        false_refusal_rate=rate(positive,lambda r:r['status']=='refused'),false_clarification_rate=rate(positive,lambda r:r['status']=='clarification'),
        mean_requirement_coverage=rate(positive,lambda r:r['requirement_coverage'] or 0),
        unsafe_answers=sum(r['unsafe_answer'] for r in rows),canonical_output_validity=rate(rows,lambda r:r['canonical_output_valid']),
        verbatim_claim_support_rate=supported/claims if claims else None)


def _context(root,model_directory,reranker_directory):
    from ..ingestion.registry import load_registry
    from ..ingestion.pipeline import build_fixture
    from ..snapshots import build_snapshot,SnapshotCatalog
    from ..retrieval.lexical import BM25Index
    from ..retrieval.dense import QdrantIndex
    from ..retrieval.service import RetrievalService,IndexSet
    from ..retrieval.reranker_model import load_semantic_reranker
    from .reranking import load_embedding
    scorer,rp=load_semantic_reranker(reranker_directory);encoder,ep=load_embedding(model_directory)
    registry=load_registry((root/'registry.json').read_bytes());snapshot=build_snapshot(build_fixture(root,registry,registry.source_snapshot),registry)
    dense=QdrantIndex(snapshot,encoder);service=RetrievalService(SnapshotCatalog(registry));service.publish(IndexSet(snapshot,BM25Index(snapshot),dense))
    return snapshot,service,scorer,dense,dict(embedding=encoder.identity,reranker=scorer.identity,
        embedding_bundle_id=ep['bundle_id'],reranker_bundle_id=rp['bundle_id'])


def _apps(service,scorer):
    from ..providers import FakeLLMProvider
    from ..grounding.application import GroundedConsultant
    from ..grounding.application_v2 import GroundedConsultantV2
    return {'v1':GroundedConsultant(service,scorer,FakeLLMProvider()),'v2':GroundedConsultantV2(service,scorer,FakeLLMProvider())}


def run_calibration_comparison(root,dataset_path,model_directory,reranker_directory):
    from .dataset import validate_dataset
    from .grounding import score_grounded_result
    from ..grounding.contracts import GroundedResult
    snapshot,service,scorer,dense,identity=_context(root,model_directory,reranker_directory)
    try:
        dataset=validate_dataset(dataset_path.read_bytes(),snapshot)
        cases=[c for c in dataset.cases if c.split=='calibration'];apps=_apps(service,scorer);rows=[]
        for case in cases:
            row={'case_id':case.id,'expected_status':case.expected_status,'positive':case.must_answer}
            for name,app in apps.items():
                result=app.answer(case.question)
                # Preserve original exact quotation/gold-pointer rubric; references do not become fake quotes.
                legacy=GroundedResult(result.status,result.gate_state,result.reason_code,result.snapshot_id,result.claims,
                    tuple(c for c in result.sources if c.chunk_id in {q.chunk_id for q in result.claims}))
                scored=score_grounded_result(case,snapshot,legacy)
                valid,_,_,_,_=_output_integrity(result,snapshot)
                row[name]=dict(status=result.status,reason_code=result.reason_code,status_correct=result.status==case.expected_status,
                    canonical_output_valid=valid,strict_expected_evidence_recall=scored['expected_evidence_recall'],
                    reference_count=len(getattr(result,'references',())))
            rows.append(row)
        positives=[r for r in rows if r['positive']]
        metrics={name:dict(positive_answered=sum(r[name]['status']=='answered' for r in positives),positive_cases=len(positives),
            expected_status_correct=sum(r[name]['status_correct'] for r in rows),case_count=len(rows),
            strict_expected_evidence_recall=sum(r[name]['strict_expected_evidence_recall'] for r in positives)/len(positives),
            canonical_output_validity=sum(r[name]['canonical_output_valid'] for r in rows)/len(rows)) for name in apps}
        regression=[r['case_id'] for r in positives if r['v1']['status']=='answered' and r['v2']['status']!='answered']
        return dict(report_kind='planner_v2_calibration_comparison',schema_version=1,test_only=True,
            snapshot_id=snapshot.snapshot_id,dataset_revision=dataset.revision,config_revision=load_config()[1],**identity,
            selection='legacy calibration only; exposed held_out not executed',rubric='original strict pointers, reference correctness separate',
            metrics=metrics,legacy_positive_regression_ids=regression,no_positive_regression=not regression,cases=rows)
    finally:dense.close()


def _sha(path):return sha256(Path(path).read_bytes()).hexdigest()


def _git_root():return Path(__file__).resolve().parents[4]


def _git(*args):
    return subprocess.check_output(['git',*args],cwd=_git_root(),text=True).strip()


def create_freeze(dataset_path,model_directory,reranker_directory,freeze_path):
    if _git('status','--porcelain','--untracked-files=all'):raise ValueError('Freeze requires clean committed tree')
    manifest_path=dataset_path.with_name(dataset_path.stem+'.manifest.json')
    # Hash/counts only before freeze: payload not parsed here.
    manifest=json.loads(manifest_path.read_text());digest=_sha(dataset_path)
    if digest!=manifest['dataset_sha256']:raise ValueError('Blind dataset identity mismatch')
    if (_git_root()/'evaluation/experiments'/f'{digest}.START.json').exists():
        raise ValueError('Blind dataset already consumed')
    data=dict(schema_version=1,source_commit=_git('rev-parse','HEAD'),config_sha256=_sha(_git_root()/'config/planner-v2.json'),
        projection_sha256=_sha(_git_root()/'backend/src/saturn_ai/grounding/projections.py'),dataset_sha256=digest,
        author_manifest_sha256=_sha(manifest_path),model_manifest_sha256=_sha(model_directory/'manifest.json'),
        reranker_manifest_sha256=_sha(reranker_directory/'manifest.json'),snapshot_id=manifest['snapshot_id'],
        protocol='pre-implementation independent author/review; first blind run only after this freeze')
    freeze_path.parent.mkdir(parents=True,exist_ok=True)
    with freeze_path.open('x') as f:json.dump(data,f,indent=2)
    return data


def run_blind_comparison(root,dataset_path,model_directory,reranker_directory,freeze_path,report_path):
    from datetime import datetime,timezone
    from .blind_dataset import validate_blind
    freeze=json.loads(freeze_path.read_text());manifest_path=dataset_path.with_name(dataset_path.stem+'.manifest.json')
    if (_git('status','--porcelain','--untracked-files=all') or _git('rev-parse','HEAD')!=freeze['source_commit']
            or _sha(_git_root()/'config/planner-v2.json')!=freeze['config_sha256']
            or _sha(_git_root()/'backend/src/saturn_ai/grounding/projections.py')!=freeze['projection_sha256']
            or _sha(dataset_path)!=freeze['dataset_sha256'] or _sha(manifest_path)!=freeze['author_manifest_sha256']
            or _sha(model_directory/'manifest.json')!=freeze['model_manifest_sha256']
            or _sha(reranker_directory/'manifest.json')!=freeze['reranker_manifest_sha256']):
        raise ValueError('Frozen code/config/dataset/artifact identity changed')
    if report_path.exists():raise ValueError('First-run report already exists')
    report_path.parent.mkdir(parents=True,exist_ok=True)
    start_path=_git_root()/'evaluation/experiments'/f'{freeze["dataset_sha256"]}.START.json'
    start_path.parent.mkdir(parents=True,exist_ok=True)
    with start_path.open('x') as f:json.dump(dict(state='started',utc=datetime.now(timezone.utc).isoformat(),**freeze),f,indent=2)
    # START is durable and exclusive BEFORE parsing any blind questions/labels. Failure consumes this set.
    dense=None;rows=[];phase='model_setup';attempts=0
    try:
        snapshot,service,scorer,dense,identity=_context(root,model_directory,reranker_directory)
        phase='dataset_validation'
        if snapshot.snapshot_id!=freeze['snapshot_id']:raise ValueError('Frozen snapshot mismatch')
        cases=validate_blind(dataset_path.read_bytes(),snapshot);apps=_apps(service,scorer);rows=[]
        phase='evaluation'
        for case in cases:
            row={'case_id':case['id'],'group':case['group']};rows.append(row)
            for name,app in apps.items():
                attempts+=1
                result=app.answer(case['question'])
                row[name]=score_v2_case(case,snapshot,result)
        metrics={name:aggregate_v2([r[name] for r in rows]) for name in apps}
        experiment_valid=all(m['errors']==0 for m in metrics.values())
        target=experiment_valid and metrics['v2']['fully_correct_rate']==1.0 and metrics['v2']['unsafe_answers']==0 and metrics['v2']['canonical_output_validity']==1.0
        report=dict(report_kind='planner_v2_first_blind_comparison',schema_version=1,test_only=True,freeze=freeze,
            experiment_valid=experiment_valid,unexecuted_cases=0,attempted_system_runs=attempts,
            snapshot_id=snapshot.snapshot_id,dataset_sha256=freeze['dataset_sha256'],**identity,config_revision=load_config()[1],
            selection='independently authored/reviewed40case set; first evaluation after freeze; no subsequent tuning',
            metrics=metrics,new_quality_target_met=target,full_prototype_accepted=False,
            default_enabled=False,quality_evaluation=dict(structured_requirement_binding='measured',reference_correctness='measured',
                exact_quote_support='measured',natural_language_entailment='not_run',real_sample='not_run'),cases=rows)
        report_path.parent.mkdir(parents=True,exist_ok=True)
        with report_path.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
        return report
    except Exception as exc:
        failure=dict(report_kind='planner_v2_first_blind_comparison',schema_version=1,test_only=True,
            freeze=freeze,experiment_valid=False,new_quality_target_met=False,full_prototype_accepted=False,
            default_enabled=False,failure_phase=phase,failure_type=type(exc).__name__,
            completed_cases=sum(all(name in row for name in ('v1','v2')) for row in rows),
            unexecuted_cases=40-len(rows),attempted_system_runs=attempts,cases=rows)
        # Retain partial rows and the consumed receipt even if setup/scoring fails.
        outcome=report_path if not report_path.exists() else start_path.with_name(start_path.name.replace('START','FAILED'))
        with outcome.open('x') as f:json.dump(failure,f,ensure_ascii=False,indent=2)
        raise ValueError('Blind attempt consumed; invalid outcome persisted') from exc
    finally:
        if dense is not None:dense.close()
