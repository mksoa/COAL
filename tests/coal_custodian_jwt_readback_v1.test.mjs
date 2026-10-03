import test from 'node:test';
import assert from 'node:assert/strict';
import { qualifyReadback } from '../tools/assurance/coal_custodian_jwt_readback_v1.mjs';

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
