"""W038 offline monotonic-frontier verifier. Passing it does NOT install or prove an external witness."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

from .identity import is_sha256_hex

_KEYS = {"epoch", "frontier", "digest"}


class CheckpointError(ValueError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    epoch: str
    frontier: int
    digest: str

    @classmethod
    def from_dict(cls, d: Any) -> "Checkpoint":
        if not isinstance(d, Mapping) or set(d) != _KEYS:
            raise CheckpointError("checkpoint must have exactly epoch, frontier, digest")
        e, f, g = d["epoch"], d["frontier"], d["digest"]
        if not isinstance(e, str) or not e or e != e.strip():
            raise CheckpointError("invalid epoch")
        if isinstance(f, bool) or not isinstance(f, int) or f < 0:
            raise CheckpointError("frontier must be a non-negative integer")
        if not is_sha256_hex(g):
            raise CheckpointError("digest must be 64 lowercase hex chars")
        return cls(e, f, g)

    def to_dict(self) -> dict:
        return {"epoch": self.epoch, "frontier": self.frontier, "digest": self.digest}


@dataclass(frozen=True)
class CheckpointVerdict:
    ok: bool
    reason: str
    witness_installed: ClassVar[bool] = False
    w038_qualified: ClassVar[bool] = False


def verify_frontier(previous: Any, candidate: Any) -> CheckpointVerdict:
    try:
        prev = previous if isinstance(previous, Checkpoint) else Checkpoint.from_dict(previous)
        cand = candidate if isinstance(candidate, Checkpoint) else Checkpoint.from_dict(candidate)
    except CheckpointError as e:
        return CheckpointVerdict(False, "STRUCTURAL_INVALID: " + str(e))
    if cand.epoch != prev.epoch:
        return CheckpointVerdict(False, "EPOCH_MISMATCH")
    if cand.frontier < prev.frontier:
        return CheckpointVerdict(False, "FRONTIER_REGRESSION")
    if cand.frontier == prev.frontier:
        if cand.digest != prev.digest:
            return CheckpointVerdict(False, "SAME_FRONTIER_DIGEST_CONFLICT")
        return CheckpointVerdict(True, "IDEMPOTENT_SAME_FRONTIER")
    return CheckpointVerdict(True, "FRONTIER_ADVANCED")
