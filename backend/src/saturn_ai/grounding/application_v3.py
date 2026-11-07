"""Explicit V3 experiment: locked proofs, exact quotes, atomic current policy."""
from hashlib import sha256
from ..domain import Chunk,Claim,GenerationRequest
from .contracts import GateResult,GroundedCitation
from .v3_contracts import QueryPlanV3,ResultV3
from .v2_contracts import GateV2
from .v3_config import load_v3_config,checked_settings
from .projections import build_projections
from .router_v3 import IntentRouter,plan_v3
from .retrieval_v3 import retrieve_v3
from .evidence_v3 import select_v3,evaluate_v3
from .gate_v2 import canonical_reference

class GroundedConsultantV3:
    def __init__(self,service,scorer,provider,*,mode='hybrid',router=None,settings=None):
        if provider.offline is not True or provider.test_only is not True:raise ValueError('Offline test provider required')
        if mode not in ('lexical','dense','hybrid'):raise ValueError('Explicit retrieval mode required')
        self.service=service;self.scorer=scorer;self.provider=provider;self.mode=mode
        self.router=router or IntentRouter(scorer);self.settings=checked_settings(settings or load_v3_config()[0])
    def answer(self,question):
        snapshot_id='';plan=None;trace={};initial_pairs=self.router.pairs_scored
        def stop(reason,status='refused',state='not_evaluated'):
            return ResultV3(status,state,reason,snapshot_id,plan=plan,trace=dict(trace))
        if self.provider.offline is not True or self.provider.test_only is not True:return stop('provider_not_allowed','error')
        try:
            indexes=self.service.capture();snapshot=indexes.snapshot;snapshot_id=snapshot.snapshot_id
            projections=build_projections(snapshot)
            planned=plan_v3(question,snapshot,projections,self.router,self.settings,self.service.catalog)
            trace['intent_pairs']=self.router.pairs_scored-initial_pairs
            if not isinstance(planned,QueryPlanV3):
                return stop(planned.reason,'error' if planned.reason=='invalid_question' else 'clarification' if planned.state=='ambiguous' else 'refused',planned.state)
            plan=planned
            if plan.question_sha256!=sha256(question.encode()).hexdigest():raise ValueError('Question/plan mismatch')
            pool,retrieval=retrieve_v3(self.service,indexes,plan,question,self.scorer,mode=self.mode);trace.update(retrieval)
            if trace['intent_pairs']+trace['pairs_scored']>110:raise ValueError('V3 pair budget exceeded')
            selection=select_v3(plan,snapshot,pool,self.service.catalog,projections)
            if isinstance(selection,GateV2):return stop(selection.reason,'clarification' if selection.state=='ambiguous' else 'refused',selection.state)
            gate=evaluate_v3(plan,selection,snapshot,self.service.catalog,projections)
        except Exception:return stop('pipeline_unavailable','error')
        if gate.state!='sufficient':return stop(gate.reason,'clarification' if gate.state=='ambiguous' else 'refused',gate.state)
        mapping={c.chunk_id:c for c in snapshot.chunks};records={r.source_id:r for r in snapshot.registry.entries}
        quote_ids=tuple(dict.fromkeys(cid for b in gate.bindings if b.reference is None for cid in b.evidence_ids))
        def permitted():
            allowed={c.chunk_id for c in self.service.catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
            return set(gate.evidence_ids)<=allowed
        trace.update(selected_ids=list(gate.evidence_ids),selected_groups=[o.group_id for o in selection.options],anchor_ids=list(gate.anchor_ids))
        try:
            if not permitted():return stop('source_revoked',state='insufficient')
            claims=()
            if quote_ids:
                evidence=tuple(Chunk(cid,mapping[cid].source_id,';'.join(sorted({plan.needs[b.need_index].entity_id for b in gate.bindings if cid in b.evidence_ids})),
                    ' / '.join(mapping[cid].chunk.heading_path),mapping[cid].chunk.text,'typed-v3') for cid in quote_ids)
                if self.provider.offline is not True or self.provider.test_only is not True:return stop('provider_not_allowed','error')
                try:claims=self.provider.generate(GenerationRequest(question,evidence))
                except Exception:return stop('provider_unavailable','error',gate.state)
            if not permitted():return stop('source_revoked',state='insufficient')
            if (not isinstance(claims,tuple) or len(claims)!=len(quote_ids) or any(not isinstance(c,Claim) or type(c.chunk_id) is not str
                    or type(c.text) is not str or c.chunk_id not in quote_ids or c.text!=mapping[c.chunk_id].chunk.text for c in claims)
                    or {c.chunk_id for c in claims}!=set(quote_ids)):
                return stop('unverified_answer',state=gate.state)
            verified=tuple(Claim(mapping[c.chunk_id].chunk.text,c.chunk_id) for c in claims);refs=[]
            for binding in gate.bindings:
                if binding.reference is not None:
                    r=binding.reference;ref=canonical_reference(r.kind,r.entity_id,r.source_id,r.anchor_chunk_id,snapshot)
                    if ref!=r:return stop('unverified_reference',state=gate.state)
                    if ref not in refs:refs.append(ref)
            citations=[]
            for cid in gate.evidence_ids:
                c=mapping[cid];r=records[c.source_id]
                citations.append(GroundedCitation(cid,c.source_id,r.title,r.url or r.canonical_path,c.chunk.document_id,c.source_hash,c.source_commit,
                    c.chunk.heading_path,c.chunk.page_start,c.chunk.page_end))
            if not permitted():return stop('source_revoked',state='insufficient')
            return ResultV3('answered',gate.state,None,snapshot_id,verified,tuple(citations),tuple(refs),plan,gate.bindings,gate.anchor_ids,trace=dict(trace))
        except Exception:return stop('publication_unavailable','error',gate.state)
