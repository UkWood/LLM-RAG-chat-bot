"""Calibrated predicate proposals; relevance logits are never semantic proof."""
from hashlib import sha256
import json,re
from ..ingestion.contracts import identifier
from ..retrieval.reranking import checked_scores
from .contracts import GateResult
from .v2_contracts import EvidenceNeed,SourceConstraints
from .v3_contracts import IntentEntry,IntentDecision,QueryPlanV3
from .v3_config import load_v3_config,checked_settings,revision
from .v2_config import load_config
from .roles_v3 import parse_roles
from .projections import norm

class IntentRouter:
    def __init__(self,scorer):
        self.scorer=scorer;self.pairs_scored=0;self.identity=json.loads(json.dumps(scorer.identity,allow_nan=False))
        if type(self.identity.get('max_length')) is not int or not 1<=self.identity['max_length']<=512:raise ValueError('Explicit token budget required')
    def propose(self,phrase,entries,settings):
        settings=checked_settings(settings)
        if self.scorer.identity!=self.identity:raise ValueError('Intent model identity drift')
        if not 1<=len(entries)<=20 or len(set(entries))!=len(entries):raise ValueError('Invalid bounded catalogue')
        passages=[e.description for e in entries]
        lengths=self.scorer.pair_lengths(phrase,passages)
        if len(lengths)!=len(entries) or any(type(n) is not int or n<1 for n in lengths):raise ValueError('Invalid token lengths')
        if max(lengths)>self.identity['max_length']:return GateResult('insufficient','intent_input_budget')
        self.pairs_scored+=len(entries)
        scores=checked_scores(self.scorer.score_pairs(phrase,passages),len(entries))
        if self.scorer.identity!=self.identity:raise ValueError('Intent model identity drift')
        order=sorted(range(len(entries)),key=lambda i:(-scores[i],entries[i].predicate,entries[i].selector))
        best=order[0];second=scores[order[1]] if len(order)>1 else scores[best]-100
        gap=scores[best]-second
        if scores[best]<settings['score_min']:return GateResult('insufficient','unknown_predicate')
        if gap<=0 or gap<settings['margin_min']:return GateResult('ambiguous','ambiguous_predicate')
        e=entries[best];return IntentDecision(e.predicate,e.selector,scores[best],gap,'semantic')


def catalogue(snapshot,projections,catalog):
    cfg,_=load_v3_config()
    entries=[IntentEntry(p,'',d) for p,d in cfg['descriptions'].items()]
    allowed={c.chunk_id for c in catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
    labels=sorted({p.selector for p in projections if p.predicate=='spec' and p.selector and all(s.chunk_id in allowed for s in p.spans)})
    entries.extend(IntentEntry('spec',label,'Именованная характеристика: '+label+'.') for label in labels)
    if len(entries)>20:raise ValueError('Catalogue overflow')
    return tuple(entries)


def exact_intent(phrase,entries):
    patterns={'power':r'(?:питани[ея]|напряжени[ея](?: питания)?)','interfaces':r'(?:физические )?(?:интерфейсы?|разъемы?)(?: прибора)?',
        'protocols':r'протокол(?:ы|ов)?(?: (?:обмена|связи))?','temperature_c':r'(?:диапазон )?температур[а-я]*',
        'status':r'статус(?: выпуска)?','features':r'(?:возможности|функции)','purpose':r'(?:назначение|для чего)',
        'composition':r'состав','document_reference':r'(?:руководств[а-я]*|инструкц[а-я]*)','entity_type':r'тип(?: сущности)?',
        'configuration_interface':r'(?:интерфейс|разъем|порт)(?: для)?(?: локальной)? настройки'}
    matches=[]
    for e in entries:
        if e.predicate=='spec':
            words=re.findall(r'[а-яa-z]+',phrase);labels=re.findall(r'[а-яa-z]+',e.selector)
            if len(words)==len(labels) and all(a[:4]==b[:4] for a,b in zip(words,labels)):matches.append(e)
        elif re.fullmatch(patterns[e.predicate],phrase):matches.append(e)
    if len(matches)>1:return GateResult('ambiguous','ambiguous_selector')
    return matches[0] if matches else None


def plan_v3(question,snapshot,projections,router,settings,catalog):
    settings=checked_settings(settings);parsed=parse_roles(question,snapshot)
    if isinstance(parsed,GateResult):return parsed
    entries=catalogue(snapshot,projections,catalog);cat_revision=identifier('intent-catalogue-v3',[(e.predicate,e.selector,e.description) for e in entries])
    needs=[];decisions=[];roles=[]
    eligible_sources={x.source_id for x in catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
    allowed_entities={c.entity_id.removeprefix('synthetic:') for c in snapshot.documents if c.source_id in eligible_sources}
    for clause in parsed:
        candidates=tuple(e for e in entries if (not clause.count or e.predicate=='spec') and
            (not clause.selector or e.predicate in ('interfaces','configuration_interface','purpose')))
        e=next((e for e in candidates if clause.recognized==(e.predicate,e.selector)),None) if clause.recognized else exact_intent(clause.phrase,candidates)
        if isinstance(e,GateResult):return e
        decision=IntentDecision(e.predicate,e.selector,None,None,'exact') if e else router.propose(clause.phrase,candidates,settings)
        if isinstance(decision,GateResult):return decision
        selector=clause.selector or decision.selector
        for entity in clause.entity_ids:
            if entity not in allowed_entities:return GateResult('insufficient','source_not_allowed')
            need=EvidenceNeed(entity,decision.predicate,selector,clause.constraints)
            if need not in needs:needs.append(need)
        decisions.append(decision);roles.extend(clause.roles)
    if not 1<=len(needs)<=4:return GateResult('insufficient','need_budget')
    return QueryPlanV3(tuple(needs),sha256(question.encode()).hexdigest(),revision(settings),cat_revision,load_config()[1],tuple(sorted(set(roles),key=lambda s:(s.start,s.end,s.role))),tuple(decisions))
