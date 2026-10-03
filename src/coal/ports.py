"""Transport ports. Read and create are separate so read-only use never needs a create capability."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import TransportResponse


@runtime_checkable
class ReadPort(Protocol):
    def get_ref(self, ref: str) -> TransportResponse: ...


@runtime_checkable
class CreatePort(Protocol):
    def create_ref(self, ref: str, sha: str) -> TransportResponse: ...
