"""Strict synthetic blind-schema validation. Never imported by application/planner."""
import json
from collections import Counter
from ..ingestion.registry import unique_object
from ..grounding.gate import entity_id
from ..grounding.v2_config import load_config

GROUPS={'single_field':8,'multi_need':4,'source_scoped':4,'document_reference':4,'relationship_type':4,
        'mandatory_refusal':8,'ambiguous_invalid':8}


def validate_blind(raw,snapshot):
    if not isinstance(raw,bytes) or len(raw)>500000:raise ValueError('Blind dataset size/type limit')
    data=json.loads(raw,object_pairs_hook=unique_object)
    if (not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version')!=1 or data.get('profile')!='planner_v2_blind'
            or data.get('snapshot_id')!=snapshot.snapshot_id or data.get('registry_revision')!=snapshot.registry.revision
            or not isinstance(data.get('cases'),list) or len(data['cases'])!=40):
        raise ValueError('Expected pinned40case blind profile')
    config,_=load_config();ids=set();questions=set();mapping=snapshot.chunks
    entities={entity_id(d) for d in snapshot.documents};docs={d.source_id:d for d in snapshot.documents}
    records={r.source_id:r for r in snapshot.registry.entries}
    for case in data['cases']:
        if (not isinstance(case,dict) or not isinstance(case.get('id'),str) or case['id'] in ids
                or case.get('group') not in GROUPS or case.get('expected_status') not in ('answered','refused','clarification')
                or not isinstance(case.get('question'),str) or not 0<len(case['question'].strip())<=4000
                or case['question'].strip().casefold() in questions or not isinstance(case.get('requirements'),list)):
            raise ValueError('Invalid blind case identity/question/outcome')
        ids.add(case['id']);questions.add(case['question'].strip().casefold())
        if case['expected_status']!='answered':
            if case['requirements']:raise ValueError('Non-answer case cannot prescribe facts')
            continue
        if not 1<=len(case['requirements'])<=4:raise ValueError('Invalid complete requirement count')
        if len({n.get('entity_id') for n in case['requirements']})>3:raise ValueError('Too many required entities')
        for need in case['requirements']:
            if (not isinstance(need,dict) or need.get('entity_id') not in entities or need.get('predicate') not in config['predicates']
                    or not isinstance(need.get('selector'),str) or len(need['selector'])>128
                    or need.get('document_kind') not in config['document_kinds']
                    or need.get('representation') not in config['representations'] or not isinstance(need.get('evidence'),list)):
                raise ValueError('Invalid typed gold requirement')
            ref=need.get('reference')
            if ref is not None:
                if (not isinstance(ref,dict) or ref.get('kind') not in ('document','entity_type') or ref.get('source_id') not in docs):
                    raise ValueError('Invalid gold metadata reference')
                expected_pred='document_reference' if ref['kind']=='document' else 'entity_type'
                if need['predicate']!=expected_pred:raise ValueError('Reference predicate/kind mismatch')
                doc=docs[ref['source_id']];record=records[ref['source_id']]
                value=record.title if ref['kind']=='document' else doc.entity_type
                if (entity_id(doc)!=need['entity_id'] or ref.get('value')!=value
                        or ref['kind']=='document' and record.document_type!='manual'
                        or ref['kind']=='entity_type' and record.entity_type is None):
                    raise ValueError('Unsupported reference metadata')
            elif need['predicate'] in ('document_reference','entity_type') or not need['evidence']:
                raise ValueError('Reference/quote support kind mismatch')
            for ev in need['evidence']:
                if (not isinstance(ev,dict) or not isinstance(ev.get('text'),str) or not ev['text']
                        or ev.get('page') is not None and (type(ev['page']) is not int or ev['page']<1)
                        or not any(c.source_id==ev.get('source_id') and c.chunk.field_path==ev.get('field_path')
                            and c.chunk.page_start==ev.get('page') and ev['text'] in c.chunk.text for c in mapping)):
                    raise ValueError('Gold support lacks canonical field/page/text provenance')
    if Counter(c['group'] for c in data['cases'])!=GROUPS:raise ValueError('Blind distribution mismatch')
    if Counter(c['expected_status'] for c in data['cases'])!={'answered':24,'refused':12,'clarification':4}:
        raise ValueError('Blind outcome distribution mismatch')
    return data['cases']
