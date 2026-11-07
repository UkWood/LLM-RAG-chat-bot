"""Calibration feasibility and a single immutable V2/V3 blinded comparison."""
from dataclasses import replace
from hashlib import sha256
import json,math,statistics,subprocess
from pathlib import Path
from time import perf_counter
from ..providers import FakeLLMProvider
from ..grounding.application_v2 import GroundedConsultantV2
from ..grounding.application_v3 import GroundedConsultantV3
from ..grounding.application import GroundedConsultant
from ..grounding.router_v3 import IntentRouter
from ..grounding.v3_contracts import ResultV3
from ..grounding.v3_config import load_v3_config,checked_settings,revision
from .planner_v2 import score_v2_case,aggregate_v2,_context,_output_integrity
from .v3_dataset import validate_v3


def _need_key(n):
    if not isinstance(n,dict):
        e,p,s=n.entity_id,n.predicate,n.selector;k=n.constraints.document_kind;r=n.constraints.representation
    else:e,p,s,k,r=(n[x] for x in ('entity_id','predicate','selector','document_kind','representation'))
    if p=='document_reference':k='manual';r='quoted_statement'
    if p=='entity_type':r='structured_field'
    return e,p,s,k,r


def score_v3_case(case,snapshot,result):
    row=score_v2_case(case,snapshot,result)
    positive=case['expected_status']=='answered'
    plan=getattr(result,'plan',None)
    correct=bool(plan is not None and sorted(_need_key(n) for n in plan.needs)==sorted(_need_key(n) for n in case['requirements'])) if positive else None
    row.update(plan_correct=correct)
    if result.status=='answered' and positive:
        row['fully_correct']=row['fully_correct'] and correct
        row['unsafe_answer']=not row['fully_correct']
    trace=getattr(result,'trace',{})
    row.update(intent_pairs=trace.get('intent_pairs',0),retrieval_pairs=trace.get('pairs_scored'),search_count=trace.get('search_count'))
    mapping={c.chunk_id:c for c in snapshot.chunks};pool=set(trace.get('pool_ids',[]));hit=total=0
    for n in case['requirements']:
        for e in n['evidence']:
            total+=1
            if any(cid in mapping and mapping[cid].source_id==e['source_id'] and mapping[cid].chunk.field_path==e['field_path'] and mapping[cid].chunk.page_start==e['page'] and e['text'] in mapping[cid].chunk.text for cid in pool):hit+=1
    row['pool_gold_pointer_recall']=hit/total if total and 'pool_ids' in trace else None
    return row


def legacy_answer_correct(case,snapshot,result):
    """Grade V1-supported questions against original gold and equivalent complete facts."""
    from ..grounding.gate import plan_question
    from ..grounding.contracts import QuestionPlan
    if result.status!='answered' or not case.must_answer:return False
    legacy=plan_question(case.question,snapshot)
    if not isinstance(legacy,QuestionPlan):return False
    reference=None;predicate=legacy.aspect
    if predicate=='manual':
        manuals=[r for r in snapshot.registry.entries if r.source_id in case.expected_sources and r.document_type=='manual']
        if len(manuals)!=1:return False
        record=manuals[0];predicate='document_reference'
        reference=dict(kind='document',source_id=record.source_id,value=record.title)
    need=dict(entity_id=legacy.entity_id,predicate=predicate,selector='',document_kind='any',representation='any',
        reference=reference,evidence=[dict(source_id=e.source_id,field_path=e.field_path,page=e.page,text=e.text) for e in case.expected_evidence])
    gold=dict(id=case.id,expected_status='answered',requirements=[need])
    return score_v2_case(gold,snapshot,result)['fully_correct']


def metrics(rows):
    m=aggregate_v2(rows);pos=[r for r in rows if r['expected_status']=='answered']
    m['plan_accuracy']=sum(r.get('plan_correct') is True for r in pos)/len(pos) if pos else None
    return m


def project_threshold_result(base,frames,settings):
    settings=checked_settings(settings)
    if base.status=='error':return base
    for frame in frames:
        scores=sorted(frame['scores'],reverse=True)
        if not scores or any(not math.isfinite(s) for s in scores):return base
        best=scores[0];second=scores[1] if len(scores)>1 else best-100;gap=best-second
        state=reason=None
        if best<settings['score_min']:state,reason='refused','unknown_predicate'
        elif gap<=0 or gap<settings['margin_min']:
            state,reason=('clarification','ambiguous_predicate') if second>=settings['score_min'] else ('refused','unknown_predicate')
        if state:return ResultV3(state,'ambiguous' if state=='clarification' else 'insufficient',reason,base.snapshot_id,trace=dict(base.trace))
    return replace(base,plan=replace(base.plan,planner_revision=revision(settings))) if base.plan is not None else base


def choose_configuration(grid,baseline):
    floor=sum(r['fully_correct'] for r in baseline if r['expected_status']=='answered');valid=[]
    for trial in grid:
        rows=trial['rows'];positives=sum(r['fully_correct'] for r in rows if r['expected_status']=='answered')
        if (len(rows)!=len(baseline) or [(r.get('case_id'),r['expected_status']) for r in rows]!=[(r.get('case_id'),r['expected_status']) for r in baseline]
                or not rows or trial['legacy_regression_ids'] or positives<=floor or any(r['status']=='error' or r['unsafe_answer'] or not r['canonical_output_valid'] for r in rows)
                or any(not r['fully_correct'] for r in rows if r['expected_status']!='answered')):continue
        valid.append(trial)
    return min(valid,key=lambda t:(-sum(r['fully_correct'] for r in t['rows'] if r['expected_status']=='answered'),
        sum(r['status']=='answered' for r in t['rows']),-t['settings']['score_min'],-t['settings']['margin_min'])) if valid else None


def _root():return Path(__file__).resolve().parents[4]
def _git(*args):return subprocess.check_output(['git',*args],cwd=_root(),text=True).strip()
def _sha(p):return sha256(Path(p).read_bytes()).hexdigest()
def _runtime_sha():
    names=_git('ls-files','--','backend/src','config','backend/requirements.lock','backend/requirements-onnx.lock').splitlines()
    return revision({n:_sha(_root()/n) for n in names})

class RecordingScorer:
    def __init__(self,scorer):self.scorer=scorer;self.frames=[]
    @property
    def identity(self):return self.scorer.identity
    def pair_lengths(self,q,p):return self.scorer.pair_lengths(q,p)
    def score_pairs(self,q,p):
        scores=self.scorer.score_pairs(q,p);self.frames.append(dict(scores=list(scores)));return scores


def run_v3_calibration(corpus,dataset_path,model_directory,reranker_directory):
    from .dataset import validate_dataset
    if _git('status','--porcelain','--untracked-files=all'):raise ValueError('Calibration requires committed code/catalogue')
    runtime=_runtime_sha();commit=_git('rev-parse','HEAD');cfg,_=load_v3_config();low=dict(cfg,score_min=float(min(cfg['score_grid'])),margin_min=float(min(cfg['margin_grid'])))
    start=perf_counter();snapshot,service,scorer,dense,identity=_context(corpus,model_directory,reranker_directory);setup=perf_counter()-start
    try:
        cases=validate_v3(dataset_path.read_bytes(),snapshot,'calibration')
        old_path=_root()/'evaluation/datasets/synthetic-v1.json';old=validate_dataset(old_path.read_bytes(),snapshot)
        legacy=[c for c in old.cases if c.split=='calibration']
        recording=RecordingScorer(scorer);router=IntentRouter(recording)
        probe=GroundedConsultantV3(service,scorer,FakeLLMProvider(),router=router,settings=low)
        v2=GroundedConsultantV2(service,scorer,FakeLLMProvider());v1=GroundedConsultant(service,scorer,FakeLLMProvider())
        baseline=[];probes=[];frames=[];first_seconds=None
        for case in cases:
            baseline.append(score_v3_case(case,snapshot,v2.answer(case['question'])))
            recording.frames=[];t=perf_counter();probes.append(probe.answer(case['question']))
            if first_seconds is None:first_seconds=perf_counter()-t
            frames.append(list(recording.frames))
        legacy_probes=[]
        for case in legacy:
            old_result=v1.answer(case.question);recording.frames=[];result=probe.answer(case.question)
            legacy_probes.append((case,old_result,result,list(recording.frames)))
        grid=[]
        for s in cfg['score_grid']:
            for m in cfg['margin_grid']:
                settings=dict(cfg,score_min=float(s),margin_min=float(m))
                rows=[score_v3_case(c,snapshot,project_threshold_result(r,f,settings)) for c,r,f in zip(cases,probes,frames)]
                regressions=[]
                for c,base,result,f in legacy_probes:
                    actual=project_threshold_result(result,f,settings)
                    if legacy_answer_correct(c,snapshot,base) and not legacy_answer_correct(c,snapshot,actual):regressions.append(c.id)
                grid.append(dict(settings=settings,rows=rows,legacy_regression_ids=regressions))
        selected=choose_configuration(grid,baseline);actual_rows=[];times=[];replay_matches=False
        if selected is not None:
            app=GroundedConsultantV3(service,scorer,FakeLLMProvider(),settings=selected['settings'])
            for c in cases:
                t=perf_counter();actual_rows.append(score_v3_case(c,snapshot,app.answer(c['question'])));times.append(perf_counter()-t)
            fields=('status','reason_code','fully_correct','plan_correct','canonical_output_valid','correct_requirements','gold_pointer_coverage')
            replay_matches=all(all(a[k]==b[k] for k in fields) for a,b in zip(actual_rows,selected['rows']))
            for c,old_result,_,_ in legacy_probes:
                if legacy_answer_correct(c,snapshot,old_result):
                    r=app.answer(c.question)
                    if not legacy_answer_correct(c,snapshot,r):replay_matches=False
        feasible=selected is not None and replay_matches
        chosen=actual_rows if selected is not None else []
        summaries=[dict(score_min=t['settings']['score_min'],margin_min=t['settings']['margin_min'],metrics=metrics(t['rows']),legacy_regression_ids=t['legacy_regression_ids']) for t in grid]
        return dict(report_kind='semantic_planner_calibration_feasibility',schema_version=1,test_only=True,
            source_commit=commit,runtime_sha256=runtime,snapshot_id=snapshot.snapshot_id,registry_revision=snapshot.registry.revision,
            calibration_sha256=_sha(dataset_path),legacy_sha256=_sha(old_path),embedding_manifest_sha256=_sha(model_directory/'manifest.json'),
            reranker_manifest_sha256=_sha(reranker_directory/'manifest.json'),**identity,feasible=feasible,
            selected_settings=selected['settings'] if selected is not None else None,selected_replay_matches=replay_matches,
            legacy_rubric='V1-supported requirements; original gold pointers define complete canonical fact equivalence; canonical manual reference equivalence',
            legacy_v1_correct_positive_ids=[c.id for c,b,_,_ in legacy_probes if legacy_answer_correct(c,snapshot,b)],
            grid_method='35 fixed-grid abstention projections from actual permissive proposal outputs; selected configuration fully replayed',
            metrics=dict(v2=metrics(baseline),v3=metrics(chosen) if chosen else None),grid=summaries,
            cases=[dict(case_id=c['id'],group=c['group'],v2=b,v3=chosen[i] if chosen else None) for i,(c,b) in enumerate(zip(cases,baseline))],
            latency=dict(cold_setup_seconds=setup,first_probe_seconds=first_seconds,warm_selected_p50_seconds=statistics.median(times) if times else None,
                warm_selected_p95_seconds=sorted(times)[math.ceil(.95*len(times))-1] if times else None),
            independent_quality='not_run',blind_consumed=False,full_prototype_accepted=False,default_enabled=False)
    finally:dense.close()


def create_v3_freeze(dataset_path,calibration_report,model_directory,reranker_directory,freeze_path):
    cal=json.loads(calibration_report.read_text())
    if cal.get('feasible') is not True or cal.get('selected_replay_matches') is not True:raise ValueError('Calibration did not qualify a blind attempt')
    if _git('status','--porcelain','--untracked-files=all') or cal['runtime_sha256']!=_runtime_sha():raise ValueError('Clean calibrated code identity required')
    if (cal['calibration_sha256']!=_sha(_root()/'evaluation/datasets/planner-v3-calibration.json') or cal['legacy_sha256']!=_sha(_root()/'evaluation/datasets/synthetic-v1.json')
            or cal['embedding_manifest_sha256']!=_sha(model_directory/'manifest.json') or cal['reranker_manifest_sha256']!=_sha(reranker_directory/'manifest.json')):raise ValueError('Calibrated data/artifact identity changed')
    settings=checked_settings(cal['selected_settings']);manifest_path=dataset_path.with_name(dataset_path.stem+'.manifest.json')
    manifest=json.loads(manifest_path.read_text());digest=_sha(dataset_path);review=manifest['independent_review']
    if (manifest.get('profile')!='planner_v3_blind' or manifest['sha256']!=digest or manifest['snapshot_id']!=cal['snapshot_id']
            or manifest['registry_revision']!=cal['registry_revision'] or review.get('semantic_label_review')!='passed'
            or review.get('deduplication',{}).get('status')!='passed' or manifest.get('baseline_capability_review',{}).get('final_independent_review')!='passed'):
        raise ValueError('Independent author/review identity required')
    if (_root()/'evaluation/experiments'/f'{digest}.START.json').exists():raise ValueError('Blind dataset consumed')
    data=dict(schema_version=1,source_commit=_git('rev-parse','HEAD'),runtime_sha256=cal['runtime_sha256'],dataset_sha256=digest,
        author_manifest_sha256=_sha(manifest_path),calibration_report=str(calibration_report.resolve().relative_to(_root().resolve())),
        calibration_report_sha256=_sha(calibration_report),selected_settings=settings,snapshot_id=cal['snapshot_id'],registry_revision=cal['registry_revision'],
        embedding_manifest_sha256=_sha(model_directory/'manifest.json'),reranker_manifest_sha256=_sha(reranker_directory/'manifest.json'))
    freeze_path.parent.mkdir(parents=True,exist_ok=True)
    with freeze_path.open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False)
    return data


def run_v3_blind(corpus,dataset_path,model_directory,reranker_directory,freeze_path,report_path):
    from datetime import datetime,timezone
    freeze=json.loads(freeze_path.read_text());manifest_path=dataset_path.with_name(dataset_path.stem+'.manifest.json')
    if (_git('status','--porcelain','--untracked-files=all') or _git('rev-parse','HEAD')!=freeze['source_commit'] or _runtime_sha()!=freeze['runtime_sha256']
            or _sha(dataset_path)!=freeze['dataset_sha256'] or _sha(manifest_path)!=freeze['author_manifest_sha256']
            or _sha(_root()/freeze['calibration_report'])!=freeze['calibration_report_sha256']
            or _sha(model_directory/'manifest.json')!=freeze['embedding_manifest_sha256'] or _sha(reranker_directory/'manifest.json')!=freeze['reranker_manifest_sha256']):raise ValueError('V3 frozen identity changed')
    cal=json.loads((_root()/freeze['calibration_report']).read_text())
    if (cal.get('feasible') is not True or cal.get('selected_replay_matches') is not True
            or checked_settings(cal['selected_settings'])!=checked_settings(freeze['selected_settings'])):
        raise ValueError('Frozen qualified settings changed')
    if report_path.exists():raise ValueError('V3 first report already exists')
    report_path.parent.mkdir(parents=True,exist_ok=True);start_path=_root()/'evaluation/experiments'/f'{freeze["dataset_sha256"]}.START.json';start_path.parent.mkdir(parents=True,exist_ok=True)
    with start_path.open('x') as f:json.dump(dict(state='started',utc=datetime.now(timezone.utc).isoformat(),**freeze),f,indent=2)
    dense=None;rows=[];attempts=0;phase='model_setup'
    try:
        snapshot,service,scorer,dense,identity=_context(corpus,model_directory,reranker_directory);phase='dataset_validation'
        if snapshot.snapshot_id!=freeze['snapshot_id'] or snapshot.registry.revision!=freeze['registry_revision']:raise ValueError('Frozen snapshot mismatch')
        cases=validate_v3(dataset_path.read_bytes(),snapshot,'blind')
        apps=dict(v2=GroundedConsultantV2(service,scorer,FakeLLMProvider()),v3=GroundedConsultantV3(service,scorer,FakeLLMProvider(),settings=freeze['selected_settings']))
        phase='evaluation';times={name:[] for name in apps}
        for case in cases:
            row=dict(case_id=case['id'],group=case['group']);rows.append(row)
            for name,app in apps.items():
                attempts+=1;t=perf_counter();result=app.answer(case['question']);times[name].append(perf_counter()-t)
                row[name]=score_v3_case(case,snapshot,result)
        measured={name:metrics([r[name] for r in rows]) for name in apps};valid=all(m['errors']==0 for m in measured.values())
        target=valid and measured['v3']['fully_correct_rate']==1. and measured['v3']['unsafe_answers']==0 and measured['v3']['canonical_output_validity']==1.
        report=dict(report_kind='semantic_planner_first_blind_comparison',schema_version=1,test_only=True,freeze=freeze,**identity,
            experiment_valid=valid,unexecuted_cases=0,attempted_system_runs=attempts,metrics=measured,cases=rows,
            new_quality_target_met=target,full_prototype_accepted=False,default_enabled=False,
            latency={name:dict(warm_p50_seconds=statistics.median(t),warm_p95_seconds=sorted(t)[math.ceil(.95*len(t))-1]) for name,t in times.items()},
            quality_evaluation=dict(typed_plan_binding='measured',canonical_output='measured',natural_language_entailment='not_run',real_sample='not_run'))
        with report_path.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        return report
    except Exception as exc:
        failed=dict(report_kind='semantic_planner_first_blind_comparison',schema_version=1,test_only=True,freeze=freeze,
            experiment_valid=False,new_quality_target_met=False,full_prototype_accepted=False,default_enabled=False,
            failure_phase=phase,failure_type=type(exc).__name__,completed_cases=sum(all(k in r for k in ('v2','v3')) for r in rows),
            unexecuted_cases=40-len(rows),attempted_system_runs=attempts,cases=rows)
        outcome=report_path if not report_path.exists() else start_path.with_name(start_path.name.replace('START','FAILED'))
        with outcome.open('x') as f:json.dump(failed,f,ensure_ascii=False,indent=2,allow_nan=False)
        raise ValueError('Blind attempt consumed; invalid outcome persisted') from exc
    finally:
        if dense is not None:dense.close()
