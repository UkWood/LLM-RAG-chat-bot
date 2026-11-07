"""Draft claims are not verified claims; citations are constructed by the backend."""
from dataclasses import dataclass,asdict

@dataclass(frozen=True)
class EvidenceQuote:
    chunk_id: str
    quote: str

@dataclass(frozen=True)
class SupportedClaim:
    id: str
    text: str
    evidence: tuple[EvidenceQuote,...]

@dataclass(frozen=True)
class Citation:
    number: int
    chunk_id: str
    url: str
    title: str
    content_sha256: str
    page: int|None

@dataclass(frozen=True)
class Answer:
    status: str
    text: str
    snapshot_id: str=''
    claims: tuple[SupportedClaim,...]=()
    questions: tuple[str,...]=()
    sources: tuple[Citation,...]=()
    reason_code: str|None=None
    as_of: float|None=None

    def to_dict(self):return asdict(self)
