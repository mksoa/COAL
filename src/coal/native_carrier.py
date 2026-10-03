"""COAL Git-native NEXT-001 carrier object preparation. SOURCE-ONLY; NOT an active custodian.

Object POSTs are one-shot and never write any ref or COAL main. A separately
injected read transport verifies the complete exact Git object binding.
Neither transport establishes H0/M0, trust separation, W038, or issuer identity.
"""
from __future__ import annotations

import base64
import json
import re
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

from .carrier import (CARRIER_PATH, COAL_REPO, ORIGINAL_PREACT, CarrierMismatch, CarrierPlan,
                      NativeCarrierObservation, plan_carrier, verify_native_carrier)
from .github_adapter import API, HttpFn, CreateNotActivated, _headers, _resp, urllib_http
from .identity import is_sha1_hex
from .models import TransportResponse, utc_now
from .receipts import Receipt, build_receipt

# The original six GLOW R12 operations, not six new attempt identities.
OPERATIONS = frozenset("GLOW-V2-T03-NEXT001:" + p + ":001" for p in (
    "BRANCH", "ADD_TEST_ONLY", "VERIFY_LOCAL", "COMMIT_CANDIDATE",
    "PUBLISH_BRANCH", "OPEN_PR",
))
COMMIT_PREFIX = "COAL NEXT-001 carrier v1: "


def _exact(plan: CarrierPlan) -> None:
    if not isinstance(plan, CarrierPlan) or plan.identity.repository != COAL_REPO:
        raise CarrierMismatch("not an exact COAL carrier plan")
    if plan.binding.operation_id not in OPERATIONS:
        raise CarrierMismatch("operation outside frozen six R12 IDs")
    if plan.identity.subject != "NEXT-001" or plan.identity.epoch != ORIGINAL_PREACT:
        raise CarrierMismatch("subject or epoch outside original NEXT-001")
    if plan != plan_carrier(plan.identity, plan.binding, plan.coal_parent):
        raise CarrierMismatch("carrier plan fields have diverged")


def _json(resp: TransportResponse) -> dict:
    if not isinstance(resp, TransportResponse) or not isinstance(resp.body, (bytes, bytearray)):
        raise CarrierMismatch("invalid native response")
    try:
        d = json.loads(resp.body)
    except (UnicodeError, ValueError, TypeError):
        raise CarrierMismatch("unparseable native body") from None
    if not isinstance(d, dict):
        raise CarrierMismatch("native body not object")
    return d


def _receipt(op: str, plan: CarrierPlan, resp: Optional[TransportResponse], error: str = "") -> Receipt:
    return build_receipt(operation=op, native_ref=plan.identity.ref_name,
                         observed_at=utc_now(), http_status=resp.status if resp else None,
                         body=bytes(resp.body) if resp and isinstance(resp.body, (bytes, bytearray)) else None,
                         request_id=resp.request_id if resp else None,
                         reconciliation="UNQUALIFIED_NATIVE_SHAPE", error=error or None)


@dataclass
class CarrierObjectRequest:
    plan: CarrierPlan
    _used: bool = field(default=False, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def claim(self) -> bool:
        with self._lock:
            if self._used:
                return False
            self._used = True
            return True


@dataclass(frozen=True)
class CarrierObjectResult:
    status: str
    commit_sha: Optional[str]
    post_receipts: Tuple[Receipt, ...]
    read_receipts: Tuple[Receipt, ...]
    # A verified object is not an attempt, ref, independent issuer or W038 witness.
    custody_qualified = False
    attempt_reserved = False
    h0_m0_issued = False


class GitHubCarrierObjectWrite:
    def __init__(self, *, transport: Optional[HttpFn], token_provider: Optional[Callable[[], str]],
                 repository: str = COAL_REPO, timeout: float = 15.0):
        if repository != COAL_REPO or transport is None or token_provider is None or transport is urllib_http:
            raise CreateNotActivated("fixed COAL repository and externally injected writer required")
        self.repository, self._http, self._token, self._timeout = repository, transport, token_provider, timeout

    def post(self, kind: str, data: dict) -> TransportResponse:
        if kind not in ("blobs", "trees", "commits"):
            raise CarrierMismatch("outside carrier Git object endpoints")
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return _resp(*self._http("POST", f"{API}/repos/{COAL_REPO}/git/{kind}",
                                 _headers(self._token()), payload, self._timeout))


class GitHubCarrierObjectRead:
    def __init__(self, *, http: HttpFn = urllib_http, token: Optional[str] = None,
                 repository: str = COAL_REPO, timeout: float = 15.0):
        if repository != COAL_REPO:
            raise CarrierMismatch("foreign carrier repository")
        self.repository, self._http, self._token, self._timeout = repository, http, token, timeout

    def get(self, kind: str, sha: str) -> TransportResponse:
        if kind not in ("blobs", "trees", "commits") or not is_sha1_hex(sha):
            raise CarrierMismatch("invalid fixed Git object read")
        return _resp(*self._http("GET", f"{API}/repos/{COAL_REPO}/git/{kind}/{sha}",
                                 _headers(self._token), None, self._timeout))


def prepare_native_carrier_once(request: CarrierObjectRequest,
                                writer: GitHubCarrierObjectWrite,
                                reader: GitHubCarrierObjectRead) -> CarrierObjectResult:
    """At most one blob/tree/commit POST in order, then independent read-only verification.

    Ambiguous ACK stops immediately; no retry, no follow-on Git object POST.
    No Git refs, operational attempt or H0/M0 created by this procedure.
    """
    if not isinstance(request, CarrierObjectRequest):
        raise TypeError("CarrierObjectRequest required")
    plan = request.plan
    _exact(plan)
    if (not isinstance(writer, GitHubCarrierObjectWrite) or
            not isinstance(reader, GitHubCarrierObjectRead) or
            writer.repository != COAL_REPO or reader.repository != COAL_REPO):
        raise CarrierMismatch("fixed separate carrier writer/reader required")
    if not request.claim():
        return CarrierObjectResult("REQUEST_ALREADY_CONSUMED_NO_RETRY", None, (), ())
    posts: list[Receipt] = []
    reads: list[Receipt] = []

    message = COMMIT_PREFIX + plan.identity.digest
    steps = (
        ("blobs", {"content": base64.b64encode(plan.content).decode("ascii"), "encoding": "base64"},
         plan.blob_sha),
        ("trees", {"tree": [{"path": CARRIER_PATH, "mode": "100644",
                             "type": "blob", "sha": plan.blob_sha}]}, plan.tree_sha),
        ("commits", {"message": message, "tree": plan.tree_sha,
                     "parents": [plan.coal_parent]}, None),
    )
    created_commit: Optional[str] = None
    for kind, payload, expected in steps:
        resp = None
        try:
            resp = writer.post(kind, payload)
            posts.append(_receipt("carrier_post_" + kind, plan, resp))
            got = _json(resp)
            if resp.status != 201 or not is_sha1_hex(got.get("sha")):
                return CarrierObjectResult("POST_" + kind.upper() + "_UNKNOWN_STOP", None, tuple(posts), ())
            if expected is not None and got["sha"] != expected:
                return CarrierObjectResult("POST_" + kind.upper() + "_DIVERGENT_STOP", None, tuple(posts), ())
            if kind == "commits":
                created_commit = got["sha"]
        except Exception as exc:
            if resp is None:
                posts.append(_receipt("carrier_post_" + kind, plan, None, type(exc).__name__))
            return CarrierObjectResult("POST_" + kind.upper() + "_UNKNOWN_STOP", None, tuple(posts), ())

    assert created_commit is not None
    observations: dict[str, dict] = {}
    for kind, sha in (("blobs", plan.blob_sha), ("trees", plan.tree_sha), ("commits", created_commit)):
        resp = None
        try:
            resp = reader.get(kind, sha)
            reads.append(_receipt("carrier_read_" + kind, plan, resp))
            obj = _json(resp)
            if resp.status != 200 or obj.get("sha") != sha:
                raise CarrierMismatch("native read HTTP or exact object SHA mismatch")
            observations[kind] = obj
        except Exception as exc:
            if resp is None:
                reads.append(_receipt("carrier_read_" + kind, plan, None, type(exc).__name__))
            return CarrierObjectResult("READ_" + kind.upper() + "_UNKNOWN_STOP", None,
                                       tuple(posts), tuple(reads))
    try:
        blob, tree, commit = (observations[k] for k in ("blobs", "trees", "commits"))
        if blob.get("encoding") != "base64" or blob.get("size") != len(plan.content):
            raise CarrierMismatch("blob encoding or size mismatch")
        encoded = blob["content"]
        if not isinstance(encoded, str):
            raise CarrierMismatch("blob content not base64 string")
        raw = base64.b64decode(re.sub(r"\s+", "", encoded), validate=True)
        if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
            raise CarrierMismatch("tree incomplete or invalid")
        entries = tuple((e["path"], e["mode"], e["type"], e["sha"]) for e in tree["tree"])
        if not isinstance(commit.get("parents"), list) or commit.get("message") != message:
            raise CarrierMismatch("commit parent/message invalid")
        parents = tuple(x["sha"] for x in commit["parents"])
        observation = NativeCarrierObservation(created_commit, commit["tree"]["sha"],
                                               parents, entries, raw)
        verify_native_carrier(plan, observation)
    except (KeyError, ValueError, TypeError, CarrierMismatch):
        return CarrierObjectResult("NATIVE_SHAPE_DIVERGENT_STOP", None, tuple(posts), tuple(reads))
    return CarrierObjectResult("NATIVE_OBJECT_SHAPE_VERIFIED_NOT_CUSTODY", created_commit,
                               tuple(posts), tuple(reads))
