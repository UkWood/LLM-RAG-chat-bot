"""Stage 5B deterministic question decomposition and exact snapshot resolution.

This intentionally supports a SMALL explicit grammar, not open-ended NLP.
Any unknown portion of a question is represented as unresolved, never dropped.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from ..ingestion.saturn_contracts import stable_id
from .saturn_contracts import SaturnContextError

MAX_QUESTION_NEEDS = 6

# Field paths are exact canonical paths (including generic additive fields).
# No field-name dictionary and no synonym or engineering unit inference.
_COMPONENT = r"[\w-]+(?:\[\d+\])?"
_FIELD = _COMPONENT + r"(?:\." + _COMPONENT + r")*"
_SEPARATOR = r"(?:,|\band\b|\bи\b)"
_LIST_RX = re.compile(r"^" + _FIELD + r"(?:[ \t]*" + _SEPARATOR +
                      r"[ \t]*" + _FIELD + r")*$", re.IGNORECASE)
_TOKEN_RX = re.compile(_FIELD, re.UNICODE)
_SEPARATOR_RX = re.compile(r"[ \t]*" + _SEPARATOR + r"[ \t]*", re.IGNORECASE)
_FIELD_QUERY = re.compile(
    r"^\s*(?P<entity>[^:\r\n?]{1,160}?)\s*:\s*"
    r"(?P<fields>[^?\r\n]{1,240}?)\s*\?",
    re.UNICODE,
)
_RELATION_QUERY = re.compile(
    r"^\s*relation\(\s*(?P<subject>[^,()?]{1,160}?)\s*,\s*"
    r"(?P<predicate>[^,()?]{1,100}?)\s*,\s*"
    r"(?P<object>[^,()?]{1,160}?)\s*\)\s*\?\s*$",
    re.UNICODE,
)
_DOCUMENT_QUERY = re.compile(
    r"^\s*(?:Документ|Document)\s*:\s*(?P<title>[^|\r\n?]{1,250}?)"
    r"(?:\s*\|\s*owner=(?P<owner>[^|\r\n?]{1,160}?))?\s*\??\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SaturnQuestionNeed:
    need_id: str
    kind: str
    question_span: tuple[int, int]
    original_text: str
    entity_id: str | None
    field_path: str | None
    predicate: str | None
    object_entity_id: str | None
    resolution_status: str
    # Metadata lookup remains separate from engineering answer evidence.
    document_title: str | None = None


def _identity_index(snapshot):
    """Build an exact source-declared identity map once for the pinned corpus."""
    index = {}
    for entity in snapshot.entities:
        names = {entity.entity_id, entity.title}
        # Only explicit identity fields from the original trusted source.
        try:
            raw = json.loads(entity.raw_frontmatter_json)
        except (ValueError, TypeError):
            raw = {}
        for key in ("designation", "model", "alias", "aliases"):
            value = raw.get(key)
            if isinstance(value, str):
                names.add(value)
            elif isinstance(value, list) and len(value) <= 64:
                names.update(v for v in value if isinstance(v, str))
        for name in names:
            if name and len(name) <= 256:
                index.setdefault(name, set()).add(entity.entity_id)
    return index


def _resolve(name, index):
    candidates = index.get(name.strip(), ())
    if not candidates:
        return None, "missing_entity"
    if len(candidates) != 1:
        return None, "ambiguous"
    return next(iter(candidates)), "resolved"


def _need(question, start, end, kind, *, entity_id=None, field_path=None,
          predicate=None, object_entity_id=None, resolution_status="resolved",
          document_title=None):
    digest = sha256(question.encode("utf-8")).hexdigest()
    need_id = stable_id("saturn-question-need-v1", digest, start, end, kind,
                        entity_id, field_path, predicate, object_entity_id,
                        resolution_status, document_title)
    return SaturnQuestionNeed(
        need_id, kind, (start, end), question[start:end], entity_id,
        field_path, predicate, object_entity_id, resolution_status, document_title,
    )


def _unresolved(question, start=0, end=None):
    return _need(question, start, len(question) if end is None else end,
                 "unresolved", resolution_status="unresolved")


def parse_saturn_question_needs(question, snapshot):
    """Pure parser: deterministic, original UTF-8 spans, max 6 needs.

    Examples:
      ENTITY: interface, protocol?
      relation(ENTITY A, contains, ENTITY B)?
      Документ: exact title | owner=ENTITY
    """
    if not isinstance(question, str):
        raise SaturnContextError("invalid_request")
    # This also rejects invalid surrogate strings independently of caller.
    try:
        question.encode("utf-8")
    except UnicodeError:
        raise SaturnContextError("invalid_request") from None
    index = _identity_index(snapshot)
    relation = _RELATION_QUERY.fullmatch(question)
    if relation:
        subject, subject_status = _resolve(relation.group("subject"), index)
        obj, object_status = _resolve(relation.group("object"), index)
        status = ("ambiguous" if "ambiguous" in (subject_status, object_status)
                  else "missing_entity" if "missing_entity" in
                       (subject_status, object_status) else "resolved")
        return (_need(question, 0, len(question), "relation",
                      entity_id=subject, predicate=relation.group("predicate").strip(),
                      object_entity_id=obj, resolution_status=status),)

    document = _DOCUMENT_QUERY.fullmatch(question)
    if document:
        title = document.group("title").strip()
        owner = document.group("owner")
        entity_id, status = _resolve(owner, index) if owner else (None, "resolved")
        return (_need(question, 0, len(question), "document_lookup",
                      entity_id=entity_id, resolution_status=status,
                      document_title=title),)

    match = _FIELD_QUERY.match(question)
    if match:
        raw_fields = match.group("fields")
        fields_text = raw_fields.strip()
        if _LIST_RX.fullmatch(fields_text):
            eid, status = _resolve(match.group("entity"), index)
            result = []
            cursor = 0
            # Consume field / separator / field sequentially. Using re.split
            # would incorrectly split a literal source field named "and".
            origin = match.start("fields") + len(raw_fields) - len(raw_fields.lstrip())
            while cursor < len(fields_text):
                token = _TOKEN_RX.match(fields_text, cursor)
                if token is None:
                    return (_unresolved(question),)
                field = token.group()
                result.append(_need(question, origin + token.start(),
                                    origin + token.end(), "field_value",
                                    entity_id=eid, field_path=field,
                                    resolution_status=status))
                if len(result) > MAX_QUESTION_NEEDS:
                    raise SaturnContextError("resource_budget_exceeded")
                cursor = token.end()
                if cursor < len(fields_text):
                    separator = _SEPARATOR_RX.match(fields_text, cursor)
                    if separator is None or separator.end() == cursor:
                        return (_unresolved(question),)
                    cursor = separator.end()
            # A recognized prefix is not permission to discard the suffix.
            if match.end() < len(question) and question[match.end():].strip():
                result.append(_unresolved(question, match.end(), len(question)))
            if len(result) > MAX_QUESTION_NEEDS:
                raise SaturnContextError("resource_budget_exceeded")
            return tuple(result)

    # Failure of the strict grammar includes all words, qualifiers, negations,
    # numeric expressions and unsupported question clauses in one safe need.
    return (_unresolved(question),)
