"""All-needs gate with typed provenance and atomic current policy intersection."""
from math import isfinite
from ..retrieval.contracts import Candidate
from .gate import entity_id
from .v2_contracts import QueryPlanV2,EvidenceNeed,SourceConstraints,GateV2,NeedBinding,TypedReference
from .v2_config import load_config
from .projections import build_projections,projection_id,document_kind,selector_matches


def canonical_reference(kind,eid,source_id,anchor_id,snapshot):
    docs={d.source_id:d for d in snapshot.documents};mapping={c.chunk_id:c for c in snapshot.chunks}
    records={r.source_id:r for r in snapshot.registry.entries}
    if source_id not in docs or anchor_id not in mapping:raise ValueError('Reference source/anchor absent')
    doc=docs[source_id];record=records[source_id];anchor=mapping[anchor_id]
    if anchor.source_id!=source_id or entity_id(doc)!=eid:raise ValueError('Reference entity/source mismatch')
    if kind=='document':
        if record.document_type!='manual' or anchor.chunk.page_start is None:raise ValueError('Unapproved manual reference')
        value=record.title
    elif kind=='entity_type':
        if record.entity_type is None or anchor.chunk.field_path!='title':raise ValueError('Typed metadata title anchor required')
        value=doc.entity_type
    else:raise ValueError('Unsupported metadata reference')
    return TypedReference(kind,eid,source_id,value,record.title,record.url or record.canonical_path,
        doc.document_id,doc.content_hash,anchor_id,anchor.chunk.page_start)


def evaluate_v2(plan,snapshot,candidates,catalog,projections):
    config,revision=load_config()
    if (not isinstance(plan,QueryPlanV2) or plan.config_revision!=revision or not 1<=len(plan.needs)<=4
            or len({n.entity_id for n in plan.needs})>3):raise ValueError('Invalid pinned v2 plan')
    for n in plan.needs:
        if (not isinstance(n,EvidenceNeed) or n.predicate not in config['predicates']
                or not isinstance(n.constraints,SourceConstraints)
                or n.constraints.document_kind not in config['document_kinds']
                or n.constraints.representation not in config['representations']
                or type(n.selector) is not str or len(n.selector)>128 or (n.selector and n.predicate!='spec' and not (n.predicate in ('interfaces','configuration_interface','purpose') and n.selector in ('interface=usb','interface=ethernet','interface=rs-485')))):
            raise ValueError('Invalid typed requirement')
    mapping={c.chunk_id:c for c in snapshot.chunks};docs={d.source_id:d for d in snapshot.documents}
    records={r.source_id:r for r in snapshot.registry.entries}
    if not isinstance(candidates,tuple) or len(candidates)>5:raise ValueError('Canonical top5 required')
    seen=set()
    for rank,c in enumerate(candidates,1):
        if (not isinstance(c,Candidate) or c.chunk_id not in mapping or c.chunk_id in seen
                or c.source_id!=mapping[c.chunk_id].source_id or c.snapshot_id!=snapshot.snapshot_id
                or type(c.rank) is not int or c.rank!=rank or type(c.score) not in (int,float) or not isfinite(c.score)):
            raise ValueError('Invalid v2 candidate')
        seen.add(c.chunk_id)
    allowed={c.chunk_id for c in catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
    if tuple(projections)!=build_projections(snapshot):raise ValueError('Projection set differs from canonical derivation')
    ranked=[c.chunk_id for c in candidates if c.chunk_id in allowed];ranked_sources={mapping[cid].source_id for cid in ranked}
    bindings=[];evidence=[];anchors=[]
    def add(ids):
        for cid in ids:
            if cid not in evidence:evidence.append(cid)
    def matches(source,constraints,representation):
        return (constraints.document_kind=='any' or document_kind(docs[source],records[source])==constraints.document_kind) and (
            constraints.representation=='any' or constraints.representation==representation)
    for index,need in enumerate(plan.needs):
        if need.predicate in ('document_reference','entity_type'):
            kind='document' if need.predicate=='document_reference' else 'entity_type'
            possible=[]
            for source,doc in docs.items():
                if entity_id(doc)!=need.entity_id or source not in ranked_sources:continue
                rep='quoted_statement' if kind=='document' else 'structured_field'
                if not matches(source,need.constraints,rep):continue
                eligible=[c for c in snapshot.chunks if c.source_id==source and c.chunk_id in allowed]
                if kind=='document':
                    if records[source].document_type!='manual':continue
                    pages=[c for c in eligible if c.chunk.page_start is not None]
                    if not pages:continue
                    anchor=min(pages,key=lambda c:(c.chunk.page_start,c.chunk_id))
                else:
                    if records[source].entity_type is None:continue
                    titles=[c for c in eligible if c.chunk.field_path=='title' and c.chunk_id in ranked]
                    if not titles:continue
                    anchor=titles[0]
                possible.append(canonical_reference(kind,need.entity_id,source,anchor.chunk_id,snapshot))
            if not possible:return GateV2('insufficient','missing_reference')
            values={(r.value,r.content_hash) for r in possible}
            if len(values)>1:return GateV2('ambiguous','ambiguous_reference')
            ref=possible[0]
            if ref.anchor_chunk_id not in ranked and ref.anchor_chunk_id not in anchors:anchors.append(ref.anchor_chunk_id)
            add((ref.anchor_chunk_id,));bindings.append(NeedBinding(index,(ref.anchor_chunk_id,),reference=ref));continue
        matching=[p for p in projections if p.entity_id==need.entity_id and p.predicate==need.predicate and selector_matches(p,need.selector)
            and matches(p.source_id,need.constraints,p.representation)
            and all(span.chunk_id in allowed for span in p.spans)]
        if not matching:return GateV2('insufficient','no_evidence')
        if any(not p.valid for p in matching):return GateV2('insufficient','malformed_evidence')
        groups={}
        for p in matching:groups.setdefault(p.group_id,[]).append(p)
        complete=[]
        for group in groups.values():
            values=frozenset((p.value,p.unit) for p in group)
            if group[0].cardinality=='scalar' and len(values)>1:return GateV2('conflict','conflicting_evidence')
            if all(p.complete or (need.constraints.representation=='markdown_table' and p.complete_for_source) for p in group):
                complete.append((values,group))
        if not complete:return GateV2('insufficient','incomplete_evidence')
        agreed=complete[0][0]
        if any(values!=agreed for values,_ in complete):return GateV2('conflict','conflicting_evidence')
        if any(not {(p.value,p.unit) for p in group}<=agreed for group in groups.values()):
            return GateV2('conflict','conflicting_evidence')
        chosen=[];covered=set()
        valid_complete={projection_id(p) for _,group in complete for p in group}
        for cid in ranked:
            for p in matching:
                key=(p.value,p.unit)
                quote_ids={span.chunk_id for span in p.spans if span.role=='value'}
                if (key not in covered and cid in quote_ids and quote_ids<=set(ranked)
                        and projection_id(p) in valid_complete):
                    chosen.append(p);covered.add(key)
        if covered!=set(agreed):return GateV2('insufficient','incomplete_evidence')
        ids=tuple(dict.fromkeys(span.chunk_id for p in chosen for span in p.spans if span.role=='value'))
        add(ids);bindings.append(NeedBinding(index,ids,tuple(projection_id(p) for p in chosen)))
    if len(anchors)>1 or len(evidence)>5 or sum(len(mapping[cid].chunk.text) for cid in evidence)>8000:
        return GateV2('insufficient','evidence_budget')
    return GateV2('sufficient','requirements_complete',tuple(evidence),tuple(bindings),tuple(anchors))
