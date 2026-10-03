"""Shared value types."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class ReserveOutcome(str, enum.Enum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class ReadStatus(str, enum.Enum):
    PRESENT_MATCH = "PRESENT_MATCH"
    ABSENT_OBSERVED = "ABSENT_OBSERVED"
    DIVERGENT = "DIVERGENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TransportResponse:
    """Authorization headers are never part of this type."""
    status: int
    body: bytes
    request_id: Optional[str] = None
    issuer: Optional[str] = None  # only if independently available


class TransportError(Exception):
    pass


class TransportTimeout(TransportError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
