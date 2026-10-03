"""Conditional reservation. At most one native CREATE per request; no retry; no authority claims."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Callable, ClassVar, Optional, Tuple

from .identity import AttemptIdentity, is_sha1_hex
from .models import ReserveOutcome as O, TransportResponse, utc_now
from .receipts import Receipt, build_receipt


class ReservationRequest:
    """Single-use. Carries no caller-supplied authority flag."""

    def __init__(self, identity: AttemptIdentity, target_sha: str):
        if not isinstance(identity, AttemptIdentity):
            raise TypeError("identity must be AttemptIdentity")
        if not is_sha1_hex(target_sha):
            raise ValueError("target_sha must be 40 lowercase hex chars")
        self.identity = identity
        self.target_sha = target_sha
        self._lock = threading.Lock()
        self._attempted = False

    def _claim(self) -> bool:
        with self._lock:
            if self._attempted:
                return False
            self._attempted = True
            return True


@dataclass(frozen=True)
class ReservationResult:
    outcome: O
    reason: str
    receipt: Optional[Receipt]
    # Fixed by design: this function never establishes these.
    ownership_established: ClassVar[bool] = False
    h0_m0_issued: ClassVar[bool] = False
    credential_qualified: ClassVar[bool] = False


def parse_ref_body(body: bytes) -> Optional[Tuple[str, str]]:
    try:
        d = json.loads(body.decode("utf-8"))
        return d["ref"], d["object"]["sha"]
    except Exception:
        return None


def _message(body: bytes) -> str:
    try:
        return str(json.loads(body.decode("utf-8")).get("message", "")).lower()
    except Exception:
        return ""


def _interpret(resp: TransportResponse, ref: str, sha: str) -> Tuple[O, str]:
    s = resp.status
    if s == 201:
        if parse_ref_body(resp.body) == (ref, sha):
            return O.CREATED, "create_201_body_matches_request"
        return O.CONFLICT, "create_201_body_divergent"
    if s == 422:
        # Native 422 is not a qualified proof of an existing exact reservation:
        # other validation failures/rate limiting are possible. Never retry POST.
        return O.CONFLICT, "http_422_read_only_reconciliation_required"
    if s == 409:
        return O.CONFLICT, "http_409"
    if s in (408, 429):
        return O.UNKNOWN, f"http_{s}_no_retry"
    if 400 <= s < 500:
        return O.REJECTED, f"http_{s}"
    return O.UNKNOWN, f"http_{s}_unclassified"


def reserve_exact_attempt(request: ReservationRequest, port, *,
                          clock: Callable[[], str] = utc_now) -> ReservationResult:
    """Perform at most ONE native create via `port`. Performs no pre-check (a GET 404 proves nothing)."""
    if not isinstance(request, ReservationRequest):
        raise TypeError("request must be ReservationRequest")
    if not callable(getattr(port, "create_ref", None)):
        raise TypeError("port must provide create_ref")
    ident = request.identity
    ref = ident.ref_name
    port_repo = getattr(port, "repository", None)
    if port_repo is not None and port_repo.lower() != ident.repository.lower():
        return ReservationResult(O.REJECTED, "port_repository_mismatch", None)
    if not request._claim():
        return ReservationResult(O.REJECTED, "attempt_already_consumed_reconcile_instead", None)
    observed = clock()
    try:
        resp = port.create_ref(ref, request.target_sha)
    except Exception as exc:  # timeout / lost ACK / anything: outcome unknown, never retried
        rc = build_receipt(operation="create", native_ref=ref, observed_at=observed,
                           reconciliation="UNRECONCILED", error=type(exc).__name__)
        return ReservationResult(O.UNKNOWN, "transport_failure_" + type(exc).__name__, rc)
    if not isinstance(resp, TransportResponse) or not isinstance(resp.status, int) \
            or not isinstance(resp.body, (bytes, bytearray)):
        rc = build_receipt(operation="create", native_ref=ref, observed_at=observed,
                           reconciliation="UNRECONCILED", error="malformed_transport_response")
        return ReservationResult(O.UNKNOWN, "malformed_transport_response", rc)
    outcome, reason = _interpret(resp, ref, request.target_sha)
    rc = build_receipt(operation="create", native_ref=ref, observed_at=observed,
                       http_status=resp.status, body=bytes(resp.body), request_id=resp.request_id,
                       issuer=resp.issuer, reconciliation="UNRECONCILED")
    return ReservationResult(outcome, reason, rc)
