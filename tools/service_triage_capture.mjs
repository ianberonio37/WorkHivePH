/**
 * service_triage_capture.mjs — drive the LIVE service-triage agent exactly as marketplace.html does.
 *
 * Signs in with supabase-js and calls `db.functions.invoke('ai-gateway', ...)`, which is the page's
 * own code path. A hand-rolled HTTP call is NOT equivalent: the gateway resolves the caller through
 * `authedClient.auth.getUser()` and refuses every agent but voice-journal without a real session, so
 * a raw fetch tests the auth wall rather than the agent.
 *
 * Prints one JSON object per prompt to stdout: { prompt, triage, error }. The grading lives in
 * tools/validate_service_triage_eval.py, against vocabularies read from the database — this file
 * only captures, so a change in what counts as a good answer never means editing the transport.
 */
import { createClient } from '@supabase/supabase-js';

const URL = process.env.WH_TEST_SUPABASE_URL || 'http://127.0.0.1:54321';
const KEY = process.env.WH_TEST_PUBLISHABLE_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const EMAIL = process.env.WH_TRIAGE_EMAIL || 'pabloaguilar@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';

const prompts = JSON.parse(process.argv[2] || '[]');
const db = createClient(URL, KEY, { auth: { persistSession: false } });

const { error: signInErr } = await db.auth.signInWithPassword({ email: EMAIL, password: PASSWORD });
if (signInErr) {
  console.log(JSON.stringify({ fatal: `sign-in failed: ${signInErr.message}` }));
  process.exit(0);
}

for (const prompt of prompts) {
  let out = { prompt, triage: null, error: null };
  try {
    const r = await db.functions.invoke('ai-gateway', {
      body: { agent: 'service-triage', message: prompt },
    });
    if (r.error) {
      let body = r.error.message;
      try { body = (await r.error.context.text()).slice(0, 200); } catch (_) { /* keep message */ }
      out.error = body;
    } else {
      const env = (r.data && r.data.data) || r.data || {};
      out.triage = (env.route_result && env.route_result.triage) || env.triage || null;
      if (!out.triage) out.error = 'no triage field in the envelope';
    }
  } catch (e) {
    out.error = String(e && e.message || e);
  }
  console.log(JSON.stringify(out));
  // The chain is free-tier and rate-limited; pace so a burst is not mistaken for a broken agent.
  await new Promise(r => setTimeout(r, 1200));
}
