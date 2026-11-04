from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from unit.test_registry import source, manifest, load, COMMIT, ROOT
from saturn_ai.ingestion.pipeline import build_fixture
from saturn_ai.ingestion.site import parse_site

FIXTURES = ROOT / 'fixtures/ingestion'
DEVICE = FIXTURES / 'src/content/products/demo-300.md'


def record_for(content, **changes):
    digest = sha256(content).hexdigest()
    return load(manifest(source(observed_content_sha256=digest,
                               approved_content_sha256=digest, **changes))).entries[0]


class IngestionTests(unittest.TestCase):
    def test_facts_units_tables_and_provenance(self):
        content = DEVICE.read_bytes()
        document = parse_site(record_for(content), content)
        self.assertEqual(document.entity_type, 'Device')
        self.assertEqual(document.source_commit, COMMIT)
        self.assertEqual(document.parser_version, 'site-v1')
        self.assertIn('24 В', '\n'.join(c.text for c in document.chunks))
        self.assertTrue(any(c.field_path == 'temperature_c' and '°C' in c.text for c in document.chunks))
        self.assertTrue(any('obsolete' in c.text for c in document.chunks))
        table, = [c for c in document.chunks if '| Параметр |' in c.text]
        self.assertIn('| Ток | 2 | А |', table.text)
        self.assertEqual(table.heading_path, ('Учебная карточка', 'Параметры стенда'))
        all_text = '\n'.join(c.text for c in document.chunks)
        self.assertNotIn('INTERNAL_CANARY', all_text)
        self.assertNotIn('CANARY_CODE', all_text)
        self.assertTrue(all(c.page_start is None and c.page_end is None for c in document.chunks))
        relation, = [r for r in document.relationships if r.field_path == 'software[0]']
        self.assertEqual((relation.target_entity_id, relation.source_id),
                         ('products/demo-soft', document.source_id))
        self.assertFalse(any(r.kind == 'compatible_with' for r in document.relationships))
        self.assertEqual(document.document_links[0].url, 'https://example.invalid/synthetic/demo-300.pdf')

    def test_mapping_software_and_category(self):
        for rel, kind, title in [('products/demo-soft.md', 'Software', 'DEMO-SOFT'),
                                 ('systems/demo-category.md', 'Category', 'Учебная категория')]:
            content = (FIXTURES / 'src/content' / rel).read_bytes()
            record = record_for(content, path='src/content/'+rel, entity_type=kind, title=title)
            self.assertEqual(parse_site(record, content).entity_type, kind)

    def test_draft_and_invalid_frontmatter_are_rejected(self):
        content = DEVICE.read_bytes()
        for changed in [content.replace(b'draft: false', b'draft: true'),
                        content.replace(b'draft: false', b'draft: "false"'),
                        content.replace(b'draft: false', b'draft: false\ndraft: true'),
                        content.replace(b'interfaces: [rs-485]', b'interfaces: !!python/object:evil {}'),
                        content.replace(b'interfaces: [rs-485]', b'interfaces: &a [*a]'),
                        content.replace(b'interfaces: [rs-485]', b'interfaces: [42]'),
                        content.replace(b'24', b'24\x00'), b'no frontmatter',
                        content + b'\n<script>evil()</script>', content + b'\n```unclosed']:
            with self.subTest(changed=changed[:30]):
                with self.assertRaises(ValueError):
                    parse_site(record_for(changed), changed)

    def test_code_fence_lengths_and_indented_code_are_excluded(self):
        front = DEVICE.read_bytes().split(b'\n---\n', 1)[0] + b'\n---\n'
        for body in [b'Visible.\n\n    CANARY_CODE_NOT_EVIDENCE = 42\n',
                     b'Visible.\n\n \tCANARY_CODE_NOT_EVIDENCE = 42\n',
                     b'````python\n```\nCANARY_CODE_NOT_EVIDENCE\n```\n````\nVisible.\n',
                     b'```python\n```not-a-close\nCANARY_CODE_NOT_EVIDENCE\n```\nVisible.\n']:
            with self.subTest(body=body):
                content = front + body
                document = parse_site(record_for(content), content)
                output = '\n'.join(c.text for c in document.chunks)
                self.assertIn('Visible.', output)
                self.assertNotIn('CANARY_CODE_NOT_EVIDENCE', output)

    def test_heading_provenance_tracks_levels_not_list_length(self):
        front = DEVICE.read_bytes().split(b'\n---\n', 1)[0] + b'\n---\n'
        for body, expected in [
                (b'## First\nOne.\n## Second\nTwo.\n', [('First',), ('Second',)]),
                (b'# Root\n### First\nOne.\n### Second\nTwo.\n',
                 [('Root', 'First'), ('Root', 'Second')])]:
            with self.subTest(body=body):
                content = front + body
                document = parse_site(record_for(content), content)
                self.assertEqual([c.heading_path for c in document.chunks if c.field_path == 'body'], expected)

    def test_parser_does_not_bypass_hash_and_policy(self):
        content = DEVICE.read_bytes()
        with self.assertRaises(ValueError):
            parse_site(record_for(content), content + b'changed')
        record = record_for(content)
        from dataclasses import replace
        with self.assertRaises(ValueError):
            parse_site(replace(record, visibility='INTERNAL'), content)

    def test_idempotence_and_source_identity(self):
        content = DEVICE.read_bytes()
        first = parse_site(record_for(content), content)
        self.assertEqual(first, parse_site(record_for(content), content))
        other = parse_site(record_for(content, source_id='synthetic:other/demo-300'), content)
        self.assertNotEqual(first.document_id, other.document_id)
        self.assertNotEqual(first.chunks[0].chunk_id, other.chunks[0].chunk_id)

    def test_pipeline_deny_before_read_and_commit_binding(self):
        content = DEVICE.read_bytes()
        registry = load(manifest(source(observed_content_sha256=sha256(content).hexdigest(),
                                        approved_content_sha256=sha256(content).hexdigest())))
        result = build_fixture(FIXTURES, registry, COMMIT)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result, build_fixture(FIXTURES, registry, COMMIT))
        with self.assertRaises(ValueError):
            build_fixture(FIXTURES, registry, 'b'*40)
        denied = load(manifest(source(approval_state='pending', allowed_usage=[])))
        self.assertEqual(build_fixture(Path('/does/not/exist'), denied, COMMIT).documents, ())
        real = load_registry_file()
        self.assertEqual(build_fixture(Path('/does/not/exist'), real, real.source_snapshot).documents, ())

    def test_pipeline_real_approvals_not_usable_in_fixture_runner(self):
        content = DEVICE.read_bytes()
        registry = load(manifest(source(source_id='saturn:products/demo-300',
                                        observed_content_sha256=sha256(content).hexdigest(),
                                        approved_content_sha256=sha256(content).hexdigest())))
        with self.assertRaises(ValueError):
            build_fixture(FIXTURES, registry, COMMIT)

    def test_pipeline_rejects_symlink_escape_and_drift(self):
        content = DEVICE.read_bytes()
        registry = load(manifest(source(observed_content_sha256=sha256(content).hexdigest(),
                                        approved_content_sha256=sha256(content).hexdigest())))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'root'
            shutil.copytree(FIXTURES, root)
            path = root / 'src/content/products/demo-300.md'
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                build_fixture(root, registry, COMMIT)
            path.unlink()
            path.symlink_to(DEVICE)
            with self.assertRaises(ValueError):
                build_fixture(root, registry, COMMIT)


def load_registry_file():
    from saturn_ai.ingestion.registry import load_registry
    return load_registry((ROOT / 'config/knowledge/public-sources.json').read_bytes())
