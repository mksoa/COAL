/** COAL App credentialless-by-default JWT GET verification candidate.
 * Source only; NOT a custody issuer, installation token, H0/M0, or NEXT-001 effect.
 * The --selftest path never accesses an environment secret or network.
 */
import { sign } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const APP_ID = 5178248;
const INSTALLATION_ID = 167609061;
const OWNER_ID = 337364968;
const APP_SLUG = 'coal-custodian-001';

function requireExact(test, code) {
  if (!test) throw new Error(code);
}

export function qualifyReadback(app, installation, repositoryInstallation) {
  requireExact(app && app.id === APP_ID && app.slug === APP_SLUG &&
    app.owner?.login === 'mksoa' && app.owner?.id === OWNER_ID, 'APP_IDENTITY_MISMATCH');
  requireExact(installation && installation.id === INSTALLATION_ID &&
    installation.app_id === APP_ID && installation.app_slug === APP_SLUG &&
    installation.account?.login === 'mksoa' && installation.account?.id === OWNER_ID &&
    installation.account?.type === 'User' && installation.target_type === 'User',
    'INSTALLATION_IDENTITY_MISMATCH');
  requireExact(installation.repository_selection === 'selected' &&
    installation.suspended_at === null, 'INSTALLATION_SELECTION_OR_SUSPENSION');
  const p = installation.permissions;
  requireExact(p && !Array.isArray(p) && Object.keys(p).sort().join(',') === 'contents,metadata' &&
    p.contents === 'write' && p.metadata === 'read', 'INSTALLATION_PERMISSIONS_MISMATCH');
  requireExact(repositoryInstallation && repositoryInstallation.id === INSTALLATION_ID &&
    repositoryInstallation.app_id === APP_ID &&
    repositoryInstallation.account?.login === 'mksoa' &&
    repositoryInstallation.account?.id === OWNER_ID &&
    repositoryInstallation.repository_selection === 'selected' &&
    repositoryInstallation.suspended_at === null, 'COAL_REPOSITORY_INSTALLATION_MISMATCH');
  return {
    classification: 'JWT_GET_IDENTITY_SHAPE_VERIFIED_NOT_CUSTODY_OR_H0',
    app_id: APP_ID,
    installation_id: INSTALLATION_ID,
    account: 'mksoa',
    repository_included: 'mksoa/COAL',
    installation_repository_selection: 'selected',
    selected_repository_set_exhaustively_verified: false,
    observed_permissions: { contents: 'write', metadata: 'read' },
    jwt_get_count: 3,
    installation_token_created: false,
    operational_h0: false,
    effect_authorized: false,
    next001_effects_consumed: 0,
  };
}

function jwtFromPrivateKey(privateKey) {
  requireExact(typeof privateKey === 'string' && privateKey.includes('BEGIN') &&
    privateKey.includes('PRIVATE KEY'), 'PRIVATE_KEY_UNAVAILABLE');
  const now = Math.floor(Date.now() / 1000);
  const b64 = obj => Buffer.from(JSON.stringify(obj)).toString('base64url');
  const payload = `${b64({ alg: 'RS256', typ: 'JWT' })}.${b64({ iat: now - 60, exp: now + 480, iss: String(APP_ID) })}`;
  return `${payload}.${sign('RSA-SHA256', Buffer.from(payload), privateKey).toString('base64url')}`;
}

async function fixedGet(path, jwt, label) {
  const response = await fetch(`https://api.github.com${path}`, {
    method: 'GET', redirect: 'manual', signal: AbortSignal.timeout(10000),
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${jwt}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'coal-custodian-jwt-readback-v1',
    },
  });
  requireExact(response.status === 200, `GET_${label}_HTTP_NOT_200`);
  try { return await response.json(); } catch { throw new Error(`GET_${label}_NON_JSON`); }
}

function checkFixedHostedContext() {
  const e = process.env;
  requireExact(e.GITHUB_ACTIONS === 'true' && e.GITHUB_REPOSITORY === 'mksoa/COAL' &&
    e.GITHUB_REF === 'refs/heads/main' && e.GITHUB_REF_PROTECTED === 'true' &&
    e.GITHUB_ACTOR === 'mksoa' && e.GITHUB_RUN_ATTEMPT === '1' &&
    e.GITHUB_EVENT_NAME === 'workflow_dispatch', 'HOSTED_CONTEXT_UNQUALIFIED');
}

async function main() {
  requireExact(process.argv.length === 3 && process.argv[2] === '--native-read', 'INVALID_MODE');
  checkFixedHostedContext();
  const jwt = jwtFromPrivateKey(process.env.COAL_CUSTODIAN_APP_PRIVATE_KEY);
  // GET-only. No arbitrary endpoints or installation access token POST.
  const app = await fixedGet('/app', jwt, 'APP');
  const installation = await fixedGet(`/app/installations/${INSTALLATION_ID}`, jwt, 'INSTALLATION');
  const repositoryInstallation = await fixedGet('/repos/mksoa/COAL/installation', jwt, 'COAL_INSTALLATION');
  console.log(JSON.stringify(qualifyReadback(app, installation, repositoryInstallation)));
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(() => {
    // Never print exception/request body, JWT, PEM, token or secret-bearing response.
    console.error('COAL_CUSTODIAN_JWT_READBACK_S0_FAIL_CLOSED');
    process.exitCode = 1;
  });
}
