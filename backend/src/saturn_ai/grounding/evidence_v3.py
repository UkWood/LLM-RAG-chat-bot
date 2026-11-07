"""Complete canonical group options, bounded cover and exact locked V3 validation."""
from dataclasses import asdict
from math import isfinite
import re
from ..ingestion.contracts import identifier
from ..retrieval.contracts import Candidate
from .v2_contracts import EvidenceNeed,SourceConstraints,GateV2,NeedBinding
from .v3_contracts import QueryPlanV3,GroupOption,EvidenceSelectionV3,RoleSpan
from .v2_config import load_config
from .v3_config import load_v3_config,revision
from .router_v3 import catalogue
from .projections import build_projections,projection_id,selector_matches,document_kind
from .gate_v2 import canonical_reference
from .gate import entity_id


def validate_plan(plan):
    cfg,_=load_v3_config();v2,gate_revision=load_config()
    revisions={revision(dict(cfg,score_min=float(s),margin_min=float(m))) for s in cfg['score_grid'] for m in cfg['margin_grid']}
    if (not isinstance(plan,QueryPlanV3) or plan.planner_revision not in revisions or plan.gate_schema_revision!=gate_revision
            or not isinstance(plan.needs,tuple) or not 1<=len(plan.needs)<=4 or len({n.entity_id for n in plan.needs})>3
            or type(plan.question_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',plan.question_sha256)
            or not plan.roles or any(not isinstance(r,RoleSpan) or type(r.start) is not int or type(r.end) is not int or not 0<=r.start<r.end<=4000 for r in plan.roles)):
        raise ValueError('Invalid pinned V3 plan')
    for n in plan.needs:
        if (not isinstance(n,EvidenceNeed) or type(n.entity_id) is not str or not isinstance(n.constraints,SourceConstraints)
                or n.predicate not in v2['predicates'] or n.constraints.document_kind not in v2['document_kinds']
                or n.constraints.representation not in v2['representations'] or type(n.selector) is not str or len(n.selector)>128
                or n.selector and n.predicate!='spec' and not (n.predicate in ('interfaces','configuration_interface','purpose')
                and n.selector in ('interface=usb','interface=ethernet','interface=rs-485'))):raise ValueError('Invalid V3 need')
    if len(set(plan.needs))!=len(plan.needs):raise ValueError('Duplicate V3 needs')


def validate_pool(snapshot,pool):
    mapping={c.chunk_id:c for c in snapshot.chunks};seen=set()
    if not isinstance(pool,tuple) or len(pool)>30:raise ValueError('Bounded canonical pool required')
    for rank,c in enumerate(pool,1):
        if (not isinstance(c,Candidate) or c.chunk_id not in mapping or c.chunk_id in seen or c.source_id!=mapping[c.chunk_id].source_id
                or c.snapshot_id!=snapshot.snapshot_id or type(c.rank) is not int or c.rank!=rank
                or type(c.score) not in (float,int) or not isfinite(c.score)):raise ValueError('Invalid V3 candidate')
        seen.add(c.chunk_id)
    return mapping


def _matches(source,representation,need,docs,records):
    return (need.constraints.document_kind=='any' or document_kind(docs[source],records[source])==need.constraints.document_kind) and (
        need.constraints.representation=='any' or representation==need.constraints.representation)


def options_for_need(need,index,snapshot,pool,catalog,projections):
    mapping=validate_pool(snapshot,pool)
    if tuple(projections)!=build_projections(snapshot):raise ValueError('Noncanonical V3 projections')
    docs={d.source_id:d for d in snapshot.documents};records={r.source_id:r for r in snapshot.registry.entries}
    allowed={c.chunk_id for c in catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
    ids={c.chunk_id for c in pool if c.chunk_id in allowed};sources={mapping[cid].source_id for cid in ids}
    if need.predicate in ('document_reference','entity_type'):
        kind='document' if need.predicate=='document_reference' else 'entity_type';options=[]
        for source,d in docs.items():
            rep='quoted_statement' if kind=='document' else 'structured_field'
            if entity_id(d)!=need.entity_id or source not in sources or not _matches(source,rep,need,docs,records):continue
            if kind=='document':
                if records[source].document_type!='manual':continue
                anchors=[c for c in snapshot.chunks if c.source_id==source and c.chunk_id in allowed and c.chunk.page_start is not None]
                if not anchors:continue
                anchor=min(anchors,key=lambda c:(c.chunk.page_start,c.chunk_id))
            else:
                if records[source].entity_type is None:continue
                anchors=[c for c in snapshot.chunks if c.source_id==source and c.chunk_id in ids and c.chunk.field_path=='title']
                if not anchors:continue
                anchor=anchors[0]
            ref=canonical_reference(kind,need.entity_id,source,anchor.chunk_id,snapshot)
            options.append(GroupOption(index,identifier('reference-v3',asdict(ref)),(),(anchor.chunk_id,),ref))
        if not options:return GateV2('insufficient','missing_reference')
        if len({(o.reference.value,o.reference.content_hash) for o in options})>1:return GateV2('ambiguous','ambiguous_reference')
        return tuple(sorted(options,key=lambda o:o.group_id))
    matching=[p for p in projections if p.entity_id==need.entity_id and p.predicate==need.predicate and selector_matches(p,need.selector)
        and _matches(p.source_id,p.representation,need,docs,records) and all(s.chunk_id in allowed for s in p.spans)]
    if not matching:return GateV2('insufficient','no_evidence')
    if any(not p.valid for p in matching):return GateV2('insufficient','malformed_evidence')
    groups={}
    for p in matching:groups.setdefault(p.group_id,[]).append(p)
    complete=[]
    for gid,group in groups.items():
        values={(p.value,p.unit) for p in group}
        if group[0].cardinality=='scalar' and len(values)>1:return GateV2('conflict','conflicting_evidence')
        if all(p.complete or need.constraints.representation=='markdown_table' and p.complete_for_source for p in group):complete.append((gid,group,values))
    if not complete:return GateV2('insufficient','incomplete_evidence')
    agreed=complete[0][2]
    if any(values!=agreed for _,_,values in complete) or any(not {(p.value,p.unit) for p in g}<=agreed for g in groups.values()):
        return GateV2('conflict','conflicting_evidence')
    options=[]
    for gid,group,_ in complete:
        evidence=tuple(sorted({s.chunk_id for p in group for s in p.spans if s.role=='value'}))
        if set(evidence)<=ids:options.append(GroupOption(index,gid,tuple(sorted(projection_id(p) for p in group)),evidence))
    return tuple(sorted(options,key=lambda o:o.group_id)) if options else GateV2('insufficient','incomplete_evidence')


def _fingerprint(plan,options,pool,anchors):
    return identifier('selection-v3',asdict(plan),[asdict(o) for o in options],[asdict(c) for c in pool],anchors)


def select_v3(plan,snapshot,pool,catalog,projections,limits=None):
    validate_plan(plan);mapping=validate_pool(snapshot,pool);cfg,_=load_v3_config();bounds=dict(cfg['limits'])
    for key,value in (limits or {}).items():
        if key not in ('states','transitions') or type(value) is not int or not 0<=value<=bounds[key]:raise ValueError('Invalid reduced test budget')
        bounds[key]=value
    states={frozenset():()};transitions=0;pool_ids={c.chunk_id for c in pool};scores={c.chunk_id:c.score for c in pool}
    def quality(options):
        vals=[min((scores.get(cid,0.) for cid in o.evidence_ids),default=0.) for o in options]
        return (-min(vals,default=0.),-sum(vals),tuple(o.group_id for o in options))
    for i,need in enumerate(plan.needs):
        options=options_for_need(need,i,snapshot,pool,catalog,projections)
        if isinstance(options,GateV2):return options
        new={}
        for union,chosen in states.items():
            for option in options:
                transitions+=1
                if transitions>bounds['transitions']:return GateV2('insufficient','evidence_selection_budget')
                ids=union|set(option.evidence_ids)
                if len(ids)>5 or len(ids-pool_ids)>1 or sum(len(mapping[cid].chunk.text) for cid in ids)>8000:continue
                candidate=chosen+(option,)
                if ids not in new or quality(candidate)<quality(new[ids]):new[ids]=candidate
                if len(new)>bounds['states']:return GateV2('insufficient','evidence_selection_budget')
        if not new:return GateV2('insufficient','evidence_budget')
        states=new
    ids,options=min(states.items(),key=lambda pair:(len(pair[0]),quality(pair[1])))
    anchors=tuple(sorted(ids-pool_ids))
    return EvidenceSelectionV3(options,pool,anchors,_fingerprint(plan,options,pool,anchors))


def evaluate_v3(plan,selection,snapshot,catalog,projections):
    validate_plan(plan)
    if not isinstance(selection,EvidenceSelectionV3) or type(selection.options) is not tuple or len(selection.options)!=len(plan.needs):raise ValueError('Invalid V3 selection')
    mapping=validate_pool(snapshot,selection.candidates)
    if selection.binding_hash!=_fingerprint(plan,selection.options,selection.candidates,selection.anchors):raise ValueError('Selected bindings changed')
    entries=catalogue(snapshot,projections,catalog)
    if identifier('intent-catalogue-v3',[(e.predicate,e.selector,e.description) for e in entries])!=plan.catalogue_revision:
        return GateV2('insufficient','catalogue_changed')
    evidence=[];bindings=[];seen=set()
    for option in selection.options:
        if type(option.need_index) is not int or option.need_index in seen or not 0<=option.need_index<len(plan.needs):raise ValueError('Invalid selected need index')
        seen.add(option.need_index)
        canonical=options_for_need(plan.needs[option.need_index],option.need_index,snapshot,selection.candidates,catalog,projections)
        if isinstance(canonical,GateV2):return canonical
        if option not in canonical:return GateV2('insufficient','unverified_selected_group')
        evidence.extend(cid for cid in option.evidence_ids if cid not in evidence)
        bindings.append(NeedBinding(option.need_index,option.evidence_ids,option.projection_ids,option.reference))
    anchors=tuple(sorted(set(evidence)-{c.chunk_id for c in selection.candidates}))
    if selection.anchors!=anchors or len(anchors)>1 or len(evidence)>5 or sum(len(mapping[cid].chunk.text) for cid in evidence)>8000:
        return GateV2('insufficient','evidence_budget')
    return GateV2('sufficient','requirements_complete',tuple(evidence),tuple(sorted(bindings,key=lambda b:b.need_index)),anchors)
