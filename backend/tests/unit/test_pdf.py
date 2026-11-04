from hashlib import sha256
from io import BytesIO
import unittest
from unittest.mock import patch
import subprocess

from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
from unit.test_registry import source, manifest, load
from saturn_ai.ingestion.pdf import parse_pdf


def make_pdf(texts=('Synthetic DEMO-300 manual page one', 'Supply voltage 24 V. Page two'), active=False, encrypted=False):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(('BT /F1 12 Tf 20 200 Td ('+text+') Tj ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    if active:
        writer.add_js("app.alert('synthetic-test')")
    if encrypted:
        writer.encrypt('synthetic-password')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def pdf_record(content):
    raw = source()
    for key in ('repository', 'source_commit', 'path', 'entity_type', 'canonical_path'):
        del raw[key]
    digest = sha256(content).hexdigest()
    raw.update(source_id='synthetic:pdf:demo-300', source_kind='external_document',
               url='https://example.invalid/synthetic/demo-300.pdf',
               discovered_from='synthetic:products/demo-300', document_type='manual', fetch_state='fetched',
               observed_content_sha256=digest, approved_content_sha256=digest)
    return load(manifest(raw)).entries[0]


class PdfTests(unittest.TestCase):
    def test_physical_pages_and_provenance(self):
        content = make_pdf()
        document = parse_pdf(pdf_record(content), content)
        self.assertEqual(document.parser_version, 'pdf-v1')
        self.assertEqual([c.page_start for c in document.chunks], [1, 2])
        self.assertEqual([c.page_end for c in document.chunks], [1, 2])
        self.assertIn('24 V', document.chunks[1].text)
        self.assertEqual(document, parse_pdf(pdf_record(content), content))
        self.assertTrue(all(c.source_id == document.source_id and c.document_id == document.document_id
                            for c in document.chunks))

    def test_bad_empty_active_encrypted_and_page_limits(self):
        for content in [b'not pdf', make_pdf(('',)), make_pdf(active=True), make_pdf(encrypted=True)]:
            with self.subTest(size=len(content)):
                with self.assertRaises(ValueError):
                    parse_pdf(pdf_record(content), content)
        content = make_pdf()
        with self.assertRaises(ValueError):
            parse_pdf(pdf_record(content), content, max_pages=1)

    def test_hash_and_denied_policy_checked_before_worker(self):
        content = make_pdf()
        from dataclasses import replace
        with patch('saturn_ai.ingestion.pdf.subprocess.run') as worker:
            for record, data in [(pdf_record(content), content+b'changed'),
                                 (replace(pdf_record(content), visibility='INTERNAL'), content)]:
                with self.assertRaises(ValueError):
                    parse_pdf(record, data)
            worker.assert_not_called()

    def test_timeout_is_controlled(self):
        content = make_pdf()
        with patch('saturn_ai.ingestion.pdf.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', 5)):
            with self.assertRaises(ValueError):
                parse_pdf(pdf_record(content), content)

    def test_pipeline_binds_pdf_to_separate_approval(self):
        from saturn_ai.ingestion.pipeline import build_fixture
        from unit.test_registry import COMMIT
        from dataclasses import replace
        from pathlib import Path
        import tempfile
        content = make_pdf()
        record = pdf_record(content)
        registry = load(manifest())
        registry = replace(registry, entries=(record,))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'pdf').mkdir()
            (root/'pdf'/(sha256(record.source_id.encode()).hexdigest()+'.pdf')).write_bytes(content)
            result = build_fixture(root, registry, COMMIT)
            self.assertEqual(len(result.documents[0].chunks), 2)
            denied = replace(record, approval_state='pending', allowed_usage=())
            result = build_fixture(root, replace(registry, entries=(denied,)), COMMIT)
            self.assertEqual(result.documents, ())
