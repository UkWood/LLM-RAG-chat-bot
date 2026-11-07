"""Bounded structural role parser. Semantic topic spans are never ignored context."""
import re
from ..application import DESIGNATION
from .gate import entity_id,_near
from .contracts import GateResult
from .v2_contracts import SourceConstraints
from .v3_contracts import ClauseV3,RoleSpan
from .projections import norm

DENY=re.compile(r'\b(?:не|ни|нет|без|или|либо|можно|нельзя|почему|зачем|игнор\w*|придум\w*|ignore|reveal|pretend|invent|modbus|tcp|rtu|udp|bacnet)\b|цен[ауы]|стоимост|гаранти|совмест|кот[её]л|котл|рецепт|борщ|самолет|погод|секрет|потребля\w*\s+ток|разниц|рассчита|мощност|ампер|ватт|\bток(?:а|у|ом|и|ов)?\b',re.I)
TEMPERATURE=r'температур(?:а|ы|е|у|ой|ою|ам|ами|ах)?'
MANUAL=r'руководств(?:о|а|у|ом|е|ам|ами|ах)?'
INSTRUCTION=r'инструкци(?:я|и|ю|ей|ею|ям|ями|ях|й)'
CARD=r'карточк(?:а|и|е|у|ой|ою|ам|ами|ах)'
TABLE=r'таблиц(?:а|ы|е|у|ей|ею|ам|ами|ах)?'
SOURCE=re.compile(r'\b(?:по|из|в|согласно)\s+(?:(?:его|ее|учебной|учебному|учебного)\s+)?(?:'+CARD+'|'+MANUAL+'|'+INSTRUCTION+'|'+TABLE+r')\b(?:\s+изделия)?',re.I)
PREFIX=re.compile(r'^\s*(?:(?:пожалуйста|скажите|подскажите|укажите|покажите|перечислите|назовите|сообщите|найдите|дайте|сравните|сравни)\s+)?(?:(?:какое|какие|какой|какая|каков|каковы|какую|каким|какому|сколько|число|количество)\s+)?',re.I)


def parse_roles(question,snapshot):
    if not isinstance(question,str) or not question.strip() or len(question)>4000:return GateResult('insufficient','invalid_question')
    # Full character validation precedes tokenization; no invisible/operator loss.
    if re.search(r'[^A-Za-zА-Яа-яЁё0-9\s?!.:,;()/—…\-]',question) or any(c.isspace() and c not in ' \t\r\n' for c in question):
        return GateResult('insufficient','unsupported_symbol')
    text=norm(question)
    if DENY.search(text):return GateResult('insufficient','unsupported_operator')
    # Related compound nouns are different quantities/topics, not grammatical cases.
    for stem,pattern in (('температур',TEMPERATURE),('руководств',MANUAL),('инструкци',INSTRUCTION),('карточк',CARD),('таблиц',TABLE)):
        if any(not re.fullmatch(pattern,w) for w in re.findall(r'\b'+stem+r'[а-я]*\b',text)):
            return GateResult('insufficient','unsupported_qualifier')
    names={}
    for d in snapshot.documents:
        name=norm(entity_id(d).split('/')[-1])
        if DESIGNATION.fullmatch(name):names.setdefault(name,set()).add(entity_id(d))
    entity_spans=[]
    for m in DESIGNATION.finditer(question):
        name=norm(m[0])
        if name in ('rs-485','rs485'):continue
        if (m.end()<len(question) and question[m.end()] in '-—/' or m.start()>0 and question[m.start()-1] in '-—/'):
            return GateResult('insufficient','unknown_entity')
        if name not in names:
            near=any(_near(name,n) for n in names)
            return GateResult('ambiguous' if near else 'insufficient','ambiguous_entity' if near else 'unknown_entity')
        if len(names[name])!=1:return GateResult('ambiguous','ambiguous_entity')
        entity_spans.append((m.start(),m.end(),next(iter(names[name]))))
    found=tuple(dict.fromkeys(e for _,_,e in entity_spans))
    if len(found)>3:return GateResult('insufficient','entity_budget')
    # Existing declared lookup constructions, not mutation instructions.
    software=re.fullmatch(r'(?:какой|какая|какую|каким)\s+(?:программой|программа|программу|по)\s+(?:изменить|поменять|настроить)\s+адрес\s+(?:контроллера|прибора|устройства)(?:\s+через\s+кабель\s+(usb))?[?.!]*',text)
    if software and not found:
        choices={entity_id(d) for d in snapshot.documents if d.entity_type=='Software'}
        if len(choices)!=1:return GateResult('ambiguous','ambiguous_entity')
        return (ClauseV3(tuple(choices),'назначение',(0,len(question)),selector='interface=usb' if software[1] else '',recognized=('purpose',''),roles=(RoleSpan(0,len(question),'software_purpose_lookup'),)),)
    if not found:return GateResult('ambiguous','ambiguous_entity')
    config=re.fullmatch(r'через\s+(?:какой|каким)\s+(?:разъем|интерфейс|порт)\s+(?:настраива[а-я]*|конфигуриру[а-я]*)\s+([a-zа-я0-9./-]+)(?:\s+рядом со стендом)?[?.!]*',text)
    if config and len(found)==1:
        return (ClauseV3(found,'интерфейс настройки',(0,len(question)),recognized=('configuration_interface',''),roles=(RoleSpan(0,len(question),'configuration_interface_lookup'),)),)
    # No generic how-to/action tokens may reach a semantic descriptor.
    if re.search(r'\b(?:как|чтобы|измени\w*|помен\w*|настрой\b|настроить|конфигурир\w*|повыс\w*|подключ\w*|увелич\w*|уменьш\w*|замен\w*)\b',text):
        return GateResult('insufficient','unsupported_action')
    cuts=list(re.finditer(r'\b(?:и|а также|плюс)\b|[;,]',question,re.I))
    ranges=[];start=0
    for m in cuts:ranges.append((start,m.start()));start=m.end()
    ranges.append((start,len(question)))
    if len(ranges)>4:return GateResult('insufficient','need_budget')
    connector_roles=tuple(RoleSpan(m.start(),m.end(),'conjunction') for m in cuts)
    result=[]
    for start,end in ranges:
        raw=question[start:end];marks={};subjects=[];kind='any';representation='any';selector=''
        def mark(a,b,role):
            for i in range(a,b):marks.setdefault(i,role)
        for a,b,e in entity_spans:
            if start<=a and b<=end:
                subjects.append(e);mark(a-start,b-start,'entity')
                before=raw[:a-start];prep=re.search(r'\b(?:у|для|на)\s*(?:(?:изделия|прибора|устройства)\s*)?$',before,re.I)
                if prep:mark(prep.start(),a-start,'entity_owner')
                # Fixture descriptor belongs only to a directly named synthetic entity.
                training=re.search(r'\bучебн(?:ого|ый|ое|ой)\s*$',before,re.I)
                if training and any(d.source_id.startswith('synthetic:') and entity_id(d)==e for d in snapshot.documents):
                    mark(training.start(),a-start,'synthetic_entity_descriptor')
        for m in SOURCE.finditer(raw):
            value=norm(m[0]);mark(m.start(),m.end(),'source_constraint')
            if 'таблиц' in value:representation='markdown_table'
            else:
                k='product_card' if 'карточ' in value else 'manual'
                if kind!='any' and kind!=k:return GateResult('insufficient','incompatible_source_constraints')
                kind=k
        for m in re.finditer(r'\b(?:usb|ethernet|rs-?485)\b',raw,re.I):
            v=norm(m[0]).replace('rs485','rs-485')
            if selector and selector!='interface='+v:return GateResult('insufficient','unsupported_qualifier')
            selector='interface='+v;mark(m.start(),m.end(),'interface_selector')
        clean=''.join(' ' if i in marks else c for i,c in enumerate(raw))
        # Type lookup construction is wholly recognized, including its verb/preposition.
        typed=re.match(r'^\s*к какому типу относится\s*',clean,re.I)
        prefix=typed or PREFIX.match(clean)
        count=bool(re.search(r'\b(?:сколько|число|количество)\b',prefix[0] if prefix else '',re.I))
        if prefix:mark(prefix.start(),prefix.end(),'lookup')
        if typed:
            phrase='тип сущности';recognized=('entity_type','')
        else:phrase='';recognized=None
        # The adjective is part of this exact manual noun phrase, never ignored globally.
        if re.fullmatch(r'\s*учебн(?:ое|ую)\s+(?:'+MANUAL+'|'+INSTRUCTION+r')\s*[?!.:]*',
                ''.join(' ' if i in marks else c for i,c in enumerate(raw)),re.I):
            training=re.search(r'\bучебн(?:ое|ую)\b',raw,re.I)
            mark(training.start(),training.end(),'synthetic_manual_descriptor')
        declaration_clean=''.join(' ' if i in marks else c for i,c in enumerate(raw)).rstrip(' ?!.:')
        declaration=re.search(r'\b(?:требуется|требуются|указан|указаны|указано|перечислены|предусмотрены|предусмотрен|поддерживает)\s*$',declaration_clean,re.I)
        if declaration:mark(declaration.start(),declaration.end(),'lookup_declaration')
        for i,c in enumerate(raw):
            if c.isspace() or c in '?!.:—…()':marks.setdefault(i,'grammar')
        remaining=[i for i in range(len(raw)) if i not in marks]
        if typed and (remaining or selector):return GateResult('insufficient','unsupported_qualifier')
        if not typed:phrase=norm(''.join(raw[i] if i in remaining else ' ' for i in range(len(raw))))
        phrase=' '.join(phrase.split())
        if not phrase and (declaration or (prefix and re.search('[A-Za-zА-Яа-яЁё]',prefix[0]))):
            return GateResult('insufficient','unsupported_clause')
        if re.search(r'беспровод|оптическ|радио|внешн|максимальн|минимальн|резервн|[\/]',phrase):
            return GateResult('insufficient','unsupported_qualifier')
        english={'power','voltage','supply','electrical','interface','interfaces','protocol','protocols','temperature','status','features','purpose','composition','manual','type','entity'}
        if any(w not in english for w in re.findall(r'[a-z]+',phrase)):
            return GateResult('insufficient','unsupported_qualifier')
        heads=(r'питан|напряжен',r'интерфейс|разъем',r'протокол',r'температур',r'статус',r'руководств|инструкц',r'состав',r'назначен')
        if sum(bool(re.search(r'\b(?:'+p+r')',phrase)) for p in heads)>1:
            return GateResult('insufficient','unsupported_mixed_topic')
        if re.search(r'\b(?:для|по|из|в|на|через|при|к|с|от|о|об|между|согласно|ли)\b|\d',phrase):
            # A declared nominal interface-of-configuration phrase is the sole PP exception.
            if re.fullmatch(r'(?:интерфейс|разъем|порт)\s+(?:для\s+)?(?:локальной\s+)?настройки',phrase):recognized=('configuration_interface','')
            else:return GateResult('insufficient','unsupported_qualifier')
        if re.search(r'\b\w+(?:ать|ять|ить|уть|ает|яют|ует|уют|ется|ются)\b',phrase) and not typed:
            return GateResult('insufficient','unsupported_action')
        for i in remaining:marks[i]='predicate_phrase'
        roles=[]
        for i in range(len(raw)):
            role=marks.get(i,'grammar')
            if roles and roles[-1].end==start+i and roles[-1].role==role:
                roles[-1]=RoleSpan(roles[-1].start,start+i+1,role)
            else:roles.append(RoleSpan(start+i,start+i+1,role))
        result.append(ClauseV3(tuple(dict.fromkeys(subjects)),phrase,(start+min(remaining),start+max(remaining)+1) if remaining else (start,start),SourceConstraints(kind,representation),selector,recognized,tuple(roles),count))
    # Deferred initial fields share the following explicit subject/scope.
    first=next((i for i,c in enumerate(result) if c.entity_ids),None)
    if first is None:return GateResult('ambiguous','ambiguous_entity')
    last_entities=();last_phrase=None
    from dataclasses import replace
    for i,c in enumerate(result):
        if not c.entity_ids:
            anchor=result[first] if i<first else None
            c=replace(c,entity_ids=anchor.entity_ids if anchor else last_entities,
                constraints=anchor.constraints if anchor and c.constraints==SourceConstraints() else c.constraints)
        if not c.phrase:
            if c.constraints!=SourceConstraints() and last_phrase is not None and last_phrase.constraints==SourceConstraints():
                return GateResult('ambiguous','ambiguous_attachment')
            if last_phrase is None:return GateResult('insufficient','unsupported_clause')
            c=replace(c,phrase=last_phrase.phrase,phrase_span=last_phrase.phrase_span,recognized=last_phrase.recognized,count=last_phrase.count)
        else:last_phrase=c
        if not c.entity_ids:return GateResult('ambiguous','ambiguous_entity')
        last_entities=c.entity_ids;result[i]=c
    if first>0 and len(found)>1:return GateResult('ambiguous','ambiguous_attachment')
    result[0]=replace(result[0],roles=result[0].roles+connector_roles)
    return tuple(result)
