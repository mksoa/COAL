"""Deterministic attempt identity (canonical JSON + SHA-256, domain separated)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

DOMAIN = "COAL/attempt-identity/v1"
REF_NAMESPACE = "refs/coal/attempts/"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class IdentityError(ValueError):
    pass


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_sha1_hex(v: Any) -> bool:
    return isinstance(v, str) and bool(_HEX40.match(v))


def is_sha256_hex(v: Any) -> bool:
    return isinstance(v, str) and bool(_HEX64.match(v))


def _check(name: str, value: Any) -> None:
    if not isinstance(value, str):
        raise IdentityError(f"{name} must be a string")
    if not value or len(value) > 256:
        raise IdentityError(f"{name} must be 1..256 characters")
    if unicodedata.normalize("NFC", value) != value:
        raise IdentityError(f"{name} must be NFC-normalized")
    for ch in value:
        if ch.isspace() or unicodedata.category(ch).startswith("C"):
            raise IdentityError(f"{name} must not contain whitespace/control characters")


@dataclass(frozen=True)
class AttemptIdentity:
    repository: str
    subject: str
    epoch: str
    operation_id: str
    source_binding: str

    def __post_init__(self) -> None:
        for n in ("repository", "subject", "epoch", "operation_id", "source_binding"):
            _check(n, getattr(self, n))
        if not _REPO_RE.match(self.repository):
            raise IdentityError("repository must look like owner/name")

    def payload(self) -> dict:
        return {"domain": DOMAIN, "repository": self.repository, "subject": self.subject,
                "epoch": self.epoch, "operation_id": self.operation_id,
                "source_binding": self.source_binding}

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json(self.payload()))

    @property
    def ref_name(self) -> str:
        return REF_NAMESPACE + self.digest

    def to_dict(self) -> dict:
        d = self.payload()
        del d["domain"]
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "AttemptIdentity":
        keys = {"repository", "subject", "epoch", "operation_id", "source_binding"}
        if not isinstance(d, Mapping) or set(d) != keys:
            raise IdentityError("identity must have exactly: " + ", ".join(sorted(keys)))
        return cls(**{k: d[k] for k in keys})
