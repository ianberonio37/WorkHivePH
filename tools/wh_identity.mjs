// wh_identity — sign in once, hand every walk the same session.
//
// ★WRITTEN THREE TIMES IN ONE NIGHT BEFORE IT BECAME A FILE. The shared-component prover walked the SIGN-IN
// DOOR 57 times and 37 rows were banked on it; the lifecycle prover, which does check where it landed,
// refused 105 of 202 rows for the same reason; the first-run prover still has four. Each fix was the same
// forty lines pasted again — which is exactly the shape of the credential-pointer defect found the same
// night: **a paragraph copied onto siblings, and a correction that reaches whichever copy someone is looking
// at.** So it lives here once.
//
// What it does: resolve the person's hive from the database, sign in through the page's own Supabase client
// (not a back door — the walk must exercise what a person exercises), stamp the localStorage the pages read,
// and return a storageState every context can reuse. One sign-in for a walk of 57 contexts, because 57
// sign-ins against the auth server is a self-inflicted load test.
//
//   import { establishIdentity } from './wh_identity.mjs';
//   const session = await establishIdentity(browser, ORIGIN);   // null when it could not sign in
//   const ctx = await browser.newContext({ viewport, ...(session ? { storageState: session } : {}) });
// ★THIS EXACT BLIND SPOT ALREADY COST THE A11Y RATCHET ITS RISKIEST PAGES. `tools/axe_scan.js` seeded a FAKE
// identity, so every auth-gated write surface — hive, inventory, logbook, pm-scheduler, skillmatrix,
// community, dayplanner, marketplace, project-manager — redirected to the sign-in gate and was SKIPPED. The
// baseline covered eleven read-mostly pages while the forms, modals and destructive surfaces, where
// accessibility matters most, had zero coverage behind a green gate. `tools/axe_scan_live.js` was written to
// close it. **A walk without an identity does not fail loudly; it quietly grades a different page.**
//
// ★ON THE METHOD: this signs in through the page's own Supabase client, which is what
// `tools/prove_full_journeys.mjs` does. The project also documents a modal recipe for hand-driven MCP runs
// (index.html?signin=1 -> #si-username / #si-password / #si-btn, then seed the wh_* keys) — that path
// exercises the form itself and is the right one when the SIGN-IN is the subject. Here the sign-in is
// setup, not subject, and 57 modal round-trips per walk would be the load test this file exists to avoid.
import { execSync } from 'node:child_process';

export const PERSON = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com' };
const SUPA = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';

// ★A BUSY DATABASE IS NOT AN ABSENT ONE. One attempt came back empty while another wave held the host, and a
// prover concluded there was no such person rather than "ask again in a moment".
export const psql = (sql, tries = 5) => {
  for (let i = 0; i < tries; i++) {
    try {
      const out = execSync(
        `docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`,
        { encoding: 'utf8', timeout: 25000 }).trim();
      if (out) return out;
    } catch { /* busy or wedged - wait and ask again */ }
    try { execSync('powershell -NoProfile -Command "Start-Sleep -Seconds 4"', { stdio: 'ignore', timeout: 12000 }); } catch { /* even the wait can fail */ }
  }
  return '';
};

/** Returns a storageState to reuse, or null with the reason on `establishIdentity.why`. */
export async function establishIdentity(browser, origin, who = PERSON) {
  establishIdentity.why = '';
  const hive = psql(`select hive_id::text from hive_members where worker_name = '${who.name}' and status = 'active' limit 1`);
  if (!hive) {
    establishIdentity.why = 'the database could not name the hive this person belongs to';
    return null;
  }
  const role = psql(`select role from hive_members where worker_name = '${who.name}' and hive_id::text = '${hive}' limit 1`) || 'worker';
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`${origin}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  // ★getDb EXISTS BEFORE IT WORKS: wait for the client the page actually builds, not just for the symbol.
  await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
  const out = await p.evaluate(async ({ hive, who, role, supa }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email: who.email, password: 'test1234' });
      if (error) return 'auth: ' + error.message;
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', who.name);
      localStorage.setItem('wh_hive_role', role);
      const { data: h } = await db.from('hives').select('name').eq('id', hive).maybeSingle();
      if (h && h.name) localStorage.setItem('wh_hive_name', h.name);
      return 'ok';
    } catch (e) { return 'threw: ' + (e && e.message); }
  }, { hive, who, role, supa: SUPA }).catch((e) => 'evaluate: ' + e.message);
  const state = out === 'ok' ? await ctx.storageState() : null;
  await ctx.close();
  if (!state) establishIdentity.why = out;
  return state;
}
