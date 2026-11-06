"""Deterministic projections of existing canonical text. No new corpus/parser output."""
from dataclasses import asdict
from decimal import Decimal,InvalidOperation
import re
from ..ingestion.contracts import identifier
from .gate import entity_id,_typed_value
from .v2_contracts import CanonicalSpan,FactProjection
from .v2_config import load_config


def norm(text):return text.casefold().replace('ё','е').strip()


def document_kind(document,record):
    if record.document_type=='manual':return 'manual'
    if record.source_kind=='site_content' and document.entity_id.startswith('products/'):return 'product_card'
    return 'any'


def projection_id(projection):return identifier('fact-projection-v2',asdict(projection))


def _number(value):
    try:return str(Decimal(value.replace(',','.')).normalize())
    except InvalidOperation:raise ValueError('Invalid numeric value') from None


def _voltage(text):
    match=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(?:В|V)(?:\s*(?:постоянного тока|DC))?\.?',text,re.I)
    return (_number(match[1]),'V') if match else None


def build_projections(snapshot):
    docs={d.source_id:d for d in snapshot.documents}
    names={norm(entity_id(d).split('/')[-1]):entity_id(d) for d in snapshot.documents if d.entity_type!='Document'}
    result=[];projection_revision=load_config()[0]['projection_revision']
    def emit(c,entity,predicate,value,*,unit='',selector='',cardinality='scalar',complete=True,valid=True,representation='structured_field',spans=None,complete_for_source=False):
        group=identifier(c.source_id,entity,predicate,selector,representation)
        spans=tuple(spans or (CanonicalSpan(c.chunk_id,0,len(c.chunk.text),'value'),))
        result.append(FactProjection(entity,predicate,value,c.source_id,spans,unit,group,cardinality,complete,representation,selector,valid,complete_for_source,docs[c.source_id].parser_version,projection_revision))
    for c in snapshot.chunks:
        doc=docs[c.source_id];entity=entity_id(doc);field=c.chunk.field_path.split('[')[0];text=c.chunk.text
        if field in ('power','interfaces','protocols','temperature_c','status'):
            valid=_typed_value(c,field) is not None
            value=_typed_value(c,field) or '';unit=''
            if field=='power':
                parsed=_voltage(text);valid=parsed is not None
                if parsed:value,unit=parsed
            emit(c,entity,field,value,unit=unit,valid=valid,complete=valid,
                 cardinality='set' if field in ('interfaces','protocols') else 'scalar')
        elif field=='features':
            value=text.removeprefix('features: ').strip()
            valid=value!=text and bool(value) and not re.search(r'ignore|reveal|игнор|секрет',value,re.I)
            emit(c,entity,'features',norm(value),cardinality='set',complete=valid and not re.search(r'и друг|например|в том числе|etc|проч|и т\.|…|\.\.\.',value,re.I),valid=valid)
        elif field=='specs':
            label,sep,value=text.partition(': ')
            if sep:
                valid=bool(re.fullmatch(r'\d+(?:[.,]\d+)?(?:\s+[A-Za-zА-Яа-я°]+)?',value))
                count=bool(re.search('вход|выход|количеств',label,re.I))
                if count:valid=bool(re.fullmatch(r'\d+',value))
                emit(c,entity,'spec',value,selector=norm(label),unit='count' if count else '',valid=valid,complete=valid)
        if field=='pdf.page':
            # Explicit typed lines only; flat text is never a PDF table.
            for match in re.finditer(r'(?:Supply: )(?P<value>\d+(?:\.\d+)? V DC)\.',text):
                value,unit=_voltage(match['value'])
                emit(c,entity,'power',value,unit=unit,representation='quoted_statement',
                     spans=(CanonicalSpan(c.chunk_id,match.start('value'),match.end('value'),'value'),))
            for match in re.finditer(r'(?:Network interface: |Application protocol: )(?P<value>[A-Za-z0-9 -]+)\.',text):
                pred='interfaces' if match[0].startswith('Network') else 'protocols'
                emit(c,entity,pred,norm(match['value']),cardinality='set',representation='quoted_statement',
                     spans=(CanonicalSpan(c.chunk_id,match.start('value'),match.end('value'),'value'),))
        if field!='body':continue
        # Body relation grammar is deliberately a closed declaration, not arbitrary co-occurrence.
        purpose=re.fullmatch(r'(?:Вымышленное\s+)?ПО\s+([A-Za-z0-9-]+)\s+настраивает адрес Modbus (?:учебного\s+)?([A-Za-z0-9-]+) по ([A-Za-z0-9-]+)\.',text)
        if purpose and norm(purpose[1]) in names and norm(purpose[2]) in names and names[norm(purpose[1])]==entity:
            emit(c,entity,'purpose',norm(text),representation='quoted_statement')
            emit(c,names[norm(purpose[2])],'configuration_interface',norm(purpose[3]),representation='quoted_statement')
        composition=re.fullmatch(r'В состав (?:вымышленного\s+)?(?:стенда|системы)\s+([A-Za-z0-9-]+)\s+входят\s+(.+)\.',text)
        if composition and norm(composition[1]) in names and names[norm(composition[1])]==entity:
            found=re.findall(r'[A-Za-z]+-[A-Za-z0-9-]+',composition[2])
            remainder=composition[2]
            for name in found:remainder=remainder.replace(name,'')
            complete=not re.sub(r'контроллер|шлюз|ПО|и|[\s,]','',remainder)
            for name in found:
                if norm(name) in names:
                    emit(c,entity,'composition',names[norm(name)],cardinality='set',complete=complete,
                         representation='quoted_statement')
        config=re.search(r'\b([A-Za-z0-9-]+) используется для локальной настройки\.',text)
        if config:
            rest=text[:config.start()]+text[config.end():]
            # Permit the known declarative protocol/interface clause, never arbitrary instructions.
            if not rest.strip() or re.fullmatch(r'Контроллер передаёт показания по [A-Za-z0-9 ]+ через [A-Za-z0-9-]+\.\s*',rest):
                emit(c,entity,'configuration_interface',norm(config[1]),representation='quoted_statement',
                     spans=(CanonicalSpan(c.chunk_id,config.start(),config.end(),'value'),))
        if '|' not in text:continue
        lines=text.splitlines(keepends=True)
        if any(line.strip() and not line.strip().startswith('|') for line in lines):continue
        rows=[];offset=0
        for line in lines:
            cells=[]
            if line.strip().startswith('|'):
                bars=[m.start() for m in re.finditer(r'\|',line)]
                for left,right in zip(bars,bars[1:]):
                    raw=line[left+1:right];value=raw.strip();start=offset+left+1+len(raw)-len(raw.lstrip())
                    cells.append((value,start,start+len(value)))
                if cells and not all(re.fullmatch(r':?-+:?',v[0]) for v in cells):rows.append(cells)
            offset+=len(line)
        if len(rows)<2:continue
        headers=rows[0]
        entity_cols=[i for i,h in enumerate(headers) if re.search(r'модель|изделие|model',h[0],re.I)]
        if len(entity_cols)!=1:continue
        ec=entity_cols[0]
        for row in rows[1:]:
            if len(row)!=len(headers) or norm(row[ec][0]) not in names:continue
            subject=names[norm(row[ec][0])]
            for i,(cell,start,end) in enumerate(row):
                header,hstart,hend=headers[i];pred=None
                if re.search('питан|напряжен',header,re.I):pred='power'
                elif re.search('интерфейс',header,re.I):pred='interfaces'
                elif re.search('протокол',header,re.I):pred='protocols'
                if pred is None:continue
                spans=(CanonicalSpan(c.chunk_id,row[ec][1],row[ec][2],'subject'),
                       CanonicalSpan(c.chunk_id,hstart,hend,'header'),CanonicalSpan(c.chunk_id,start,end,'value'))
                value=norm(cell);unit='';valid=True
                if pred=='power':
                    parsed=_voltage(cell)
                    valid=parsed is not None
                    if parsed:value,unit=parsed
                else:valid=bool(re.fullmatch(r'[A-Za-z0-9+./_-]+(?: [A-Za-z0-9]+)?',cell))
                emit(c,subject,pred,value,unit=unit,cardinality='scalar' if pred=='power' else 'set',
                     complete=valid and (pred=='power' or 'интерфейсы' in norm(header) or 'протоколы' in norm(header)),
                     valid=valid,representation='markdown_table',spans=spans,complete_for_source=valid)
    return tuple(result)


def validate_projection(projection,snapshot):
    mapping={c.chunk_id:c for c in snapshot.chunks}
    if not isinstance(projection,FactProjection):raise ValueError('Invalid fact projection')
    for span in projection.spans:
        if (span.chunk_id not in mapping or mapping[span.chunk_id].source_id!=projection.source_id
                or type(span.start) is not int or type(span.end) is not int
                or not 0<=span.start<span.end<=len(mapping[span.chunk_id].chunk.text)):
            raise ValueError('Invalid canonical projection span')
    if projection not in build_projections(snapshot):raise ValueError('Projection differs from canonical derivation')
    return projection


def selector_matches(projection,selector):
    if selector.startswith('interface='):
        value=selector.removeprefix('interface=')
        if projection.predicate in ('interfaces','configuration_interface'):
            return projection.value==value
        if projection.predicate=='purpose':
            return bool(re.search(r' по '+re.escape(value)+r'\.$',projection.value))
        return False
    return projection.selector==selector
