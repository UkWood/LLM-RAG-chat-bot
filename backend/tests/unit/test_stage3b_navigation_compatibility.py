"""Stage 3B strict inert PDF navigation — real subprocess regression matrix.

Execute with PYTHONPATH=backend/src python -m unittest ... (or standalone here).
No network calls or original Saturn PDF fixtures are used.
"""
from io import BytesIO
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from pypdf import PdfWriter, PdfReader
from pypdf.generic import (ArrayObject, DictionaryObject, NameObject, NumberObject,
                           FloatObject, NullObject, TextStringObject, DecodedStreamObject,
                           IndirectObject)

WORKER = Path(__file__).with_name("external_pdf_worker.py")
if not WORKER.is_file():
    WORKER = Path(__file__).resolve().parents[2] / "src/saturn_ai/ingestion/external_pdf_worker.py"


def v(x):
    if x is None:
        return NullObject()
    if type(x) is int:
        return NumberObject(x)
    return FloatObject(x)


def xyz(w, *, page=1, mode="/XYZ", left=None, top=12.5, zoom=0):
    return ArrayObject([w.pages[page].indirect_reference, NameObject(mode),
                        v(left), v(top), v(zoom)])


def box():
    return ArrayObject([NumberObject(1), NumberObject(2), NumberObject(100), NumberObject(110)])


def annotation(w, variant="A", uri="https://www.mnppsaturn.ru/docs/paper"):
    d = DictionaryObject({NameObject("/Subtype"): NameObject("/Link"),
                          NameObject("/Rect"): box()})
    if variant == "A":
        d[NameObject("/Dest")] = xyz(w)
        d[NameObject("/BS")] = DictionaryObject({NameObject("/W"): NumberObject(0)})
        d[NameObject("/F")] = NumberObject(4)
        d[NameObject("/StructParent")] = NumberObject(0)
    elif variant in ("B", "C"):
        d[NameObject("/Type")] = NameObject("/Annot")
        d[NameObject("/Border")] = ArrayObject([NumberObject(0)] * 3)
        if variant == "B":
            d[NameObject("/Dest")] = xyz(w)
        else:
            d[NameObject("/A")] = DictionaryObject({
                NameObject("/S"): NameObject("/URI"),
                NameObject("/Type"): NameObject("/Action"),
                NameObject("/URI"): TextStringObject(uri)})
    else:
        raise ValueError("unknown fixture variant")
    return d


def pdf(*, pages=2, annotate=None, open_action=None, mutate=None):
    writer = PdfWriter()
    for i in range(pages):
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
            DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 200 Td (Exact text page {i + 1}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    if annotate is not None:
        for idx, make in enumerate(annotate):
            if make is None:
                continue
            annotations = make(writer) if callable(make) else make
            if not isinstance(annotations, list):
                annotations = [annotations]
            writer.pages[idx][NameObject("/Annots")] = ArrayObject(
                [writer._add_object(a) for a in annotations])
    if open_action is not None:
        writer._root_object[NameObject("/OpenAction")] = open_action(writer)
    if mutate is not None:
        mutate(writer)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def execute(data, *, max_pages=256, timeout=18):
    args = [sys.executable, "-I", "-B", str(WORKER), str(24 * 1024 * 1024),
            str(max_pages), str(4 * 1024 * 1024), str(1 * 1024 * 1024),
            str(4 * 1024 * 1024), str(16 * 1024 * 1024),
            str(512 * 1024 * 1024), "8"]
    cp = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, timeout=timeout)
    return cp.returncode, json.loads(cp.stdout.decode("utf-8"))


class Stage3BPN(unittest.TestCase):
    def accept(self, data):
        status, result = execute(data)
        self.assertEqual(status, 0, result)
        self.assertEqual(result["page_count"], len(result["pages"]))
        self.assertEqual([p["number"] for p in result["pages"]],
                         list(range(1, result["page_count"] + 1)))
        self.assertEqual([p["text"] for p in result["pages"]],
                         [f"Exact text page {i}" for i in range(1, result["page_count"] + 1)])
        self.assertNotIn("URI", str(result))
        self.assertNotIn("Dest", str(result))

    def test_PN01_no_navigation(self): self.accept(pdf())
    def test_PN02_exact_A(self): self.accept(pdf(annotate=[lambda w: annotation(w, "A")]))
    def test_PN03_exact_B(self): self.accept(pdf(annotate=[lambda w: annotation(w, "B")]))
    def test_PN04_exact_C(self): self.accept(pdf(annotate=[lambda w: annotation(w, "C")]))
    def test_PN05_open_action_null_xy(self):
        self.accept(pdf(open_action=lambda w: xyz(w, left=None, top=None, zoom=0)))
    def test_PN06_finite_coordinates(self):
        self.accept(pdf(open_action=lambda w: xyz(w, left=-1_000_000, top=1_000_000)))
    def test_PN07_http_uri(self):
        self.accept(pdf(annotate=[lambda w: annotation(w, "C", "http://www.mnppsaturn.ru:8080/page")]))
    def test_PN08_two_uris(self):
        self.accept(pdf(annotate=[lambda w: [annotation(w, "C") for _ in range(2)]]))
    def test_PN09_64_on_one_page(self):
        self.accept(pdf(annotate=[lambda w: [annotation(w, "B") for _ in range(64)]]))
    def test_PN10_complex_real_like_215(self):
        # 27 A, 186 B, 2 C, with the same total of 215 /Link annotations
        # observed on the three reviewed documents.
        self.accept(pdf(pages=5, annotate=[
            lambda w: [annotation(w, "A") for _ in range(27)],
            lambda w: [annotation(w, "B") for _ in range(38)],
            lambda w: [annotation(w, "B") for _ in range(64)],
            lambda w: [annotation(w, "B") for _ in range(64)],
            lambda w: [annotation(w, "B") for _ in range(20)] +
                      [annotation(w, "C") for _ in range(2)]]))


class Stage3BInertCompatibility(unittest.TestCase):
    """Navigation is inert metadata; no shape or count gates are consulted."""

    def accept(self, raw):
        status, result = execute(raw)
        self.assertEqual(status, 0, result)
        self.assertEqual([p["text"] for p in result["pages"]],
                         [f"Exact text page {i}" for i in range(1, result["page_count"] + 1)])
        self.assertNotIn("www.mnppsaturn.ru/docs/paper", str(result))
        return result

    def mutate_ann(self, change, variant="A"):
        def maker(writer):
            item = annotation(writer, variant)
            change(item, writer)
            return item
        return pdf(annotate=[maker])

    def test_navigation_non_xyz_destinations(self):
        for mode, params in (
                ("/Fit", []), ("/FitH", [NumberObject(42)]),
                ("/FitV", [NumberObject(24)]),
                ("/FitR", [NumberObject(1), NumberObject(2),
                           NumberObject(90), NumberObject(120)])):
            with self.subTest(mode=mode):
                def op(w):
                    return ArrayObject([w.pages[1].indirect_reference,
                                        NameObject(mode), *params])
                self.accept(pdf(open_action=op))

    def test_inert_root_names_outlines_acroform_and_aa(self):
        def mutate(w):
            root = w._root_object
            for key in ("/Names", "/Outlines", "/AcroForm", "/AA",
                        "/JavaScript", "/EmbeddedFiles", "/Collection"):
                root[NameObject(key)] = DictionaryObject()
            w.pages[0][NameObject("/AA")] = DictionaryObject()
        self.accept(pdf(mutate=mutate))

    def test_action_dictionaries_never_executed_or_emitted(self):
        for action in ("/Launch", "/GoToR", "/JavaScript", "/URI"):
            with self.subTest(action=action):
                def maker(w):
                    a = annotation(w, "C")
                    act = a.raw_get("/A")
                    act[NameObject("/S")] = NameObject(action)
                    act[NameObject("/Next")] = DictionaryObject()
                    act[NameObject("/URI")] = TextStringObject(
                        "file:///should-not-be-opened?secret=NO_EVIDENCE")
                    return a
                result = self.accept(pdf(annotate=[maker]))
                self.assertNotIn("NO_EVIDENCE", str(result))

    def test_unrestricted_uri_variants_remain_inert(self):
        for value in ("ftp://host/path", "file:///etc/passwd",
                      "https://user:pass@example.com/doc#fragment",
                      "javascript:alert(999)", "https://example.com/" + "x"*2300):
            with self.subTest(uri_scheme=value.split(":")[0]):
                self.accept(pdf(annotate=[lambda w: annotation(w, "C", value)]))

    def test_arbitrary_link_fields_and_border(self):
        def maker(w):
            a = annotation(w, "B")
            a[NameObject("/Unexpected")] = ArrayObject([NumberObject(2)])
            a[NameObject("/Border")] = ArrayObject([NumberObject(3)]*4)
            a[NameObject("/Subtype")] = NameObject("/Widget")
            a[NameObject("/Dest")] = ArrayObject([NumberObject(9)])
            return a
        self.accept(pdf(annotate=[maker]))

    def test_more_than_64_annotations_per_page(self):
        self.accept(pdf(annotate=[lambda w: [annotation(w, "B") for _ in range(65)]]))

    def test_more_than_256_annotations_in_document(self):
        result=self.accept(pdf(pages=5, annotate=[
            lambda w: [annotation(w, "B") for _ in range(65)]
            for _ in range(4)] + [lambda w: annotation(w, "C")]))
        self.assertEqual(result["page_count"], 5)

    def test_destination_and_openaction_unknown_shapes_not_blocking(self):
        def op(w):
            return DictionaryObject({NameObject("/S"): NameObject("/Launch"),
                                     NameObject("/F"): TextStringObject("unvisited")})
        self.accept(pdf(open_action=op))

    def test_corrupted_pdf_is_fail_closed(self):
        status, result = execute(b"%PDF-bad")
        self.assertNotEqual(status, 0)
        self.assertNotIn("pages", result)

    def test_excess_page_limit_is_fail_closed(self):
        status, result = execute(pdf(pages=2), max_pages=1)
        self.assertEqual(status, 2)
        self.assertEqual(result, {"error": "page_limit"})

    def test_text_budget_is_preserved(self):
        raw = pdf()
        args = [sys.executable, "-I", "-B", str(WORKER),
                str(24*1024*1024), "200", "5", str(1024*1024),
                str(4*1024*1024), str(16*1024*1024),
                str(512*1024*1024), "8"]
        cp = subprocess.run(args, input=raw, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=18)
        self.assertEqual(cp.returncode, 2)
        self.assertEqual(json.loads(cp.stdout), {"error":"resource_limit"})

    def test_page_stream_budget_is_preserved(self):
        raw = pdf()
        args = [sys.executable, "-I", "-B", str(WORKER),
                str(24*1024*1024), "200", str(4*1024*1024),
                str(1024*1024), "1", str(16*1024*1024),
                str(512*1024*1024), "8"]
        cp = subprocess.run(args, input=raw, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=18)
        self.assertEqual(cp.returncode, 2)
        self.assertEqual(json.loads(cp.stdout), {"error":"resource_limit"})

    def test_oversized_input_rejected_before_parse(self):
        raw = pdf()
        args = [sys.executable, "-I", "-B", str(WORKER),
                "16", "200", str(4*1024*1024), str(1024*1024),
                str(4*1024*1024), str(16*1024*1024),
                str(512*1024*1024), "8"]
        cp = subprocess.run(args, input=raw, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=18)
        self.assertEqual(cp.returncode, 2)
        self.assertEqual(json.loads(cp.stdout), {"error":"size_limit"})


class Stage3BExternalAdapterContract(unittest.TestCase):
    """Run against the actual repo packages and development subprocess worker."""

    def setUp(self):
        try:
            from saturn_ai.ingestion.external_document_adapter import adapt_external_documents
            from saturn_ai.ingestion.external_document_extractor import (
                PARSER_VERSION, SubprocessPdfExtractor)
            from unit.test_external_document_adapter import (
                sample, policy, MemoryTransport)
        except ImportError:
            self.skipTest("Full repository modules required (GitHub CI / Linux stand)")
        self.adapt = adapt_external_documents
        self.version = PARSER_VERSION
        self.extractor = SubprocessPdfExtractor
        self.sample = sample
        self.policy = policy
        self.transport = MemoryTransport

    def test_adapter_valid_navigation_retains_physical_pages_and_only_text_evidence(self):
        raw = pdf(annotate=[lambda w: [annotation(w, "A"),
                                       annotation(w, "B"),
                                       annotation(w, "C")]])
        transport = self.transport(raw=raw)
        result = self.adapt(self.sample(), self.policy(), transport=transport,
                            extractor=self.extractor(enable_development_worker=True))
        self.assertTrue(result.ready_for_promotion, result.diagnostics)
        self.assertEqual(result.statuses[0].status, "extracted")
        self.assertEqual([e.page_number for e in result.evidence], [1, 2])
        self.assertEqual([e.text for e in result.evidence],
                         ["Exact text page 1", "Exact text page 2"])
        self.assertEqual(result.revisions[0].parser_version, self.version)
        self.assertEqual(len(transport.calls), 1)
        self.assertTrue(all("www.mnppsaturn.ru/docs/paper" not in e.text for e in result.evidence))

    def test_adapter_corrupted_pdf_has_no_evidence_or_promotable_cache(self):
        result = self.adapt(self.sample(), self.policy(),
                            transport=self.transport(raw=b"%PDF-bad"),
                            extractor=self.extractor(enable_development_worker=True))
        self.assertFalse(result.ready_for_promotion)
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.cached_extractions, ())
        self.assertIn(result.statuses[0].status, ("invalid_pdf", "parser_error"))

    def test_parser_revision_invalidates_verified_cached_extraction(self):
        self.assertEqual(self.version, "saturn-pdf-pypdf-6.10.0/0.3.0")
        raw = pdf(annotate=[lambda w: annotation(w, "B")])
        initial = self.adapt(self.sample(), self.policy(), transport=self.transport(raw=raw),
                             extractor=self.extractor(enable_development_worker=True),
                             parser_version="saturn-pdf-pypdf-6.10.0/0.2.0")
        self.assertTrue(initial.ready_for_promotion)
        class Counted:
            calls = 0
            def extract(inner, data, policy):
                inner.calls += 1
                return self.extractor(enable_development_worker=True).extract(data, policy)
        tracked = Counted()
        fresh = self.adapt(self.sample(), self.policy(), transport=self.transport(raw=raw),
                           extractor=tracked, previous_cache=initial.cached_extractions)
        self.assertTrue(fresh.ready_for_promotion)
        self.assertEqual(tracked.calls, 1)
        self.assertEqual(fresh.revisions[0].bytes_sha256, initial.revisions[0].bytes_sha256)
        self.assertNotEqual(fresh.statuses[0].revision_id, initial.statuses[0].revision_id)
        self.assertNotEqual(fresh.revisions[0].parser_version, initial.revisions[0].parser_version)


def dict_with_next(w):
    item = annotation(w, "C")
    item.raw_get("/A")[NameObject("/Next")] = DictionaryObject()
    return item


if __name__ == "__main__":
    unittest.main()