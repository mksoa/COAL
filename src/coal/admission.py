"""An inert fail-closed seam for externally durable, one-use admission.

The injected admission port MUST be separately qualified: a supplied positive
decision is never, on its own, native proof, W038, H0, M0, or issuer independence.
No live transport or credential is installed in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .carrier import CarrierMismatch, CarrierPlan, NativeCarrierObservation, verify_native_carrier
from .identity import is_sha256_hex
from .models import ReserveOutcome
from .reservation import ReservationRequest, ReservationResult, reserve_exact_attempt


@dataclass(frozen=True)
class AdmissionDecision:
    status: str  # FIRST_CONSUMED, ALREADY_CONSUMED, UNKNOWN, REJECTED
    identity_digest: str
    carrier_sha: str
    receipt_id: str = ""
    original_body_sha256: str = ""
    # No authority or custody bit: a caller must separately verify original native evidence.


class OneUseAdmissionPort(Protocol):
    def consume_once(self, identity_digest: str, carrier_sha: str) -> AdmissionDecision: ...


@dataclass(frozen=True)
class GuardedResult:
    disposition: str
    admission: Optional[AdmissionDecision]
    reservation: Optional[ReservationResult]
    custody_qualified = False
    h0_m0_issued = False


def reserve_with_admission(plan: CarrierPlan, observed: NativeCarrierObservation,
                           request: ReservationRequest, create_port,
                           admission_port: OneUseAdmissionPort) -> GuardedResult:
    """One admission call max, then one original ref POST max. Never retries either.

    The caller MUST authenticate native carrier readback and separately qualify the
    external admission port. A second fresh request cannot bypass a truly durable port.
    """
    if not isinstance(request, ReservationRequest) or not isinstance(plan, CarrierPlan):
        raise TypeError("exact typed reservation/carrier required")
    if request.identity != plan.identity:
        raise CarrierMismatch("reservation identity differs from carrier")
    verified_sha = verify_native_carrier(plan, observed)
    if request.target_sha != verified_sha:
        raise CarrierMismatch("ref must target the observed COAL-local carrier, not GLOW SHA")
    if not callable(getattr(admission_port, "consume_once", None)):
        raise TypeError("missing independently controlled admission port")
    if not request._claim():
        return GuardedResult("REQUEST_ALREADY_CONSUMED_NO_RETRY", None, None)
    try:
        decision = admission_port.consume_once(request.identity.digest, verified_sha)
    except Exception:
        return GuardedResult("ADMISSION_UNKNOWN_READ_ONLY", None, None)
    if not isinstance(decision, AdmissionDecision):
        return GuardedResult("ADMISSION_UNKNOWN_READ_ONLY", None, None)
    if decision.identity_digest != request.identity.digest or decision.carrier_sha != verified_sha:
        return GuardedResult("ADMISSION_DIVERGENT_STOP", decision, None)
    if decision.status != "FIRST_CONSUMED":
        status = ("ALREADY_CONSUMED_STOP" if decision.status == "ALREADY_CONSUMED"
                  else "ADMISSION_UNKNOWN_READ_ONLY")
        return GuardedResult(status, decision, None)
    if not decision.receipt_id or not is_sha256_hex(decision.original_body_sha256):
        return GuardedResult("ADMISSION_UNVERIFIED_STOP", decision, None)
    # The outer request has been permanently consumed. The inner object is
    # private to this single approved effect and reuses V0.3 native receipt logic.
    inner = ReservationRequest(request.identity, verified_sha)
    result = reserve_exact_attempt(inner, create_port)
    return GuardedResult("ATTEMPTED_" + result.outcome.value, decision, result)
