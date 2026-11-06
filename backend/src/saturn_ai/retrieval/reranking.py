"""Bounded pair-scoring contracts; scores are relevance logits, not confidence."""
from dataclasses import dataclass
from math import isfinite
from typing import Protocol
from .contracts import Candidate, SearchTrace


class Reranker(Protocol):
    identity: dict
    def score_pairs(self, query: str, passages: list[str]) -> list[float]: ...


def validate_pairs(query, passages):
    if (not isinstance(query,str) or not query.strip() or len(query)>4000
            or not isinstance(passages,list) or len(passages)>30
            or any(not isinstance(p,str) or not p.strip() or len(p)>20000 for p in passages)):
        raise ValueError('Invalid bounded query/passage pairs')


def checked_scores(scores, count):
    if (not isinstance(scores,list) or len(scores)!=count
            or any(type(s) not in (int,float) or not isfinite(s) for s in scores)):
        raise ValueError('Expected one finite scalar per passage')
    return scores


@dataclass(frozen=True)
class RerankTrace:
    snapshot_id: str
    mode: str
    baseline: SearchTrace
    input_candidates: tuple[Candidate,...]
    scored: tuple[Candidate,...]
    final: tuple[Candidate,...]
    reranker_identity: dict
    scoring_seconds: float
