"""Conservative fixture-only gate and extractive grounding; no semantic quality claim."""
import re
from .domain import AnswerResult, Citation, Claim, GenerationRequest, Snapshot
from .providers import LLMProvider

DESIGNATION = re.compile(r'\b(?:[a-zа-я][a-zа-я0-9]*(?:-[a-zа-я0-9]+)+(?:[./][a-zа-я0-9]+)*|[a-zа-я]+\d+)\b', re.I)


class Consultant:
    def __init__(self, snapshot: Snapshot, provider: LLMProvider):
        if provider.offline is not True or provider.test_only is not True:
            raise ValueError('M1 accepts only offline test providers')
        self.snapshot = snapshot
        self.provider = provider
        self.revoked: set[str] = set()

    def answer(self, question: str) -> AnswerResult:
        def stop(reason, status='refused'):
            message = ('Уточните одно учебное изделие и один поддерживаемый запрос.'
                       if status == 'clarification' else
                       'Сервис недоступен.' if status == 'error' else
                       'В синтетическом корпусе недостаточно подтверждений для ответа.')
            return AnswerResult(status, message, reason_code=reason, snapshot_id=self.snapshot.snapshot_id)

        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            return stop('invalid_question', 'error')
        if self.provider.offline is not True or self.provider.test_only is not True:
            return stop('provider_not_allowed', 'error')
        folded = question.casefold()
        entities = {match.upper() for match in DESIGNATION.findall(question)}
        approved = {s.entity for s in self.snapshot.sources if s.allowed()}
        if entities - approved:
            return stop('unknown_entity')
        if not entities:
            return stop('no_evidence')
        if len(entities) != 1:
            return stop('ambiguous_entity', 'clarification')
        entity = re.escape(next(iter(entities)).casefold())
        # Full question grammar prevents answering just one supported substring of
        # a mixed or negated request. More natural phrasing is future evaluation work.
        forms = {
            'interfaces': rf'(?:какие\s+)?интерфейсы(?:\s+(?:у|поддерживает))?\s+{entity}[?!.]?',
            'manual': rf'(?:найдите\s+)?руководство(?:\s+(?:для|на))?\s+{entity}[?!.]?',
        }
        intents = {intent for intent, form in forms.items() if re.fullmatch(form, folded.strip())}
        if len(intents) != 1:
            return stop('no_evidence')
        # Minimal lexical retrieval is deliberately limited to entity + explicit aspect.
        evidence = tuple(c for c in self.snapshot.chunks
                         if c.entity in entities and c.intent in intents)
        if not evidence:
            return stop('no_evidence')
        registry = {s.source_id: s for s in self.snapshot.sources}

        def permitted():
            return all(c.source_id not in self.revoked and registry[c.source_id].allowed() for c in evidence)

        if not permitted():
            return stop('source_revoked')
        if len(evidence) > 5 or sum(len(c.text) for c in evidence) > 8000:
            return stop('evidence_budget')
        if len({c.text for c in evidence}) > 1:
            return stop('conflicting_evidence')
        try:
            claims = self.provider.generate(GenerationRequest(question, evidence))
        except Exception:
            return stop('provider_unavailable', 'error')
        if not permitted():
            return stop('source_revoked')
        by_id = {c.chunk_id: c for c in evidence}
        if (not isinstance(claims, tuple) or not claims or len(claims) > 5
                or any(not isinstance(claim, Claim) or not isinstance(claim.chunk_id, str)
                       or claim.chunk_id not in by_id or claim.text != by_id[claim.chunk_id].text
                       for claim in claims)):
            return stop('unverified_answer')
        cited = tuple(dict.fromkeys(claim.chunk_id for claim in claims))
        citations = tuple(Citation(c.source_id, registry[c.source_id].title,
                                   registry[c.source_id].url, c.heading, c.chunk_id,
                                   registry[c.source_id].content_hash)
                          for c in (by_id[cid] for cid in cited))
        return AnswerResult('answered', '\n'.join(dict.fromkeys(claim.text for claim in claims)),
                            citations, cited, snapshot_id=self.snapshot.snapshot_id)
