/**
 * Tier 1 — Authentication & Identity (5 scenarios, P0)
 *
 * Without these, no other journey works. Test identity per
 * reference_playwright_test_identity:
 *   - Pablo Aguilar (supervisor), hive 586fd158-42d1-4853-a406-64a4695e71c4
 *   - Leandro Marquez is NOT in any hive (negative tests)
 *
 * Scaffolds use test.fixme until DB setup is wired in. Real assertions
 * land when the auth flow data fixtures are seeded.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');
const HIVE_ID_BAGUIO = '586fd158-42d1-4853-a406-64a4695e71c4';
const SEVEN_IDENTITY_KEYS = [
  'wh_last_worker', 'wh_worker_name', 'workerName',
  'wh_active_hive_id', 'wh_hive_id', 'wh_hive_role', 'wh_hive_name',
];

test.describe('Tier 1 — Authentication & Identity', () => {

  test('A1_first_signup: signup form structure (synthetic email pattern)', async () => {
    // STATIC: signup form must exist with username + password fields (the platform's auth model)
    const html = readFileSync(resolve(ROOT, 'index.html'), 'utf-8');
    // Username input must be present (the user types it, synthetic email is generated).
    expect(html, 'signup must have a username field').toMatch(/<input[^>]*(?:id|name)=["'][^"']*username/i);
    // Password input must be present.
    expect(html, 'signup must have a password field').toMatch(/<input[^>]*type=["']password["']/i);
    // Synthetic email pattern must be referenced somewhere in the auth code.
    expect(html, 'auth code must construct @auth.workhiveph.com synthetic email').toMatch(/@auth\.workhiveph\.com/);
  });

  test('A2_signin_username: signin modal + ?signin=1 redirect wiring present', async () => {
    // STATIC: pages must redirect to index.html?signin=1 when WORKER_NAME is empty
    // and index.html must have a signin modal with username + password inputs.
    const html = readFileSync(resolve(ROOT, 'index.html'), 'utf-8');
    // Signin modal exists.
    expect(html, 'index.html must include #signin-modal').toMatch(/id=['"]signin-modal['"]/i);
    // signin URL param handling -- either openSignIn handler reads it or a redirect uses it.
    expect(html, 'signin URL param must be handled (?signin=1 or openSignIn)')
      .toMatch(/\?signin=1|openSignIn\s*\(/);
    // Has both username + password inputs.
    expect(html, 'signin needs username field somewhere').toMatch(/username/i);
    expect(html, 'signin needs password input').toMatch(/<input[^>]*type=['"]password['"]/i);
  });

  test('A3_identity_restoration: restoreIdentityFromSession is defined in utils.js + called from worker pages', async () => {
    // WHY: fire-and-forget restoration pattern (lesson #22)
    const utils = readFileSync(resolve(ROOT, 'utils.js'), 'utf-8');
    expect(utils, 'utils.js must define restoreIdentityFromSession').toMatch(/function\s+restoreIdentityFromSession|restoreIdentityFromSession\s*=/);
    // At least one major worker page calls it.
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    expect(hive, 'hive.html must call restoreIdentityFromSession').toMatch(/restoreIdentityFromSession\s*\(/);
  });

  test('A4_signout_clears_all_seven_keys: canonical signOut clears every identity key', async () => {
    // WHY: prevents cross-user contamination on shared devices (signOut completeness rule)
    // STATIC: index.html owns the signOut handler; it must clear each of the 7 identity keys via removeItem
    const html = readFileSync(resolve(ROOT, 'index.html'), 'utf-8');
    const signOutMatch = html.match(/function\s+signOut\s*\([\s\S]{0,800}?\}/);
    expect(signOutMatch, 'index.html must define signOut handler').not.toBeNull();
    const body = signOutMatch![0];
    const missing: string[] = [];
    for (const k of SEVEN_IDENTITY_KEYS) {
      if (!new RegExp(`['"]${k}['"]`).test(body)) missing.push(k);
    }
    expect(missing, `signOut must clear every identity key; missing: ${missing.join(', ')}`).toEqual([]);
    expect(body, 'signOut must call localStorage.removeItem').toMatch(/localStorage\.removeItem|forEach\s*\([^)]*removeItem/);
  });

  test('A5_hive_membership_revalidation: hive_members revalidation present in protected pages', async () => {
    // WHY: stale localStorage cannot unlock data; DB is source of truth
    // STATIC: hive.html (and similar) must query hive_members on load to revalidate
    const hive = readFileSync(resolve(ROOT, 'hive.html'), 'utf-8');
    // The page must query hive_members in its bootstrap.
    expect(hive, 'hive.html must query hive_members on load').toMatch(/from\s*\(\s*['"]hive_members['"]/);
    // And check status='active'.
    expect(hive, 'must filter by status=active').toMatch(/status['"]\s*,\s*['"]active['"]/i);
  });
});
