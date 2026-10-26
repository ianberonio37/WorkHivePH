#!/usr/bin/env node
/**
 * create_smoke_bench.mjs - the post-deploy smoke's own production identity (BRH-AF, 2026-10-26).
 *
 * The smoke's signed-in tier never ran on production: production had no account it could sign in with, and the one it
 * would have used must not walk a real tenant's pages. This makes that account the way a person would, through the
 * product's own calls (index.html's sign-up, hive.html's Create Hive):
 *
 *   1. a username account (synthetic email, as the sign-up page derives it) with a long random password
 *   2. its worker profile
 *   3. its own hive - the bench - holding no tenant's data, with the account as its supervisor
 *
 * and writes WH_SMOKE_EMAIL / WH_SMOKE_PASS / WH_SMOKE_HIVE to .env (the only place credentials live). The password is
 * never printed. tools/post_deploy_smoke.mjs then signs in, reads its hive FROM THE SERVER and refuses any hive but the
 * bench; its contexts send no analytics_events, so the bench never counts in the founder's growth figures.
 *
 * If production's sign-up refuses a scripted request (a captcha), the account is created through the auth admin API
 * with the project's service key, taken in-process from the linked Supabase CLI and never stored; every later step
 * runs as the account itself.
 *
 *   node tools/create_smoke_bench.mjs            # create (refuses if .env already names a smoke account)
 *   node tools/create_smoke_bench.mjs --verify   # sign in with the .env credentials and read the bench membership
 */
import { createClient } from '@supabase/supabase-js';
import { execFileSync } from 'node:child_process';
import { randomBytes, randomUUID } from 'node:crypto';
import { readFileSync, appendFileSync, existsSync } from 'node:fs';

const REF = 'hzyvnjtisfgbksicrouu';
const URL = `https://${REF}.supabase.co`;
const PUBLISHABLE = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';   // the key every page ships
const USERNAME = 'whsmokebench';
const DISPLAY = 'WorkHive Smoke Bench';
const HIVE_NAME = 'WorkHive Smoke Bench (internal)';
const EMAIL = `${USERNAME}@auth.workhiveph.com`;
const ENV = '.env';

const envVal = (k) => {
  if (!existsSync(ENV)) return '';
  const m = readFileSync(ENV, 'utf8').match(new RegExp(`^${k}=(.*)$`, 'm'));
  return m ? m[1].trim() : '';
};
const log = (s) => process.stdout.write(s + '\n');
const client = () => createClient(URL, PUBLISHABLE, { auth: { persistSession: false, autoRefreshToken: false } });

async function verify() {
  const email = envVal('WH_SMOKE_EMAIL'), pass = envVal('WH_SMOKE_PASS'), hive = envVal('WH_SMOKE_HIVE');
  if (!email || !pass || !hive) { log('verify: .env names no smoke account'); return 1; }
  const db = client();
  const { data, error } = await db.auth.signInWithPassword({ email, password: pass });
  if (error) { log(`verify: sign-in refused (${error.message})`); return 1; }
  const { data: rows, error: mErr } = await db.from('hive_members')
    .select('hive_id, role, status').eq('auth_uid', data.user.id).eq('status', 'active');
  if (mErr) { log(`verify: membership read refused (${mErr.message})`); return 1; }
  const ok = (rows || []).length === 1 && rows[0].hive_id === hive && rows[0].role === 'supervisor';
  log(`verify: signed in as ${email}; active memberships ${(rows || []).length}; bench supervisor ${ok}`);
  await db.auth.signOut();
  return ok ? 0 : 1;
}

function serviceKey() {
  const out = execFileSync('supabase', ['projects', 'api-keys', '--project-ref', REF, '-o', 'json'], { encoding: 'utf8' });
  const k = JSON.parse(out).find((x) => x.name === 'service_role');
  if (!k) throw new Error('the linked Supabase CLI returned no service key');
  return k.api_key;
}

async function create() {
  if (envVal('WH_SMOKE_EMAIL')) { log(`refusing: .env already names a smoke account (${envVal('WH_SMOKE_EMAIL')}) - run --verify`); return 1; }
  const password = randomBytes(24).toString('base64url');
  const db = client();

  const { data: free } = await db.rpc('check_username_available', { p_username: USERNAME });
  if (free === false) { log(`refusing: the username ${USERNAME} is taken on production`); return 1; }

  let signedUp = await db.auth.signUp({ email: EMAIL, password });
  let how = 'the sign-up page\'s call';
  if (signedUp.error) {
    if (!/captcha/i.test(signedUp.error.message)) { log(`sign-up refused: ${signedUp.error.message}`); return 1; }
    const admin = createClient(URL, serviceKey(), { auth: { persistSession: false, autoRefreshToken: false } });
    const { error } = await admin.auth.admin.createUser({ email: EMAIL, password, email_confirm: true });
    if (error) { log(`admin create refused: ${error.message}`); return 1; }
    how = 'the auth admin API (production sign-up asks for a captcha)';
  }
  const { data: auth, error: sErr } = await db.auth.signInWithPassword({ email: EMAIL, password });
  if (sErr) { log(`sign-in after create refused: ${sErr.message}`); return 1; }
  const uid = auth.user.id;

  const { error: pErr } = await db.from('worker_profiles').insert({ auth_uid: uid, username: USERNAME, display_name: DISPLAY });
  if (pErr) { log(`profile refused: ${pErr.message}`); return 1; }

  const hiveId = randomUUID();
  const code = randomBytes(4).toString('hex').slice(0, 6).toUpperCase();
  const { error: hErr } = await db.from('hives').insert({ id: hiveId, name: HIVE_NAME, invite_code: code, created_by: DISPLAY });
  if (hErr) { log(`hive refused: ${hErr.message}`); return 1; }
  const { error: mErr } = await db.from('hive_members').upsert(
    { hive_id: hiveId, worker_name: DISPLAY, role: 'supervisor', status: 'active', auth_uid: uid },
    { onConflict: 'hive_id,worker_name' });
  if (mErr) { log(`membership refused: ${mErr.message}`); return 1; }
  await db.auth.signOut();

  appendFileSync(ENV, `\n# post-deploy smoke identity on production (BRH-AF, ${new Date().toISOString().slice(0, 10)}) - its own bench hive, no tenant data\n`
    + `WH_SMOKE_EMAIL=${EMAIL}\nWH_SMOKE_PASS=${password}\nWH_SMOKE_HIVE=${hiveId}\n`);
  log(`created ${EMAIL} through ${how}; bench hive "${HIVE_NAME}" ${hiveId}; credentials written to .env (password not shown)`);
  return verify();
}

process.exit(await (process.argv.includes('--verify') ? verify() : create()));
