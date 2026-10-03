# COAL — Custodian JWT native GET-only installation candidate V1

Classification: LOCAL CANDIDATE / PRE-H0 / NON-BEARER. Preparing this bundle is NOT owner source-installation approval, main merge, credential placement, workflow dispatch, or permission to consume an original NEXT-001 operation.

## Exact anchors (readback)
- Pre-existing COAL main: `bf9188d68daffd2211a3fbad341fd579f4b98131`; tree `2f161a2c39f61428e22b139a4ead520e1dbfddec`.
- Owner-adopted GLOW main: `cb22d1e9c4717ce159feceb1fa8f157364744e70`.
- Original PRE-ACT: `343884f170db11e7a091e1c9b32ead90d3595f66`.
- COAL retention ruleset 24425208: update and deletion restricted for `coal/admissions/*` and `coal/attempts/*`, active, zero bypass.
- COAL main protection ruleset 24427491: main protected with PR requirement, deletion and non-fast-forward restrictions, active, zero bypass.
- `coal-custodian-verify` Environment: **confirmed by project owner in conversation**, not independently readable through available connector. Deployment restricted to main per owner's confirmation. No key has been placed by this candidate.
- App ID `5178248`; Installation ID `167609061`; account `mksoa`; exact COAL repository. App's effective permissions still require native JWT proof.

## One proposed source-only PR
Exactly four ADD-only paths relative to the pinned main:
1. `tools/assurance/coal_custodian_jwt_readback_v1.mjs` — fixed Node standard-library JWT verifier, no generic endpoints/commands;
2. `tests/coal_custodian_jwt_readback_v1.test.mjs` — 10 offline cases, non-bearer;
3. `.github/workflows/coal-custodian-jwt-verify-v1.yml` — manually dispatchable job *only* after separate authorization; GITHUB_TOKEN contents:read, fixed exact protected main and owner/run attempt, Environment `coal-custodian-verify`, `persist-credentials:false`, fixed 3 GETs via the reviewed script;
4. this scope/status note.

Existing `.github/workflows/ci.yml` remains untouched. Its filter triggers on `push` to `main` and includes `tests/**`; it does not provide natural PR CI or Node tests. The proposed workflow runs the Node test suite first, then only on a separately approved native hosted run and after the owner privately provisions `COAL_CUSTODIAN_APP_PRIVATE_KEY` in COAL's Environment, performs GET `/app`, GET `/app/installations/167609061`, GET `/repos/mksoa/COAL/installation`. **No native requests occur from ordinary source preparation, opening a draft PR, merging the PR, or COAL CI.** Output remains sanitized. JWT issued in-memory is NOT an installation access token.

Never store `.pem`, JWT, token or private key in code, chat, issue, PR, artifact or GLOW; source/UI review first. Environment branch restrictions are not exclusive per-workflow ACL. Exact installed workflow source and one eventual run must be rechecked independently. JWT proof establishes App identity, installation permission metadata, and repository inclusion only, NOT a complete enumeration of selected repositories or effective future installation-token scope.

**After source installation:** the COAL main changes. Read exact integrated HEAD/tree and obtain distinct owner re-adoption of COAL source successor; the user has NOT yet authorized this step. The source installation does not authorize secret placement, workflow_dispatch, reservation/ref creation, Claim/Slot, W038 authority, H0/M0 or any of six original NEXT-001 effects. R-J experiment remains closed. If any ambiguity: S0, no retry/refund/fallback.

Disposition: INSTALL_SOURCE_PROPOSAL_ONLY / NATIVE_JWT_NOT_RUN / NEXT001_PREH0_HOLD / ORIGINAL_EFFECTS_0_OF_6.
