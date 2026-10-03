"""Fixed NEXT-001 COAL-native, original-operation-keyed admission source adapter.

NOT installed/activated; no credential, trigger, CLI or runtime caller is supplied.
The first-create Git ref is a distributed admission primitive only while its
administrator does not move/delete refs. A separate W038 witness is still required.
"""
from __future__ import annotations

import json
import threading
from typing import Callable, Optional

from .admission import AdmissionDecision, OneUseAdmissionPort
from .carrier import (COAL_REPO, ORIGINAL_PREACT, CarrierPlan, CarrierMismatch,
                      NativeCarrierObservation, verify_native_carrier)
from .github_adapter import API, CreateNotActivated, HttpFn, _headers, _resp, urllib_http
from .identity import canonical_json, is_sha1_hex, sha256_hex
from .models import TransportResponse, utc_now
from .native_carrier import OPERATIONS, _exact
from .receipts import Receipt, build_receipt
from .reservation import parse_ref_body

ADMISSION_DOMAIN = "COAL/NEXT001/original-operation-admission/v1"
ADMISSION_PREFIX = "refs/heads/coal/admissions/"


def original_operation_admission_ref(operation_id: str) -> str:
    """Key excludes source successor/carrier digest: changing them cannot mint a new key."""
    if not isinstance(operation_id, str) or operation_id not in OPERATIONS:
        raise CarrierMismatch("not one of the original six NEXT-001 effect IDs")
    d = {"domain": ADMISSION_DOMAIN, "repository": COAL_REPO,
         "subject": "NEXT-001", "epoch": ORIGINAL_PREACT, "operation_id": operation_id}
    return ADMISSION_PREFIX + sha256_hex(canonical_json(d))


def _receipt(kind: str, ref: str, resp: Optional[TransportResponse],
             error: Optional[str] = None) -> Receipt:
    return build_receipt(operation=kind, native_ref=ref, observed_at=utc_now(),
                         http_status=resp.status if resp else None,
                         body=bytes(resp.body) if resp and isinstance(resp.body, (bytes, bytearray)) else None,
                         request_id=resp.request_id if resp else None,
                         issuer=resp.issuer if resp else None,
                         reconciliation="UNQUALIFIED_CUSTODY_NEEDS_W038", error=error)


class NativeOperationAdmission(OneUseAdmissionPort):
    """Injected one-shot admission source port. No independent authority is minted here.

    The original HTTP 201 body is retained as a Receipt; a separate native GET
    must match. The same operation always maps to the same CREATE-ABSENT ref.
    """
    custody_qualified = False
    w038_qualified = False
    h0_m0_issued = False

    def __init__(self, plan: CarrierPlan, observation: NativeCarrierObservation, *,
                 transport: Optional[HttpFn], token_provider: Optional[Callable[[], str]],
                 read_http: Optional[HttpFn], read_token: Optional[str] = None,
                 timeout: float = 15.0):
        _exact(plan)
        carrier_sha = verify_native_carrier(plan, observation)
        if transport is None or transport is urllib_http or token_provider is None or read_http is None:
            raise CreateNotActivated("external fixed-purpose custodian write/read injectors required")
        self.repository = COAL_REPO
        self.identity_digest = plan.identity.digest
        self.operation_id = plan.binding.operation_id
        self.carrier_sha = carrier_sha
        self.admission_ref = original_operation_admission_ref(self.operation_id)
        self._transport = transport
        self._token = token_provider
        self._read_http = read_http
        self._read_token = read_token
        self._timeout = timeout
        self._lock = threading.Lock()
        self._used = False
        self.original_create_receipt: Optional[Receipt] = None
        self.readback_receipt: Optional[Receipt] = None

    def _answer(self, status: str) -> AdmissionDecision:
        receipt = self.original_create_receipt
        return AdmissionDecision(
            status, self.identity_digest, self.carrier_sha,
            receipt_id=receipt.receipt_digest if receipt else "",
            original_body_sha256=receipt.body_sha256 or "" if receipt else "",
        )

    def consume_once(self, identity_digest: str, carrier_sha: str) -> AdmissionDecision:
        # Bad caller must not consume the operation. Identical request object
        # cannot reattempt even after unknown native ACK.
        if identity_digest != self.identity_digest or carrier_sha != self.carrier_sha:
            return self._answer("REJECTED")
        with self._lock:
            if self._used:
                return self._answer("ALREADY_CONSUMED")
            self._used = True
        body = json.dumps({"ref": self.admission_ref, "sha": self.carrier_sha},
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        response = None
        try:
            response = _resp(*self._transport(
                "POST", f"{API}/repos/{COAL_REPO}/git/refs",
                _headers(self._token()), body, self._timeout))
            self.original_create_receipt = _receipt("native_admission_create", self.admission_ref, response)
        except Exception as exc:
            self.original_create_receipt = _receipt("native_admission_create", self.admission_ref,
                                                    None, type(exc).__name__)
            return self._answer("UNKNOWN")
        if (response.status != 201 or
                parse_ref_body(response.body) != (self.admission_ref, self.carrier_sha) or
                self.original_create_receipt.body_sha256 is None):
            # 422 is not collision/ownership proof. Even matching future GET is not
            # evidence that this caller created a reference. No second POST.
            return self._answer("UNKNOWN")
        try:
            read = _resp(*self._read_http(
                "GET", f"{API}/repos/{COAL_REPO}/git/ref/{self.admission_ref[len('refs/') :]}",
                _headers(self._read_token), None, self._timeout))
            self.readback_receipt = _receipt("native_admission_read", self.admission_ref, read)
            if read.status != 200 or parse_ref_body(read.body) != (self.admission_ref, self.carrier_sha):
                return self._answer("UNKNOWN")
        except Exception as exc:
            self.readback_receipt = _receipt("native_admission_read", self.admission_ref,
                                             None, type(exc).__name__)
            return self._answer("UNKNOWN")
        # A bounded original ACK + exact readback only, not issuer/auth/W038.
        return self._answer("FIRST_CONSUMED")
