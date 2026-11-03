"""Offline checks for project documentation and registry invariants.

Not a replacement for the future application's access-control validator.
"""
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def validate_registry(data):
    errors = []
    if data.get('schema_version') != 1 or data.get('default_policy') != 'deny':
        errors.append('registry must use schema 1 and default deny')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return errors + ['entries must be a nonempty list']
    seen = set()
    for entry in entries:
        sid = entry.get('source_id')
        if not isinstance(sid, str) or not sid or sid in seen:
            errors.append('missing or duplicate source_id')
        seen.add(sid)
        def fail(message):
            errors.append(f'{sid}: {message}')
        state = entry.get('approval_state')
        visibility = entry.get('visibility')
        usage = entry.get('allowed_usage')
        if state not in {'pending', 'approved', 'revoked'}:
            fail('invalid approval state')
        if visibility not in {'UNKNOWN', 'PUBLIC', 'INTERNAL'}:
            fail('invalid visibility')
        if not isinstance(usage, list) or any(x not in {'local_index', 'local_generate', 'cloud_generate'} for x in usage):
            fail('invalid allowed_usage')
            usage = []
        if type(entry.get('cloud_allowed')) is not bool:
            fail('cloud_allowed must be explicit boolean')
        if state != 'approved' and (usage or entry.get('cloud_allowed')):
            fail('unapproved source must not have usage permissions')
        if state == 'approved':
            if visibility != 'PUBLIC':
                fail('public registry approval requires PUBLIC')
            if entry.get('publication_verified') is not True:
                fail('approval requires publication verification')
            if not re.fullmatch(r'[0-9a-f]{64}', entry.get('approved_content_sha256') or ''):
                fail('approval requires exact SHA-256')
            for field in ('approval_id', 'approved_by', 'approved_at'):
                if not entry.get(field):
                    fail(f'approval requires {field}')
        if bool(entry.get('cloud_allowed')) != ('cloud_generate' in usage):
            fail('cloud flag and usage disagree')
        kind = entry.get('source_kind')
        if kind == 'site_content':
            path = entry.get('path', '')
            if not path.startswith('src/content/') or '..' in Path(path).parts or not path.endswith('.md'):
                fail('invalid content path')
            if entry.get('repository') != 'UkWood/Saturn-Main-Site':
                fail('unexpected content repository')
            if not re.fullmatch(r'[0-9a-f]{40}', entry.get('source_commit', '')):
                fail('missing pinned commit')
            if not re.fullmatch(r'[0-9a-f]{64}', entry.get('observed_content_sha256', '')):
                fail('missing observed hash')
        elif kind == 'external_document':
            url = urlsplit(entry.get('url', ''))
            if url.scheme != 'https' or url.hostname != 'www.mnppsaturn.ru' or url.username or url.password:
                fail('invalid external document URL')
            if state == 'approved' and entry.get('fetch_state') == 'not_fetched':
                fail('unfetched document cannot be approved')
        else:
            fail('invalid source_kind')
    return errors


def check():
    errors = validate_registry(json.loads((ROOT / 'config/knowledge/public-sources.json').read_text()))
    for path in [ROOT / 'README.md', ROOT / 'AGENTS.md', *(ROOT / 'docs').rglob('*.md')]:
        # Preserve original user brief verbatim; its conceptual links are not repo links.
        if path.name == 'original-brief.ru.md':
            continue
        content = path.read_text()
        if content.count('```') % 2:
            errors.append(f'{path.relative_to(ROOT)}: unclosed fenced block')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if '://' in target or target.startswith('#'):
                continue
            resolved = (path.parent / target.split('#')[0]).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                errors.append(f'{path.relative_to(ROOT)}: broken or escaping link {target}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print('PASS: documentation links/fences and registry invariants (offline).')


if __name__ == '__main__':
    check()
