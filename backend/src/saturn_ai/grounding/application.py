"""Captured offline evidence -> verbatim claims -> canonical citations. No cloud or labels."""
from ..domain import Chunk,Claim,GenerationRequest
from .contracts import GroundedCitation,GroundedResult,QuestionPlan
from .gate import plan_question,evaluate_evidence


class GroundedConsultant:
    def __init__(self,service,scorer,provider,*,mode='hybrid'):
        if provider.offline is not True or provider.test_only is not True:
            raise ValueError('Grounded synthetic pipeline accepts only offline test provider')
        if mode not in ('lexical','dense','hybrid'):raise ValueError('Invalid explicit retrieval mode')
        self.service=service;self.scorer=scorer;self.provider=provider;self.mode=mode

    def answer(self,question):
        snapshot_id=''
        def stop(reason,status='refused',state='not_evaluated'):
            return GroundedResult(status,state,reason,snapshot_id)
        if self.provider.offline is not True or self.provider.test_only is not True:
            return stop('provider_not_allowed','error')
        try:
            indexes=self.service.capture();snapshot=indexes.snapshot;snapshot_id=snapshot.snapshot_id
            planned=plan_question(question,snapshot)
            if not isinstance(planned,QuestionPlan):
                status='error' if planned.reason=='invalid_question' else 'clarification' if planned.state=='ambiguous' else 'refused'
                return stop(planned.reason,status,planned.state)
            trace=self.service._rerank(indexes,question,self.scorer,mode=self.mode)
            if trace.snapshot_id!=snapshot_id:raise ValueError('Captured snapshot mismatch')
            gate=evaluate_evidence(planned,snapshot,trace.final,self.service.catalog)
        except Exception:
            return stop('retrieval_unavailable','error')
        if gate.state!='sufficient':return stop(gate.reason,state=gate.state)
        mapping={c.chunk_id:c for c in snapshot.chunks};ids=gate.evidence_ids
        def permitted():
            indexed={c.chunk_id for c in self.service.catalog.eligible_snapshot_chunks(snapshot,'local_index')}
            generated={c.chunk_id for c in self.service.catalog.eligible_snapshot_chunks(snapshot,'local_generate')}
            return set(ids)<=indexed&generated
        try:
            if not permitted():return stop('source_revoked',state='insufficient')
            if len(ids)>5 or sum(len(mapping[cid].chunk.text) for cid in ids)>8000:
                return stop('evidence_budget',state='insufficient')
            evidence=tuple(Chunk(cid,mapping[cid].source_id,planned.entity_id,
                                 ' / '.join(mapping[cid].chunk.heading_path),mapping[cid].chunk.text,planned.aspect) for cid in ids)
            request=GenerationRequest(question,evidence)
            if self.provider.offline is not True or self.provider.test_only is not True:
                return stop('provider_not_allowed','error')
            claims=self.provider.generate(request)
        except Exception:
            return stop('provider_unavailable','error',gate.state)
        try:
            if not permitted():return stop('source_revoked',state='insufficient')
            if (not isinstance(claims,tuple) or not 1<=len(claims)<=5
                    or any(not isinstance(c,Claim) or type(c.chunk_id) is not str or type(c.text) is not str
                           or c.chunk_id not in ids or c.text!=mapping[c.chunk_id].chunk.text for c in claims)
                    or len({c.chunk_id for c in claims})!=len(claims) or {c.chunk_id for c in claims}!=set(ids)):
                return stop('unverified_answer',state=gate.state)
            records={r.source_id:r for r in snapshot.registry.entries}
            verified=tuple(Claim(mapping[c.chunk_id].chunk.text,c.chunk_id) for c in claims)
            citations=[]
            for claim in verified:
                c=mapping[claim.chunk_id];record=records[c.source_id]
                citations.append(GroundedCitation(c.chunk_id,c.source_id,record.title,record.url or record.canonical_path,
                    c.chunk.document_id,c.source_hash,c.source_commit,c.chunk.heading_path,c.chunk.page_start,c.chunk.page_end))
            if not permitted():return stop('source_revoked',state='insufficient')
            return GroundedResult('answered',gate.state,None,snapshot_id,verified,tuple(citations))
        except Exception:
            return stop('validation_unavailable','error',gate.state)
