import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { qualifyReadback, boundedFailureCode } from '../tools/assurance/coal_custodian_jwt_readback_v1.mjs';

function fixture() {
  const account = { login: 'mksoa', id: 337364968, type: 'User' };
  return [
    { id: 5178248, slug: 'coal-custodian-001', owner: account },
    { id: 167609061, app_id: 5178248, app_slug: 'coal-custodian-001',
      account, target_type: 'User', repository_selection: 'selected',
      suspended_at: null, permissions: { contents: 'write', metadata: 'read' } },
    { id: 167609061, app_id: 5178248, account, repository_selection: 'selected', suspended_at: null },
  ];
}
test('exact positive is deliberately non-bearer and does not attest complete selected set', () => {
  const x = qualifyReadback(...fixture());
  assert.equal(x.installation_token_created, false);
  assert.equal(x.effect_authorized, false);
  assert.equal(x.selected_repository_set_exhaustively_verified, false);
  assert.equal(x.jwt_get_count, 3);
});
for (const [label, mutate] of [
  ['foreign app', x => { x[0].id++; }],
  ['foreign app owner', x => { x[0].owner = { ...x[0].owner, login: 'foreign' }; }],
  ['wrong install', x => { x[1].id++; }],
  ['unrestricted selection', x => { x[1].repository_selection = 'all'; }],
  ['suspended install', x => { x[1].suspended_at = '2026-01-01'; }],
  ['write permissions missing', x => { x[1].permissions.contents = 'read'; }],
  ['surplus permissions', x => { x[1].permissions.issues = 'write'; }],
  ['foreign repo installation', x => { x[2].id++; }],
  ['repo installation suspended', x => { x[2].suspended_at = '2026-01-01'; }],
]) test(label + ' stops', () => {
  const x = fixture(); mutate(x);
  assert.throws(() => qualifyReadback(...x));
});

const hosted = {
  GITHUB_ACTIONS: 'true', GITHUB_REPOSITORY: 'mksoa/COAL',
  GITHUB_REF: 'refs/heads/main', GITHUB_REF_PROTECTED: 'true',
  GITHUB_ACTOR: 'mksoa', GITHUB_RUN_ATTEMPT: '1',
  GITHUB_EVENT_NAME: 'workflow_dispatch', COAL_CUSTODIAN_APP_PRIVATE_KEY: '',
};
function offlineChild(overrides) {
  const script = fileURLToPath(new URL('../tools/assurance/coal_custodian_jwt_readback_v1.mjs', import.meta.url));
  return spawnSync(process.execPath, [script, '--native-read'], {
    env: { ...process.env, ...hosted, ...overrides }, encoding: 'utf8', timeout: 5000,
  });
}
for (const stage of [
  'HOSTED_CONTEXT_FAILED', 'KEY_UNAVAILABLE_OR_INVALID', 'JWT_SIGNING_FAILED',
  'GET_APP_FAILED', 'GET_INSTALLATION_FAILED', 'GET_COAL_INSTALLATION_FAILED',
  'READBACK_SHAPE_FAILED',
]) test(`closed failure label ${stage}`, () => {
  assert.equal(boundedFailureCode(stage), `COAL_CUSTODIAN_JWT_READBACK_S0_${stage}`);
});
test('unexpected diagnostic input is never echoed', () => {
  const secretLooking = '-----BEGIN PRIVATE KEY-----\nTOP_SECRET_DO_NOT_ECHO';
  assert.equal(boundedFailureCode(secretLooking), 'COAL_CUSTODIAN_JWT_READBACK_S0_UNCLASSIFIED');
});
for (const [label, overrides, expected] of [
  ['hosted actor mismatch', { GITHUB_ACTOR: 'foreign' }, 'HOSTED_CONTEXT_FAILED'],
  ['missing key', {}, 'KEY_UNAVAILABLE_OR_INVALID'],
  ['invalid key format', { COAL_CUSTODIAN_APP_PRIVATE_KEY: 'NO_PEM_CONTENT' }, 'KEY_UNAVAILABLE_OR_INVALID'],
  ['malformed fake PEM signing', { COAL_CUSTODIAN_APP_PRIVATE_KEY: '-----BEGIN PRIVATE KEY-----\nLOCAL_FAKE_DO_NOT_LOG\n-----END PRIVATE KEY-----' }, 'JWT_SIGNING_FAILED'],
]) test(`offline subprocess ${label} has no secret output or network`, () => {
  const result = offlineChild(overrides);
  assert.equal(result.error, undefined);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, '');
  assert.equal(result.stderr.trim(), `COAL_CUSTODIAN_JWT_READBACK_S0_${expected}`);
  assert.doesNotMatch(result.stderr, /PRIVATE KEY|NO_PEM_CONTENT|LOCAL_FAKE|TOP_SECRET/);
});
