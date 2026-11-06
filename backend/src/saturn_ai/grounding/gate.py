"""Schema facts only: conservative sufficiency, never a score threshold or label lookup."""
from math import isfinite
import re
from ..application import DESIGNATION
from ..retrieval.contracts import Candidate
from .contracts import QuestionPlan,GateResult

ASPECTS={'power':r'(?:питание|напряжение питания)',
         'interfaces':r'интерфейсы','protocols':r'протокол(?:ы)?',
         'temperature_c':r'(?:диапазон температуры|температура)','status':r'статус'}


def entity_id(document):return document.entity_id.removeprefix('synthetic:')


def _near(first,second):
    if len(first)==len(second):return sum(a!=b for a,b in zip(first,second))==1
    short,long=sorted((first,second),key=len)
    return len(long)==len(short)+1 and any(long[:i]+long[i+1:]==short for i in range(len(long)))


def plan_question(question,snapshot):
    if not isinstance(question,str) or not question.strip() or len(question)>4000:
        return GateResult('insufficient','invalid_question')
    names={}
    for doc in snapshot.documents:
        canonical=entity_id(doc);name=canonical.split('/')[-1].casefold()
        if DESIGNATION.fullmatch(name):names.setdefault(name,set()).add(canonical)
    found={name.casefold() for name in DESIGNATION.findall(question)}
    if not found:return GateResult('insufficient','unsupported_question')
    unknown=found-set(names)
    if unknown:
        if len(found)==1 and any(_near(next(iter(unknown)),name) for name in names):
            return GateResult('ambiguous','ambiguous_entity')
        return GateResult('insufficient','unknown_entity')
    if len(found)!=1 or len(names[next(iter(found))])!=1:return GateResult('ambiguous','ambiguous_entity')
    name=next(iter(found));entity=next(iter(names[name]));escaped=re.escape(name)
    folded=question.strip().casefold()
    for aspect,form in ASPECTS.items():
        grammar=(rf'(?:(?:какое|какие|какой|каков|какова|какая|каковы)\s+)?{form}\s+'
                 rf'(?:(?:требуется|требуются|указан|указаны|указано|перечислены|поддерживает)\s+)?'
                 rf'(?:(?:у|для|на)\s+)?(?:учебного\s+)?{escaped}[?!.]?')
        if re.fullmatch(grammar,folded):return QuestionPlan(entity,aspect)
    if re.fullmatch(rf'(?:найдите\s+)?(?:учебное\s+)?руководство\s+(?:(?:для|на)\s+)?{escaped}[?!.]?',folded):
        return QuestionPlan(entity,'manual')
    return GateResult('insufficient','unsupported_question')


def _typed_value(chunk,aspect):
    field=chunk.chunk.field_path.split('[')[0];text=chunk.chunk.text.strip()
    if field!=aspect:return None
    if aspect=='power':
        return text.casefold() if re.fullmatch(r'\d+(?:[.,]\d+)?\s*(?:В постоянного тока|V DC)',text,re.I) else None
    if aspect=='temperature_c':
        return text if re.fullmatch(r'temperature: -?\d+(?:\.\d+)? … -?\d+(?:\.\d+)? °C',text) else None
    if aspect=='status':return text if text in ('status: active','status: obsolete','status: discontinued') else None
    if aspect in ('interfaces','protocols'):
        prefix=aspect+': '
        if not text.startswith(prefix):return None
        value=text[len(prefix):]
        return value.casefold() if re.fullmatch(r'[A-Z0-9][A-Z0-9+./_-]{0,30}(?: [A-Z0-9]{1,10})?',value.upper()) else None
    return None


def evaluate_evidence(plan,snapshot,candidates,catalog):
    if not isinstance(plan,QuestionPlan) or plan.aspect not in (*ASPECTS,'manual'):
        raise ValueError('Invalid evidence plan')
    if not isinstance(candidates,tuple) or len(candidates)>5:raise ValueError('Expected bounded canonical top5')
    mapping={c.chunk_id:c for c in snapshot.chunks};seen=set()
    for rank,c in enumerate(candidates,1):
        if (not isinstance(c,Candidate) or c.chunk_id not in mapping or c.chunk_id in seen
                or c.source_id!=mapping[c.chunk_id].source_id or c.snapshot_id!=snapshot.snapshot_id
                or type(c.rank) is not int or c.rank!=rank or type(c.score) not in (float,int) or not isfinite(c.score)):
            raise ValueError('Invalid evidence candidate identity/rank')
        seen.add(c.chunk_id)
    indexed={c.chunk_id for c in catalog.eligible_snapshot_chunks(snapshot,'local_index')}
    generated={c.chunk_id for c in catalog.eligible_snapshot_chunks(snapshot,'local_generate')}
    allowed=indexed&generated
    docs={d.source_id:d for d in snapshot.documents};records={r.source_id:r for r in snapshot.registry.entries}
    target=[c for c in snapshot.chunks if entity_id(docs[c.source_id])==plan.entity_id]
    if plan.aspect=='manual':
        matching=[c for c in target if records[c.source_id].document_type=='manual' and c.chunk.page_start is not None]
        eligible=[c for c in matching if c.chunk_id in allowed and c.chunk_id in seen]
        if not eligible:
            reason='source_revoked' if matching and not any(c.chunk_id in allowed for c in matching) else 'no_evidence'
            return GateResult('insufficient',reason)
        # A manual link is a document lookup: one real approved page establishes a citation.
        chosen=next(mapping[c.chunk_id] for c in candidates if c.chunk_id in {e.chunk_id for e in eligible})
        return GateResult('sufficient','document_lookup',(chosen.chunk_id,))
    raw=[c for c in target if c.chunk.field_path.split('[')[0]==plan.aspect]
    by_source={};valid={}
    for c in raw:
        value=_typed_value(c,plan.aspect)
        if c.chunk_id in allowed and value is not None:
            by_source.setdefault(c.source_id,set()).add(value);valid[c.chunk_id]=value
    if not by_source:
        reason='source_revoked' if raw and not any(c.chunk_id in allowed for c in raw) else 'no_evidence'
        return GateResult('insufficient',reason)
    groups={tuple(sorted(values)) for values in by_source.values()}
    if len(groups)>1:return GateResult('conflict','conflicting_evidence')
    required=set(next(iter(groups)));selected=[];covered=set()
    for c in candidates:
        if c.chunk_id in valid and valid[c.chunk_id] not in covered:
            selected.append(c.chunk_id);covered.add(valid[c.chunk_id])
    if covered!=required:return GateResult('insufficient','incomplete_evidence')
    if len(selected)>5 or sum(len(mapping[cid].chunk.text) for cid in selected)>8000:
        return GateResult('insufficient','evidence_budget')
    return GateResult('sufficient','structured_fact',tuple(selected))
