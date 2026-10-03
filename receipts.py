"""Tamper-evident receipts preserving original response data. Never stores credentials."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Optional, Tuple

from .identity import canonical_json, sha256_hex

_SECRET_RE = re.compile(
    rb"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[osu]_[A-Za-z0-9]{20,}"
    rb"|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:authorization\s*:)|(?i:bearer\s+[A-Za-z0-9._-]{12,}))")
_FIELDS = ("operation", "request_id", "http_status", "body_b64", "body_sha256", "body_withheld",
           "native_ref", "observed_at", "issuer", "reconciliation", "error", "receipt_digest")


class ReceiptError(ValueError):
    pass


@dataclass(frozen=True)
class Receipt:
    operation: str
    request_id: Optional[str]
    http_status: Optional[int]
    body_b64: Optional[str]
    body_sha256: Optional[str]
    body_withheld: bool
    native_ref: str
    observed_at: str
    issuer: Optional[str]
    reconciliation: Optional[str]
    error: Optional[str]
    receipt_digest: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Receipt":
        if not isinstance(d, Mapping) or set(d) != set(_FIELDS):
            raise ReceiptError("receipt fields mismatch")
        return cls(**{k: d[k] for k in _FIELDS})


def _digest(fields: Mapping[str, Any]) -> str:
    body = {k: v for k, v in fields.items() if k != "receipt_digest"}
    return sha256_hex(canonical_json(body))


def build_receipt(*, operation: str, native_ref: str, observed_at: str,
                  http_status: Optional[int] = None, body: Optional[bytes] = None,
                  request_id: Optional[str] = None, issuer: Optional[str] = None,
                  reconciliation: Optional[str] = None, error: Optional[str] = None) -> Receipt:
    withheld = False
    b64 = sha = None
    if body is not None:
        if _SECRET_RE.search(body):
            withheld = True
            error = (error + ";" if error else "") + "body_withheld_secret_pattern"
        else:
            b64 = base64.b64encode(body).decode("ascii")
            sha = sha256_hex(body)
    f = dict(operation=operation, request_id=request_id, http_status=http_status, body_b64=b64,
             body_sha256=sha, body_withheld=withheld, native_ref=native_ref,
             observed_at=observed_at, issuer=issuer, reconciliation=reconciliation, error=error)
    return Receipt(receipt_digest=_digest(f), **f)


def verify_receipt(r: Receipt) -> Tuple[bool, str]:
    d = r.to_dict()
    if _digest(d) != r.receipt_digest:
        return False, "receipt_digest_mismatch"
    if r.body_b64 is not None:
        try:
            raw = base64.b64decode(r.body_b64, validate=True)
        except Exception:
            return False, "body_not_base64"
        if sha256_hex(raw) != r.body_sha256:
            return False, "body_sha256_mismatch"
    elif r.body_sha256 is not None:
        return False, "sha_without_body"
    return True, "ok"


def body_bytes(r: Receipt) -> Optional[bytes]:
    return None if r.body_b64 is None else base64.b64decode(r.body_b64)
