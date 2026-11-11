"""Stage 5B deterministic question decomposition and exact snapshot resolution.

This intentionally supports a SMALL explicit grammar, not open-ended NLP.
Any unknown portion of a question is represented as unresolved, never dropped.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from ..ingestion.saturn_contracts import canonical_json, stable_id
from .saturn_contracts import SaturnContextError

MAX_QUESTION_NEEDS = 6

# Stage 4A emits dotted ASCII components, repeated numeric index brackets,
# and bracketed canonical JSON strings for every non-simple nested key.
# Root keys are source-defined, so exact paths may additionally contain
# punctuation; they can be recognized against this pinned snapshot only.
_ROOT_TOKEN = re.compile(r"[\w-]+", re.UNICODE)
_DOT_COMPONENT = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_ARRAY_INDEX = re.compile(r"(?:0|[1-9][0-9]*)")
_FIELD_HEAD = re.compile(
    r"^\s*(?P<entity>[^:\r\n?]{1,160}?)\s*:\s*", re.UNICODE,
)
_JSON_DECODER = json.JSONDecoder()

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
        names = {entity.entity_id, entity.title, entity.slug}
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


def _canonical_field_end(text, start):
    """Read the exact Stage 4A child-path syntax, not comma-separated prose."""
    root = _ROOT_TOKEN.match(text, start)
    if root is None:
        return None
    cursor = root.end()
    while cursor < len(text):
        if text[cursor] == ".":
            child = _DOT_COMPONENT.match(text, cursor + 1)
            if child is None:
                return None
            cursor = child.end()
        elif text[cursor] == "[":
            part = cursor + 1
            if part >= len(text):
                return None
            if text[part] == '"':
                try:
                    key, end = _JSON_DECODER.raw_decode(text, part)
                except (ValueError, TypeError):
                    return None
                # Stage 4A uses canonical_json(key), not arbitrary JSON
                # spelling or decoding/re-encoding with lost source identity.
                if (not isinstance(key, str) or
                        text[part:end] != canonical_json(key) or
                        end >= len(text) or text[end] != "]"):
                    return None
                cursor = end + 1
            else:
                index = _ARRAY_INDEX.match(text, part)
                if (index is None or index.end() >= len(text) or
                        text[index.end()] != "]"):
                    return None
                cursor = index.end() + 1
        else:
            break
    return cursor


def _field_boundary(text, pos):
    return pos == len(text) or text[pos] in " \t,?"


def _field_end(text, start, declared):
    """Prefer an exact source-backed field when Stage 4A root keys are unusual.

    The ordinary scanner is still needed for absent/unknown fields, which
    remain independently diagnosable as missing_in_context.
    """
    scanned = _canonical_field_end(text, start)
    declared_ends = [
        start + len(path) for path in declared
        if text.startswith(path, start) and
        _field_boundary(text, start + len(path))
    ]
    if declared_ends:
        best = max(declared_ends)
        if scanned is None or best > scanned:
            return best
    return scanned


def _fields_for_entity(snapshot, entity_id):
    return frozenset(f.field_path for f in snapshot.facts
                     if f.entity_id == entity_id)


def _parse_field_list(question, start, entity_id, status, declared):
    """Bounded lexical scanner, respecting comma/and/и only outside JSON."""
    cursor = start
    needs = []
    while True:
        end = _field_end(question, cursor, declared)
        if end is None or end <= cursor:
            return (_unresolved(question),)
        needs.append(_need(question, cursor, end, "field_value",
                           entity_id=entity_id, field_path=question[cursor:end],
                           resolution_status=status))
        if len(needs) > MAX_QUESTION_NEEDS:
            raise SaturnContextError("resource_budget_exceeded")
        following = end
        while following < len(question) and question[following] in " \t":
            following += 1
        if following < len(question) and question[following] == "?":
            # The suffix is not assumed to be an optional extra question:
            # it is a separate unresolved need, with its literal span.
            remainder = question[following + 1:]
            if remainder.strip():
                needs.append(_unresolved(question, following + 1))
                if len(needs) > MAX_QUESTION_NEEDS:
                    raise SaturnContextError("resource_budget_exceeded")
            return tuple(needs)
        if following < len(question) and question[following] == ",":
            cursor = following + 1
            while cursor < len(question) and question[cursor] in " \t":
                cursor += 1
            continue
        if following > end:
            for word in ("and", "и"):
                limit = following + len(word)
                if (question[following:limit].casefold() == word and
                        limit < len(question) and question[limit] in " \t"):
                    cursor = limit
                    while cursor < len(question) and question[cursor] in " \t":
                        cursor += 1
                    break
            else:
                return (_unresolved(question),)
            continue
        return (_unresolved(question),)


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

    match = _FIELD_HEAD.match(question)
    if match:
        entity_id, status = _resolve(match.group("entity"), index)
        return _parse_field_list(
            question, match.end(), entity_id, status,
            _fields_for_entity(snapshot, entity_id) if entity_id else (),
        )

    # Failure of the strict grammar includes all words, qualifiers, negations,
    # numeric expressions and unsupported question clauses in one safe need.
    return (_unresolved(question),)
