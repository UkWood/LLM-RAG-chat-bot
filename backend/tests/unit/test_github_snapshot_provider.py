import base64
import hashlib
from http.client import IncompleteRead
import json
import unittest

from saturn_ai.ingestion.github_snapshot_provider import (
    BlobIntegrityError,
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubProviderConfig,
    GitHubRateLimitError,
    GitHubSnapshotProvider,
    HttpResponse,
    IncompleteTreeError,
    OperationTimeoutError,
    ProviderConfigurationError,
    ResourceLimitError,
    RouteSourceDriftError,
    TreeValidationError,
    UnsupportedGitObjectFormatError,
)
from saturn_ai.ingestion.saturn_site_adapter import adapt_snapshot


COMMIT_A = "a" * 40
COMMIT_B = "f" * 40
ROOT_TREE_SHA = "b" * 40
REPOSITORY = "UkWood/Saturn-Main-Site"
API = "https://api.github.com"
BASE = API + "/repos/UkWood/Saturn-Main-Site"
REF_URL = BASE + "/git/ref/heads/main"
COMMIT_URL = BASE + "/git/commits/" + COMMIT_A
ROOT_RECURSIVE_URL = BASE + "/git/trees/" + ROOT_TREE_SHA + "?recursive=1"
ROOT_NONRECURSIVE_URL = BASE + "/git/trees/" + ROOT_TREE_SHA + "?recursive=0"


def git_blob_sha1(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def json_response(value, status=200, headers=None):
    rendered = json.dumps(value).encode("utf-8")
    return HttpResponse(status, {"Content-Type": "application/json", **(headers or {})}, rendered)


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, *, headers, timeout, max_bytes):
        self.calls.append({
            "url": url,
            "headers": dict(headers),
            "timeout": timeout,
            "max_bytes": max_bytes,
        })
        if url not in self.routes:
            raise AssertionError("Unexpected HTTP request: " + url)
        value = self.routes[url]
        if isinstance(value, list):
            if len(value) > 1:
                value = value.pop(0)
            else:
                value = value[0]
        if callable(value):
            value = value()
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, HttpResponse):
            return value
        return json_response(value)


def site_files():
    return {
        "astro.config.mjs": (
            b"const site = process.env.SITE_URL || 'https://www.mnppsaturn.ru';\n"
        ),
        "src/content.config.ts": b"export const collections = {};\n",
        "src/pages/index.astro": b"<html>home</html>\n",
        "src/pages/products/[slug].astro": b"<html>product</html>\n",
        "src/content/products/demo.md": b"---\ntitle: Demo device\n---\nA trusted demo device.\n",
        "src/data/industries.yaml": b"industries:\n  - heating\n",
        "src/lib/url.ts": b"export const url = '/';\n",
        "src/content/products/preview.png": b"not selected image bytes",
        "src/data/notes.json": b'{"not":"selected"}',
        "public/logo.png": b"unrelated binary asset",
    }


def build_transport(
    files=None,
    *,
    recursive_truncated=False,
    fallback_truncated=False,
    blob_overrides=None,
    missing_blobs=(),
    recursive_entries_mutator=None,
):
    files = site_files() if files is None else dict(files)
    blob_overrides = blob_overrides or {}
    directories = set()
    for path in files:
        parts = path.split("/")
        for index in range(1, len(parts)):
            directories.add("/".join(parts[:index]))

    tree_shas = {"": ROOT_TREE_SHA}
    for directory in sorted(directories):
        tree_shas[directory] = hashlib.sha1(("tree:" + directory).encode()).hexdigest()

    recursive_entries = []
    direct_entries = {directory: [] for directory in tree_shas}
    for directory in sorted(directories):
        parent, _, name = directory.rpartition("/")
        entry = {
            "path": name if parent else directory,
            "mode": "040000",
            "type": "tree",
            "sha": tree_shas[directory],
        }
        direct_entries[parent].append(entry)
        recursive_entries.append({
            "path": directory,
            "mode": "040000",
            "type": "tree",
            "sha": tree_shas[directory],
        })

    blob_shas = {}
    for path, content in sorted(files.items()):
        parent, _, name = path.rpartition("/")
        digest = git_blob_sha1(content)
        blob_shas[path] = digest
        entry = {
            "path": name,
            "mode": "100644",
            "type": "blob",
            "sha": digest,
            "size": len(content),
        }
        direct_entries[parent].append(entry)
        recursive_entries.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": digest,
            "size": len(content),
        })

    for entries in direct_entries.values():
        entries.sort(key=lambda item: item["path"])
    recursive_entries.sort(key=lambda item: item["path"])
    if recursive_entries_mutator is not None:
        recursive_entries = recursive_entries_mutator(list(recursive_entries))

    routes = {
        REF_URL: {
            "ref": "refs/heads/main",
            "object": {"sha": COMMIT_A, "type": "commit"},
        },
        COMMIT_URL: {
            "sha": COMMIT_A,
            "tree": {"sha": ROOT_TREE_SHA, "url": BASE + "/git/trees/" + ROOT_TREE_SHA},
        },
        ROOT_RECURSIVE_URL: {
            "sha": ROOT_TREE_SHA,
            "truncated": recursive_truncated,
            "tree": recursive_entries,
        },
    }

    for directory, tree_sha in tree_shas.items():
        routes[BASE + "/git/trees/" + tree_sha + "?recursive=0"] = {
            "sha": tree_sha,
            "truncated": fallback_truncated,
            "tree": direct_entries[directory],
        }

    for path, content in files.items():
        digest = blob_shas[path]
        if path in missing_blobs:
            routes[BASE + "/git/blobs/" + digest] = HttpResponse(404, {}, b"{}")
            continue
        payload = {
            "sha": digest,
            "size": len(content),
            "encoding": "base64",
            "content": base64.b64encode(content).decode("ascii"),
        }
        routes[BASE + "/git/blobs/" + digest] = blob_overrides.get(path, payload)

    return FakeTransport(routes), blob_shas


def make_provider(transport, **overrides):
    values = {
        "request_timeout_seconds": 5.0,
        "operation_timeout_seconds": 60.0,
        "max_attempts": 3,
        "max_retry_delay_seconds": 1.0,
    }
    values.update(overrides)
    config = GitHubProviderConfig(
        token="read-only-test-token",
        object_format="sha1",
        **values,
    )
    sleeps = []
    provider = GitHubSnapshotProvider(
        config,
        transport=transport,
        sleeper=sleeps.append,
        wall_clock=lambda: 0.0,
    )
    return provider, sleeps


class GitHubSnapshotProviderTests(unittest.TestCase):
    def test_success_pins_once_selects_only_contract_files_and_adapts_offline(self):
        transport, blob_shas = build_transport()
        provider, _ = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertEqual(snapshot.repository, "UkWood/Saturn-Main-Site")
        self.assertEqual(snapshot.branch, "main")
        self.assertEqual(snapshot.commit_sha, COMMIT_A)
        self.assertEqual(snapshot.tree_sha, ROOT_TREE_SHA)
        paths = [item.path for item in snapshot.files]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(set(paths), {
            "astro.config.mjs",
            "src/content.config.ts",
            "src/content/products/demo.md",
            "src/data/industries.yaml",
            "src/lib/url.ts",
            "src/pages/index.astro",
            "src/pages/products/[slug].astro",
        })
        self.assertNotIn("public/logo.png", paths)
        self.assertNotIn("src/content/products/preview.png", paths)
        self.assertNotIn("src/data/notes.json", paths)
        for item in snapshot.files:
            self.assertEqual(item.blob_sha, blob_shas[item.path])
            self.assertEqual(item.content_sha256, hashlib.sha256(item.content).hexdigest())

        package = adapt_snapshot(snapshot)
        self.assertTrue(package.ready_for_promotion)
        demo, = [item for item in package.entities if item.slug == "demo"]
        self.assertEqual(demo.title, "Demo device")
        self.assertEqual(demo.canonical_url, "https://www.mnppsaturn.ru/products/demo/")

        self.assertEqual(sum(call["url"] == REF_URL for call in transport.calls), 1)
        first_call = transport.calls[0]
        self.assertEqual(first_call["headers"]["Authorization"], "Bearer read-only-test-token")
        self.assertEqual(first_call["headers"]["Accept"], "application/vnd.github+json")
        self.assertEqual(first_call["headers"]["X-GitHub-Api-Version"], "2022-11-28")

    def test_main_moving_during_blob_download_does_not_change_pinned_revision(self):
        transport, _ = build_transport()
        transport.routes[REF_URL] = [
            json_response({"ref": "refs/heads/main", "object": {"sha": COMMIT_A, "type": "commit"}}),
            json_response({"ref": "refs/heads/main", "object": {"sha": COMMIT_B, "type": "commit"}}),
        ]
        provider, _ = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertEqual(snapshot.commit_sha, COMMIT_A)
        self.assertEqual(sum(call["url"] == REF_URL for call in transport.calls), 1)
        self.assertFalse(any(COMMIT_B in call["url"] for call in transport.calls))

    def test_truncated_recursive_tree_uses_full_nonrecursive_fallback(self):
        transport, _ = build_transport(recursive_truncated=True)
        provider, _ = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertEqual(snapshot.commit_sha, COMMIT_A)
        self.assertTrue(any(call["url"] == ROOT_NONRECURSIVE_URL for call in transport.calls))
        self.assertEqual(sum(call["url"] == REF_URL for call in transport.calls), 1)
        self.assertEqual(len(snapshot.files), 7)

    def test_truncated_nonrecursive_tree_fails_closed(self):
        transport, _ = build_transport(
            recursive_truncated=True,
            fallback_truncated=True,
        )
        provider, _ = make_provider(transport)

        with self.assertRaises(IncompleteTreeError):
            provider.fetch_snapshot()

    def test_recursive_tree_duplicate_path_is_rejected(self):
        def duplicate(entries):
            return entries + [dict(entries[-1])]
        transport, _ = build_transport(recursive_entries_mutator=duplicate)
        provider, _ = make_provider(transport)

        with self.assertRaises(TreeValidationError):
            provider.fetch_snapshot()

    def test_recursive_tree_missing_parent_directory_is_rejected(self):
        def remove_parent(entries):
            return [item for item in entries if item["path"] != "src/content"]
        transport, _ = build_transport(recursive_entries_mutator=remove_parent)
        provider, _ = make_provider(transport)

        with self.assertRaises(IncompleteTreeError):
            provider.fetch_snapshot()

    def test_tree_response_identity_must_match_requested_tree(self):
        transport, _ = build_transport()
        transport.routes[ROOT_RECURSIVE_URL]["sha"] = "c" * 40
        provider, _ = make_provider(transport)

        with self.assertRaises(TreeValidationError):
            provider.fetch_snapshot()

    def test_commit_response_identity_must_match_pinned_ref(self):
        transport, _ = build_transport()
        transport.routes[COMMIT_URL]["sha"] = COMMIT_B
        provider, _ = make_provider(transport)

        with self.assertRaises(TreeValidationError):
            provider.fetch_snapshot()

    def test_branch_ref_must_resolve_to_commit_object(self):
        transport, _ = build_transport()
        transport.routes[REF_URL]["object"]["type"] = "tag"
        provider, _ = make_provider(transport)

        with self.assertRaises(TreeValidationError):
            provider.fetch_snapshot()

    def test_missing_required_file_fails_before_any_blob_fetch(self):
        files = site_files()
        del files["src/content.config.ts"]
        transport, _ = build_transport(files)
        provider, _ = make_provider(transport)

        with self.assertRaises(TreeValidationError):
            provider.fetch_snapshot()
        self.assertFalse(any("/git/blobs/" in call["url"] for call in transport.calls))

    def test_unknown_route_extension_and_d_ts_are_drift_errors(self):
        for path in ("src/pages/custom.json", "src/pages/global.d.ts"):
            with self.subTest(path=path):
                files = site_files()
                files[path] = b"not a supported Astro route source"
                transport, _ = build_transport(files)
                provider, _ = make_provider(transport)
                with self.assertRaises(RouteSourceDriftError) as caught:
                    provider.fetch_snapshot()
                self.assertIn(path, caught.exception.paths)
                self.assertFalse(any("/git/blobs/" in call["url"] for call in transport.calls))

    def test_symlink_or_submodule_in_selected_source_is_rejected(self):
        for mode, object_type in (("120000", "blob"), ("160000", "commit")):
            with self.subTest(mode=mode):
                transport, _ = build_transport()
                tree = transport.routes[ROOT_RECURSIVE_URL]["tree"]
                target = next(item for item in tree if item["path"] == "src/content/products/demo.md")
                target["mode"] = mode
                target["type"] = object_type
                provider, _ = make_provider(transport)
                with self.assertRaises(TreeValidationError):
                    provider.fetch_snapshot()

    def test_symlink_in_unrelated_asset_directory_is_not_downloaded(self):
        files = site_files()
        files["public/logo-link.png"] = b"link target"
        transport, _ = build_transport(files)
        tree = transport.routes[ROOT_RECURSIVE_URL]["tree"]
        target = next(item for item in tree if item["path"] == "public/logo-link.png")
        target["mode"] = "120000"
        provider, _ = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertNotIn("public/logo-link.png", {item.path for item in snapshot.files})

    def test_blob_sha_mismatch_fails(self):
        transport, _ = build_transport()
        path = "src/content/products/demo.md"
        blob_sha = git_blob_sha1(site_files()[path])
        transport.routes[BASE + "/git/blobs/" + blob_sha]["sha"] = "c" * 40
        provider, _ = make_provider(transport)

        with self.assertRaises(BlobIntegrityError):
            provider.fetch_snapshot()

    def test_blob_content_hash_mismatch_fails(self):
        transport, _ = build_transport()
        path = "src/content/products/demo.md"
        blob_sha = git_blob_sha1(site_files()[path])
        transport.routes[BASE + "/git/blobs/" + blob_sha]["content"] = base64.b64encode(b"tampered").decode()
        transport.routes[BASE + "/git/blobs/" + blob_sha]["size"] = len(b"tampered")
        provider, _ = make_provider(transport)

        with self.assertRaises(BlobIntegrityError):
            provider.fetch_snapshot()

    def test_invalid_base64_fails(self):
        transport, _ = build_transport()
        path = "src/content/products/demo.md"
        blob_sha = git_blob_sha1(site_files()[path])
        transport.routes[BASE + "/git/blobs/" + blob_sha]["content"] = "%%%not-base64%%%"
        provider, _ = make_provider(transport)

        with self.assertRaises(BlobIntegrityError):
            provider.fetch_snapshot()

    def test_blob_size_mismatch_fails(self):
        transport, _ = build_transport()
        path = "src/content/products/demo.md"
        blob_sha = git_blob_sha1(site_files()[path])
        transport.routes[BASE + "/git/blobs/" + blob_sha]["size"] += 1
        provider, _ = make_provider(transport)

        with self.assertRaises(BlobIntegrityError):
            provider.fetch_snapshot()

    def test_missing_blob_fails_without_returning_partial_snapshot(self):
        files = site_files()
        missing_path = "src/pages/index.astro"
        transport, blob_shas = build_transport(files, missing_blobs={missing_path})
        provider, _ = make_provider(transport)

        with self.assertRaises(GitHubNotFoundError):
            provider.fetch_snapshot()
        self.assertEqual(blob_shas[missing_path], git_blob_sha1(files[missing_path]))

    def test_retry_after_is_respected_and_retry_count_is_bounded(self):
        transport, _ = build_transport()
        path = "src/content/products/demo.md"
        blob_sha = git_blob_sha1(site_files()[path])
        blob_url = BASE + "/git/blobs/" + blob_sha
        success = transport.routes[blob_url]
        transport.routes[blob_url] = [
            HttpResponse(429, {"Retry-After": "0.1"}, b'{"message":"slow down"}'),
            success,
        ]
        provider, sleeps = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertEqual(snapshot.commit_sha, COMMIT_A)
        self.assertEqual(sleeps, [0.1])
        self.assertEqual(sum(call["url"] == blob_url for call in transport.calls), 2)

    def test_persistent_rate_limit_fails_after_max_attempts(self):
        transport, _ = build_transport()
        transport.routes[REF_URL] = HttpResponse(
            403,
            {"X-RateLimit-Remaining": "0", "Retry-After": "0"},
            b'{"message":"API rate limit exceeded"}',
        )
        provider, _ = make_provider(transport, max_attempts=2)

        with self.assertRaises(GitHubRateLimitError):
            provider.fetch_snapshot()
        self.assertEqual(sum(call["url"] == REF_URL for call in transport.calls), 2)

    def test_network_error_uses_bounded_retry(self):
        transport, _ = build_transport()
        original = transport.routes[REF_URL]
        transport.routes[REF_URL] = [GitHubNetworkError("temporary"), original]
        provider, sleeps = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertEqual(snapshot.commit_sha, COMMIT_A)
        self.assertEqual(sum(call["url"] == REF_URL for call in transport.calls), 2)
        self.assertEqual(sleeps, [0.25])

    def test_authentication_and_not_found_errors_are_typed(self):
        for status, expected in (
            (401, GitHubAuthenticationError),
            (403, GitHubAuthenticationError),
            (404, GitHubNotFoundError),
        ):
            with self.subTest(status=status):
                transport, _ = build_transport()
                transport.routes[REF_URL] = HttpResponse(status, {}, b"{}")
                provider, _ = make_provider(transport)
                with self.assertRaises(expected):
                    provider.fetch_snapshot()

    def test_incomplete_http_read_is_retried(self):
        transport, _ = build_transport()
        original = transport.routes[REF_URL]
        transport.routes[REF_URL] = [IncompleteRead(b"partial", 5), original]
        provider, sleeps = make_provider(transport)

        snapshot = provider.fetch_snapshot()

        self.assertEqual(snapshot.commit_sha, COMMIT_A)
        self.assertEqual(sum(call["url"] == REF_URL for call in transport.calls), 2)
        self.assertEqual(sleeps, [0.25])

    def test_content_length_mismatch_is_rejected(self):
        transport, _ = build_transport()
        valid = json_response(transport.routes[REF_URL])
        transport.routes[REF_URL] = HttpResponse(
            200,
            {"Content-Length": "1"},
            valid.body,
        )
        provider, _ = make_provider(transport)

        with self.assertRaises(GitHubAPIError):
            provider.fetch_snapshot()

    def test_selected_route_path_rejects_percent_encoding(self):
        files = site_files()
        files["src/pages/unsafe%20route.astro"] = b"<html>unsafe</html>\n"
        transport, _ = build_transport(files)
        provider, _ = make_provider(transport)

        with self.assertRaises(TreeValidationError):
            provider.fetch_snapshot()
        self.assertFalse(any("/git/blobs/" in call["url"] for call in transport.calls))

    def test_redirect_is_not_followed(self):
        transport, _ = build_transport()
        transport.routes[REF_URL] = HttpResponse(302, {"Location": "https://evil.example/"}, b"")
        provider, _ = make_provider(transport)

        with self.assertRaises(GitHubAPIError):
            provider.fetch_snapshot()
        self.assertEqual(len(transport.calls), 1)

    def test_non_json_and_oversized_responses_fail(self):
        transport, _ = build_transport()
        transport.routes[REF_URL] = HttpResponse(200, {}, b"not json")
        provider, _ = make_provider(transport)
        with self.assertRaises(GitHubAPIError):
            provider.fetch_snapshot()

        transport, _ = build_transport()
        provider, _ = make_provider(transport, max_response_bytes=10)
        with self.assertRaises(ResourceLimitError):
            provider.fetch_snapshot()

    def test_resource_limits_cover_tree_depth_count_file_and_snapshot(self):
        cases = (
            {"max_tree_entries": 1},
            {"max_tree_depth": 1},
            {"max_selected_files": 1},
            {"max_file_bytes": 5},
            {"max_snapshot_bytes": 10},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                transport, _ = build_transport()
                provider, _ = make_provider(transport, **overrides)
                with self.assertRaises(ResourceLimitError):
                    provider.fetch_snapshot()

    def test_api_request_limit_and_operation_timeout_fail_closed(self):
        transport, _ = build_transport()
        provider, _ = make_provider(transport, max_api_requests=1)
        with self.assertRaises(ResourceLimitError):
            provider.fetch_snapshot()

        transport, _ = build_transport()
        ticks = iter((0.0, 2.0))
        provider = GitHubSnapshotProvider(
            GitHubProviderConfig(
                token="read-only-test-token",
                object_format="sha1",
                operation_timeout_seconds=1.0,
            ),
            transport=transport,
            clock=lambda: next(ticks),
        )
        with self.assertRaises(OperationTimeoutError):
            provider.fetch_snapshot()
        self.assertEqual(transport.calls, [])

    def test_object_format_must_be_explicit_and_sha1(self):
        with self.assertRaises(UnsupportedGitObjectFormatError):
            GitHubProviderConfig(token="read-only-test-token", object_format="sha256")
        with self.assertRaises(ProviderConfigurationError):
            GitHubProviderConfig(token="read-only-test-token", object_format="")

    def test_non_finite_timeout_and_invalid_token_are_rejected(self):
        with self.assertRaises(ProviderConfigurationError):
            GitHubProviderConfig(
                token="read-only-test-token",
                object_format="sha1",
                request_timeout_seconds=float("inf"),
            )
        with self.assertRaises(ProviderConfigurationError):
            GitHubProviderConfig(token="bad token", object_format="sha1")
        with self.assertRaises(ProviderConfigurationError):
            GitHubProviderConfig(token="bad\x00token", object_format="sha1")

    def test_environment_configuration_requires_explicit_object_format(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"SATURN_GITHUB_TOKEN": "test-token"}, clear=True):
            with self.assertRaises(ProviderConfigurationError):
                GitHubProviderConfig.from_env()
        with patch.dict(
            "os.environ",
            {
                "SATURN_GITHUB_TOKEN": "test-token",
                "SATURN_GITHUB_OBJECT_FORMAT": "sha1",
            },
            clear=True,
        ):
            config = GitHubProviderConfig.from_env()
        self.assertEqual(config.object_format, "sha1")
        self.assertNotIn("test-token", repr(config))

    def test_result_is_deterministic_independent_of_tree_order(self):
        transport_a, _ = build_transport()
        transport_b, _ = build_transport(
            recursive_entries_mutator=lambda entries: list(reversed(entries))
        )
        snapshot_a, _ = make_provider(transport_a)
        snapshot_b, _ = make_provider(transport_b)

        self.assertEqual(snapshot_a.fetch_snapshot(), snapshot_b.fetch_snapshot())


if __name__ == "__main__":
    unittest.main()
