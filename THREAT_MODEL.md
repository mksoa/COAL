# Threat model (V0.3, offline-tested only)

| Threat | Mitigation | Residual |
|---|---|---|
| Duplicate/racing creators | Single native create per request; ref uniqueness at the remote; concurrency tests on a synthetic remote | Real GitHub behavior not exercised |
| Lost ACK / timeout | UNKNOWN + mandatory readback; request consumed | A match does not prove authorship |
| Stale 404 | No pre-check used as a guard | Absence is only at observation time |
| Divergent body / SHA | CONFLICT / DIVERGENT | |
| Receipt tampering | Digest over fields + body SHA | Receipts are not signed; no external anchor |
| Credential leakage | Receipts have no header fields; secret-pattern bodies withheld | Pattern list is best-effort |
| Caller self-asserting authority | No authority boolean in API; create adapter not activatable by CLI | Trusted caller is out of scope for V0.3 |
| Repo admin rewriting/deleting refs | **Not mitigated** | Needs an independent witness (W038) |
| Checkpoint rollback/fork | Offline verifier | Not an installed witness |
