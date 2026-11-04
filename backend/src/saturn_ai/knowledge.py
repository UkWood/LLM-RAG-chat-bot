"""Strict, network-free synthetic Markdown ingestion and immutable memory index."""
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .domain import Chunk, Snapshot, Source

FIELDS = {'source_id', 'entity', 'title', 'url', 'path', 'approved_sha256',
          'visibility', 'approval_state', 'allowed_usage', 'test_only', 'cloud_allowed'}
INTENTS = {'Интерфейсы': 'interfaces', 'Руководство': 'manual'}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest key')
        result[key] = value
    return result


def load_snapshot(root: Path) -> Snapshot:
    root = root.resolve()
    raw = (root / 'manifest.json').read_bytes()
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'test_only', 'sources'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['test_only'] is not True or not isinstance(data['sources'], list)):
        raise ValueError('Expected synthetic manifest v1')
    sources, chunks, seen = [], [], set()
    for entry in data['sources']:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise ValueError('Invalid source fields')
        if entry['test_only'] is not True or entry['cloud_allowed'] is not False:
            raise ValueError('Synthetic sources must remain local test fixtures')
        for key in FIELDS - {'test_only', 'cloud_allowed', 'allowed_usage'}:
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError('Missing source string')
        sid = entry['source_id']
        if sid in seen or not re.fullmatch(r'[a-z0-9-]+', sid):
            raise ValueError('Invalid or duplicate source ID')
        seen.add(sid)
        if not re.fullmatch(r'[A-Z]+-\d+', entry['entity']):
            raise ValueError('Invalid synthetic entity')
        if entry['visibility'] not in {'PUBLIC', 'INTERNAL', 'UNKNOWN'}:
            raise ValueError('Invalid visibility')
        if entry['approval_state'] not in {'approved', 'pending', 'revoked'}:
            raise ValueError('Invalid approval state')
        usage = entry['allowed_usage']
        if (not isinstance(usage, list) or any(not isinstance(x, str) or x not in {'local_index', 'local_generate'} for x in usage)
                or len(usage) != len(set(usage))):
            raise ValueError('Invalid synthetic usage')
        url = urlsplit(entry['url'])
        if (url.scheme != 'https' or url.netloc != 'example.invalid'
                or not url.path.startswith('/synthetic/') or url.query or url.fragment):
            raise ValueError('Only inert synthetic citation URLs allowed')
        rel = Path(entry['path'])
        path = (root / rel).resolve()
        if rel.is_absolute() or '..' in rel.parts or not path.is_relative_to(root) or path.suffix != '.md':
            raise ValueError('Unsafe fixture path')
        if not re.fullmatch(r'[a-f0-9]{64}', entry['approved_sha256']):
            raise ValueError('Invalid hash')
        content = path.read_bytes()
        digest = sha256(content).hexdigest()
        if digest != entry['approved_sha256']:
            raise ValueError('Fixture content hash drift')
        source = Source(sid, entry['entity'], entry['title'], entry['url'], digest,
                        entry['visibility'], entry['approval_state'], tuple(usage))
        # Denied bytes are never parsed or indexed; metadata is not provider context.
        sources.append(source)
        if not source.allowed():
            continue
        text = content.decode('utf-8')
        for number, section in enumerate(re.split(r'^## ', text, flags=re.MULTILINE)[1:]):
            heading, _, body = section.partition('\n')
            intent = INTENTS.get(heading.strip())
            if not intent:  # Unsupported sections cannot become technical facts.
                continue
            body = body.strip()
            # This fixture profile accepts complete facts, never arbitrary prose.
            # It is deliberately not a general prompt-injection detector.
            entity = re.escape(source.entity)
            grammar = (rf'Учебный {entity} поддерживает интерфейс RS-(?:485|232)\.'
                       if intent == 'interfaces' else
                       rf'Руководство учебного {entity}: синтетическая инструкция, версия [1-9][0-9]*\.')
            if not re.fullmatch(grammar, body):
                continue
            chunk_id = sha256(f'{sid}:{digest}:{number}:{body}'.encode()).hexdigest()
            chunks.append(Chunk(chunk_id, sid, source.entity, heading.strip(), body, intent))
    # Includes all manifest bytes and content hashes; metadata changes change snapshot identity.
    return Snapshot(sha256(raw).hexdigest(), tuple(sources), tuple(chunks))
