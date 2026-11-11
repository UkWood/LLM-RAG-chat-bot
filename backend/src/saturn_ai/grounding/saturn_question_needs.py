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
    """Return every exact syntactically valid field end at this offset.

    A source-declared root name can contain literal separators, but the
    alternative ordinary field-list grammar must not be discarded merely
    because the declared name is longer.
    """
    scanned = _canonical_field_end(text, start)
    ends = {scanned} if scanned is not None else set()
    ends.update(start + len(path) for path in declared
                if text.startswith(path, start)
                and _field_boundary(text, start + len(path)))
    return tuple(sorted(ends))


def _fields_for_entity(snapshot, entity_id):
    return frozenset(f.field_path for f in snapshot.facts
                     if f.entity_id == entity_id)


def _parse_field_list(question, start, entity_id, status, declared):
    """Enumerate bounded competing syntactic parses; never guess between them.

    Both source-declared unusual names and ordinary comma/and/и lists are
    eligible. The chosen interpretation must be unique regardless of
    retrieval evidence, source order, or token length. Quoted JSON components
    are consumed as a whole by _canonical_field_end, not split by punctuation.
    """
    pending = [(start, ())]
    complete = set()
    visited = 0
    # This is a lexical ambiguity guard, not an unbounded combinatorial
    # parser. Resource exhaustion fails closed instead of selecting a path.
    max_states = 256

    while pending:
        cursor, spans = pending.pop()
        visited += 1
        if visited > max_states:
            return (_unresolved(question),)
        for end in _field_end(question, cursor, declared):
            if end <= cursor:
                continue
            fields = spans + ((cursor, end),)
            if len(fields) > MAX_QUESTION_NEEDS:
                raise SaturnContextError("resource_budget_exceeded")
            following = end
            while following < len(question) and question[following] in " \t":
                following += 1
            if following < len(question) and question[following] == "?":
                if (question[following + 1:].strip()
                        and len(fields) == MAX_QUESTION_NEEDS):
                    raise SaturnContextError("resource_budget_exceeded")
                complete.add(fields)
                continue

            # A list delimiter is recognized only *between* field tokens.
            # In particular, a comma inside a canonical ["JSON, key"] is
            # consumed in the field token and cannot start a new list item.
            separator_end = None
            if following < len(question) and question[following] == ",":
                separator_end = following + 1
            elif following > end:
                for word in ("and", "и"):
                    limit = following + len(word)
                    if (question[following:limit].casefold() == word
                            and limit < len(question)
                            and question[limit] in " \t"):
                        separator_end = limit
                        break
            if separator_end is None:
                continue
            while (separator_end < len(question)
                   and question[separator_end] in " \t"):
                separator_end += 1
            if len(fields) == MAX_QUESTION_NEEDS:
                # Do not allow a long declared field to bypass the limit of
                # a competing multi-need interpretation.
                raise SaturnContextError("resource_budget_exceeded")
            pending.append((separator_end, fields))

    if len(complete) != 1:
        # Zero parses: unsupported syntax. Multiple parses: syntactically
        # competing needs, even if just one has selected structured evidence.
        return (_unresolved(question),)

    spans = next(iter(complete))
    needs = [
        _need(question, left, right, "field_value",
              entity_id=entity_id, field_path=question[left:right],
              resolution_status=status)
        for left, right in spans
    ]
    # No valid parse may silently hide an unsupported question suffix.
    end = question.find("?", spans[-1][1])
    if end >= 0 and question[end + 1:].strip():
        needs.append(_unresolved(question, end + 1))
    if len(needs) > MAX_QUESTION_NEEDS:
        raise SaturnContextError("resource_budget_exceeded")
    return tuple(needs)


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
