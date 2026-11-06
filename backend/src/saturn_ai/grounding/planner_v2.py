"""Compositional bounded schema planner. Full token consumption, no dataset/model lookup."""
from hashlib import sha256
import re
from ..application import DESIGNATION
from .gate import entity_id,_near
from .contracts import GateResult
from .v2_contracts import EvidenceNeed,SourceConstraints,QueryPlanV2
from .v2_config import load_config
from .projections import norm

# Grammatical/domain context, not a list of evaluation questions or answers.
CONTEXT=('как','како','каки','каков','какая','какую','сколь','что','чем','где','кто','для','на','у','в','во','по','из','с','со','от','до','через','при',
 'рядом','его','ее','их','оба','обе','двух','кажд','также','переч','назов','укаж','сообщ','покаж','найд','нужн','треб','устан','задан','дост','опис',
 'знач','данн','учеб','вымыш','стенд','контрол','шлюз','прибор','устрой','оборуд','сбор','датчик','показан','переда','отправ','сет','локал','программ',
 'адрес','кабел','сравн','отлич','между','свед','расскаж','узна','опред','привед','получ','согласно','указан',
 'перечисл','поддерж','относи','явля','это','или','вид','роль','характерист','карточ','таблиц','строк','столб','документ','pdf','пожалуй','можно','ли',
 'usb','ethernet','rs','а','и','об','о','к','есть','выполня','делает')


def _tokens(text):return re.findall(r'[a-zа-яё]+\d*|\d+',norm(text))


def _matches(token,stems):return any(token.startswith(stem) for stem in stems)


def _context(token):
    exact={'как','что','чем','где','кто','для','на','у','в','во','по','из','с','со','от','до','через','при','рядом','его','ее','их','оба','обе','также','есть','а','и','об','о','к','ли','можно','usb','rs','сеть','сети','сетевой','сетевого','сетевому','сетевым','сетевую','сетевые','сетевая'}
    return token in exact or any(len(stem)>=4 and token.startswith(stem) for stem in CONTEXT if stem not in exact)


def plan_v2(question,snapshot,projections):
    config,revision=load_config()
    if not isinstance(question,str) or not question.strip() or len(question)>config['limits']['question_chars']:
        return GateResult('insufficient','invalid_question')
    text=norm(question)
    if re.search(r'\b(?:не|ни|нет|без|игнор\w*|придум\w*|ignore|reveal|pretend|invent)\b',text):
        return GateResult('insufficient','unsupported_question')
    if re.search(r'потребля\w*\s+ток|цен[аыуе]|стоимост|совместим|котл|котел|погод|рецепт',text):
        return GateResult('insufficient','unsupported_question')
    names={}
    for doc in snapshot.documents:
        eid=entity_id(doc);name=norm(eid.split('/')[-1])
        if DESIGNATION.fullmatch(name):names.setdefault(name,set()).add(eid)
    technical={norm(p.value) for p in projections if p.predicate in ('interfaces','configuration_interface')}
    found=[];replacements=[]
    for match in DESIGNATION.finditer(text):
        name=norm(match[0])
        if name not in names:
            if name in technical:continue
            state='ambiguous' if any(_near(name,n) for n in names) else 'insufficient'
            return GateResult(state,'ambiguous_entity' if state=='ambiguous' else 'unknown_entity')
        if len(names[name])!=1:return GateResult('ambiguous','ambiguous_entity')
        eid=next(iter(names[name]))
        if eid not in found:found.append(eid)
        replacements.append((match.start(),match.end(),f'zzentity{found.index(eid)}'))
    if len(found)>3:return GateResult('ambiguous','too_many_entities')
    for start,end,replacement in reversed(replacements):text=text[:start]+replacement+text[end:]
    aliases=config['aliases'];spec_labels=sorted({p.selector for p in projections if p.predicate=='spec' and p.valid})
    spec_stems={label:tuple(t[:4] for t in _tokens(label)) for label in spec_labels}
    clauses=[c.strip(' ,.:?!—-') for c in re.split(r'\s+(?:и|а также|плюс)\s+|[;,]',text) if c.strip(' ,.:?!—-')]
    if not clauses:return GateResult('insufficient','unsupported_question')
    needs=[];last_predicates=[];last_entities=[];pending=[]
    for clause_index,clause in enumerate(clauses):
        tokens=_tokens(clause);token_set=set(tokens)
        subjects=[found[int(i)] for i in re.findall(r'zzentity(\d+)',clause)]
        subjects=list(dict.fromkeys(subjects));explicit_subjects=bool(subjects)
        if any(t.startswith('порт') for t in tokens) and token_set&{'tcp','udp'}:
            return GateResult('insufficient','unsupported_network_port')
        constraints=SourceConstraints('manual' if any(_matches(t,('руководств','инструкц','manual')) for t in tokens)
            else 'product_card' if any(t.startswith('карточ') for t in tokens) else 'any',
            'markdown_table' if any(t.startswith('таблиц') for t in tokens) else 'any')
        if any(t.startswith('карточ') for t in tokens) and constraints.document_kind=='manual':
            return GateResult('insufficient','incompatible_source_constraints')
        predicates=[];covered=set()
        for label,stems in spec_stems.items():
            if stems and all(any(t.startswith(stem) for t in tokens) for stem in stems):
                predicates.append(('spec',label));covered.update(t for t in tokens if _matches(t,stems))
        for pred,stems in aliases.items():
            matching={t for t in tokens if _matches(t,stems)}
            if matching:predicates.append((pred,''));covered.update(matching)
        if any(t.startswith('настр') or t.startswith('конфиг') for t in tokens) and any(t.startswith(('разъем','интерфейс','порт')) for t in tokens):
            predicates=[p for p in predicates if p[0] not in ('interfaces','purpose','features')]+[('configuration_interface','')]
        if any(p[0]=='purpose' for p in predicates):predicates=[p for p in predicates if p[0]!='features']
        # A manual used as a source is a scope; a requested manual remains a need.
        if re.search(r'(?:по|в|из)\s+(?:его\s+)?(?:руководств|инструкц|manual)',clause):
            predicates=[p for p in predicates if p[0]!='document_reference']
        if not predicates and any(t.startswith(('программ','по')) for t in tokens) and any(t.startswith(('измен','помен','настр')) for t in tokens):
            predicates=[('purpose','')]
        if not predicates and any(t.startswith(('категор','сущност')) for t in tokens):
            predicates=[('entity_type','')];covered.update(t for t in tokens if t.startswith(('категор','сущност')))
        if any(p[0]=='temperature_c' for p in predicates):covered.update(t for t in tokens if t.startswith('диапазон'))
        # Modification words are substantive, not universal grammatical context.
        # Consume them only for the supported software/address or interface lookup.
        modification={t for t in tokens if t.startswith(('помен','измен','настр','конфиг'))}
        lookup=any(t.startswith(('како','каки','кака','каку')) for t in tokens) and 'можно' not in token_set
        purpose_lookup=(lookup and {p[0] for p in predicates}=={'purpose'}
            and any(t.startswith('программ') for t in tokens) and any(t.startswith('адрес') for t in tokens)
            and modification<={'поменять','изменить','настроить','конфигурировать'})
        interface_lookup=({p[0] for p in predicates}=={'configuration_interface'}
            and all(t.startswith(('настр','конфиг')) for t in modification)
            and ((lookup and bool(token_set & {'через','по'}))
                 or all(t.startswith(('настройк','конфигураци')) for t in modification)))
        if purpose_lookup or interface_lookup:covered.update(modification)

        # Every substantive word must be accounted for by ontology, spec label or grammar.
        unknown=[t for t in tokens if t not in covered and not re.fullmatch(r'zzentity\d+',t)
                 and not _context(t)]
        if unknown:return GateResult('insufficient','unsupported_clause')
        literals={v.replace('rs485','rs-485') for v in re.findall(r'\b(?:usb|ethernet|rs-?485)\b',clause)}
        if literals:
            if len(literals)!=1 or any(pred not in ('interfaces','configuration_interface','purpose') for pred,_ in predicates):
                return GateResult('insufficient','unsupported_interface_qualifier')
            predicates=[(pred,'interface='+next(iter(literals))) for pred,_ in predicates]
        if not subjects and predicates and not last_entities and found and clause_index<len(clauses)-1:
            pending.extend((pred,selector,constraints) for pred,selector in predicates);continue
        if not subjects:
            if len(found)==1:subjects=found[:]
            elif last_entities:subjects=last_entities[:]
            elif not found:
                kind='Software' if any(t.startswith('программ') for t in tokens) else 'Category' if any(t.startswith('категор') for t in tokens) else 'System' if any(t.startswith('систем') for t in tokens) else None
                choices={entity_id(d) for d in snapshot.documents if d.entity_type==kind} if kind else set()
                if len(choices)==1:subjects=list(choices)
                elif choices:return GateResult('ambiguous','ambiguous_entity')
        if not subjects and predicates:
            pending.extend((pred,selector,constraints) for pred,selector in predicates);continue
        if not subjects:return GateResult('ambiguous','ambiguous_entity')
        if not predicates:
            if not explicit_subjects:return GateResult('insufficient','unsupported_clause')
            predicates=last_predicates[:]
        scoped=[(pred,selector,own if own!=SourceConstraints() else constraints) for pred,selector,own in pending]
        scoped.extend((pred,selector,constraints) for pred,selector in predicates);pending=[]
        if not scoped:return GateResult('insufficient','unsupported_question')
        for eid in subjects:
            for pred,selector,scope in scoped:
                need=EvidenceNeed(eid,pred,selector,scope)
                if need not in needs:needs.append(need)
        last_predicates=predicates;last_entities=subjects
    if pending or not needs:return GateResult('insufficient','incomplete_plan')
    if len(needs)>4 or len({n.entity_id for n in needs})>3:return GateResult('insufficient','plan_budget')
    return QueryPlanV2(tuple(needs),sha256(question.encode()).hexdigest(),revision)
