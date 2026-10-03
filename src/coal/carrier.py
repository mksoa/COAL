"""NEXT-001 COAL-local native commit carrier, pure preparation and shape verification.

No Git HTTP, token, ref CREATE, H0, or custody authority is implemented here.
A caller must independently authenticate each native Git object observation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Tuple

from .identity import AttemptIdentity, canonical_json, is_sha1_hex, is_sha256_hex

DOMAIN = "COAL/next001-native-carrier/v1"
COAL_REPO = "mksoa/COAL"
GLOW_REPO = "mshigueoka/GLOW"
ORIGINAL_PREACT = "343884f170db11e7a091e1c9b32ead90d3595f66"
TARGET_PATH = "tests/research/test_glow_v2_t03_next001_continuation_sequence.py"
TARGET_BLOB = "916d7ffa20b1713b5e5ef962363b1b718f89a9f8"
CARRIER_PATH = "reservation.json"


class CarrierMismatch(ValueError):
    """A supplied shape is divergent; no attempt may follow."""


def _git_sha(kind: str, data: bytes) -> str:
    raw = kind.encode("ascii") + b" " + str(len(data)).encode("ascii") + b"\x00" + data
    return hashlib.sha1(raw).hexdigest()  # Git object identity, NOT anti-rollback security.


@dataclass(frozen=True)
class FrozenGLOWBinding:
    source_commit: str
    source_tree: str
    source_successor_sha256: str
    operation_id: str
    operation_binding_sha256: str
    original_preact: str = ORIGINAL_PREACT
    repository: str = GLOW_REPO
    target_path: str = TARGET_PATH
    target_blob: str = TARGET_BLOB

    def __post_init__(self):
        for name in ("source_commit", "source_tree", "original_preact", "target_blob"):
            if not is_sha1_hex(getattr(self, name)):
                raise CarrierMismatch(name + " must be an exact lowercase Git SHA")
        for name in ("source_successor_sha256", "operation_binding_sha256"):
            if not is_sha256_hex(getattr(self, name)):
                raise CarrierMismatch(name + " must be SHA-256")
        if (self.repository != GLOW_REPO or self.original_preact != ORIGINAL_PREACT
                or self.target_path != TARGET_PATH or self.target_blob != TARGET_BLOB):
            raise CarrierMismatch("outside frozen NEXT-001 mission")
        if not self.operation_id or any(ch.isspace() for ch in self.operation_id):
            raise CarrierMismatch("invalid operation ID")

    def payload(self) -> dict:
        return {
            "repository": self.repository,
            "original_preact": self.original_preact,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "source_successor_sha256": self.source_successor_sha256,
            "target_path": self.target_path,
            "target_blob": self.target_blob,
            "operation_id": self.operation_id,
            "operation_binding_sha256": self.operation_binding_sha256,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.payload())).hexdigest()


@dataclass(frozen=True)
class CarrierPlan:
    identity: AttemptIdentity
    binding: FrozenGLOWBinding
    coal_parent: str
    content: bytes
    blob_sha: str
    tree_sha: str

    @property
    def expected_tree_entries(self) -> Tuple[Tuple[str, str, str, str], ...]:
        return ((CARRIER_PATH, "100644", "blob", self.blob_sha),)


@dataclass(frozen=True)
class NativeCarrierObservation:
    """Shapes supplied by a separately trusted GET; NOT provenance in themselves."""
    commit_sha: str
    tree_sha: str
    parents: Tuple[str, ...]
    tree_entries: Tuple[Tuple[str, str, str, str], ...]
    original_blob: bytes


def plan_carrier(identity: AttemptIdentity, binding: FrozenGLOWBinding, coal_parent: str) -> CarrierPlan:
    if identity.repository != COAL_REPO:
        raise CarrierMismatch("carrier must live in the COAL Git object database")
    if identity.operation_id != binding.operation_id or identity.source_binding != binding.digest:
        raise CarrierMismatch("operation or full external binding does not match identity")
    if not is_sha1_hex(coal_parent):
        raise CarrierMismatch("invalid exact COAL commit parent")
    content = canonical_json({
        "domain": DOMAIN,
        "identity": identity.payload(),
        "external_binding": binding.payload(),
    }) + b"\n"
    blob_sha = _git_sha("blob", content)
    # Dedicated one-file tree; DO NOT publish this tree onto COAL main.
    entry = b"100644 " + CARRIER_PATH.encode("ascii") + b"\x00" + bytes.fromhex(blob_sha)
    return CarrierPlan(identity, binding, coal_parent, content, blob_sha, _git_sha("tree", entry))


def verify_native_carrier(plan: CarrierPlan, observation: NativeCarrierObservation) -> str:
    """Check native object shapes; authentication of GET and issuer remains external."""
    if not isinstance(plan, CarrierPlan) or not isinstance(observation, NativeCarrierObservation):
        raise CarrierMismatch("invalid carrier observation")
    if not is_sha1_hex(observation.commit_sha):
        raise CarrierMismatch("invalid COAL-local commit SHA")
    if observation.parents != (plan.coal_parent,):
        raise CarrierMismatch("COAL commit parent mismatch")
    if observation.tree_sha != plan.tree_sha:
        raise CarrierMismatch("tree mismatch")
    if observation.tree_entries != plan.expected_tree_entries:
        raise CarrierMismatch("tree entries must be exact one-file carrier")
    if observation.original_blob != plan.content or _git_sha("blob", observation.original_blob) != plan.blob_sha:
        raise CarrierMismatch("original carrier blob mismatch")
    return observation.commit_sha
