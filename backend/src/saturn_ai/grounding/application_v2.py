"""Opt-in complete typed planner application. Exact quotes + backend-only references."""
from ..domain import Chunk,Claim,GenerationRequest
from .contracts import GateResult,GroundedCitation
from .v2_contracts import QueryPlanV2,GroundedResultV2
from .projections import build_projections
from .planner_v2 import plan_v2
from .gate_v2 import evaluate_v2,canonical_reference


class GroundedConsultantV2:
    def __init__(self,service,scorer,provider,*,mode='hybrid'):
        if provider.offline is not True or provider.test_only is not True:raise ValueError('Offline test provider required')
        if mode not in ('lexical','dense','hybrid'):raise ValueError('Explicit retrieval mode required')
        self.service=service;self.scorer=scorer;self.provider=provider;self.mode=mode

    def answer(self,question):
        snapshot_id='';plan=None
        def stop(reason,status='refused',state='not_evaluated'):
            return GroundedResultV2(status,state,reason,snapshot_id,plan=plan)
        if self.provider.offline is not True or self.provider.test_only is not True:return stop('provider_not_allowed','error')
        try:
            indexes=self.service.capture();snapshot=indexes.snapshot;snapshot_id=snapshot.snapshot_id
            projections=build_projections(snapshot);planned=plan_v2(question,snapshot,projections)
            if not isinstance(planned,QueryPlanV2):
                status='error' if planned.reason=='invalid_question' else 'clarification' if planned.state=='ambiguous' else 'refused'
                return stop(planned.reason,status,planned.state)
            plan=planned;trace=self.service._rerank(indexes,question,self.scorer,mode=self.mode)
            if trace.snapshot_id!=snapshot_id:raise ValueError('Mixed snapshot')
            gate=evaluate_v2(plan,snapshot,trace.final,self.service.catalog,projections)
        except Exception:return stop('retrieval_unavailable','error')
        if gate.state!='sufficient':
            return stop(gate.reason,'clarification' if gate.state=='ambiguous' else 'refused',gate.state)
        mapping={c.chunk_id:c for c in snapshot.chunks};records={r.source_id:r for r in snapshot.registry.entries}
        def permitted():
            allowed={c.chunk_id for c in self.service.catalog.eligible_snapshot_chunks_for_usages(snapshot,('local_index','local_generate'))}
            return set(gate.evidence_ids)<=allowed
        quote_ids=tuple(dict.fromkeys(cid for b in gate.bindings if b.reference is None for cid in b.evidence_ids))
        try:
            if not permitted():return stop('source_revoked',state='insufficient')
            claims=()
            if quote_ids:
                evidence=tuple(Chunk(cid,mapping[cid].source_id,';'.join(sorted({plan.needs[b.need_index].entity_id for b in gate.bindings if cid in b.evidence_ids})),
                    ' / '.join(mapping[cid].chunk.heading_path),mapping[cid].chunk.text,'typed-v2') for cid in quote_ids)
                if self.provider.offline is not True or self.provider.test_only is not True:return stop('provider_not_allowed','error')
                try:claims=self.provider.generate(GenerationRequest(question,evidence))
                except Exception:return stop('provider_unavailable','error',gate.state)
            if not permitted():return stop('source_revoked',state='insufficient')
            if (not isinstance(claims,tuple) or len(claims)!=len(quote_ids)
                    or any(not isinstance(c,Claim) or type(c.chunk_id) is not str or type(c.text) is not str
                        or c.chunk_id not in quote_ids or c.text!=mapping[c.chunk_id].chunk.text for c in claims)
                    or {c.chunk_id for c in claims}!=set(quote_ids)):
                return stop('unverified_answer',state=gate.state)
            verified=tuple(Claim(mapping[c.chunk_id].chunk.text,c.chunk_id) for c in claims)
            refs=[]
            for binding in gate.bindings:
                ref=binding.reference
                if ref is not None:
                    rebuilt=canonical_reference(ref.kind,ref.entity_id,ref.source_id,ref.anchor_chunk_id,snapshot)
                    if rebuilt!=ref:return stop('unverified_reference',state=gate.state)
                    if rebuilt not in refs:refs.append(rebuilt)
            citations=[]
            for cid in gate.evidence_ids:
                c=mapping[cid];r=records[c.source_id]
                citations.append(GroundedCitation(cid,c.source_id,r.title,r.url or r.canonical_path,c.chunk.document_id,
                    c.source_hash,c.source_commit,c.chunk.heading_path,c.chunk.page_start,c.chunk.page_end))
            if not permitted():return stop('source_revoked',state='insufficient')
            return GroundedResultV2('answered',gate.state,None,snapshot_id,verified,tuple(citations),tuple(refs),plan,gate.bindings,gate.anchor_ids)
        except Exception:return stop('validation_unavailable','error',gate.state)
