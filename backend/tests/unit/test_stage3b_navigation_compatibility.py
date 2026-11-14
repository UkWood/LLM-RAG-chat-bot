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


class Stage3BNN(unittest.TestCase):
    def deny(self, data, expected="invalid_pdf"):
        status, result = execute(data)
        self.assertEqual(status, 2, result)
        self.assertEqual(result, {"error": expected})

    def mutate_ann(self, change, variant="A"):
        def maker(w):
            a = annotation(w, variant)
            change(a, w)
            return a
        return pdf(annotate=[maker])

    def test_NN01_openaction_dictionary(self):
        self.deny(pdf(open_action=lambda w: DictionaryObject({NameObject("/S"): NameObject("/URI")})))
    def test_NN02_xyz_wrong_lengths(self):
        for offset in (-1, 1):
            with self.subTest(offset=offset):
                self.deny(pdf(open_action=lambda w: ArrayObject(list(xyz(w))[:5 + offset] +
                              ([NumberObject(7)] if offset == 1 else []))))
    def test_NN03_wrong_xyz_mode(self):
        self.deny(pdf(open_action=lambda w: xyz(w, mode="/Fit")))
    def test_NN04_invalid_page_reference(self):
        self.deny(pdf(open_action=lambda w: ArrayObject([NumberObject(1), NameObject("/XYZ"),
                                                        NullObject(), NullObject(), NumberObject(0)])))
    def test_NN05_nonpage_indirect(self):
        def bad(w):
            a = xyz(w)
            a[0] = w._add_object(NumberObject(7))
            return a
        self.deny(pdf(open_action=bad))
    def test_NN06_zoom_nonzero_or_null(self):
        for z in (None, 0.0, 1, -1, 2.5):
            with self.subTest(z=z):
                self.deny(pdf(open_action=lambda w: xyz(w, zoom=z)))
    def test_NN07_x_bounds(self):
        self.deny(pdf(open_action=lambda w: xyz(w, left=1000001)))
    def test_NN08_y_bounds(self):
        self.deny(pdf(open_action=lambda w: xyz(w, top=-1000001)))
    def test_NN09_unknown_annotation_key(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Unknown"), NumberObject(1))))
    def test_NN10_nonlink_subtype(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Subtype"), NameObject("/Widget"))))
    def test_NN11_wrong_annotation_type(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Type"), NameObject("/Page")), "B"))
    def test_NN12_wrong_rect_length(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Rect"), ArrayObject([NumberObject(0)]))))
    def test_NN13_rect_wrong_order(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Rect"),
            ArrayObject([NumberObject(2), NumberObject(2), NumberObject(1), NumberObject(5)]))))
    def test_NN14_missing_bs_or_extra_bs(self):
        self.deny(self.mutate_ann(lambda a, w: a.pop("/BS")))
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/BS"),
            DictionaryObject({NameObject("/W"): NumberObject(0)})), "B"))
    def test_NN15_bs_variations(self):
        for bs in (DictionaryObject(), DictionaryObject({NameObject("/W"): FloatObject(0)}),
                   DictionaryObject({NameObject("/W"): NumberObject(1)}),
                   DictionaryObject({NameObject("/W"): NumberObject(0), NameObject("/S"): NameObject("/S")})):
            with self.subTest(bs=repr(bs)):
                self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/BS"), bs)))
    def test_NN16_border_variations(self):
        for border in (ArrayObject([NumberObject(0)] * 2), ArrayObject([NumberObject(0)] * 4),
                       ArrayObject([NumberObject(0), FloatObject(0), NumberObject(0)]),
                       ArrayObject([NumberObject(0), NumberObject(1), NumberObject(0)])):
            with self.subTest(border=repr(border)):
                self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Border"), border), "B"))
    def test_NN17_F_not_4_or_float(self):
        for v0 in (NumberObject(3), NumberObject(5), FloatObject(4.5)):
            self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/F"), v0)))
    def test_NN18_struct_parent_invalid(self):
        for v0 in (NumberObject(-1), NumberObject(2**31), FloatObject(1.5)):
            self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/StructParent"), v0)))
    def test_NN19_both_navigation_methods(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/A"),
            annotation(w, "C").raw_get("/A"))))
    def test_NN20_forbidden_uri_schemes_and_creds(self):
        for uri in ("file:///etc/passwd", "https://user:pass@www.mnppsaturn.ru", "https://www.mnppsaturn.ru/frag#section"):
            self.deny(pdf(annotate=[lambda w: annotation(w, "C", uri)]))
    def test_NN21_uri_controls(self):
        for uri in ("http://www.mnppsaturn.ru/\npage", "http://www.mnppsaturn.ru/a\x7f", "http://www.mnppsaturn.ru/a b"):
            self.deny(pdf(annotate=[lambda w: annotation(w, "C", uri)]))
    def test_NN22_uri_size_limit(self):
        self.deny(pdf(annotate=[lambda w: annotation(w, "C", "https://www.mnppsaturn.ru/" + "x"*2048)]))
    def test_NN23_forbidden_action_next(self):
        def bad(a, w):
            a.raw_get("/A")[NameObject("/Next")] = DictionaryObject()
        self.deny(self.mutate_ann(bad, "C"))
    def test_NN24_navigation_budgets(self):
        self.deny(pdf(annotate=[lambda w: [annotation(w, "A") for _ in range(65)]]), "resource_limit")
        self.deny(pdf(pages=5, annotate=[lambda w: [annotation(w, "A") for _ in range(64)] for _ in range(4)]
                      + [lambda w: annotation(w, "A")]), "resource_limit")

    def test_negative_missing_dest(self):
        self.deny(self.mutate_ann(lambda a, w: a.pop("/Dest")))

    def test_negative_different_variant_mix(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/F"), NumberObject(4)), "B"))

    def test_negative_action_type(self):
        self.deny(self.mutate_ann(lambda a, w: a.raw_get("/A").__setitem__(NameObject("/Type"), NameObject("/Bad")), "C"))

    def test_negative_action_launch_or_gotor(self):
        for action in ("/Launch", "/GoToR", "/JavaScript"):
            self.deny(self.mutate_ann(lambda a, w: a.raw_get("/A").__setitem__(NameObject("/S"), NameObject(action)), "C"))

    def test_negative_action_aa_and_js(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/AA"), DictionaryObject())))
        self.deny(pdf(mutate=lambda w: w._root_object.__setitem__(NameObject("/JavaScript"), DictionaryObject())))

    def test_negative_struct_parent_upper_boundary(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/StructParent"), NumberObject(2147483648))))

    def test_negative_17_dict_keys(self):
        def add(a, w):
            for i in range(17):
                a[NameObject(f"/Unapproved{i}")] = NumberObject(1)
        self.deny(self.mutate_ann(add), "resource_limit")

    def test_negative_large_array(self):
        self.deny(self.mutate_ann(lambda a, w: a.__setitem__(NameObject("/Border"),
            ArrayObject([NumberObject(0)]*65)), "B"), "resource_limit")

    def test_negative_indirection_hops(self):
        # Construct a real five-hop chain at the PDF object level: PdfWriter
        # normalizes such chains and cannot create this case directly.
        original = pdf(open_action=xyz)
        objects = {int(m.group(1)): m.group(2) for m in
                   re.finditer(rb"(?ms)^(\d+) 0 obj\r?\n(.*?)\r?\nendobj", original)}
        root_id = next(i for i, data in objects.items() if b"/Type /Catalog" in data)
        root = objects[root_id]
        match = re.search(rb"/OpenAction\s+(\[[^\]]+\])", root)
        self.assertIsNotNone(match)
        destination = match.group(1)
        first = max(objects) + 1
        objects[root_id] = root.replace(match.group(0), f"/OpenAction {first} 0 R".encode())
        for i in range(5):
            objects[first+i] = (f"{first+i+1} 0 R".encode() if i < 4 else destination)
        output = BytesIO()
        output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for n in range(1, max(objects)+1):
            offsets.append(output.tell())
            output.write(f"{n} 0 obj\n".encode() + objects[n] + b"\nendobj\n")
        xref_at = output.tell()
        output.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            output.write(f"{offset:010} 00000 n \n".encode())
        output.write(f"trailer\n<< /Size {len(offsets)} /Root {root_id} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode())
        status, result = execute(output.getvalue())
        self.assertEqual(status, 2)
        # Some pypdf revisions reject indirect-to-indirect objects themselves;
        # fail-closed, rather than exact budget-code selection, is asserted.
        self.assertIn(result.get("error"), ("resource_limit", "parser_error", "invalid_pdf"))

    def test_negative_more_than_4096_visits(self):
        # Every exact A annotation costs multiple object visits. 256 A links
        # remain below document annotation budget but exceed total nav budget.
        self.deny(pdf(pages=4, annotate=[lambda w: [annotation(w, "A") for _ in range(64)] for _ in range(4)]),
                  "resource_limit")

    def test_negative_corrupted_pdf(self):
        status, result = execute(b"%PDF-bad")
        self.assertNotEqual(status, 0)
        self.assertNotEqual(result.get("page_count"), 1)

    def test_negative_excess_page_limit(self):
        status, result = execute(pdf(pages=2), max_pages=1)
        self.assertEqual(status, 2)
        self.assertEqual(result, {"error":"page_limit"})


class Stage3BValidatorBudgetBoundaries(unittest.TestCase):
    """Direct production-validator gates, independent of pypdf PDF parsing.

    The existing test_negative_indirection_hops is a separate real subprocess
    regression: parser-level fail-closed is not treated as a validator budget hit.
    """

    @staticmethod
    def _worker():
        spec = importlib.util.spec_from_file_location("saturn_stage3b_worker_budget_test", WORKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _chain(length):
        class SyntheticReader:
            def __init__(self):
                self.objects = {}

            def get_object(self, ref):
                return self.objects[ref.idnum]

        reader = SyntheticReader()
        refs = [IndirectObject(idx, 0, reader) for idx in range(1, length + 1)]
        for i, ref in enumerate(refs):
            reader.objects[ref.idnum] = refs[i + 1] if i + 1 < length else NameObject("/XYZ")
        return reader, refs[0]

    @staticmethod
    def _validator(worker, reader):
        # _resolve() and _name() do not use reader.pages; isolate precisely
        # these real validator methods, not an emulated budget implementation.
        validator = worker._InertNavigation.__new__(worker._InertNavigation)
        validator.reader = reader
        validator.seen = 0
        return validator

    def test_budget_exact_four_indirect_hops_is_allowed(self):
        worker = self._worker()
        reader, first = self._chain(4)
        validator = self._validator(worker, reader)
        validator._name(first, "/XYZ", 0)
        self.assertEqual(validator.seen, 5)  # Initial reference + four hops.

    def test_budget_fifth_indirect_hop_rejected_by_validator(self):
        worker = self._worker()
        reader, first = self._chain(5)
        validator = self._validator(worker, reader)
        with self.assertRaises(worker.WorkerRejection) as ctx:
            validator._name(first, "/XYZ", 0)
        self.assertEqual(str(ctx.exception), "resource_limit")
        self.assertEqual(validator.seen, 5)

    def test_budget_exact_depth_six_is_allowed(self):
        worker = self._worker()
        validator = self._validator(worker, object())
        validator._name(NameObject("/XYZ"), "/XYZ", 6)
        self.assertEqual(validator.seen, 1)

    def test_budget_depth_seven_rejected_by_validator(self):
        worker = self._worker()
        validator = self._validator(worker, object())
        with self.assertRaises(worker.WorkerRejection) as ctx:
            validator._name(NameObject("/XYZ"), "/XYZ", 7)
        # The approved worker uses invalid_pdf for over-depth, not
        # resource_limit; this is intentionally asserted, not concealed.
        self.assertEqual(str(ctx.exception), "invalid_pdf")
        self.assertEqual(validator.seen, 0)


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

    def test_adapter_rejected_annotation_has_no_evidence_or_promotable_cache(self):
        raw = pdf(annotate=[lambda w: dict_with_next(w)])
        result = self.adapt(self.sample(), self.policy(), transport=self.transport(raw=raw),
                            extractor=self.extractor(enable_development_worker=True))
        self.assertFalse(result.ready_for_promotion)
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.cached_extractions, ())
        self.assertEqual(result.statuses[0].status, "invalid_pdf")

    def test_parser_revision_invalidates_verified_cached_extraction(self):
        self.assertEqual(self.version, "saturn-pdf-pypdf-6.10.0/0.2.0")
        raw = pdf(annotate=[lambda w: annotation(w, "B")])
        initial = self.adapt(self.sample(), self.policy(), transport=self.transport(raw=raw),
                             extractor=self.extractor(enable_development_worker=True),
                             parser_version="saturn-pdf-pypdf-6.10.0/0.1.0")
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