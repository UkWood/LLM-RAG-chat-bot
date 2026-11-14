"""Read-only real-PDF extraction gate for the Stage 3B correction.

Runs only the production SubprocessPdfExtractor (explicit development opt-in),
not Stage 5F or any internet fetch. Does not write original PDF bytes or text.

From repository root:
 PYTHONPATH=backend/src python backend/tests/manual/verify_stage3b_real_pdfs.py \
    --bkd-pk /secure/path/bkd-pk-rf2.pdf --bkd-ups /secure/path/bkd-ups.pdf \
    --sldks /secure/path/sldks-1.pdf --lanmon /secure/path/lanmon-server.pdf \
    --output /secure/path/stage3b-real-extraction.json
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from saturn_ai.ingestion.external_document_extractor import (
    PARSER_VERSION, SubprocessPdfExtractor,
)
from saturn_ai.ingestion.external_document_transport import (
    DocumentError, DocumentFetchPolicy,
)

EXPECTED = {
    "bkd-pk-rf2": ("030303812b4bd8dfc7e82fcd3ad4ef8493526549c7c90d033ce25b4f8b2fe83a", 65),
    "bkd-ups": ("aeca6a7d2ff3edcd872d35aaa455d2dfc3a4838dda1c58a1d6952309f248ceb3", 39),
    "sldks-1": ("f1436a93285cad9a201b6b387ed64a606ad2768cfc7ee70627c188411e9ce61f", 83),
    "lanmon-server": ("fedd8b6a3de63efb9ff29de8d62b3cf98dea05d7ce189a68100a3ced096e70bf", 69),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("bkd-pk", "bkd-ups", "sldks", "lanmon"):
        parser.add_argument("--" + arg, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {"bkd-pk-rf2": args.bkd_pk, "bkd-ups": args.bkd_ups,
             "sldks-1": args.sldks, "lanmon-server": args.lanmon}
    extractor = SubprocessPdfExtractor(enable_development_worker=True)
    policy = DocumentFetchPolicy()
    results = []
    for name, (expected_sha, expected_pages) in EXPECTED.items():
        entry = {"document": name, "expected_sha256": expected_sha,
                 "expected_pages": expected_pages, "status": "STOPPED"}
        try:
            # Read once and verify EXACT bytes supplied to the subprocess worker.
            raw = paths[name].read_bytes()
            actual_sha = sha256(raw).hexdigest()
            entry["actual_sha256"] = actual_sha
            if actual_sha != expected_sha:
                entry["status"] = "SHA256_MISMATCH"
            else:
                extracted = extractor.extract(raw, policy)
                entry["actual_pages"] = extracted.page_count
                # Only a digest is recorded; no extracted text or PDF URI is output.
                digest_payload = json.dumps(extracted.pages, ensure_ascii=False,
                                             separators=(",", ":")).encode("utf-8")
                entry["extracted_pages_sha256"] = sha256(digest_payload).hexdigest()
                entry["status"] = ("PASS" if extracted.page_count == expected_pages
                                   else "PAGE_COUNT_MISMATCH")
        except DocumentError as exc:
            entry["status"] = "REJECTED"
            entry["error_code"] = exc.code
        except (OSError, ValueError):
            entry["status"] = "STOPPED"
            entry["error_code"] = "io_or_parser_error"
        results.append(entry)
    overall = "PASS" if all(item["status"] == "PASS" for item in results) else "BLOCKED"
    report = {"tool": "saturn-stage3b-real-pdf-extraction-gate-v0.2",
              "parser_version": PARSER_VERSION, "overall": overall,
              "passed": sum(item["status"] == "PASS" for item in results),
              "expected": 4, "results": results,
              "note": "Worker/extraction gate only; this report does not claim Stage 5F or full adapter provenance."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"overall": overall, "passed": report["passed"],
                      "expected": 4, "report": str(args.output)}, ensure_ascii=False))
    return 0 if overall == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
