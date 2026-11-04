"""Read-only Astro content adapter. Pinned schema, bounded YAML, no execution."""
from hashlib import sha256
import math
from pathlib import PurePosixPath
import re
import yaml
from yaml.tokens import AliasToken, AnchorToken, TagToken

from .contracts import Document, DocumentLink, Relationship, identifier, make_chunk
from .registry import SourceRecord

PARSER_VERSION = 'site-v1'
MAX_BYTES = 1_000_000


class StrictLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError('Duplicate or non-string YAML key')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _string(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 6000 or '\x00' in value:
        raise ValueError('Invalid content string')
    if re.search(r'<[!/a-zA-Z]', value):
        raise ValueError('HTML content needs a separately evaluated adapter')
    return value.strip()


def _strings(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError('Expected bounded string list')
    return [_string(item) for item in value]


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Expected finite number')
    return str(value)


def parse_site(record: SourceRecord, content: bytes) -> Document:
    digest = sha256(content).hexdigest()
    if (record.source_kind != 'site_content' or len(content) > MAX_BYTES
            or not record.permits('local_index', digest, record.source_commit)):
        raise ValueError('Source denied or invalid size/hash')
    text = content.decode('utf-8').replace('\r\n', '\n')
    if '\x00' in text or not text.startswith('---\n'):
        raise ValueError('Missing frontmatter')
    front, separator, body = text[4:].partition('\n---\n')
    if not separator or len(front) > 65536:
        raise ValueError('Invalid frontmatter')
    try:
        tokens = list(yaml.scan(front))
        if len(tokens) > 10000 or any(isinstance(t, (AliasToken, AnchorToken, TagToken)) for t in tokens):
            raise ValueError('YAML aliases/tags disabled')
        meta = yaml.load(front, Loader=StrictLoader)
    except (yaml.YAMLError, RecursionError):
        raise ValueError('Invalid YAML frontmatter') from None
    if not isinstance(meta, dict) or type(meta.get('draft', False)) is not bool or meta.get('draft', False):
        raise ValueError('Draft or malformed content')
    title = _string(meta.get('title'))
    if title != record.title:
        raise ValueError('Title does not match approved registry metadata')
    path = PurePosixPath(record.path)
    collection, slug = path.parts[2], path.stem
    entity_id = f'{collection}/{slug}'
    mapping = {'products': 'Device', 'systems': 'System', 'groups': 'Group',
               'articles': 'Article', 'news': 'News', 'pages': 'Page'}
    entity_type = mapping[collection]
    if collection == 'products' and meta.get('group') == 'programmnoe-obespechenie':
        entity_type = 'Software'
    if collection == 'systems':
        if meta.get('kind', 'system') not in ('system', 'category'):
            raise ValueError('Invalid system kind')
        if meta.get('kind') == 'category':
            entity_type = 'Category'
    if collection == 'pages' and meta.get('kind') == 'solution':
        entity_type = 'Solution'
    if entity_type != record.entity_type:
        raise ValueError('Entity mapping disagrees with registry')
    docid = identifier(record.source_id, digest, record.source_commit, record.path, PARSER_VERSION)
    chunks, relations, links = [], [], []

    def add(value, field, heading=()):
        chunks.append(make_chunk(docid, record.source_id, _string(value), heading, field))

    add(title, 'title')
    for key in ('name', 'subtitle', 'summary', 'notice', 'power', 'ip'):
        if key in meta:
            add(meta[key], key)
    if collection == 'products':
        status = meta.get('status', 'active')
        if status not in ('active', 'obsolete', 'discontinued'):
            raise ValueError('Invalid product status')
        add('status: '+status, 'status')
    for key in ('interfaces', 'protocols', 'features', 'applications'):
        if key in meta:
            for index, value in enumerate(_strings(meta[key])):
                add(f'{key}: {value}', f'{key}[{index}]')
    if 'temperature_c' in meta:
        values = meta['temperature_c']
        if not isinstance(values, dict) or set(values) != {'min', 'max'}:
            raise ValueError('Invalid temperature')
        low, high = _number(values['min']), _number(values['max'])
        if float(low) > float(high):
            raise ValueError('Invalid temperature range')
        add(f'temperature: {low} … {high} °C', 'temperature_c')
    for key, unit in (('mass_kg', 'kg'), ('lifetime_years', 'years')):
        if key in meta:
            add(f'{key}: {_number(meta[key])} {unit}', key)
    if 'dimensions_mm' in meta:
        values = meta['dimensions_mm']
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError('Invalid dimensions')
        add('dimensions: '+' × '.join(_number(v) for v in values)+' mm', 'dimensions_mm')
    specs = meta.get('specs', [])
    if not isinstance(specs, list) or len(specs) > 100:
        raise ValueError('Invalid specs')
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict) or not {'name', 'value'} <= set(spec) or set(spec) - {'name', 'value', 'group'}:
            raise ValueError('Invalid specification')
        group = (_string(spec['group'])+' / ') if 'group' in spec else ''
        add(group+_string(spec['name'])+': '+_string(spec['value']), f'specs[{index}]')
    # Explicit references only. Links do not imply compatibility or approve targets.
    targets = {'systems': 'systems', 'software': 'products', 'related': 'products',
               'products': 'products', 'articles': 'articles', 'solutions': 'pages'}
    for field, target_collection in targets.items():
        for index, ref in enumerate(_strings(meta.get(field, []))):
            if not re.fullmatch(r'[a-z0-9-]+', ref):
                raise ValueError('Invalid relationship reference')
            relations.append(Relationship(record.source_id, entity_id, f'{target_collection}/{ref}',
                                          field, f'{field}[{index}]'))
    for field, target_collection in (('group', 'groups'), ('system', 'systems'), ('variant_of', 'products')):
        if field in meta:
            ref = _string(meta[field])
            if not re.fullmatch(r'[a-z0-9-]+', ref):
                raise ValueError('Invalid relationship reference')
            relations.append(Relationship(record.source_id, entity_id, f'{target_collection}/{ref}', field, field))
    docs = meta.get('documents', [])
    if not isinstance(docs, list) or len(docs) > 100:
        raise ValueError('Invalid document candidates')
    for doc in docs:
        if (not isinstance(doc, dict) or not {'title', 'kind', 'url'} <= set(doc)
                or set(doc) - {'title', 'kind', 'url', 'version', 'date'}):
            raise ValueError('Invalid document candidate')
        links.append(DocumentLink(_string(doc['title']), _string(doc['url']), _string(doc['kind']),
                                  _string(doc['version']) if 'version' in doc else None))
    headings, section = [], []
    fence = None

    def flush():
        joined = '\n'.join(section).strip()
        if joined:
            add(joined, 'body', tuple(title for level, title in headings))
        section.clear()

    for line in body.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if marker:
            if fence is None:
                fence = (marker[1][0], len(marker[1]))
            elif (marker[1][0] == fence[0] and len(marker[1]) >= fence[1]
                  and not marker[2].strip()):
                fence = None
            continue
        if fence or line.expandtabs(4).startswith('    '):
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading:
            flush()
            level = len(heading[1])
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, _string(heading[2])))
        else:
            section.append(line)
    if fence:
        raise ValueError('Unclosed code fence')
    flush()
    if len(chunks) > 500:
        raise ValueError('Chunk count limit')
    return Document(docid, record.source_id, digest, PARSER_VERSION, title, entity_id, entity_type,
                    record.source_commit, record.path, tuple(chunks), tuple(relations), tuple(links))
