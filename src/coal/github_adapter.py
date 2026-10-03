"""GitHub REST adapters for Git refs.

GitHubReadAdapter  - GET only; usable read-only.
GitHubCreateAdapter - prepared port only. It cannot be built without an explicitly injected
transport and token provider from a trusted caller; COAL V0.3 supplies neither, and no CLI
command constructs it. A Git ref is not, by itself, immutable storage or admin-proof CAS.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Callable, Mapping, Optional, Tuple

from .identity import REF_NAMESPACE, is_sha1_hex
from .models import TransportError, TransportResponse, TransportTimeout

API = "https://api.github.com"
# http(method, url, headers, body, timeout) -> (status, response_headers, body_bytes)
HttpFn = Callable[[str, str, Mapping[str, str], Optional[bytes], float], Tuple[int, Mapping[str, str], bytes]]


class CreateNotActivated(RuntimeError):
    pass


def urllib_http(method, url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (https api only)
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except (socket.timeout, TimeoutError) as e:
        raise TransportTimeout(str(type(e).__name__)) from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise TransportTimeout("timeout") from None
        raise TransportError("url_error") from None


def _headers(token: Optional[str]) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
         "User-Agent": "coal-custody/0.3"}
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def _resp(status, headers, body) -> TransportResponse:
    rid = None
    for k, v in (headers or {}).items():
        if k.lower() == "x-github-request-id":
            rid = v
    return TransportResponse(status=status, body=body, request_id=rid, issuer=None)


def _check_ref(ref: str) -> None:
    if not ref.startswith(REF_NAMESPACE) or ".." in ref or len(ref) <= len(REF_NAMESPACE):
        raise ValueError("ref outside COAL candidate namespace")


class GitHubReadAdapter:
    def __init__(self, repository: str, *, token: Optional[str] = None,
                 http: HttpFn = urllib_http, timeout: float = 15.0):
        self.repository = repository
        self._token = token
        self._http = http
        self._timeout = timeout

    def get_ref(self, ref: str) -> TransportResponse:
        _check_ref(ref)
        url = f"{API}/repos/{self.repository}/git/ref/{ref[len('refs/'):]}"
        return _resp(*self._http("GET", url, _headers(self._token), None, self._timeout))


class GitHubCreateAdapter:
    def __init__(self, repository: str, *, transport: Optional[HttpFn],
                 token_provider: Optional[Callable[[], str]], timeout: float = 15.0):
        if transport is None or token_provider is None or transport is urllib_http:
            raise CreateNotActivated(
                "create adapter requires an explicitly injected transport and token provider "
                "from a trusted external caller; COAL V0.3 does not provide one")
        self.repository = repository
        self._http = transport
        self._token_provider = token_provider
        self._timeout = timeout

    def create_ref(self, ref: str, sha: str) -> TransportResponse:
        _check_ref(ref)
        if not is_sha1_hex(sha):
            raise ValueError("invalid sha")
        url = f"{API}/repos/{self.repository}/git/refs"
        body = json.dumps({"ref": ref, "sha": sha}).encode("utf-8")
        return _resp(*self._http("POST", url, _headers(self._token_provider()), body, self._timeout))
