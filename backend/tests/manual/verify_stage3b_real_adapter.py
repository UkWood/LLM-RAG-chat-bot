"""Read-only Stage 3B real External Document Adapter diagnostic (NOT production sandbox).

Uses a real pinned local Saturn-Main-Site Git commit and its real-derived catalog.
The selected subset of catalog candidates is not falsely presented as the
complete production catalog. Original URLs/document IDs/owners are never forged.

Step 1 (discover site URLs):
 PYTHONPATH=backend/src python backend/tests/manual/verify_stage3b_real_adapter.py \\
  --site-repo /path/Saturn-Main-Site --site-commit <40-sha> \\
  --discover --output /safe/dir/stage3b-real-catalog.json

Step 2 (real four-PDF run, after filling binding file with exact discovered URLs):
 PYTHONPATH=backend/src python backend/tests/manual/verify_stage3b_real_adapter.py \\
  --site-repo /path/Saturn-Main-Site --site-commit <40-sha> \\
  --bindings /safe/dir/real-pdf-bindings.json \\
  --allowed-host www.mnppsaturn.ru --allowed-prefix /ftp \\
  --allowed-prefix /public --allowed-prefix /photos \\
  --output /safe/dir/stage3b-real-adapter.json

Bindings JSON: {"bkd-pk-rf2":{"url":"<EXACT catalog resolved_url>",
"path":"/absolute/path/to/original.pdf"}, ...}. Keys are the 4 EXPECTED labels.
No network requests or writes to site repo. No PDFs or extracted text in reports.
"""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from saturn_ai.ingestion.external_document_adapter import adapt_external_documents
from saturn_ai.ingestion.external_document_extractor import PARSER_VERSION, SubprocessPdfExtractor
from saturn_ai.ingestion.external_document_transport import DocumentError, DocumentFetchPolicy
from saturn_ai.ingestion.saturn_contracts import stable_id
from saturn_ai.ingestion.github_snapshot_provider import (
    _REQUIRED_FILES, _OPTIONAL_FILES, _REGULAR_BLOB_MODES,
)
from saturn_ai.ingestion.saturn_site_adapter import PinnedSiteSnapshot, adapt_snapshot, git_blob_sha1
from saturn_ai.ingestion.support_catalog_adapter import adapt_support_catalog

EXPECTED = {
    "bkd-pk-rf2": ("030303812b4bd8dfc7e82fcd3ad4ef8493526549c7c90d033ce25b4f8b2fe83a", 65),
    "bkd-ups": ("aeca6a7d2ff3edcd872d35aaa455d2dfc3a4838dda1c58a1d6952309f248ceb3", 39),
    "sldks-1": ("f1436a93285cad9a201b6b387ed64a606ad2768cfc7ee70627c188411e9ce61f", 83),
    "lanmon-server": ("fedd8b6a3de63efb9ff29de8d62b3cf98dea05d7ce189a68100a3ced096e70bf", 69),
}
MAX_SOURCE_FILES = 2000
MAX_SOURCE_FILE_BYTES = 2_000_000
MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_REPORT_BYTES = 4 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{40}\Z")


def _git(repo, *args, timeout=45):
    result = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError("Pinned Git source is unavailable or incomplete")
    return result.stdout


def _selected_source(path):
    if path in _REQUIRED_FILES or path in _OPTIONAL_FILES:
        return True
    if path.startswith("src/content/") and path.lower().endswith(".md"):
        return True
    if path.startswith("src/data/") and path.lower().endswith((".yaml", ".yml")):
        return True
    if path.startswith("src/pages/") and path.endswith((".astro", ".ts")) and not path.endswith(".d.ts"):
        return True
    return False


def _snapshot_from_git(repo, commit):
    if not SHA.fullmatch(commit):
        raise ValueError("A fully pinned 40-character site commit is required")
    repo = Path(repo).resolve(strict=True)
    resolved = _git(repo, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    if resolved != commit:
        raise ValueError("Source commit did not resolve to the exact pin")
    tree = _git(repo, "rev-parse", "--verify", commit + "^{tree}").decode().strip()
    if not SHA.fullmatch(tree):
        raise ValueError("Invalid pinned Git tree SHA")
    entries = _git(repo, "ls-tree", "-r", "-z", commit)
    selected = {}
    selected_count = 0
    for line in entries.split(b"\x00"):
        if not line:
            continue
        try:
            descriptor, path_raw = line.split(b"\t", 1)
            mode, kind, object_sha = descriptor.decode("ascii").split()
            path = path_raw.decode("utf-8", "strict")
        except (UnicodeDecodeError, ValueError):
            raise ValueError("Invalid pinned tree entry") from None
        if path.startswith(("src/content/", "src/data/", "src/pages/")) or path in ("src", "src/content", "src/data", "src/pages", "src/lib"):
            if kind == "commit" or mode == "120000":
                raise ValueError("Gitlink or symlink in trusted discovery tree")
        if path.startswith("src/pages/") and not (path.endswith((".astro", ".ts")) and not path.endswith(".d.ts")):
            raise ValueError("Unrecognized route source in pinned tree: " + path)
        if not _selected_source(path):
            continue
        if (not path or "%" in path or kind != "blob" or mode not in _REGULAR_BLOB_MODES or
                not SHA.fullmatch(object_sha)):
            raise ValueError("Unapproved snapshot file object: " + path)
        selected_count += 1
        if selected_count > MAX_SOURCE_FILES:
            raise ValueError("Source-file count budget exceeded")
        # Verify both the immutable tree's SHA and the canonical Git blob hash.
        raw = _git(repo, "cat-file", "blob", object_sha)
        if len(raw) > MAX_SOURCE_FILE_BYTES or git_blob_sha1(raw) != object_sha:
            raise ValueError("Pinned site source blob failed integrity or size checks")
        selected[path] = (object_sha, raw)
    if not _REQUIRED_FILES.issubset(selected):
        raise ValueError("Pinned snapshot missing mandatory site source files")
    return PinnedSiteSnapshot.from_mapping(commit_sha=commit, tree_sha=tree, files=selected)


def _read_pdf_once(path, digest):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES or sha256(data).hexdigest() != digest:
        raise ValueError("Original PDF size/SHA-256 mismatch")
    return data


class _PinnedLocalTransport:
    def __init__(self, by_url):
        self._by_url = dict(by_url)
        self.calls = []

    def fetch(self, url, policy):
        self.calls.append(url)
        if url not in self._by_url:
            raise DocumentError("policy_denied")
        return self._by_url[url]


def _report_file(output, record):
    content = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(content) > MAX_REPORT_BYTES:
        raise ValueError("Diagnostic report budget exceeded")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)


def _catalog_entries(catalog):
    return [{"document_id": c.document_id,
             "original_url": c.resolved_url,
             "owner_entity_ids": list(c.owner_entity_ids),
             "source_locators": list(c.source_locators),
             "source_revision_ids": list(c.source_revision_ids)}
            for c in catalog.pdf_candidates]


def _run(args):
    site = _snapshot_from_git(args.site_repo, args.site_commit)
    package = adapt_snapshot(site)
    catalog = adapt_support_catalog(package)
    base = {"tool":"stage3b-real-adapter-pinned-local-v0.1",
            "source_commit":site.commit_sha, "source_tree":site.tree_sha,
            "site_parser_version":package.parser_version,
            "pdf_parser_version":PARSER_VERSION,
            "site_ready_for_promotion":package.ready_for_promotion,
            "catalog_ready_for_promotion":catalog.ready_for_promotion,
            "catalog_candidate_count":len(catalog.pdf_candidates),
            "mode":"DISCOVERY" if args.discover else "EXTRACTION"}
    if args.discover:
        base.update({"catalog_candidates":_catalog_entries(catalog),
                     "note":"Exact IDs and URLs from immutable site source; no PDFs were opened."})
        return base, 0 if catalog.ready_for_promotion else 2
    if not catalog.ready_for_promotion:
        return {**base,"overall":"BLOCKED","error":"real_catalog_not_promotable"}, 2
    bindings = json.loads(Path(args.bindings).read_text(encoding="utf-8"))
    if type(bindings) is not dict or set(bindings) - set(EXPECTED):
        raise ValueError("Bindings must contain only four approved labels")
    candidates_by_url = {candidate.resolved_url: candidate for candidate in catalog.pdf_candidates}
    # A subset of the full real-derived catalog: never synthesize IDs or owners.
    selected = []
    results = {}
    contents = {}
    for label, (expected_sha, expected_pages) in EXPECTED.items():
        item = {"label":label,"expected_sha256":expected_sha,"expected_pages":expected_pages}
        binding = bindings.get(label)
        if (type(binding) is not dict or set(binding) != {"url", "path"} or
                any(type(v) is not str or not v for v in binding.values())):
            item["status"] = "UNCOVERED"
            item["reason"] = "no_exact_binding_to_real_catalog"
            results[label] = item
            continue
        url = binding["url"]
        candidate = candidates_by_url.get(url)
        if candidate is None:
            item["status"] = "UNCOVERED"
            item["reason"] = "real_catalog_contains_no_matching_url"
            results[label] = item
            continue
        if url in contents:
            raise ValueError("Multiple labels cannot alias one original catalog URL")
        try:
            raw = _read_pdf_once(binding["path"], expected_sha)
        except (OSError, ValueError):
            item["status"] = "SHA256_MISMATCH_OR_UNAVAILABLE"
            results[label] = item
            continue
        contents[url] = raw
        selected.append(candidate)
        item["original_url"] = url
        item["document_id"] = candidate.document_id
        item["owner_entity_ids"] = list(candidate.owner_entity_ids)
        item["source_locators"] = list(candidate.source_locators)
        item["source_revision_ids"] = list(candidate.source_revision_ids)
        item["status"] = "VERIFIED_INPUT"
        results[label] = item
    if not selected:
        return {**base,"overall":"BLOCKED","results":list(results.values()),
                "note":"No matching SHA-verified original PDFs in the pinned catalog."}, 2
    selected_ids = {c.document_id for c in selected}
    scoped = replace(catalog,
        documents=tuple(d for d in catalog.documents if d.document_id in selected_ids),
        pdf_candidates=tuple(c for c in catalog.pdf_candidates if c.document_id in selected_ids),
        occurrences=tuple(o for o in catalog.occurrences if o.document_id in selected_ids))
    hosts = tuple(args.allowed_host)
    prefixes = tuple(args.allowed_prefix)
    policy = DocumentFetchPolicy(allowed_hosts=hosts, allowed_path_prefixes=prefixes)
    transport = _PinnedLocalTransport(contents)
    adapter = adapt_external_documents(scoped, policy, transport=transport,
                extractor=SubprocessPdfExtractor(enable_development_worker=True))
    status_map = {s.document_id: s for s in adapter.statuses}
    revision_map = {r.document_id: r for r in adapter.revisions}
    association_map = {a.document_id: a for a in adapter.associations}
    diagnostic_by_id = {}
    for d in adapter.diagnostics:
        diagnostic_by_id.setdefault(d.document_id, []).append(d.code)
    for label, entry in results.items():
        if entry["status"] != "VERIFIED_INPUT":
            continue
        c = candidates_by_url[entry["original_url"]]
        s, rev, assoc = status_map.get(c.document_id), revision_map.get(c.document_id), association_map.get(c.document_id)
        evidences = [e for e in adapter.evidence if s is not None and e.source_revision_id == s.revision_id]
        provenance = (assoc is not None and assoc.owner_entity_ids == c.owner_entity_ids and
                      assoc.source_locators == c.source_locators and
                      assoc.source_revision_ids == c.source_revision_ids)
        revision_id = (stable_id("saturn-pdf-revision-v1", rev.document_id, rev.url,
                       rev.bytes_sha256, rev.parser_version) if rev is not None else None)
        valid = bool(s and rev and provenance and revision_id == s.revision_id and
            rev.url == c.resolved_url and rev.bytes_sha256 == entry["expected_sha256"] and
            rev.parser_version == PARSER_VERSION and rev.page_count == entry["expected_pages"] and
            rev.extraction_state == "extracted" and s.status == "extracted" and
            len(evidences) == entry["expected_pages"] and
            [e.page_number for e in evidences] == list(range(1, entry["expected_pages"]+1)) and
            all(e.locator == rev.url + "#page=" + str(e.page_number) and
                e.source_revision_id == revision_id for e in evidences) and
            not diagnostic_by_id.get(c.document_id))
        entry.update({"status":"PASS" if valid else "FAILED",
                      "adapter_status":s.status if s else None,
                      "revision_id":s.revision_id if s else None,
                      "revision_state":rev.extraction_state if rev else None,
                      "page_count":rev.page_count if rev else None,
                      "pdf_sha256":rev.bytes_sha256 if rev else None,
                      "parser_version":rev.parser_version if rev else None,
                      "extracted_text_sha256":rev.extracted_text_sha256 if rev else None,
                      "physical_pages":[e.page_number for e in evidences],
                      "evidence_count":len(evidences),
                      "provenance_matches_real_catalog":provenance,
                      "diagnostics":diagnostic_by_id.get(c.document_id, [])})
    passed = sum(x["status"] == "PASS" for x in results.values())
    overall = "PASS" if (passed == 4 and adapter.ready_for_promotion and
                 len(transport.calls) == 4 and set(transport.calls) == set(contents)) else "BLOCKED"
    base.update({"overall":overall,"passed":passed,"expected":4,
                 "scoped_adapter_ready_for_promotion":adapter.ready_for_promotion,
                 "scoped_adapter_complete":adapter.complete,
                 "scoped_document_count":len(selected),
                 "full_catalog_was_not_extracted":len(catalog.pdf_candidates) != len(selected),
                 "transport_calls":len(transport.calls),
                 "adapter_statuses":[{"document_id":s.document_id,"status":s.status,"revision_id":s.revision_id}
                                     for s in adapter.statuses],
                 "adapter_diagnostics":[{"document_id":d.document_id,"code":d.code} for d in adapter.diagnostics],
                 "results":[results[k] for k in EXPECTED],
                 "uri_inertness_note":"Worker output is page text only; no annotation URI fields are used as evidence. Independent literal-URI-equality inspection of original PDFs is not claimed by this runner.",
                 "note":"This is an authorized scoped local-transport test derived from a real pinned site catalog, NOT a full-catalog promotion or production sandbox."})
    return base, 0 if overall == "PASS" else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-repo", type=Path, required=True)
    p.add_argument("--site-commit", required=True)
    p.add_argument("--discover", action="store_true")
    p.add_argument("--bindings", type=Path)
    p.add_argument("--allowed-host", action="append", default=[])
    p.add_argument("--allowed-prefix", action="append", default=[])
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if not args.discover and (args.bindings is None or not args.allowed_host or not args.allowed_prefix):
        p.error("Extraction requires --bindings, explicit --allowed-host and --allowed-prefix")
    try:
        report, code = _run(args)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired, DocumentError) as exc:
        report, code = ({"tool":"stage3b-real-adapter-pinned-local-v0.1",
                        "overall":"STOPPED", "error_code":type(exc).__name__,
                        "note":"Fail-closed; no extracted content or partial result."}, 2)
    _report_file(args.output, report)
    print(json.dumps({"overall":report.get("overall",report.get("mode")),
                      "passed":report.get("passed",0),"output":str(args.output)}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())