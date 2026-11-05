"""Strict gold-label validation without generating answers or retrieval metrics."""
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from ..ingestion.pipeline import build_fixture
from ..ingestion.registry import load_registry, unique_object
from ..snapshots import KnowledgeSnapshot, build_snapshot

DISTRIBUTION = dict(exact_spec=5, exact_entity=4, paraphrase=4, multi_doc=3, document_lookup=3,
                    typo=2, no_answer=3, unknown_entity=2, injection=2, out_of_domain=2)
FIELDS = {'id', 'question', 'category', 'split', 'expected_status', 'must_answer', 'must_refuse',
          'expected_sources', 'expected_facts', 'expected_evidence', 'tags'}


@dataclass(frozen=True)
class ExpectedEvidence:
    source_id: str
    text: str
    field_path: str
    page: int | None


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    category: str
    split: str
    expected_status: str
    must_answer: bool
    must_refuse: bool
    expected_sources: tuple[str, ...]
    expected_facts: tuple[str, ...]
    expected_evidence: tuple[ExpectedEvidence, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Dataset:
    revision: str
    registry_revision: str
    cases: tuple[Case, ...]
    profile: str = 'synthetic_offline'


def _strings(value):
    if (not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() or len(v) > 4000 for v in value)
            or len(value) != len(set(value))):
        raise ValueError('Expected unique bounded strings')
    return tuple(value)


def validate_dataset(raw: bytes, snapshot: KnowledgeSnapshot) -> Dataset:
    if (not isinstance(snapshot, KnowledgeSnapshot)
            or snapshot != build_snapshot(snapshot.ingestion, snapshot.registry)):
        raise ValueError('Invalid snapshot')
    if len(raw) > 1_000_000:
        raise ValueError('Dataset size limit')
    data = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'profile', 'registry_revision', 'cases'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['profile'] != 'synthetic_offline' or data['registry_revision'] != snapshot.registry.revision
            or not isinstance(data['cases'], list) or len(data['cases']) != 30):
        raise ValueError('Expected revision-bound synthetic dataset v1 with 30 cases')
    if len(snapshot.documents) != 10 or sum(d.parser_version == 'pdf-v1' for d in snapshot.documents) != 2:
        raise ValueError('Expected ten-document baseline with two PDF manuals')
    allowed = [c for c in snapshot.chunks if c.visibility == 'PUBLIC' and c.approval_state == 'approved'
               and 'local_generate' in c.allowed_usage]
    cases, seen, covered = [], set(), set()
    for item in data['cases']:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError('Invalid case fields')
        for field in ('id', 'question', 'category', 'split', 'expected_status'):
            if not isinstance(item[field], str) or not item[field].strip() or len(item[field]) > 4000:
                raise ValueError('Missing bounded case string')
        if item['id'] in seen or item['category'] not in DISTRIBUTION or item['split'] not in ('calibration', 'held_out'):
            raise ValueError('Invalid/duplicate case identity or category/split')
        seen.add(item['id'])
        status = item['expected_status']
        if (status not in ('answered', 'refused', 'clarification')
                or type(item['must_answer']) is not bool or type(item['must_refuse']) is not bool
                or item['must_answer'] != (status == 'answered') or item['must_refuse'] != (status == 'refused')):
            raise ValueError('Contradictory expected outcome')
        category = item['category']
        if (category in ('exact_spec', 'exact_entity', 'paraphrase', 'multi_doc', 'document_lookup') and status != 'answered'
                or category in ('no_answer', 'unknown_entity', 'out_of_domain') and status != 'refused'
                or category == 'typo' and status != 'clarification'):
            raise ValueError('Expected status disagrees with baseline category')
        sources, facts, tags = (_strings(item[key]) for key in ('expected_sources', 'expected_facts', 'tags'))
        if (any(not s.startswith('synthetic:') for s in sources)
                or not {category, 'synthetic'} <= set(tags) or not isinstance(item['expected_evidence'], list)):
            raise ValueError('Invalid synthetic sources/tags/evidence')
        evs, ev_seen = [], set()
        for ev in item['expected_evidence']:
            if not isinstance(ev, dict) or set(ev) != {'source_id', 'text', 'field_path', 'page'}:
                raise ValueError('Invalid evidence pointer')
            if (any(not isinstance(ev[key], str) or not ev[key].strip() for key in ('source_id', 'text', 'field_path'))
                    or ev['page'] is not None and (type(ev['page']) is not int or ev['page'] < 1)):
                raise ValueError('Invalid evidence fields')
            expected = ExpectedEvidence(**ev)
            if expected in ev_seen or not any(
                    c.source_id == expected.source_id and c.chunk.field_path == expected.field_path
                    and c.chunk.page_start == expected.page and expected.text in c.chunk.text for c in allowed):
                raise ValueError('Gold fact/source/field/page not supported by allowed parsed chunk')
            ev_seen.add(expected)
            evs.append(expected)
        if status == 'answered':
            if not sources or not facts or not evs:
                raise ValueError('Answered case requires source/fact/evidence labels')
            if set(sources) != {e.source_id for e in evs} or set(facts) != {e.text for e in evs}:
                raise ValueError('Fact/source labels disagree with evidence pointers')
            if category == 'multi_doc' and len(sources) < 2:
                raise ValueError('Multi-doc labels require independent sources')
            covered.update(sources)
        elif sources or facts or evs:
            raise ValueError('Negative/clarification cases cannot claim evidence')
        cases.append(Case(**dict(item, expected_sources=sources, expected_facts=facts,
                                 expected_evidence=tuple(evs), tags=tags)))
    if (Counter(c.category for c in cases) != DISTRIBUTION
            or Counter(c.split for c in cases) != dict(calibration=20, held_out=10)
            or Counter(c.category for c in cases if c.split == 'held_out') != {key: 1 for key in DISTRIBUTION}
            or covered != {d.source_id for d in snapshot.documents}):
        raise ValueError('Baseline distribution/split/source coverage mismatch')
    return Dataset(sha256(raw).hexdigest(), snapshot.registry.revision, tuple(cases))


def run_preflight(root: Path, dataset_path: Path) -> dict:
    registry = load_registry((root/'registry.json').read_bytes())
    snapshot = build_snapshot(build_fixture(root, registry, registry.source_snapshot), registry)
    dataset = validate_dataset(dataset_path.read_bytes(), snapshot)
    return dict(report_kind='synthetic_baseline_preflight', schema_version=1, test_only=True,
                registry_revision=registry.revision, snapshot_id=snapshot.snapshot_id,
                dataset_revision=dataset.revision, document_count=len(snapshot.documents),
                pdf_document_count=sum(d.parser_version == 'pdf-v1' for d in snapshot.documents),
                chunk_count=len(snapshot.chunks), case_count=len(dataset.cases),
                category_distribution=dict(Counter(c.category for c in dataset.cases)),
                split_distribution=dict(Counter(c.split for c in dataset.cases)),
                parser_versions=sorted({d.parser_version for d in snapshot.documents}),
                snapshot_contract_version=1,
                quality_evaluation=dict(retrieval='not_run', reranking='not_run', grounding='not_run', source_hit_at_5=None),
                case_labels=[dict(id=c.id, split=c.split, expected_status=c.expected_status,
                                  label_support='validated') for c in dataset.cases])
