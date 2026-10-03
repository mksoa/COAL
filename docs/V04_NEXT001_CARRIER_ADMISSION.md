# COAL V0.4 — NEXT-001 carrier/admission technical candidate

**SOURCE-ONLY / PRE-H0 / NON-BEARER / NOT LIVE CUSTODY.** This is one additive COAL V0.3 successor for the original NEXT-001; not a new runner, mission, store, workflow, framework or research campaign. No credential, token, HTTP POST, ref, Claim, Slot, W038 write or original six GLOW effects is installed/consumed by this change.

## Why this delta exists

GitHub native `POST /repos/mksoa/COAL/git/refs` must point to a **COAL-local commit**, not the immutable external GLOW source SHA. `src/coal/carrier.py` plans one canonical JSON `reservation.json` blob and exact one-file tree; it checks a supplied native commit/tree/parent/blob shape before releasing the local carrier commit SHA as the expected ref target. The external binding explicitly retains original PRE-ACT, frozen target path/blob, operation ID/binding digest, newly adopted source commit/tree and exact successor digest. The old PRE-ACT is not rebased. Pure shape checking alone does not authenticate GET responses or credentials.

The COAL-local carrier **tree is never to be published to COAL main**; the future separately authorized custodian would create its blob, tree and commit objects and independently read them back, while keeping the source main unchanged. No such objects are created by this PR.

`src/coal/admission.py` consumes one **externally controlled** admission before invoking the already-existing V0.3 one-POST reservation method. A divergent, missing, duplicate or unknown admission stops before POST; lost POST ACK burns the admission and permits read-only reconciliation, not retry/refund. Its synthetic tests demonstrate only source-level control flow with a shared fake port. The injected `OneUseAdmissionPort` still requires **actual distributed, custodian-enforced atomic durability** and independent original receipt/readback qualification; a supplied `FIRST_CONSUMED` value is not authenticated custody. This PR does not make the legacy unguarded synthetic `reserve_exact_attempt` into an operational public route.

## Required operational work, not automatically authorized

1. Select the actual COAL custodial issuer with narrowly scoped credential and an independently authenticated atomic admission, retaining the original ACK. GLOW must not receive generic COAL `contents:write`, because that permission also allows reference updates. An additional independently administered W038 witness is needed for strong anti-rollback; a Git ref alone cannot prove this.
2. Verify the native COAL-local blob/tree/commit objects with an independent GET and exact binding; one admissible first ref CREATE; original response/body hash and later readback retained, no repeat on ambiguity. No generated synthetic fixture is proof.
3. Separately qualify GLOW's one resident non-`workflow_dispatch` conductor, installed source successor, effective GitHub App scope, native Claim→Slot and direct human H0 plus per-effect JIT M0. Retain all original six R12 IDs, budget 1 each; no additional V2 campaign inferred from an unproven property.
4. Run the **original** NEXT-001 once to PR/natural CI/terminal receipt; stop before merge, acceptance or release.

V0.3 COAL original policy and schema and GLOW original PRE-ACT/R10–R16 remain unchanged. No extra executable workflow or branch of production authority is introduced.
