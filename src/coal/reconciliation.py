"""Read-only reconciliation. A compatible readback is NOT proof of who created the reservation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, ClassVar, Optional

from .identity import AttemptIdentity, is_sha1_hex
from .models import ReadStatus as R, TransportResponse, utc_now
from .receipts import Receipt, build_receipt
from .reservation import parse_ref_body


@dataclass(frozen=True)
class ReadbackResult:
    status: R
    reason: str
    observed_sha: Optional[str]
    receipt: Optional[Receipt]
    causal_authorship_proven: ClassVar[bool] = False
    absence_is_future_guarantee: ClassVar[bool] = False


def read_exact_attempt(identity: AttemptIdentity, port, *, expected_sha: str,
                       clock: Callable[[], str] = utc_now) -> ReadbackResult:
    if not isinstance(identity, AttemptIdentity):
        raise TypeError("identity must be AttemptIdentity")
    if not is_sha1_hex(expected_sha):
        raise ValueError("expected_sha must be 40 lowercase hex chars")
    if not callable(getattr(port, "get_ref", None)):
        raise TypeError("port must provide get_ref")
    ref = identity.ref_name
    port_repo = getattr(port, "repository", None)
    if port_repo is not None and port_repo.lower() != identity.repository.lower():
        return ReadbackResult(R.UNKNOWN, "port_repository_mismatch", None, None)
    observed = clock()
    try:
        resp = port.get_ref(ref)
    except Exception as exc:
        rc = build_receipt(operation="read", native_ref=ref, observed_at=observed,
                           reconciliation="UNKNOWN", error=type(exc).__name__)
        return ReadbackResult(R.UNKNOWN, "read_failure_" + type(exc).__name__, None, rc)
    if not isinstance(resp, TransportResponse):
        rc = build_receipt(operation="read", native_ref=ref, observed_at=observed,
                           reconciliation="UNKNOWN", error="malformed_transport_response")
        return ReadbackResult(R.UNKNOWN, "malformed_transport_response", None, rc)

    def done(status, reason, sha=None):
        rc = build_receipt(operation="read", native_ref=ref, observed_at=observed,
                           http_status=resp.status, body=bytes(resp.body),
                           request_id=resp.request_id, issuer=resp.issuer,
                           reconciliation=status.value)
        return ReadbackResult(status, reason, sha, rc)

    if resp.status == 404:
        return done(R.ABSENT_OBSERVED, "absent_at_observation_time")
    if resp.status != 200:
        return done(R.UNKNOWN, f"http_{resp.status}")
    parsed = parse_ref_body(resp.body)
    if parsed is None:
        return done(R.UNKNOWN, "unparsable_body")
    got_ref, got_sha = parsed
    if got_ref != ref:
        return done(R.DIVERGENT, "ref_name_mismatch", got_sha)
    if got_sha != expected_sha:
        return done(R.DIVERGENT, "sha_mismatch", got_sha)
    return done(R.PRESENT_MATCH, "present_and_matches_expected_binding", got_sha)
