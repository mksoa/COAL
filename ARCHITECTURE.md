# COAL V0.3 architecture

COAL is a **custodian**, not an executor and not an authority issuer.

| Module | Role |
|---|---|
| `identity` | Canonical JSON (domain `COAL/attempt-identity/v1`) + SHA-256 over repository, subject, epoch, operation_id, source_binding. Candidate ref: `refs/coal/attempts/<digest>`. No timestamps or randomness. |
| `reservation` | `reserve_exact_attempt(request, port)`: at most one native create per single-use request; no pre-check, no retry. Outcomes: CREATED, ALREADY_EXISTS, CONFLICT, UNKNOWN, REJECTED. |
| `reconciliation` | `read_exact_attempt(identity, port, expected_sha=...)`: PRESENT_MATCH, ABSENT_OBSERVED, DIVERGENT, UNKNOWN. Never proves who created the ref. |
| `receipts` | Tamper-evident receipt (request id, status, original body base64 + SHA-256, native ref, observed time, issuer if independent, reconciliation). Bodies matching credential patterns are withheld. |
| `checkpoint` | Offline W038 monotonic-frontier verifier. |
| `github_adapter` | `GitHubReadAdapter` (GET only). `GitHubCreateAdapter` (prepared; cannot be constructed without an injected transport + token provider). |
| `synthetic` | In-memory fault-injecting transport for tests and `coal simulate`. |
| `cli` | `validate`, `inspect`, `simulate` (synthetic only), `readback` (GET only). No create/live/force path. |

Outcome mapping for create: 201 with matching body -> CREATED; 201 divergent body -> CONFLICT; 422 "already exists" -> ALREADY_EXISTS (ownership **not** established); other 422, 401/403/404/other 4xx -> REJECTED; 409 -> CONFLICT; timeout, lost ACK, 408/429/5xx, malformed -> UNKNOWN (reconcile by read, never re-create).

A Git ref is not immutable storage and is not CAS protected against repository administrators.
