"""Administrative CLI. Read-only or synthetic only. There is intentionally NO create/live/force command."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .checkpoint import Checkpoint, CheckpointError, verify_frontier
from .github_adapter import GitHubReadAdapter
from .identity import AttemptIdentity, IdentityError
from .reconciliation import read_exact_attempt
from .reservation import ReservationRequest, reserve_exact_attempt
from .synthetic import SyntheticGitHub

SCENARIOS = {
    "created": None, "exists": "exists", "timeout-before": "timeout_before",
    "ack-lost": "timeout_after", "forbidden": "forbidden", "validation-422": "validation_422",
    "divergent-201": "divergent_201",
}
SCHEMAS = ("reservation-request", "reservation-receipt", "reservation-readback", "checkpoint")


def _out(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def _identity_args(p):
    for n in ("repository", "subject", "epoch", "operation-id", "source-binding"):
        p.add_argument("--" + n, required=True)


def _identity(a) -> AttemptIdentity:
    return AttemptIdentity(a.repository, a.subject, a.epoch, a.operation_id, a.source_binding)


def cmd_validate(a) -> int:
    errors = []
    for n in SCHEMAS:
        f = Path(a.schemas) / f"{n}.schema.json"
        try:
            s = json.loads(f.read_text("utf-8"))
            assert "$schema" in s and s.get("type") == "object"
        except Exception as e:
            errors.append(f"{f}: {type(e).__name__}")
    if a.request:
        try:
            d = json.loads(Path(a.request).read_text("utf-8"))
            AttemptIdentity.from_dict(d["identity"])
            ReservationRequest(AttemptIdentity.from_dict(d["identity"]), d["target_sha"])
        except Exception as e:
            errors.append(f"request: {e}")
    if a.checkpoint and a.previous:
        try:
            v = verify_frontier(json.loads(Path(a.previous).read_text()),
                                json.loads(Path(a.checkpoint).read_text()))
            if not v.ok:
                errors.append("checkpoint: " + v.reason)
        except Exception as e:
            errors.append(f"checkpoint: {e}")
    _out({"valid": not errors, "errors": errors})
    return 0 if not errors else 1


def cmd_inspect(a) -> int:
    i = _identity(a)
    _out({"identity": i.to_dict(), "identity_digest": i.digest, "ref_name": i.ref_name})
    return 0


def cmd_simulate(a) -> int:
    fault = SCENARIOS[a.scenario]
    net = SyntheticGitHub(create_fault=None if fault == "exists" else fault)
    ident = AttemptIdentity("owner/repo", "synthetic-subject", "E0", "op-synthetic-1", "synthetic-src")
    sha = "a" * 40
    if fault == "exists":
        net.refs[ident.ref_name] = "b" * 40
    res = reserve_exact_attempt(ReservationRequest(ident, sha), net)
    rb = read_exact_attempt(ident, net, expected_sha=sha)
    _out({"synthetic": True, "outcome": res.outcome.value, "reason": res.reason,
          "create_calls": net.create_calls, "readback": rb.status.value,
          "readback_reason": rb.reason, "ownership_established": False,
          "note": "synthetic transport only; no real custody or authority"})
    return 0


def cmd_readback(a) -> int:
    i = _identity(a)
    token = os.environ.get(a.token_env) if a.token_env else None
    r = read_exact_attempt(i, GitHubReadAdapter(i.repository, token=token), expected_sha=a.expected_sha)
    _out({"status": r.status.value, "reason": r.reason, "observed_sha": r.observed_sha,
          "causal_authorship_proven": False, "receipt": r.receipt.to_dict() if r.receipt else None})
    return 0 if r.status.value in ("PRESENT_MATCH", "ABSENT_OBSERVED") else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coal", description="COAL V0.3 (read-only / synthetic)")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.set_defaults(fn=cmd_validate)
    v.add_argument("--schemas", default="schemas"); v.add_argument("--request")
    v.add_argument("--checkpoint"); v.add_argument("--previous")
    i = sub.add_parser("inspect"); _identity_args(i); i.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("simulate"); s.set_defaults(fn=cmd_simulate)
    s.add_argument("--scenario", choices=sorted(SCENARIOS), default="created")
    r = sub.add_parser("readback"); _identity_args(r); r.set_defaults(fn=cmd_readback)
    r.add_argument("--expected-sha", required=True)
    r.add_argument("--token-env", help="name of env var holding an optional READ token")
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except (IdentityError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
