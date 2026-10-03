# Qualification status — COAL V0.3 source candidate

| Classification | Status | Boundary |
|---|---|---|
| SOURCE_IMPLEMENTED | Source integrated into `main` subject to independent HEAD/tree verification | Source code, **not** resident operational activation |
| OFFLINE_TESTED | Verified locally: `unittest` and Draft 2020-12 tests | Synthetic transport, no actual reserved refs |
| NATIVE_READBACK | Repository source metadata read via GitHub; **exact reservation readback NOT DONE** | Source audit is not a reservation receipt |
| NATIVE_RESERVATION_PROVEN | No | No real POST /git/refs |
| EXTERNAL_CUSTODY_QUALIFIED | No | Independent issuer/admin, one-use admission and anti-rollback unresolved |
| W038_QUALIFIED | No | Deterministic offline checker only; no outside witness |

The source-only CI (push on `main`) does not issue H0/M0, install credentials or perform live GitHub POST. A green CI run means code validated, not custody operationally qualified. Historical NEXT-001 identifiers: 0/6 used by this change.
