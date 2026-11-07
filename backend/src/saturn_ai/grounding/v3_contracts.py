"""V3 roles, typed proposals and locked canonical evidence options."""
from dataclasses import dataclass,field
from .v2_contracts import EvidenceNeed,SourceConstraints,TypedReference,GroundedResultV2
from ..retrieval.contracts import Candidate

@dataclass(frozen=True)
class RoleSpan:
    start:int
    end:int
    role:str

@dataclass(frozen=True)
class ClauseV3:
    entity_ids:tuple[str,...]
    phrase:str
    phrase_span:tuple[int,int]
    constraints:SourceConstraints=field(default_factory=SourceConstraints)
    selector:str=''
    recognized:tuple[str,str]|None=None
    roles:tuple[RoleSpan,...]=()
    count:bool=False

@dataclass(frozen=True)
class IntentEntry:
    predicate:str
    selector:str
    description:str

@dataclass(frozen=True)
class IntentDecision:
    predicate:str
    selector:str
    score:float|None
    margin:float|None
    origin:str

@dataclass(frozen=True)
class QueryPlanV3:
    needs:tuple[EvidenceNeed,...]
    question_sha256:str
    planner_revision:str
    catalogue_revision:str
    gate_schema_revision:str
    roles:tuple[RoleSpan,...]
    decisions:tuple[IntentDecision,...]=()

@dataclass(frozen=True)
class GroupOption:
    need_index:int
    group_id:str
    projection_ids:tuple[str,...]
    evidence_ids:tuple[str,...]
    reference:TypedReference|None=None

@dataclass(frozen=True)
class EvidenceSelectionV3:
    options:tuple[GroupOption,...]
    candidates:tuple[Candidate,...]
    anchors:tuple[str,...]=()
    binding_hash:str=''

@dataclass(frozen=True)
class ResultV3(GroundedResultV2):
    plan:QueryPlanV3|None=None
    schema_version:int=3
    trace:dict=field(default_factory=dict)
