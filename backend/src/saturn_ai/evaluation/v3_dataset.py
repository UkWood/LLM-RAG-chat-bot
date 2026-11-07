"""Strict canonical calibration/blind schemas; never imported by the application."""
from collections import Counter
import json,re,unicodedata
from ..ingestion.registry import unique_object
from ..grounding.gate import entity_id
from ..grounding.projections import build_projections,document_kind,selector_matches,norm
from ..grounding.v2_config import load_config

PROFILES={'calibration':('planner_v3_calibration',{'single_field':12,'multi_need':8,'source_scoped':6,'document_reference':4,'relationship_type':6,'mandatory_refusal':12,'ambiguous_invalid':12},{'answered':36,'refused':18,'clarification':6}),
 'blind':('planner_v3_blind',{'single_field':8,'multi_need':4,'source_scoped':4,'document_reference':4,'relationship_type':4,'mandatory_refusal':8,'ambiguous_invalid':8},{'answered':24,'refused':12,'clarification':4})}

def normalized_question(q):return ' '.join(re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',q).casefold().replace('ё','е')).split())

def validate_v3(raw,snapshot,profile):
    if profile not in PROFILES or not isinstance(raw,bytes) or len(raw)>1000000:raise ValueError('Invalid V3 data profile/size')
    name,groups,statuses=PROFILES[profile];data=json.loads(raw,object_pairs_hook=unique_object)
    if (not isinstance(data,dict) or type(data.get('schema_version')) is not int or data['schema_version']!=1 or data.get('profile')!=name
            or data.get('snapshot_id')!=snapshot.snapshot_id or data.get('registry_revision')!=snapshot.registry.revision
            or not isinstance(data.get('cases'),list) or len(data['cases'])!=sum(groups.values())):raise ValueError('V3 pinned dataset identity/count mismatch')
    cfg,_=load_config();docs={d.source_id:d for d in snapshot.documents};records={r.source_id:r for r in snapshot.registry.entries}
    entities={entity_id(d) for d in snapshot.documents};ids=set();questions=set();projections=build_projections(snapshot)
    for case in data['cases']:
        if (not isinstance(case,dict) or type(case.get('id')) is not str or not case['id'] or case['id'] in ids
                or type(case.get('group')) is not str or case.get('group') not in groups or type(case.get('expected_status')) is not str or case.get('expected_status') not in statuses or type(case.get('question')) is not str
                or not 0<len(case['question'].strip())<=4000 or normalized_question(case['question']) in questions
                or not isinstance(case.get('requirements'),list)):raise ValueError('Invalid V3 case identity/outcome')
        ids.add(case['id']);questions.add(normalized_question(case['question']))
        positive=case['expected_status']=='answered'
        if positive!=(case['group'] not in ('mandatory_refusal','ambiguous_invalid')):raise ValueError('Wrong V3 outcome/group')
        if case['group']=='mandatory_refusal' and case['expected_status']!='refused':raise ValueError('Mandatory refusal mislabeled')
        if not positive:
            if case['requirements']:raise ValueError('Negative V3 case cannot prescribe facts')
            continue
        if (not 1<=len(case['requirements'])<=4 or any(not isinstance(n,dict) or type(n.get('entity_id')) is not str for n in case['requirements'])
                or len({n.get('entity_id') for n in case['requirements']})>3):raise ValueError('Invalid V3 need count')
        seen=set()
        for need in case['requirements']:
            if (not isinstance(need,dict) or need.get('entity_id') not in entities or need.get('predicate') not in cfg['predicates']
                    or type(need.get('selector')) is not str or len(need['selector'])>128 or need['selector']!=norm(need['selector'])
                    or need.get('document_kind') not in cfg['document_kinds'] or need.get('representation') not in cfg['representations']
                    or not isinstance(need.get('evidence'),list)):raise ValueError('Invalid V3 typed requirement')
            key=tuple(need[k] for k in ('entity_id','predicate','selector','document_kind','representation'))
            if key in seen:raise ValueError('Duplicate gold need')
            seen.add(key);evidence=need['evidence'];ref=need.get('reference')
            chunks=set()
            for ev in evidence:
                if (not isinstance(ev,dict) or type(ev.get('text')) is not str or not ev['text']
                        or ev.get('page') is not None and (type(ev['page']) is not int or ev['page']<1)):raise ValueError('Invalid V3 canonical pointer')
                matched=[c for c in snapshot.chunks if c.source_id==ev.get('source_id') and c.chunk.field_path==ev.get('field_path')
                    and c.chunk.page_start==ev.get('page') and ev['text'] in c.chunk.text]
                if not matched:raise ValueError('V3 evidence lacks exact canonical pointer')
                chunks.update(c.chunk_id for c in matched)
            def scope(source,rep):
                return (need['document_kind']=='any' or document_kind(docs[source],records[source])==need['document_kind']) and (need['representation']=='any' or rep==need['representation'])
            if ref is not None:
                if not isinstance(ref,dict) or ref.get('kind') not in ('document','entity_type') or type(ref.get('source_id')) is not str or ref.get('source_id') not in docs:raise ValueError('Invalid V3 reference')
                d=docs[ref['source_id']];r=records[d.source_id];document=ref['kind']=='document'
                if (entity_id(d)!=need['entity_id'] or need['predicate']!=('document_reference' if document else 'entity_type')
                        or ref.get('value')!=(r.title if document else d.entity_type) or document and r.document_type!='manual'
                        or not document and r.entity_type is None or not scope(d.source_id,'quoted_statement' if document else 'structured_field')):raise ValueError('V3 reference binding mismatch')
                if document and not any(c.source_id==d.source_id and c.chunk.page_start is not None for c in snapshot.chunks):raise ValueError('V3 manual has no physical anchor')
            else:
                if need['predicate'] in ('document_reference','entity_type') or not evidence:raise ValueError('V3 support kind mismatch')
                matching=[p for p in projections if p.entity_id==need['entity_id'] and p.predicate==need['predicate'] and selector_matches(p,need['selector']) and scope(p.source_id,p.representation)]
                complete={}
                for p in matching:
                    if p.valid and (p.complete or need['representation']=='markdown_table' and p.complete_for_source):complete.setdefault(p.group_id,[]).append(p)
                if not any({s.chunk_id for p in group for s in p.spans if s.role=='value'}<=chunks for group in complete.values()):raise ValueError('V3 gold has no complete canonical capability')
    if Counter(c['group'] for c in data['cases'])!=groups or Counter(c['expected_status'] for c in data['cases'])!=statuses:raise ValueError('V3 distribution mismatch')
    return data['cases']
