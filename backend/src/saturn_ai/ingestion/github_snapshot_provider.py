"""Read-only GitHub Snapshot Provider for the trusted Saturn site.

The provider is deliberately separate from the pure/offline Site Content Adapter.
It pins refs/heads/main once, reads only immutable Git object IDs afterwards, and
returns the existing PinnedSiteSnapshot contract. It never clones or writes.
"""
from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from hashlib import sha1, sha256
import json
import math
import os
import re
import ssl
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .saturn_contracts import TRUSTED_SITE_BRANCH, TRUSTED_SITE_REPOSITORY
from .saturn_site_adapter import PinnedSiteSnapshot, SnapshotFile
from .snapshot_provider import SnapshotProvider


GITHUB_API_ORIGIN = "https://api.github.com"
GITHUB_PHYSICAL_REPOSITORY = "UkWood/Saturn-Main-Site"
_REPOSITORY_API_PATH = "/repos/" + GITHUB_PHYSICAL_REPOSITORY
GITHUB_API_VERSION = "2022-11-28"
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_BASE64_WHITESPACE_RE = re.compile(r"[ \t\r\n]+")

_REQUIRED_FILES = frozenset({
    "src/content.config.ts",
    "astro.config.mjs",
})
_OPTIONAL_FILES = frozenset({
    "src/lib/url.ts",
    "src/lib/nav.ts",
    "src/lib/service.ts",
})
_REGULAR_BLOB_MODES = frozenset({"100644", "100755"})


class SnapshotProviderError(RuntimeError):
    """Base class for a failed, non-partial snapshot operation."""


class ProviderConfigurationError(SnapshotProviderError):
    pass


class UnsupportedGitObjectFormatError(SnapshotProviderError):
    pass


class GitHubAuthenticationError(SnapshotProviderError):
    pass


class GitHubRateLimitError(SnapshotProviderError):
    pass


class GitHubNotFoundError(SnapshotProviderError):
    pass


class GitHubAPIError(SnapshotProviderError):
    pass


class GitHubNetworkError(SnapshotProviderError):
    pass


class OperationTimeoutError(SnapshotProviderError):
    pass


class ResourceLimitError(SnapshotProviderError):
    pass


class TreeValidationError(SnapshotProviderError):
    pass


class IncompleteTreeError(TreeValidationError):
    pass


class RouteSourceDriftError(TreeValidationError):
    """A regular file under src/pages/ is outside the approved route policy."""

    def __init__(self, paths: tuple[str, ...]):
        self.paths = paths
        super().__init__("Unsupported src/pages route-source file(s): " + ", ".join(paths))


class BlobIntegrityError(SnapshotProviderError):
    pass


@dataclass(frozen=True)
class GitHubProviderConfig:
    """Trusted runtime settings; repository, branch and API origin are fixed in code.

    GitHub's repository metadata endpoint does not currently expose a usable
    object_format field for this repository. Therefore SHA-1 must be explicitly
    set by trusted deployment configuration and is verified against every blob.
    """

    token: str = field(repr=False)
    object_format: str
    request_timeout_seconds: float = 15.0
    operation_timeout_seconds: float = 300.0
    max_attempts: int = 3
    max_retry_delay_seconds: float = 30.0
    max_api_requests: int = 2000
    max_response_bytes: int = 8_000_000
    max_tree_entries: int = 100_000
    max_tree_depth: int = 64
    max_selected_files: int = 2_000
    max_file_bytes: int = 2_000_000
    max_snapshot_bytes: int = 64_000_000

    def __post_init__(self):
        if (
            not isinstance(self.token, str)
            or not self.token
            or any(not 33 <= ord(ch) <= 126 for ch in self.token)
        ):
            raise ProviderConfigurationError("SATURN_GITHUB_TOKEN must contain a printable ASCII token")
        if not isinstance(self.object_format, str) or not self.object_format:
            raise ProviderConfigurationError("SATURN_GITHUB_OBJECT_FORMAT must be explicitly configured")
        if self.object_format != "sha1":
            raise UnsupportedGitObjectFormatError(
                "Snapshot Provider v0.1 requires explicit SATURN_GITHUB_OBJECT_FORMAT=sha1"
            )
        positive_numbers = (
            self.request_timeout_seconds,
            self.operation_timeout_seconds,
            self.max_retry_delay_seconds,
        )
        if any(type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or value <= 0 for value in positive_numbers):
            raise ProviderConfigurationError("Timeout and retry limits must be finite positive numbers")
        positive_integers = (
            self.max_attempts,
            self.max_api_requests,
            self.max_response_bytes,
            self.max_tree_entries,
            self.max_tree_depth,
            self.max_selected_files,
            self.max_file_bytes,
            self.max_snapshot_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in positive_integers):
            raise ProviderConfigurationError("All resource limits must be positive integers")

    @classmethod
    def from_env(cls) -> "GitHubProviderConfig":
        """Load the read-only token and explicit Git object format from environment."""
        return cls(
            token=os.environ.get("SATURN_GITHUB_TOKEN", ""),
            object_format=os.environ.get("SATURN_GITHUB_OBJECT_FORMAT", ""),
        )


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
        max_bytes: int,
    ) -> HttpResponse:
        """Perform one HTTPS GET without following redirects."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibHttpTransport:
    """Standard-library HTTPS transport with certificate checks and no redirects."""

    def __init__(self):
        self._opener = build_opener(
            _NoRedirectHandler(),
            HTTPSHandler(context=ssl.create_default_context()),
        )

    def get(self, url, *, headers, timeout, max_bytes) -> HttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with self._opener.open(request, timeout=timeout) as response:
                body = response.read(max_bytes + 1)
                return HttpResponse(
                    response.status,
                    dict(response.headers.items()),
                    body,
                )
        except HTTPError as exc:
            # HTTP errors are returned to the API layer for typed status handling.
            body = exc.read(max_bytes + 1)
            return HttpResponse(exc.code, dict(exc.headers.items()), body)
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            # Do not include the underlying exception text: it may contain URL details.
            raise GitHubNetworkError(
                "GitHub HTTPS request failed: " + type(exc).__name__
            ) from None


class _GitHubAPI:
    def __init__(
        self,
        config: GitHubProviderConfig,
        transport: HttpTransport,
        *,
        clock,
        sleeper,
        wall_clock,
    ):
        self._config = config
        self._transport = transport
        self._clock = clock
        self._sleeper = sleeper
        self._wall_clock = wall_clock
        self._deadline = 0.0
        self._request_count = 0

    def begin_operation(self) -> None:
        self._deadline = self._clock() + self._config.operation_timeout_seconds
        self._request_count = 0

    def get_json(self, endpoint: str) -> dict:
        if not endpoint.startswith("/") or endpoint.startswith("//"):
            raise ProviderConfigurationError("Only internal GitHub API paths are permitted")
        url = GITHUB_API_ORIGIN + endpoint
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self._config.token,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "saturn-ai-technical-consultant",
        }

        for attempt in range(1, self._config.max_attempts + 1):
            remaining = self._deadline - self._clock()
            if remaining <= 0:
                raise OperationTimeoutError("Snapshot operation time limit exceeded")
            self._request_count += 1
            if self._request_count > self._config.max_api_requests:
                raise ResourceLimitError("GitHub API request limit exceeded")

            try:
                response = self._transport.get(
                    url,
                    headers=headers,
                    timeout=min(self._config.request_timeout_seconds, remaining),
                    max_bytes=self._config.max_response_bytes,
                )
            except (GitHubNetworkError, TimeoutError, OSError, HTTPException) as exc:
                if attempt >= self._config.max_attempts:
                    raise GitHubNetworkError(
                        "GitHub network request failed after bounded retries"
                    ) from None
                self._sleep_before_retry(self._backoff(attempt), rate_limit=False)
                continue

            normalized_headers = {
                str(key).lower(): str(value)
                for key, value in response.headers.items()
            }
            content_length = normalized_headers.get("content-length")
            declared_length = None
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError:
                    raise GitHubAPIError("GitHub returned an invalid Content-Length") from None
                if declared_length < 0 or declared_length > self._config.max_response_bytes:
                    raise ResourceLimitError("GitHub API response size limit exceeded")
            if type(response.body) is not bytes:
                raise GitHubAPIError("GitHub returned a non-byte HTTP response body")
            if len(response.body) > self._config.max_response_bytes:
                raise ResourceLimitError("GitHub API response size limit exceeded")
            if declared_length is not None and declared_length != len(response.body):
                raise GitHubAPIError("GitHub response body length does not match Content-Length")

            rate_limited = self._is_rate_limited(response.status_code, normalized_headers, response.body)
            retryable = rate_limited or response.status_code in {408, 425} or 500 <= response.status_code <= 599
            if retryable:
                if attempt >= self._config.max_attempts:
                    if rate_limited:
                        raise GitHubRateLimitError("GitHub rate limit persisted after bounded retries")
                    raise GitHubAPIError(
                        "GitHub returned a temporary server error after bounded retries"
                    )
                delay = self._retry_after(normalized_headers, rate_limited, attempt)
                self._sleep_before_retry(delay, rate_limit=rate_limited)
                continue

            if response.status_code in {401, 403}:
                raise GitHubAuthenticationError(
                    "GitHub rejected the configured read-only credential or repository permission"
                )
            if response.status_code == 404:
                raise GitHubNotFoundError("A pinned GitHub repository object was not found")
            if response.status_code != 200:
                raise GitHubAPIError(
                    "GitHub API returned HTTP " + str(response.status_code)
                )

            try:
                value = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                raise GitHubAPIError("GitHub returned invalid UTF-8 JSON") from None
            if not isinstance(value, dict):
                raise GitHubAPIError("GitHub API response must be a JSON object")
            return value

        raise GitHubAPIError("GitHub request ended without a response")

    @staticmethod
    def _is_rate_limited(status: int, headers: Mapping[str, str], body: bytes) -> bool:
        if status == 429:
            return True
        if status != 403:
            return False
        if headers.get("x-ratelimit-remaining") == "0":
            return True
        message = body.decode("utf-8", errors="replace").lower()
        return "rate limit" in message or "secondary rate" in message

    def _backoff(self, attempt: int) -> float:
        return min(0.25 * (2 ** (attempt - 1)), self._config.max_retry_delay_seconds)

    def _retry_after(self, headers: Mapping[str, str], rate_limited: bool, attempt: int) -> float:
        raw = headers.get("retry-after")
        if raw is not None:
            try:
                return max(0.0, float(raw))
            except ValueError:
                try:
                    target = parsedate_to_datetime(raw)
                    if target.tzinfo is None:
                        target = target.replace(tzinfo=timezone.utc)
                    return max(0.0, target.timestamp() - self._wall_clock())
                except (TypeError, ValueError, OverflowError):
                    pass
        if rate_limited:
            reset = headers.get("x-ratelimit-reset")
            if reset is not None:
                try:
                    return max(0.0, float(reset) - self._wall_clock())
                except ValueError:
                    pass
        return self._backoff(attempt)

    def _sleep_before_retry(self, delay: float, *, rate_limit: bool) -> None:
        if delay > self._config.max_retry_delay_seconds:
            if rate_limit:
                raise GitHubRateLimitError(
                    "GitHub Retry-After exceeds the configured bounded retry window"
                )
            raise GitHubAPIError("Retry delay exceeds the configured bounded retry window")
        remaining = self._deadline - self._clock()
        if remaining <= 0 or delay > remaining:
            raise OperationTimeoutError("Snapshot operation time limit exceeded during retry")
        if delay > 0:
            self._sleeper(delay)


@dataclass(frozen=True)
class _TreeEntry:
    path: str
    mode: str
    object_type: str
    sha: str
    size: int | None


class GitHubSnapshotProvider(SnapshotProvider):
    """Fetch one exact, complete GitHub revision as the existing pinned snapshot."""

    def __init__(
        self,
        config: GitHubProviderConfig,
        *,
        transport: HttpTransport | None = None,
        clock=time.monotonic,
        sleeper=time.sleep,
        wall_clock=time.time,
    ):
        if not isinstance(config, GitHubProviderConfig):
            raise ProviderConfigurationError("GitHubProviderConfig is required")
        self.config = config
        self._api = _GitHubAPI(
            config,
            transport or UrllibHttpTransport(),
            clock=clock,
            sleeper=sleeper,
            wall_clock=wall_clock,
        )

    @classmethod
    def from_env(cls, **kwargs) -> "GitHubSnapshotProvider":
        return cls(GitHubProviderConfig.from_env(), **kwargs)

    def fetch_snapshot(self) -> PinnedSiteSnapshot:
        """Resolve main exactly once and return no object unless every check passes."""
        self._api.begin_operation()
        ref = self._api.get_json(_REPOSITORY_API_PATH + "/git/ref/heads/main")
        if ref.get("ref") != "refs/heads/main":
            raise TreeValidationError("GitHub ref response does not match refs/heads/main")
        ref_object = ref.get("object")
        if not isinstance(ref_object, dict) or ref_object.get("type") != "commit":
            raise TreeValidationError("refs/heads/main did not resolve to a commit object")
        commit_sha = self._validate_sha(ref_object.get("sha"), "branch commit")

        commit = self._api.get_json(
            _REPOSITORY_API_PATH + "/git/commits/" + quote(commit_sha, safe="")
        )
        if commit.get("sha") != commit_sha:
            raise TreeValidationError("GitHub commit response does not match the pinned commit SHA")
        commit_tree = commit.get("tree")
        if not isinstance(commit_tree, dict):
            raise TreeValidationError("Pinned commit response has no root tree")
        tree_sha = self._validate_sha(commit_tree.get("sha"), "root tree")

        inventory = self._enumerate_tree(tree_sha)
        selected = self._select_files(inventory)

        if len(selected) > self.config.max_selected_files:
            raise ResourceLimitError("Selected source file count limit exceeded")
        known_total = sum(
            entry.size for entry in selected.values()
            if entry.size is not None
        )
        if known_total > self.config.max_snapshot_bytes:
            raise ResourceLimitError("Selected snapshot byte limit exceeded")
        for entry in selected.values():
            if entry.size is not None and entry.size > self.config.max_file_bytes:
                raise ResourceLimitError("Selected file size limit exceeded: " + entry.path)

        snapshot_files = []
        total_bytes = 0
        for path in sorted(selected):
            entry = selected[path]
            blob = self._api.get_json(
                _REPOSITORY_API_PATH + "/git/blobs/" + quote(entry.sha, safe="")
            )
            content = self._decode_and_verify_blob(blob, entry)
            total_bytes += len(content)
            if total_bytes > self.config.max_snapshot_bytes:
                raise ResourceLimitError("Selected snapshot byte limit exceeded")
            raw_content_sha256 = sha256(content).hexdigest()
            snapshot_file = SnapshotFile(path, entry.sha, content)
            # The existing adapter records this exact raw-content SHA-256 in provenance.
            if snapshot_file.content_sha256 != raw_content_sha256:
                raise BlobIntegrityError("Raw content SHA-256 calculation is inconsistent")
            snapshot_files.append(snapshot_file)

        return PinnedSiteSnapshot(
            repository=TRUSTED_SITE_REPOSITORY,
            branch=TRUSTED_SITE_BRANCH,
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            files=tuple(snapshot_files),
        )

    def _enumerate_tree(self, root_tree_sha: str) -> dict[str, _TreeEntry]:
        recursive = self._api.get_json(
            _REPOSITORY_API_PATH + "/git/trees/"
            + quote(root_tree_sha, safe="") + "?recursive=1"
        )
        self._validate_tree_response_identity(recursive, root_tree_sha)
        truncated = recursive.get("truncated")
        if type(truncated) is not bool:
            raise TreeValidationError("GitHub recursive tree response has no boolean truncated flag")
        if truncated:
            # The recursive response is discarded in full; fallback starts at the pinned root tree.
            return self._enumerate_nonrecursive(root_tree_sha)
        raw_entries = recursive.get("tree")
        if not isinstance(raw_entries, list):
            raise TreeValidationError("GitHub recursive tree response has no tree entry list")
        if len(raw_entries) > self.config.max_tree_entries:
            raise ResourceLimitError("Git tree entry limit exceeded")
        entries: dict[str, _TreeEntry] = {}
        for raw in raw_entries:
            entry = self._parse_tree_entry(raw, recursive=True)
            if entry.path in entries:
                raise TreeValidationError("Duplicate Git tree path: " + entry.path)
            entries[entry.path] = entry
        self._validate_parent_directories(entries)
        return entries

    def _enumerate_nonrecursive(self, root_tree_sha: str) -> dict[str, _TreeEntry]:
        entries: dict[str, _TreeEntry] = {}

        def walk(tree_sha: str, prefix: str, ancestors: frozenset[str], depth: int) -> None:
            if depth > self.config.max_tree_depth:
                raise ResourceLimitError("Git tree traversal depth limit exceeded")
            if tree_sha in ancestors:
                raise TreeValidationError("Cycle detected in Git tree object traversal")
            response = self._api.get_json(
                _REPOSITORY_API_PATH + "/git/trees/"
                + quote(tree_sha, safe="")
            )
            self._validate_tree_response_identity(response, tree_sha)
            truncated = response.get("truncated")
            if type(truncated) is not bool:
                raise TreeValidationError("GitHub non-recursive tree response has no boolean truncated flag")
            if truncated:
                raise IncompleteTreeError(
                    "A non-recursive Git tree response was truncated; no complete fallback exists"
                )
            raw_entries = response.get("tree")
            if not isinstance(raw_entries, list):
                raise TreeValidationError("GitHub non-recursive tree response has no tree entry list")
            next_ancestors = ancestors | {tree_sha}
            for raw in raw_entries:
                child = self._parse_tree_entry(raw, recursive=False)
                path = prefix + "/" + child.path if prefix else child.path
                entry = _TreeEntry(path, child.mode, child.object_type, child.sha, child.size)
                if path in entries:
                    raise TreeValidationError("Duplicate Git tree path: " + path)
                entries[path] = entry
                if len(entries) > self.config.max_tree_entries:
                    raise ResourceLimitError("Git tree entry limit exceeded")
                if entry.object_type == "tree" and self._is_selected_source_area(path):
                    # Outside the approved source roots, whole trees are irrelevant.
                    # Every discovered content/data/pages subtree is still traversed.
                    walk(entry.sha, path, next_ancestors, depth + 1)

        walk(root_tree_sha, "", frozenset(), 0)
        self._validate_parent_directories(entries)
        return entries

    @staticmethod
    def _validate_tree_response_identity(response: dict, requested_sha: str) -> None:
        if response.get("sha") != requested_sha:
            raise TreeValidationError("GitHub tree response SHA does not match the requested tree object")

    def _parse_tree_entry(self, raw, *, recursive: bool) -> _TreeEntry:
        if not isinstance(raw, dict):
            raise TreeValidationError("GitHub tree entry must be an object")
        path = raw.get("path")
        if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
            raise TreeValidationError("Git tree entry has an invalid path")
        parts = path.split("/")
        if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise TreeValidationError("Git tree entry has an unsafe path")
        if len(parts) > self.config.max_tree_depth:
            raise ResourceLimitError("Git tree path depth limit exceeded")
        if not recursive and "/" in path:
            raise TreeValidationError("Non-recursive Git tree entry contains a nested path")

        mode = raw.get("mode")
        object_type = raw.get("type")
        expected_types = {
            "040000": "tree",
            "40000": "tree",
            "100644": "blob",
            "100755": "blob",
            "120000": "blob",
            "160000": "commit",
        }
        if mode not in expected_types or object_type != expected_types[mode]:
            raise TreeValidationError("Unsupported or inconsistent Git object mode/type")
        object_sha = self._validate_sha(raw.get("sha"), "tree entry object")
        size = raw.get("size")
        if size is not None and (type(size) is not int or size < 0):
            raise TreeValidationError("Git tree entry has an invalid size")
        return _TreeEntry(path, mode, object_type, object_sha, size)

    @staticmethod
    def _validate_parent_directories(entries: Mapping[str, _TreeEntry]) -> None:
        for path in entries:
            parts = path.split("/")
            for index in range(1, len(parts)):
                parent = "/".join(parts[:index])
                parent_entry = entries.get(parent)
                if parent_entry is None or parent_entry.object_type != "tree":
                    raise IncompleteTreeError(
                        "Git tree inventory is missing a parent directory entry: " + parent
                    )

    @staticmethod
    def _is_selected_source_area(path: str) -> bool:
        """Tree prefixes necessary for dynamic source discovery and route checks.

        The three discovery roots are open-ended; their collection/dictionary/route
        names must never become a fixed allowlist. src/lib has exact filenames.
        """
        return (
            path in {"src", "src/content", "src/data", "src/pages", "src/lib"}
            or path.startswith(("src/content/", "src/data/", "src/pages/"))
        )

    def _select_files(self, entries: Mapping[str, _TreeEntry]) -> dict[str, _TreeEntry]:
        selected: dict[str, _TreeEntry] = {}
        route_drift = []

        for path in sorted(entries):
            entry = entries[path]

            if self._is_selected_source_area(path):
                # Reject directory replacements and unsupported objects anywhere
                # in a discovery subtree, not merely selected .md/.yaml/.astro files.
                # A Gitlink/symlink can otherwise hide an entire source collection.
                if path in {"src", "src/content", "src/data", "src/pages", "src/lib"}:
                    if entry.object_type != "tree":
                        raise TreeValidationError(
                            "Unsupported Git object replaces source directory: " + path
                        )
                if entry.object_type == "blob" and entry.mode not in _REGULAR_BLOB_MODES:
                    raise TreeValidationError(
                        "Unsupported Git symlink within source tree: " + path
                    )
                if entry.object_type == "commit":
                    raise TreeValidationError(
                        "Unsupported Git submodule within source tree: " + path
                    )

            if entry.object_type == "tree":
                continue

            if path.startswith("src/pages/"):
                if "%" in path:
                    raise TreeValidationError("Selected route-source path contains a disallowed percent character")
                if entry.mode not in _REGULAR_BLOB_MODES or entry.object_type != "blob":
                    raise TreeValidationError("Symlink or submodule in selected route source: " + path)
                if path.endswith(".d.ts") or not path.endswith((".astro", ".ts")):
                    route_drift.append(path)
                    continue
                selected[path] = entry
                continue

            is_content_markdown = (
                path.startswith("src/content/")
                and path.rsplit("/", 1)[-1].lower().endswith(".md")
            )
            is_dictionary = (
                path.startswith("src/data/")
                and path.rsplit("/", 1)[-1].lower().endswith((".yaml", ".yml"))
            )
            is_required = path in _REQUIRED_FILES
            is_optional = path in _OPTIONAL_FILES
            if not (is_content_markdown or is_dictionary or is_required or is_optional):
                continue
            if "%" in path:
                raise TreeValidationError("Selected source path contains a disallowed percent character")
            if entry.object_type != "blob" or entry.mode not in _REGULAR_BLOB_MODES:
                raise TreeValidationError("Symlink or submodule in selected source path: " + path)
            selected[path] = entry

        if route_drift:
            raise RouteSourceDriftError(tuple(sorted(route_drift)))
        missing = sorted(_REQUIRED_FILES - selected.keys())
        if missing:
            raise TreeValidationError(
                "Pinned site tree is missing required source file(s): " + ", ".join(missing)
            )
        return selected

    def _decode_and_verify_blob(self, blob: dict, entry: _TreeEntry) -> bytes:
        if blob.get("sha") != entry.sha:
            raise BlobIntegrityError("GitHub blob response SHA does not match the pinned tree: " + entry.path)
        if blob.get("encoding") != "base64":
            raise BlobIntegrityError("GitHub blob response is not base64 encoded: " + entry.path)
        encoded = blob.get("content")
        if not isinstance(encoded, str):
            raise BlobIntegrityError("GitHub blob response has no content: " + entry.path)
        compact = _BASE64_WHITESPACE_RE.sub("", encoded)
        try:
            compact.encode("ascii")
            content = base64.b64decode(compact, validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError):
            raise BlobIntegrityError("GitHub blob content has invalid base64 encoding: " + entry.path) from None
        if base64.b64encode(content).decode("ascii") != compact:
            raise BlobIntegrityError("GitHub blob content is not canonical base64: " + entry.path)

        declared_size = blob.get("size")
        if type(declared_size) is not int or declared_size < 0:
            raise BlobIntegrityError("GitHub blob response has an invalid size: " + entry.path)
        if entry.size is not None and declared_size != entry.size:
            raise BlobIntegrityError("GitHub blob size disagrees with the pinned tree: " + entry.path)
        if declared_size > self.config.max_file_bytes or len(content) > self.config.max_file_bytes:
            raise ResourceLimitError("Selected file size limit exceeded: " + entry.path)
        if len(content) != declared_size:
            raise BlobIntegrityError("GitHub blob byte count does not match its declared size: " + entry.path)
        if self._git_blob_sha1(content) != entry.sha:
            raise BlobIntegrityError("Canonical Git blob SHA-1 does not match the pinned tree: " + entry.path)
        return content

    @staticmethod
    def _git_blob_sha1(content: bytes) -> str:
        header = b"blob " + str(len(content)).encode("ascii") + b"\0"
        return sha1(header + content).hexdigest()

    @staticmethod
    def _validate_sha(value, label: str) -> str:
        if not isinstance(value, str) or _SHA1_RE.fullmatch(value) is None:
            raise UnsupportedGitObjectFormatError(
                "Expected a canonical SHA-1 " + label + " under the configured object format"
            )
        return value
