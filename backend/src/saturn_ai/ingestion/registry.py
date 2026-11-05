"""Strict registry v1 loader and exact revision access checks, without content I/O."""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

COMMON = {'source_id', 'source_kind', 'title', 'observed_content_sha256', 'approved_content_sha256',
          'visibility', 'approval_state', 'approval_id', 'approved_by', 'approved_at',
          'publication_verified', 'cloud_allowed', 'allowed_usage', 'reason'}
SITE = {'repository', 'source_commit', 'path', 'entity_type', 'canonical_path'}
EXTERNAL = {'url', 'discovered_from', 'document_type', 'fetch_state'}
USAGES = {'local_index', 'local_generate', 'cloud_generate'}
COLLECTIONS = {'products', 'systems', 'groups', 'articles', 'news', 'pages'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value, length=64):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{%d}' % length, value) is not None


def safe_path(value, *, absolute=False):
    # Locator spelling is canonical; reject encoding/normalization ambiguity.
    if (not _text(value) or '\\' in value or '%' in value or any(ord(c) < 32 for c in value)
            or '?' in value or '#' in value or ':' in value or value.startswith('//')):
        raise ValueError('Unsafe path')
    parts = value.split('/')
    if '..' in parts or '.' in parts or '' in parts[1:-1] or value.startswith('/') != absolute:
        raise ValueError('Unsafe path')
    return value


def _external_url(value):
    if not _text(value):
        raise ValueError('Invalid URL')
    url = urlsplit(value)
    if (url.scheme != 'https' or url.netloc not in {'www.mnppsaturn.ru', 'example.invalid'}
            or url.query or url.fragment or any(ord(c) < 32 for c in value)):
        raise ValueError('Invalid document URL')
    # Decode once for path validation; encoded slash/dot ambiguity is rejected.
    from urllib.parse import unquote
    decoded = unquote(url.path)
    safe_path(decoded, absolute=True)
    if '%2f' in url.path.lower() or '%5c' in url.path.lower() or not decoded.lower().endswith('.pdf'):
        raise ValueError('Invalid PDF locator')


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_kind: str
    title: str
    observed_content_sha256: str | None
    approved_content_sha256: str | None
    visibility: str
    approval_state: str
    publication_verified: bool
    cloud_allowed: bool
    allowed_usage: tuple[str, ...]
    approval_id: str | None
    approved_by: str | None
    approved_at: str | None
    reason: str
    repository: str | None = None
    source_commit: str | None = None
    path: str | None = None
    entity_type: str | None = None
    canonical_path: str | None = None
    url: str | None = None
    discovered_from: str | None = None
    document_type: str | None = None
    fetch_state: str | None = None

    def permits(self, usage: str, content_hash: str, source_commit: str | None = None) -> bool:
        return (usage in USAGES and usage in self.allowed_usage and self.visibility == 'PUBLIC'
                and self.approval_state == 'approved' and self.publication_verified
                and _hash(content_hash) and content_hash == self.approved_content_sha256
                and (self.source_kind != 'site_content' or source_commit == self.source_commit)
                and (usage != 'cloud_generate' or self.cloud_allowed))


@dataclass(frozen=True)
class Registry:
    revision: str
    registry_status: str
    source_snapshot: str
    entries: tuple[SourceRecord, ...]
    raw_bytes: bytes = b''


def load_registry(raw: bytes) -> Registry:
    if len(raw) > 1_000_000:
        raise ValueError('Registry size limit')
    data = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'registry_status',
            'default_policy', 'source_snapshot', 'entries'} or type(data['schema_version']) is not int
            or data['schema_version'] != 1 or data['default_policy'] != 'deny'
            or data['registry_status'] not in ('draft_candidates_only', 'synthetic_test_only', 'approved_sources')
            or not _hash(data['source_snapshot'], 40) or not isinstance(data['entries'], list)
            or len(data['entries']) > 10000):
        raise ValueError('Invalid registry v1')
    records, seen = [], set()
    for item in data['entries']:
        if not isinstance(item, dict):
            raise ValueError('Invalid source record')
        kind = item.get('source_kind')
        if kind not in ('site_content', 'external_document') or set(item) != COMMON | (SITE if kind == 'site_content' else EXTERNAL):
            raise ValueError('Unknown or missing source fields')
        if any(not _text(item[key]) for key in ('source_id', 'title', 'reason')):
            raise ValueError('Missing source identity')
        sid = item['source_id']
        if not re.fullmatch(r'[a-z0-9:/_-]+', sid) or sid in seen:
            raise ValueError('Invalid or duplicate source ID')
        seen.add(sid)
        if item['visibility'] not in ('PUBLIC', 'INTERNAL', 'UNKNOWN') or item['approval_state'] not in ('pending', 'approved', 'revoked'):
            raise ValueError('Invalid source policy enum')
        if any(type(item[key]) is not bool for key in ('publication_verified', 'cloud_allowed')):
            raise ValueError('Policy flags require booleans')
        usage = item['allowed_usage']
        if (not isinstance(usage, list) or any(not isinstance(x, str) or x not in USAGES for x in usage)
                or len(usage) != len(set(usage))):
            raise ValueError('Invalid source usage')
        if item['cloud_allowed'] != ('cloud_generate' in usage):
            raise ValueError('Cloud scope disagreement')
        if item['approval_state'] != 'approved' and usage:
            raise ValueError('Unapproved source scopes')
        for key in ('observed_content_sha256', 'approved_content_sha256'):
            if item[key] is not None and not _hash(item[key]):
                raise ValueError('Invalid content hash')
        for key in ('approval_id', 'approved_by', 'approved_at'):
            if item[key] is not None and not _text(item[key]):
                raise ValueError('Invalid approval provenance')
        if item['approved_at'] is not None:
            try:
                date = datetime.fromisoformat(item['approved_at'].replace('Z', '+00:00'))
                if date.tzinfo is None or date.utcoffset().total_seconds() != 0:
                    raise ValueError('UTC timestamp required')
            except (ValueError, TypeError):
                raise ValueError('Invalid approval timestamp') from None
        if item['approval_state'] == 'approved':
            if (item['visibility'] != 'PUBLIC' or not item['publication_verified']
                    or not _hash(item['approved_content_sha256'])
                    or item['approved_content_sha256'] != item['observed_content_sha256']
                    or any(not item[key] for key in ('approval_id', 'approved_by', 'approved_at'))):
                raise ValueError('Incomplete exact-revision approval')
        if kind == 'site_content':
            safe_path(item['path'])
            parts = PurePosixPath(item['path']).parts
            if (len(parts) != 4 or parts[:2] != ('src', 'content') or parts[2] not in COLLECTIONS
                    or not parts[3].endswith('.md') or item['repository'] != 'UkWood/Saturn-Main-Site'
                    or not _hash(item['source_commit'], 40) or item['source_commit'] != data['source_snapshot']
                    or not _hash(item['observed_content_sha256'])
                    or item['entity_type'] not in ('Device', 'Software', 'System', 'Category', 'Group', 'Article', 'News', 'Page', 'Solution')):
                raise ValueError('Invalid site locator or entity')
            safe_path(item['canonical_path'], absolute=True)
        else:
            _external_url(item['url'])
            if (not _text(item['discovered_from']) or item['document_type'] not in
                    ('manual', 'datasheet', 'certificate', 'declaration', 'presentation', 'other')
                    or item['fetch_state'] not in ('not_fetched', 'fetched', 'quarantined')
                    or (item['approval_state'] == 'approved' and item['fetch_state'] != 'fetched')):
                raise ValueError('Invalid external document state')
        records.append(SourceRecord(**dict(item, allowed_usage=tuple(usage))))
    return Registry(sha256(raw).hexdigest(), data['registry_status'], data['source_snapshot'], tuple(records), raw)
