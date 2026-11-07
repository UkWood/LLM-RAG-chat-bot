"""Explicit OS capability check, not a language-model benchmark."""
import os
import unittest
from unit.test_pdf import make_pdf
from saturn_ai.publication.extract import PublishedSource

@unittest.skipUnless(os.environ.get('SATURN_PDF_OS_TEST')=='1','requires an outer OS namespace-capable runner')
class IsolatedPdfTests(unittest.TestCase):
    def test_two_physical_pages_extract_with_non_system_python(self):
        source=PublishedSource('https://example.invalid/manual.pdf',make_pdf(),'application/pdf')
        self.assertEqual([n for n,_ in source.pages],[1,2])
        self.assertIn('24 V',source.pages[1][1])
