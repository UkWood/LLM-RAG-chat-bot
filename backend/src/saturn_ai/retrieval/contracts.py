from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    source_id: str
    snapshot_id: str
    score: float
    rank: int
    channel: str


@dataclass(frozen=True)
class SearchTrace:
    snapshot_id: str
    mode: str
    lexical: tuple[Candidate, ...]
    dense: tuple[Candidate, ...]
    final: tuple[Candidate, ...]


# Derived from parser field names/types, not evaluation cases or expected facts.
FIELD_ALIASES = {
    'interfaces': 'интерфейс интерфейсы разъём разъем interface',
    'protocols': 'протокол протоколы protocol',
    'temperature_c': 'температура диапазон temperature',
    'power': 'питание напряжение power voltage',
    'specs': 'характеристики параметры specifications',
    'status': 'статус выпуск status',
}
REPRESENTATION_VERSION = 'title-heading-field-aliases-v1'


def passage_text(snapshot, chunk):
    field = chunk.chunk.field_path.split('[')[0]
    record = next(r for r in snapshot.registry.entries if r.source_id == chunk.source_id)
    doc_type = 'руководство инструкция manual' if record.document_type == 'manual' else ''
    return ' '.join((chunk.source_title, ' '.join(chunk.chunk.heading_path),
                     FIELD_ALIASES.get(field, ''), doc_type, chunk.chunk.text))
