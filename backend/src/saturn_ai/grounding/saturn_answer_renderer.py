"""Deterministic plain-text rendering only: no LLM, Markdown or HTML execution."""
import html
import json

from .saturn_contracts import SaturnContextError


def plain(value):
    """Escape source-supplied text for safe downstream HTML/Markdown display.

    Callers must still display answer_text as text, never as trusted HTML.
    """
    if type(value) is not str:
        raise SaturnContextError("answer_integrity_failure")
    return html.escape(value, quote=True).replace("\r", "\\r").replace("\n", "\\n")


def structured_field(entity, field_path, raw_value_json, unit, qualifiers_json):
    try:
        value = json.loads(raw_value_json)
        shown = value if isinstance(value, str) else raw_value_json
        if qualifiers_json is not None:
            qualifiers = json.loads(qualifiers_json)
            if not isinstance(qualifiers, dict):
                raise ValueError("qualifiers must be an object")
    except (TypeError, ValueError):
        raise SaturnContextError("answer_integrity_failure") from None
    text = plain(entity) + " — " + plain(field_path) + ": " + plain(
        shown if isinstance(shown, str) else raw_value_json)
    # Never concatenate unit into an ambiguous source literal (12.5V, 0,5МПа).
    # Keep each exact source token explicitly labelled.
    if unit is not None:
        text += " [unit: " + plain(unit) + "]"
    if qualifiers_json not in (None, "{}"):
        text += " [qualifiers: " + plain(qualifiers_json) + "]"
    return text + "."


def structured_relation(subject, predicate, obj):
    return plain(subject) + " — " + plain(predicate) + " — " + plain(obj) + "."


def document_reference(document):
    text = (plain(document.title) + " [" + plain(document.kind) + "] — " +
            plain(document.original_url))
    if document.version is not None:
        text += " [version: " + plain(document.version) + "]"
    if document.date is not None:
        text += " [date: " + plain(document.date) + "]"
    # A metadata hit is not a verified PDF extraction.
    text += " [extraction: " + plain(document.extraction_status or "not_extracted") + "]"
    return text + "."


def render_answer(status, statements):
    """Only structured facts and exact document references are primary answer text."""
    lines = [item.text for item in statements
             if item.statement_kind != "source_quote"]
    if status == "partial":
        lines.append("Ответ неполный. Для остальных требований недостаточно подтверждений.")
    elif status == "needs_support":
        lines.append("В доступных для текущего ответа материалах не найдено достаточного подтверждения.")
    elif status == "clarification":
        lines = ["Необходимо уточнить вопрос: неоднозначность или противоречивые сведения."]
    elif status == "error":
        lines = ["Не удалось выполнить проверку."]
    return "\n".join(lines)
