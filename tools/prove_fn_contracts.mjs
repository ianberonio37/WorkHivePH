// prove_fn_contracts — W3-FN, three contract rows per edge function (2026-09-07). No browser.
//
// The program named all 62 functions once each and then walked their SHAPE (tools/prove_edge_contract.mjs:
// preflight, no-auth refusal, malformed body, method guard). Wave 3 asks the three questions that shape
// cannot answer, and each is asked the only way it can be answered honestly:
//
//   I  REFUSAL TO A CALLER WHO IS NOT ENTITLED. Not "no token" - a REAL token, belonging to a real member of
//      one hive, asking about another hive. Answered through the function's own front door with that person's
//      access token, never through the owner connection, which carries rolbypassrls and can therefore prove
//      that data EXISTS but never that a read was REFUSED. A sentinel string is lifted from the foreign hive
//      first, so "no leak" means that hive's own words did not come back - not merely that a status was 4xx.
//
//   A  LEGIBLE DEGRADATION. Every AI-backed function here reaches a provider this machine has no key for, so
//      the failure path is the DEFAULT path locally - which makes it exactly the thing to grade. The answer
//      must be JSON, carrying a sentence a person could read, with a status that says what happened. A 500
//      with an empty body, an HTML stack, or a 200 carrying nothing is the failure: silence a reader misreads
//      as fact. The source is read too: a function with no catch around its provider call cannot degrade.
//
//   F  THE DOCUMENTED JOB, AND SOMEBODY WHO ASKS FOR IT. A function whose contract holds but which NO surface
//      ever calls is built and never called - a real defect class in this codebase's history. So F is: the
//      function answers its own documented shape, AND at least one page, script or sibling function names it.
//
// A function the runtime does not host is reported n/a, never passed and never failed - recognised by the
// runtime's own plain-text "Function not found", NOT by the bare 404, which a deployed function also uses
// to say things like "Config not found" about a row.
//
//   node tools/prove_fn_contracts.mjs                    # all three lenses, every function
//   node tools/prove_fn_contracts.mjs --lens I           # one lens
//   node tools/prove_fn_contracts.mjs --fn ai-gateway    # one function, verbose
//   node tools/prove_fn_contracts.mjs --self-test        # teeth, no network
import { readdirSync, statSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { execSync } from 'node:child_process';

const EDGE = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const args = process.argv.slice(2);
const argOf = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
// --fn takes one name or a comma-separated list, so a corrected reader can re-ask ONLY the functions that
// went unanswered rather than spending twenty-five minutes re-proving the ones that already answered
const ONLY_FN = (argOf('--fn') || '').split(',').map((s) => s.trim()).filter(Boolean);
const ONLY_LENS = argOf('--lens');
const LIMIT = Number(argOf('--limit') || 0);
const SHOW_BODY = args.includes('--show-body');   // print the ACTUAL request body, not the schema
// ★A PROBE'S PATIENCE MUST EXCEED ITS SUBJECT'S OWN BOUND. The platform bounds its provider calls at
// AbortSignal.timeout(60000) and allows one jittered retry, so a slow-but-correct answer can legitimately
// take ~2 minutes. A 35s budget therefore cannot tell "this function is broken" from "I hung up first", and
// seven contracts read n/a on the first pass for exactly that reason - a statement about the prober, not the
// product. The fast budget stays the default because most functions answer in under a second; --patient
// re-asks ONLY the calls that ran out of it, with a budget wider than the platform's worst case.
const PATIENT = args.includes('--patient');
const TIMEOUT = PATIENT ? 135000 : 35000;   // a budget too tight turns local saturation into a false contract break

// with a timeout: on this host a wedged docker engine once froze a whole walk inside execSync, which waits
// for ever by default - a probe that cannot give up cannot finish
// ★A BUSY DATABASE IS NOT AN ABSENT ONE. Run while a browser walk had the host, this helper returned '' for
// every query and the self-test reported that the plain member had no hive, that there was no foreign hive to
// ask about, and that no sentinel could be lifted - four confident statements about the platform, all of them
// really "docker was busy". It retries, and only then gives up.
const psql = (sql, tries = 5) => {
  for (let i = 0; i < tries; i++) {
    try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8', timeout: 25000, killSignal: 'SIGKILL' }).trim(); }
    catch { try { execSync('powershell -NoProfile -Command "Start-Sleep -Milliseconds 1500"', { stdio: 'ignore', timeout: 8000 }); } catch { /* even the wait may be refused */ } }
  }
  return '';
};

// ★AN ORDINARY MEMBER, NEVER AN ADMIN. Leandro Marquez is in marketplace_platform_admins, so an admin
// reading everything is the product working, not a leak - the refusal lens must speak for a plain worker.
const PLAIN = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com', password: 'test1234' };
const MINE = psql(`select hive_id::text from hive_members where worker_name = '${PLAIN.name}' and status = 'active' limit 1`);
const FOREIGN = psql(`select h.id::text from hives h where h.id::text <> '${MINE}' order by (select count(*) from logbook l where l.hive_id = h.id) desc limit 1`);
const FOREIGN_NAME = psql(`select name from hives where id::text = '${FOREIGN}'`);
// the sentinel: a word that belongs to the foreign hive and to nobody else, so "it did not come back" means something
// ★THE COLUMN THE TABLE ACTUALLY HAS. The first version asked for `title`/`task_description`, which the
// logbook has never had - it records a `problem` and an `action`. The query errored, the sentinel came back
// empty, and an empty sentinel makes every leak invisible while every lens still reads green.
const SENTINEL = psql(`select left(regexp_replace(coalesce(problem, action, machine, ''), '[^A-Za-z0-9 ]', '', 'g'), 48) from logbook where hive_id::text = '${FOREIGN}' and length(coalesce(problem, action, machine, '')) > 14 order by created_at desc limit 1`);

// ★A FIELD THAT WANTS A REAL ROW CANNOT BE SATISFIED WITH A PLACEHOLDER. Filling `asset_id` with the hive's
// own uuid got the request past the "missing field" check and straight into "no such asset" - the question
// still never reached the subject. The hive HAS assets; the probe just never asked for one. Note the table
// is `asset_nodes`, not `assets` - guessing the name would have failed silently and looked like the product.
const TABLES = new Set(psql("select table_name from information_schema.tables where table_schema='public'")
  .split('\n').map((s) => s.trim()).filter(Boolean));
// the subset that actually has an `id` column, so a lookup never asks a hive-keyed table for one
const ID_TABLES = new Set(psql("select table_name from information_schema.columns where table_schema='public' and column_name='id'")
  .split('\n').map((s) => s.trim()).filter(Boolean));
const _idCache = new Map();
const realId = (field, hive) => {
  const key = `${field}|${hive}`;
  if (_idCache.has(key)) return _idCache.get(key);
  if (!/^[0-9a-f-]{36}$/.test(String(hive))) return null;   // a busy database hands back an empty hive, and asking about '' is a question about nothing
  const stem = field.replace(/_?id$/i, '').replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase();
  // ★AND THE TABLE IS NOT ALWAYS NAMED AFTER THE FIELD'S FIRST WORD. cmms-webhook-receiver wants a
  // `config_id`; the candidates were all PREFIX guesses - configs, config, config_nodes - and the table is
  // `integration_configs`, which holds 16 rows. So a real row existed all along, the probe filled a random
  // uuid instead, and the function answered "Config not found" - which then read as the function failing
  // its documented job. A qualified name ending in the stem is the same kind of thing, so it is tried too,
  // sorted for a repeatable probe and only after the direct guesses.
  // ...and only tables that HAVE an id to hand back. Probing `hive_retention_config`, which is keyed by
  // hive, printed a psql syntax error on every run - noise that would hide a real one.
  const suffixed = [...TABLES].filter((t) => new RegExp(`_${stem}e?s?$`).test(t) && ID_TABLES.has(t)).sort();
  let val = null;
  for (const t of [`${stem}s`, stem, `${stem}_nodes`, `marketplace_${stem}s`, `${stem}es`, ...suffixed]) {
    if (!TABLES.has(t)) continue;
    val = psql(`select id::text from ${t} where hive_id = '${hive}' limit 1`, 2)
       || psql(`select id::text from ${t} limit 1`, 1);
    if (val && !val.includes('ERROR')) break;
    val = null;
  }
  _idCache.set(key, val);
  return val;
};
// a few fields name a thing by its words rather than its id
const _textCache = new Map();
const realText = (field, hive) => {
  const key = `${field}|${hive}`;
  if (_textCache.has(key)) return _textCache.get(key);
  let val = null;
  if (!/^[0-9a-f-]{36}$/.test(String(hive))) return null;
  if (/^(machine|equipment|asset_name)$/i.test(field)) {
    val = psql(`select machine from logbook where hive_id = '${hive}' and machine is not null limit 1`, 2) || null;
  }
  _textCache.set(key, val);
  return val;
};

const fnDir = 'supabase/functions';
// every function that exists, NOT narrowed by --fn: a router's target must be recognisable even when
// this run was asked to look at the router alone
const ALL_FNS = readdirSync(fnDir)
  .filter((d) => !d.startsWith('_') && statSync(join(fnDir, d)).isDirectory());
const FNS = ALL_FNS.filter((d) => !ONLY_FN.length || ONLY_FN.includes(d));

const source = (fn) => { try { return readFileSync(join(fnDir, fn, 'index.ts'), 'utf8'); } catch { return ''; } };

// who calls this function? read every page, every root script, every OTHER function - and every MIGRATION.
// ★A SCHEDULED FUNCTION'S CALLER IS A CRON JOB IN A MIGRATION. A first pass over pages, scripts and function
// sources reported `failure-signature-scan` as built-and-never-called; it is invoked daily by
// `cron.schedule('failure-signature-scan-daily', ...)` in 20260712000014_arm_intelligence_crons.sql. Looking
// only where I expected the caller to be, rather than where the platform puts it, is the error this whole
// wave keeps finding - and here it would have accused a working, scheduled function.
const CALLERS = (() => {
  const hay = [];
  const add = (f) => { try { hay.push(readFileSync(f, 'utf8')); } catch { /* unreadable is not a caller */ } };
  for (const f of readdirSync('.')) if (/\.(html|js)$/.test(f)) add(f);
  for (const d of FNS) add(join(fnDir, d, 'index.ts'));
  try { for (const f of readdirSync('supabase/functions/_shared')) add(join('supabase/functions/_shared', f)); } catch { /* no shared dir */ }
  try { for (const f of readdirSync('supabase/migrations')) if (f.endsWith('.sql')) add(join('supabase/migrations', f)); } catch { /* no migrations */ }
  // ★AND THE TOOLS DIRECTORY, WHICH IS WHERE THE THIRD KIND OF CALLER LIVES. The scan was widened three
  // times and each widening removed accusations rather than adding them: pages+functions said THREE
  // functions were never called, adding migrations left ONE (`failure-signature-scan` is a daily cron job),
  // and adding tools/ left NONE - `walkthrough-analyzer`'s own header says "Called from
  // tools/analyze_walkthrough.py after every spec run", which is exactly where it is called from. A
  // built-and-never-called claim is only as good as the places it looked.
  for (const dir of ['tools', '.']) {
    try { for (const f of readdirSync(dir)) if (/\.(py|mjs|cjs|sh)$/.test(f)) add(join(dir, f)); } catch { /* skip */ }
  }
  return hay.join('\n');
})();

// ★THE TOKEN MINT NEEDS THE SAME PATIENCE AS EVERY OTHER CALL HERE. A full 62-function run died on its
// first line - "could not mint a user token" - because the local auth server was busy with a browser walk.
// Nothing about the platform was wrong; the prober asked once, at the worst moment, and gave up. Six tries
// over about a minute is the difference between a wave and a wasted run.
const token = await (async () => {
  for (let i = 0; i < 6; i++) {
    const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
      method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: PLAIN.email, password: PLAIN.password }),
    }).catch(() => null);
    const j = r ? await r.json().catch(() => ({})) : {};
    if (j.access_token) return j.access_token;
    await new Promise((res) => setTimeout(res, 10000));
  }
  return null;
})();

// ★SOME FUNCTIONS' DOCUMENTED CALLER IS NOT A PLAIN WORKER - AND THAT IS AN F QUESTION ONLY.
// batch-risk-scoring answers "Only an active supervisor of this hive can run this", export-hive-data
// "PDPA right-to-access requires active supervisor". Asked as a plain member they refuse, correctly, and
// the F lens then recorded "it never carried out its documented job" - which is false: it was never asked
// by the person the job belongs to. So F may re-ask as a SUPERVISOR, in that supervisor's OWN hive.
//
// THE HARD LINE, AND WHY: this token is minted lazily and is read by lensF ALONE. The I lens keeps the
// plain member's token for ever, because a refusal demonstrated with an elevated credential demonstrates
// nothing. For the same reason the supervisor is chosen from OUTSIDE marketplace_platform_admins - the
// only supervisor of the walker's own hive is Leandro Marquez, who is a platform admin, and a function
// that let him through would tell us about his admin rights rather than about the supervisor contract.
const SUP = (() => {
  const row = psql("select m.worker_name || '|' || u.email || '|' || m.hive_id::text from hive_members m "
    + 'join auth.users u on u.id = m.auth_uid '
    + "where m.role = 'supervisor' and m.status = 'active' "
    + 'and m.worker_name not in (select worker_name from marketplace_platform_admins) '
    + 'order by m.worker_name limit 1').split('|');
  return row.length === 3 ? { name: row[0], email: row[1], hive: row[2] } : null;
})();
let _supToken;
async function supervisorToken() {
  if (_supToken !== undefined) return _supToken;
  _supToken = null;
  if (SUP) {
    for (let i = 0; i < 3 && !_supToken; i++) {
      const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
        method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: SUP.email, password: PLAIN.password }),
      }).catch(() => null);
      const j = r ? await r.json().catch(() => ({})) : {};
      if (j.access_token) _supToken = j.access_token;
      else await new Promise((res) => setTimeout(res, 4000));
    }
  }
  return _supToken;
}
// the function said, in its own words, that the caller is not senior enough - not that the request was wrong
const NEEDS_SUPERVISOR = /\b(supervisor|hive owner|owner of this hive|admin of this hive)\b/i;

// ★AND SOME JOBS BELONG TO NO PERSON AT ALL. The escalation above rescued the functions whose documented
// caller is a SENIOR person; a second family has no human caller in its contract. pdf-ingest answers
// "Forbidden: service-role only (background drainer)", parts-staging-recommender "Forbidden: cron-only
// batch", notify-push "This ingest endpoint requires service credentials". Asked as a plain member they
// refuse, correctly - and the F lens then recorded "it never carried out its documented job", which is
// false in the same way the supervisor case was false: the job was never asked for by the caller it
// belongs to. A cron drainer's documented caller IS the service role, so declining to ask as one measures
// the probe's credentials rather than the platform's contract.
//
// THE HARD LINE IS THE SAME ONE, AND IT MATTERS MORE HERE: this key is read by lensF ALONE, and the
// self-test below fails the file if the string appears anywhere in lensI or lensA. A refusal shown with
// the service role shows nothing whatsoever - that credential is precisely the one that bypasses RLS -
// so the refusal lens keeps the plain member's token for ever, and the degradation lens keeps it too
// (elevating would change the very path it grades). Read from the edge runtime's own environment rather
// than a file, so it is never written down anywhere in this repo.
let _svcKey;
function serviceKey() {
  if (_svcKey !== undefined) return _svcKey;
  _svcKey = null;
  // ★AND DO NOT HARDCODE WHICH CONTAINER IS THE EDGE RUNTIME. The first version named
  // supabase_edge_runtime_workhive; the moment that container was replaced (recreated with an added
  // env var, the original merely STOPPED rather than removed) every service-caller escalation died with
  // "Error response from daemon: container … is not running", and two functions silently fell back to
  // the plain member's 403 - which reads as a product verdict and was an instrument outage. Ask docker
  // which edge runtime is RUNNING instead of remembering its name.
  let names = [];
  try {
    names = execSync('docker ps --format "{{.Names}}"', { encoding: 'utf8', timeout: 15000 })
      .split('\n').map((s) => s.trim()).filter(Boolean)
      .filter((n) => /edge[_-]?runtime|edge/i.test(n));
  } catch { /* docker unreachable; handled by the empty list below */ }
  for (const n of names) {
    try {
      const k = execSync(`docker exec ${n} printenv SUPABASE_SERVICE_ROLE_KEY`,
        { encoding: 'utf8', timeout: 15000 }).trim();
      if (k && k.length > 20) { _svcKey = k; break; }
    } catch { /* try the next candidate */ }
  }
  return _svcKey;
}
// the function said, in its own words, that its caller is a machine - a service key or a cron schedule
const NEEDS_SERVICE = /\b(service[- ]role|service credentials|cron[- ]only|background drainer|internal only|machine[- ]to[- ]machine)\b/i;

// ★AND NOT EVERY FIELD A FUNCTION WANTS LIVES IN THE BODY. cmms-webhook-receiver reads
// `url.searchParams.get("config_id")` and answers "config_id query param required"; the prober filled
// config_id into the JSON body, sent it, and got the identical complaint back - so the loop called it a
// dead end and the row was reported as never reaching its documented job. The function named the PLACE as
// well as the field, in the same four words, and only the field was being read.
async function call(fn, { auth, body, query, form, method = 'POST' } = {}) {
  // ★A FIELD'S TYPE IS DECIDED BY THE SOURCE, AND EVERY REPAIR MUST RESPECT IT (2026-09-10).
  // `messages` is read out of voice-model-call's own source as an ARRAY and filled with a proper chat
  // turn - and then any later complaint naming the field sent it back through valueFor(), which reads
  // the SENTENCE and not the source, and wrote a scalar over the array. Fixing one of the four
  // request sites left the other three, so the provider kept answering, precisely, "'messages.0' :
  // value must be an object with the discriminator property: 'role'" - and the function reported that
  // to its caller as "All models failed (rate limited or down)". This is the ONE place every request
  // passes through, so it is the only place the invariant can be stated once.
  if (body && !form && typeof body === 'object') {
    for (const f of arrayFields(fn)) {
      // not an array, or an array with nothing in it - both are values the function cannot work with
      if (f in body && (!Array.isArray(body[f]) || body[f].length === 0)) {
        body[f] = [nonEmptyItemFor(f, MINE)];
      }
    }
  }
  // ★`--show-request` PRINTS THE SCHEMA, NOT WHAT IS SENT. Three wrong guesses in a row about why
  // voice-model-call's providers answered "messages.0: Input should be an object" came from reading a
  // rendering of the FIELDS rather than the BODY - the schema showed `"messages":"<messages>"` for a
  // field that is filled with a real array at call time, so it could neither confirm nor refute the
  // theory. An instrument that cannot show its own last request cannot be argued with.
  if (SHOW_BODY) {
    const shown = form ? { '<multipart>': form, ...(body || {}) } : (body || {});
    console.log(`   → ${fn} ${JSON.stringify(shown).slice(0, 600)}`);
  }
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT);
  try {
    // a multipart request must NOT carry a hand-written Content-Type: the boundary is generated with the
    // body, and naming the type without it produces a request no parser can read
    const headers = form ? { apikey: ANON } : { 'Content-Type': 'application/json', apikey: ANON };
    if (auth) headers.Authorization = 'Bearer ' + auth;
    const qs = query && Object.keys(query).length
      ? '?' + new URLSearchParams(Object.entries(query).map(([k, v]) => [k, String(v)])).toString() : '';
    let payload;
    if (form) {
      payload = new FormData();
      for (const [k, v] of Object.entries(body || {})) {
        // ★THE FILE PART OWNS ITS NAME, AND THE STRING GOT THERE FIRST (2026-09-10).
        // The multipart switch marks the part name as `filled`, so the generic field-filler puts a
        // STRING into body.audio; this loop appended it, and the Blob below appended `audio` a SECOND
        // time. FormData keeps both parts and the server's `form.get("audio")` returns the FIRST -
        // the string. The real WAV was in the request all along, sitting behind a text value.
        // Invisible until the platform stopped accepting a non-file: voice-transcribe used to take the
        // string, fail deep in the audio chain and answer "All Whisper models unavailable", so the row
        // read as a provider problem. It now answers "The audio field must be a file, not a text
        // value" - a complaint about MY request, which is what it always was.
        if (k === form) continue;
        if (typeof v === 'string' || typeof v === 'number') payload.append(k, String(v));
      }
      payload.append(form, new Blob([WAV_SILENCE], { type: 'audio/wav' }), 'probe.wav');
    } else if (method !== 'GET') {
      payload = JSON.stringify(body || {});
    }
    const res = await fetch(`${EDGE}/functions/v1/${fn}${qs}`, {
      method, headers, body: payload, signal: ctl.signal,
    });
    const text = await res.text();
    let json = null; try { json = JSON.parse(text); } catch { /* not JSON is itself the finding */ }
    return { status: res.status, text, json, ok: res.ok };
  } catch (e) { return { status: 0, text: String(e.message || e), json: null, ok: false }; }
  finally { clearTimeout(t); }
}

// ★NOT EVERY 404 MEANS "THIS FUNCTION IS NOT HERE". The edge runtime answers a route it does not host with
// the plain text `Function not found`; cmms-webhook-receiver answers a config_id matching no row with its
// own JSON `{"error":"Config not found"}`. Both are 404, and reading the status alone filed the second as
// "not deployed locally" - so a function that was deployed, reachable, and telling the prober exactly what
// was wrong with the request was recorded as absent, and its contract went unasked. The difference is not
// the status, it is whether the FUNCTION is speaking: its own words come back as JSON.
const notDeployed = (r) => r.status === 404 && (!r.json || !messageOf(r));

// a sentence a person could read: not a bare code, not a stack, not empty
const HUMAN = (s) => typeof s === 'string' && s.trim().length >= 12 && /[a-z]{3,}\s+[a-z]{2,}/i.test(s) && !/^\s*</.test(s) && !/\bat\s+\w+\s*\(.*:\d+:\d+\)/.test(s);
// ★A LENS ASKING WHETHER IT SPEAKS TO A PERSON MUST NOT READ THE MACHINE CODE FIRST. This checked `error`
// before `message` and returned whichever it found - so a response carrying BOTH, which is exactly what a
// good answer looks like, was judged on its code. `login` now replies
// {"error":"missing_credentials","message":"Enter your username and password to sign in."} and was still
// reported as "a code, not a sentence", punishing the fix that had just been made. The keys are searched in
// the same order, but a value that READS AS A SENTENCE wins over one that does not; the code is the
// fallback, so a response with only a code still reports honestly.
const messageOf = (r) => {
  const j = r.json;
  if (!j) return null;
  const found = [];
  for (const k of ['error', 'message', 'detail', 'msg', 'reason', 'error_description']) {
    const v = j[k];
    if (typeof v === 'string' && v) found.push(v);
    else if (v && typeof v === 'object' && typeof v.message === 'string' && v.message) found.push(v.message);
  }
  return found.find((s) => HUMAN(s)) || found[0] || null;
};

// ★A COMPLAINT ABOUT MY REQUEST IS NOT A REFUSAL OF MY PERSON. The first version counted every 4xx as a
// refusal, so `Missing or invalid op (must be "recall" or "store")` — the function telling me I had left a
// field out — was banked on 43 of 62 functions as proof that the platform refuses an outsider. It proves
// nothing of the sort: the request died on its SHAPE, before anything looked at whose hive it named. A 405
// (my method was wrong) and a 429 (I was rate-limited) were counted the same way. Fourteen of those 62
// readings were real; the rest were the probe reading its own mistake as the product's virtue.
//
// Two repairs. First, the function TEACHES THE PROBE ITS OWN SHAPE: the missing field is read out of the
// complaint, filled in, and the question asked again, up to five times. Second, the verdict rests on a
// DIFFERENTIAL — the same well-formed request sent twice, changing one thing only, whose hive it names. An
// answer for my own hive and a refusal for the other is entitlement. The same complaint for both is a
// question that was never asked, and that is reported as unanswered, never as a pass.
const ENTITLED = /\b(permission|not allowed|forbidden|unauthori[sz]ed|access denied|denied|not a member|membership|another hive|different hive|other hive|your hive|this hive|entitl|not yours|sign in|signed in|authenticat|admin only|owner only)\b/i;
// ★A COMPLAINT USUALLY NAMES MORE THAN ONE FIELD, AND THE READER TOOK THE FIRST WORD IT SAW. Against
// "Missing required fields: question, asset_id, hive_id" the old pattern matched the word "field" inside
// "fields", then captured the leftover "s" - so the probe added a field called `s`, learned nothing, and
// gave up. That single bug accounts for 98 of the 108 contracts this run could not answer. Read EVERY name
// the complaint lists, in all the shapes this platform writes them.
const _LIST = String.raw`[A-Za-z_][\w]*(?:\s*(?:,|\band\b|\bor\b)\s*[A-Za-z_][\w]*)*`;
const NEEDS = [
  // "Missing or EMPTY transcript" - the alternatives a platform actually writes, not just "or invalid".
  // Reading only "or invalid" made the capture land on the word "or", which the stoplist then threw away,
  // and four voice functions went unanswered one word from an answer.
  // ★"OR TOO SHORT" IS THE SAME SENTENCE AS "OR EMPTY", AND IT WAS NOT IN THE LIST. voice-logbook-entry
  // guards `transcript.trim().length < 5` and answers "Missing or too short transcript". The alternation
  // knew invalid/empty/blank/malformed/null/undefined but not "too short", so the field never parsed, the
  // loop broke on the first reply, and the row read "after a plain request" - as though the function had
  // been asked properly and refused. It had not been asked at all. Given a real sentence it answers 200
  // and writes the entry, which is the whole claim. Any "too <adjective>" belongs here for the same reason.
  new RegExp(String.raw`missing(?:\s+or\s+(?:invalid|empty|blank|malformed|null|undefined|too\s+\w+))?(?:\s+required)?(?:\s+(?:body\s+)?(?:fields?|parameters?|params?|properties|property|keys?|arguments?))?\s*:?\s+(${_LIST})`, 'i'),
  new RegExp(String.raw`(${_LIST})\s+(?:query\s+param(?:eter)?\s+|parameter\s+|field\s+)?(?:is|are)?\s*required`, 'i'),
  new RegExp(String.raw`must\s+include\s+(${_LIST})`, 'i'),
  // ★"UNKNOWN AGENT" IS A FIELD NAME TOO. The reader knew "missing" and "invalid" only, so when ai-gateway
  // came back with "Unknown agent 'status'. Available: asset, …" - its second, more helpful reply - the
  // field could not be read out of it and the whole exchange was abandoned one step from an answer.
  /(?:unknown|unrecogni[sz]ed|unsupported|invalid)\s+["'`]?([a-zA-Z_][\w]*)["'`]?/i,
  // ★"<field> MUST BE x OR y" NAMES THE FIELD AND ITS VALUES IN ONE SENTENCE. resume-extract answers
  // "kind must be 'image' or 'text'" - it is handing over the field AND the vocabulary - and no pattern
  // here read it, so three contracts went unanswered against a function that had already said what it
  // wanted. valueFor already knows how to pick from a quoted list; it was never given the field.
  new RegExp(String.raw`\b([a-z_][\w]*)\s+must\s+be\b`, 'i'),
  // ★AND SOME OF THEM PUT THE NAME FIRST. resume-extract, once its `kind` was accepted, answered
  // "payload missing" - two words, the field and the complaint, in the order the other patterns do not
  // read. Every pattern above expects "missing" or "required" to come first or last with grammar in
  // between; this is the plainest form on the platform and had no reader.
  new RegExp(String.raw`\b([a-z_][\w]*)\s+(?:is\s+)?(?:missing|empty|blank|not\s+set)\b`, 'i'),
];
// words that are grammar, not field names - a capture landing on one of these is the reader misfiring
// `missing`/`invalid` are here because pattern 2 reads "<names> are required" and the sentence
// "Missing required fields: ..." ALSO ends in "required" - so it captured the word Missing itself.
const NOT_A_FIELD = /^(?:s|the|a|an|is|are|and|or|required|field|fields|param|params|parameter|parameters|body|values|must|be|to|of|in|for|this|that|one|any|all|it|its|not|no|missing|invalid|unknown|unsupported|unrecognised|unrecognized)$/i;
// ★AND THE STOPLIST WAS EATING A REAL FIELD NAME. `payload` and `value` sit in NOT_A_FIELD because the
// loose "<names> are required" pattern can capture grammar - but data-fabric-normalizer answers "Missing
// required field: payload (object)", naming a field genuinely called payload, and it was thrown away on
// every one of six retries. The stoplist protects the LOOSE readings; a name the function introduced with
// the word "field" is not a guess, so the explicit pattern is trusted over the stoplist.
const EXPLICIT_FIELD = /\b(?:field|parameter|param|property|key)s?\s*:/i;
const wantedFields = (msg) => {
  const s = String(msg || '');
  const out = [];
  const explicit = EXPLICIT_FIELD.test(s);
  for (let i = 0; i < NEEDS.length; i++) {
    const m = NEEDS[i].exec(s);
    if (!m || !m[1]) continue;
    // only the first pattern reads the "…field: <name>" form; a stoplisted word is a real name there
    const trusted = explicit && i === 0;
    for (const raw of m[1].split(/\s*(?:,|\band\b|\bor\b)\s*/)) {
      const f = raw.trim();
      if (f.length > 1 && (trusted || !NOT_A_FIELD.test(f)) && !out.includes(f)) out.push(f);
    }
  }
  return out;
};
const wantedField = (msg) => wantedFields(msg)[0] || null;   // kept for the teeth tests
// ★A PROBE MUST NEVER PICK THE OPTION THAT WRITES. When a function lists what it will accept — `must be
// "recall" or "store"` — taking the first one would have this probe STORING rows in a stranger's hive to
// find out whether it is allowed to read one. A reading verb is preferred every time, and only if none is
// offered does the first option stand.
const READS = /^(recall|read|get|list|status|view|fetch|query|search|summary|health|check)$/i;
// ★AND THE WHOLE-WORD TEST CANNOT SEE INSIDE A HYPHENATED NAME - WHICH IS A SAFETY GAP, NOT A NUISANCE.
// platform-gateway offers routes like "semantic-search", "send-report-email" and "pdf-ingest"; READS
// matches none of them, so the probe fell through to "the first option", which is whatever the function
// happened to declare first. On this gateway that was a transcription route; on the next one it could as
// easily be the route that SENDS THE EMAIL. The rule the file already states - never pick the option that
// writes - has to survive the naming convention, so read the parts of a name and prefer a reader outright
// while actively avoiding anything that announces a side effect.
const WRITES_PART = /\b(create|insert|add|write|update|delete|remove|purge|drop|reset|send|push|email|ingest|sync|import|export|retrain|publish|revoke)\b/i;
const READS_PART = /\b(search|read|get|list|status|view|fetch|query|summary|health|check|api|recall|report)\b/i;
const parts = (v) => String(v).split(/[-_.\s]+/).filter(Boolean);
// ★AND WHEN A FUNCTION OFFERS TWO WAYS IN, TAKE THE ONE YOU CAN ACTUALLY SUPPLY. resume-extract accepts
// `kind` of 'image' or 'text' and reads the body from `payload` either way; the probe took 'image' because
// it came first, and then owed a real photograph before a single line of the function's work could run. The
// 'text' branch needs a sentence, which the probe has always had. Choosing the branch with the cheapest
// fixture is not cheating - both are the documented job, and the one that can be asked is the one that
// answers. A binary medium is the LAST resort, never the default.
const MEDIA_PART = /\b(image|photo|picture|audio|voice|video|file|binary|upload|scan|pdf)\b/i;
const pickOption = (options) => {
  const safe = options.filter((v) => !parts(v).some((p) => WRITES_PART.test(p)));
  const pool = safe.length ? safe : options;
  const cheap = pool.filter((v) => !parts(v).some((p) => MEDIA_PART.test(p)));
  const tier = cheap.length ? cheap : pool;
  return tier.find((v) => READS.test(v))
      || tier.find((v) => parts(v).some((p) => READS_PART.test(p)))
      || tier[0];
};

// ★AND ONE FUNCTION DOES NOT WANT JSON AT ALL. voice-transcribe answers "Expected multipart/form-data
// with audio field" to every request this prober has ever sent it, because the prober only knows how to
// post JSON - so the row read "never reached the claim" when the truth was that it had never been asked
// in the language it speaks. A real, decodable WAV: a 44-byte RIFF header over a short run of silence,
// built from bytes here so no escape or copy-paste can quietly corrupt it into something that is merely
// named .wav. Silence is honest input for a transcriber - it has nothing to say and should say so.
function wavSilence(ms = 200, rate = 8000) {
  const n = Math.round((rate * ms) / 1000);
  const b = Buffer.alloc(44 + n);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n, 4); b.write('WAVE', 8);
  b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(rate, 24); b.writeUInt32LE(rate, 28); b.writeUInt16LE(1, 32); b.writeUInt16LE(8, 34);
  b.write('data', 36); b.writeUInt32LE(n, 40);
  b.fill(128, 44);                                   // 8-bit PCM silence sits at the midpoint, not at 0
  return b;
}
const WAV_SILENCE = wavSilence();

// a real, decodable 1x1 PNG - the smallest thing that is genuinely an image rather than a string that
// merely starts with "data:". Built from bytes rather than pasted, so no escape can quietly corrupt it.
const PNG_1PX = 'data:image/png;base64,' + Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
  0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
  0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
  0x42, 0x60, 0x82,
]).toString('base64');

// ★A FUNCTION THAT LISTS WHAT IT ACCEPTS IS ANSWERING THE QUESTION I ASKED, however it punctuates the
// list: "Available: a, b", `must be "recall" or "store"`, "one of day, week, month", "Use parts, training,
// or jobs", "one of 06-14 / 14-22 / 22-06". Lifted out of valueFor so the SAME reading can run early -
// before a database guess can pre-empt a vocabulary the function stated outright - and be pinned by teeth.
const _cleanOpt = (v) => v.trim().replace(/^["'`]+|["'`]+$/g, '').replace(/[.;:]+$/, '').trim();
const _splitOpts = (t) => t.split(/[,;/]|\bor\b/).map(_cleanOpt).filter((v) => /^[A-Za-z0-9][\w .-]{0,30}$/.test(v));
function optionsIn(s) {
  const listed = /available:\s*([^.\n]+)/i.exec(s);
  if (listed) { const o = _splitOpts(listed[1]); if (o.length) return o; }
  if (/must be|one of|expected|accepts?|either/i.test(s)) {
    const quoted = [...s.matchAll(/["'`]([A-Za-z0-9][\w .-]{1,30})["'`]/g)].map((m) => m[1]);
    if (quoted.length) return quoted;
  }
  const unquoted = /(?:must be\s+)?one of\s*\(?\s*([^)\n]+)/i.exec(s) || /\buse\s+([^.\n]+)/i.exec(s);
  if (unquoted) { const o = _splitOpts(unquoted[1]); if (o.length) return o; }
  // ...and a list can skip "one of" entirely: "must be 06-14, 14-22, or 22-06". This shape is read only
  // when the tail actually LOOKS like a list - it must carry a comma or a slash, and every member must be
  // a bare token - so that "limit must be a number" and "must be a valid email, and not empty" are not
  // mistaken for vocabularies. A phrase is prose; a comma-separated run of tokens is a menu.
  const bare = /must be\s+([^.\n]*[,/][^.\n]*)/i.exec(s);
  if (bare) {
    const o = _splitOpts(bare[1]).filter((v) => /^[A-Za-z0-9][\w.-]{0,30}$/.test(v));
    if (o.length >= 2) return o;
  }
  return [];
}

// A short but GENUINE resume: a name, two dated roles with duties, a certificate and skills - the
// smallest text an extractor can actually do its documented job on. Deliberately a Filipino industrial
// maintenance CV, because that is the document this platform's Resume Builder exists for, and an
// extractor tuned to it should find every field. Kept plain-text: the `text` branch is the one whose
// fixture the probe can always supply, per the branch-choice note further down.
const RESUME_TEXT = [
  'ROBERTO M. SANTOS',
  'Maintenance Technician | Batangas City | roberto.santos@example.invalid',
  '',
  'EXPERIENCE',
  'Senior Maintenance Technician, Manila Electronics Assembly (March 2021 - present)',
  '- Led preventive maintenance on 12 SMT pick-and-place machines, cutting unplanned downtime by 30%.',
  '- Diagnosed and repaired conveyor gearbox failures; wrote the standard repair procedure now in use.',
  '- Trained four junior technicians on lockout/tagout and vibration screening.',
  '',
  'Maintenance Technician, Lucena Pharmaceutical Mfg. (June 2017 - February 2021)',
  '- Maintained tablet presses, blister packers and HVAC for a GMP clean area.',
  '- Kept the calibration register for 40 instruments and passed two FDA audits with no findings.',
  '',
  'CERTIFICATIONS',
  'TESDA NC II Mechatronics Servicing (2016). DOLE-accredited Safety Officer 2 (2019).',
  '',
  'SKILLS',
  'Preventive maintenance, vibration analysis, hydraulics, PLC troubleshooting, welding, MS Excel.',
].join('\n');

const valueFor = (field, msg, hive) => {
  const s = String(msg || '');
  // ★A FUNCTION THAT NAMES THE TYPE IT WANTS IS STILL ANSWERING THE QUESTION. Three of them reply
  // "Missing required field: payload (object)" or "(array)", and a string was posted back at them every
  // time, so the same complaint returned and the loop gave up - the function spelling out exactly what
  // it needed, and the probe not hearing the last two words. The same reading as the "Available:" list
  // and the "one of" list already handled below, applied to the TYPE rather than the value.
  const typed = new RegExp('\\b' + field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b[^.\\n]{0,24}\\((object|array|number|boolean)\\)', 'i').exec(s);
  if (typed) {
    const t = typed[1].toLowerCase();
    if (t === 'object')  return {};
    if (t === 'array')   return [];
    if (t === 'number')  return 1;
    if (t === 'boolean') return true;
  }
  // ★AND THE SHAPE IS IN THE MESSAGE, NOT IN THE FIELD NAME. cold-archive-query asks for
  // "time_range.{from,to}" - the field list pattern stops at the dot, so what arrives here is
  // `time_range` and the sub-keys the function actually reads are lost. The braces ARE the function
  // telling you the object it wants, so they are read off the message rather than guessed.
  const nested = new RegExp(field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\.(?:\\{([^}]+)\\}|([A-Za-z_][\\w]*))').exec(s);
  if (nested) {
    const keys = (nested[1] || nested[2] || '').split(/\s*,\s*/).map((k) => k.trim()).filter(Boolean);
    if (keys.length) {
      const obj = {};
      for (const k of keys) obj[k] = /^(from|start|since|after)$/i.test(k)
        ? new Date(Date.now() - 30 * 86400000).toISOString()
        : /^(to|end|until|before)$/i.test(k) ? new Date().toISOString()
        : /^(days|count|limit|n)$/i.test(k) ? 30
        : realText(k, hive) || realId(k, hive) || 'probe';
      return obj;
    }
  }
  // ★AND SOME NAME THE TYPE WITHOUT PARENTHESES. "Missing or invalid texts array" and "Missing or too
  // short transcript" are each a function saying precisely what is wrong with the value it got - one
  // wants a list, the other wants more words - and both were answered with the same short placeholder,
  // so the same complaint came back and the loop called it a dead end.
  if (new RegExp(field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s+(?:array|list)\\b', 'i').test(s)) {
    // ★TWO PATHS BUILD AN ARRAY HERE AND ONLY ONE WAS TAUGHT THE SHAPE (2026-09-10). This
    // field-specific branch fires FIRST for "Missing or invalid messages array" and returned
    // `[realText(field) || 'probe']` - a list holding the word "probe". The generic `\barrays?\b`
    // branch further down was fixed to use nonEmptyItemFor and never got a chance to run, so every
    // provider in voice-model-call's chain kept answering "messages.0: Input should be an object"
    // through four separate repairs of the WRONG path. A member's SHAPE is nonEmptyItemFor's job in
    // both branches, or the one that fires first quietly wins.
    return [nonEmptyItemFor(field, hive)];
  }
  if (/\btoo\s+short\b/i.test(s)) {
    return (realText(field, hive) || 'probe')
      + ' - a sentence long enough to satisfy a minimum-length check, written by the contract prober';
  }
  // ★THE VOCABULARY THE FUNCTION STATES OUTRANKS ANYTHING I CAN GUESS FROM THE DATABASE. The option list
  // was read LAST, below a lookup that invents a plausible-looking value from a real row - so for any
  // field whose name that lookup recognised, a function spelling out "must be one of A, B, C" was answered
  // with D. A guess is what you reach for when nothing was stated; here something was stated.
  // ★A FIELD THAT WANTS A PICTURE CANNOT BE ANSWERED WITH A WORD. visual-defect-capture and
  // gcash-receipt-ocr both name the format outright - "image_data_url must be data: URL or https://",
  // "Could not read that image file" - and both were handed the string 'probe', so neither ever got past
  // its own front door. This is a real 1x1 PNG, small enough to inline and valid enough to decode, so the
  // request reaches the function's actual work instead of dying on the shape.
  if (/data[_-]?url|image|photo|picture|attachment|file_?url/i.test(field) || /data:\s*URL|image file|image_data/i.test(s)) {
    return PNG_1PX;
  }
  // ★A DATE FIELD AT THE TOP LEVEL IS THE SAME FIELD AS ONE INSIDE time_range. The nested reader above
  // already knows that `from` wants an ISO date and `to` wants today; temporal-rag-orchestrator declares
  // the very same pair as plain `from?: string; to?: string`, and they fell through to the text lookup, so
  // it answered "Those from and to dates are not valid." The shape a name implies does not change with its
  // depth. A window that starts in the past and ends now is the only one that can return anything.
  if (/^(from|start|since|after|start_date|from_date|begin)$/i.test(field)) {
    return new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);
  }
  if (/^(to|end|until|before|end_date|to_date)$/i.test(field)) {
    return new Date().toISOString().slice(0, 10);
  }
  if (/(_at|_date|_on)$/i.test(field)) return new Date().toISOString();
  const stated = optionsIn(s);
  if (stated.length) return pickOption(stated);
  // a field whose NAME states its format - send-report-email validates with isValidEmail() and would have
  // refused a person's name, which is exactly what the database lookup below would have handed it. The
  // .invalid TLD is reserved by RFC 2606 and can never route, so a probe can never post real mail.
  if (/e?mail$/i.test(field) || /(recipient|sender|to)_e?mail/i.test(field)) return 'contract-prober@example.invalid';
  const words = realText(field, hive);
  if (words) return words;
  if (/(_id|Id|uuid|_uuid)$/.test(field)) {
    if (/^hive(_id)?$/i.test(field)) return hive;
    return realId(field, hive) || hive;      // a real row of that kind, or the hive when there is none
  }
  // ★A FUNCTION THAT LISTS WHAT IT ACCEPTS IS ANSWERING THE QUESTION I ASKED. `ai-gateway` replies
  // "Unknown agent 'status'. Available: asset, …" - it is handing over its own vocabulary, and the first
  // version threw that away and reported the function as unanswerable. Read the list it offers.
  // ★AND HALF OF THEM LIST THE VALUES WITHOUT QUOTING THEM. The first version read `Available: a, b` and
  // quoted options after "must be", and missed the two commonest shapes on this platform:
  //   "Missing or invalid level (must be one of day, week, month)"   - one of, UNQUOTED
  //   "Unknown section. Use parts, training, or jobs."               - "Use", not a trigger word at all
  // Four functions were reported unanswerable for that reason alone, each while spelling out exactly what
  // it wanted. A function that lists what it accepts is answering the question I asked, however it phrases
  // the list.
  // ★AND A LIST CAN BE SEPARATED BY A SLASH, AND ITS MEMBERS CAN START WITH A DIGIT. shift-planner
  // replies "shift_window must be one of 06-14 / 14-22 / 22-06" - it is handing over its whole vocabulary
  // and the reader threw all of it away twice over: the splitter knew commas, semicolons and the word
  // "or" but not the slash this function uses, and the value filter demanded a leading LETTER, so every
  // one of its three windows failed the test even after a correct split. The function was reported as
  // never reaching its documented job while spelling out, in the same sentence, the only three values it
  // would ever accept. A list is a list however it is punctuated, and a time window is a legal name.
  // ★AN EMPTY ARRAY SATISFIES `Array.isArray` AND NOTHING ELSE (2026-09-10). This returned `[]` for
  // any complaint naming an array, so voice-model-call's "Missing or invalid messages array" was
  // answered with a list containing no turns. That passes the function's own guard, reaches the
  // provider, and is refused there - and the function reports the refusal as "All models failed
  // (rate limited or down)". Every top-up downstream also skips it, because it IS an array. The
  // sibling helper `nonEmptyItemFor` exists for exactly this - "an array field guarded by
  // .length === 0 needs a MEMBER" - and was simply never reached from here.
  if (/\barrays?\b/i.test(s)) return [nonEmptyItemFor(field, hive)];
  // PLURALS. "p_threshold and f_threshold must be finite numbers." carries the type in the clearest
  // words a function can use, and `\bnumber\b` cannot match "numbers" - one letter between a well-formed
  // request and three rows reported as never reaching their claim. A complaint about two fields at once
  // is naturally plural, so the plural is the COMMON case here, not the edge one.
  if (/\b(numbers?|integers?|numerics?|ints?|finite|decimals?|floats?)\b/i.test(s)) return 5;
  // ★A FIELD THAT CARRIES A DOCUMENT NEEDS A DOCUMENT (2026-09-10). `payload` on resume-extract fell
  // all the way to the 'status' fallback below - six characters where a resume belongs - so the
  // extractor asked a model to find jobs, skills and certificates in the word "status", got `{}` back,
  // and answered "Could not read this file. Try a clearer photo or a different file." The row was then
  // filed as an AI-provider ceiling, which a falsification test disproved: resume-polish answered 200
  // from the SAME provider chain minutes later. It is the same lesson as the decodable WAV and the real
  // PNG above - a fixture must be the KIND of thing the field is for, or the function's own honest
  // complaint about the input gets recorded as a platform fault.
  // Placed LAST on purpose: every function that STATES what its payload should be (an object, an array,
  // a data: URL) is answered by a rule above, so only a function that names the field and says nothing
  // about its type reaches here.
  if (/^(payload|resume|document|body|content|raw_?text|full_?text|resume_?text)$/i.test(field)) return RESUME_TEXT;
  return 'status';
};

// ★THE FUNCTION ALREADY WROTE DOWN WHAT IT NEEDS - READ IT BEFORE ASKING. Discovering required fields by
// trial works, but it costs one round trip per field and gives up whenever a complaint is phrased in a way
// the reader does not know. 37 of the 62 functions carry their own "Missing …" strings in source, and 53
// guard with `if (!x)`; those literals are the SAME words the runtime sends back, so they can be read
// statically and the FIRST request built already well-formed. This is what the 107 withdrawn rows need:
// they were given back because the request never reached the claim, not because the claim was false.
// ★AND THE COMPLAINT THAT NAMED THE FIELD IS ALSO THE COMPLAINT THAT DESCRIBES IT. The pre-fill built its
// value from a synthesised `Missing <field>`, throwing away the very sentence it had just read the name
// out of - so every hint the function had written down (a type, an option list, a minimum length) was lost
// at exactly the moment it was most useful, and the first ask went out wrong on purpose. Keep the words.
const _declared = new Map();
// ★THE STOPLIST IS FOR PROSE, AND THE READERS BELOW READ CODE. NOT_A_FIELD exists so that "Missing
// required parameter: x" does not yield the word "parameter" - English filler around the real name. But
// `body.parameter` is not filler: pf-calculator genuinely reads a field CALLED parameter, validates it
// against a name pattern, and answered "The parameter name is wrong" to a request that never carried one,
// because the reader had struck the name out on sight. Code does not pad its property names with
// connecting words, so a name lifted from source is always a real name. Same trap as `payload`, which had
// to be rescued from this list once already - the third occurrence is the one that names the class.
function declaredFields(fn) {
  if (_declared.has(fn)) return _declared.get(fn);
  const src = source(fn);
  const out = [];
  const said = new Map();
  const take = (msg) => {
    for (const f of wantedFields(msg)) {
      if (!out.includes(f)) { out.push(f); said.set(f, msg); }
    }
  };
  // every complaint string the function itself can emit, read with the same reader used on live replies
  for (const m of src.matchAll(/["'`]((?:Missing|Invalid|Unknown|Unsupported)[^"'`]{2,90})["'`]/gi)) take(m[1]);
  for (const m of src.matchAll(/["'`]([^"'`]{2,60}?(?:is|are)\s+required)["'`]/gi)) take(m[1]);
  // ★AND A FUNCTION CAN DECLARE ITS BODY WITHOUT EVER COMPLAINING IN THOSE WORDS. gcash-receipt-ocr says
  // only "Could not read that image file. Try a clearer photo." - kind to the person, and naming no field
  // at all, so neither the source reader nor the live reader could learn what to send and the request went
  // out empty every time. One line above the message the function writes
  // `let body: { image_data_url?: string }`, which is the whole contract, stated in TypeScript instead of
  // English. Read the type: it is the same declaration, and it is the one shape a function cannot forget
  // to keep in step with itself.
  for (const decl of src.matchAll(/\bbody\s*:\s*\{([^}]{2,400})\}/g)) {
    for (const f of decl[1].matchAll(/([A-Za-z_]\w*)\s*\??\s*:/g)) {
      if (!out.includes(f[1])) { out.push(f[1]); said.set(f[1], `Missing ${f[1]}`); }
    }
  }
  // ★AND THE KINDEST FUNCTIONS ARE THE HARDEST TO ASK. platform-gateway reads `body.fn` and answers
  // "That request did not say which platform action to run. Reload the page and try again." - a message
  // whose own source comment explains it was CHANGED from "Missing fn" because naming an internal field
  // tells a person nothing they can act on. That is the right call for the product and it means the field
  // name is deliberately absent from every sentence the function will ever say. So read the property the
  // code reaches for: `<parsedBody>.<field>`, wherever the body came from req.json().
  const bodyVars = new Set(['_whBody']);
  for (const v of src.matchAll(/(?:const|let|var)\s+([A-Za-z_]\w*)\s*(?::[^=]{0,80})?=\s*await\s+req\.json\(\)/g)) bodyVars.add(v[1]);
  for (const v of bodyVars) {
    for (const m of src.matchAll(new RegExp(`\\b${v}\\s*\\.\\s*([A-Za-z_]\\w*)`, 'g'))) {
      if (!out.includes(m[1])) { out.push(m[1]); said.set(m[1], `Missing ${m[1]}`); }
    }
  }
  // ...and destructuring the parsed body names the same fields: `const { a, b } = await req.json()`
  for (const d of src.matchAll(/const\s*\{([^}]{2,200})\}\s*=\s*(?:await\s+req\.json\(\)|_whBody)/g)) {
    for (const f of d[1].split(',').map((x) => x.split(/[:=]/)[0].trim())) {
      if (/^[A-Za-z_]\w*$/.test(f) && !out.includes(f)) { out.push(f); said.set(f, `Missing ${f}`); }
    }
  }
  const fields = out.slice(0, 8);
  _declared.set(fn, { fields, said });
  return _declared.get(fn);
}

// which fields the function's OWN source insists are arrays - `Array.isArray(x)`, `x.length === 0`, or a
// TypeScript field typed `x: Array<…>` / `x: T[]`. Read from the same file declaredFields() already reads.
const _arrayFields = new Map();
function arrayFields(fn) {
  if (_arrayFields.has(fn)) return _arrayFields.get(fn);
  const src = source(fn);
  const out = [];
  const add = (f) => { if (f && !out.includes(f)) out.push(f); };
  for (const m of src.matchAll(/Array\.isArray\(\s*([A-Za-z_]\w*)\s*\)/g)) add(m[1]);
  for (const m of src.matchAll(/\b([A-Za-z_]\w*)\s*:\s*(?:Array<|\w+\s*\[\])/g)) add(m[1]);
  // ★AN ARRAY-SHAPED LOCAL IS NOT A REQUEST FIELD (2026-09-10, found by --show-request). Unrestricted,
  // this matched every array anywhere in the file and the caller then INVENTED those names into the
  // payload: engineering-calc-agent was being sent `COMPRESSOR_HP_CFM`, `HUNTERS_CURVE`,
  // `CABLE_REACTANCE_OHM_KM` and `WATER_SPEC_VOL` - its own internal constant TABLES - and
  // resume-extract got `orphanWork`, `mined` and `chunks`, which are locals in its parser. Harmless
  // where a function ignores unknown keys and not harmless at all where one rejects them, and pure
  // noise in every receipt either way. numberFields, its twin written later, already carries this exact
  // guard in its docstring - "restricted to names the body reader already declared, so a numeric LOCAL
  // never gets invented into the payload". The fix was made once and not to both.
  const declaredNames = new Set(declaredFields(fn).fields);
  _arrayFields.set(fn, out.filter((f) => declaredNames.has(f)).slice(0, 8));
  return _arrayFields.get(fn);
}

// ★A FUNCTION THAT DISPATCHES ON A FIELD HAS WRITTEN THAT FIELD'S WHOLE VOCABULARY DOWN, IN CODE.
// valueFor ends in `return 'status'` - a last-resort word for a field whose shape nothing could infer -
// and that word was being POSTED as a calculation type. engineering-calc-agent answered `Calculation type
// "status" not yet implemented` and engineering-bom-sow `BOM+SOW not yet available for status / status`;
// both were filed as "never carried out its documented job here", which reads as an accusation and was
// entirely the prober's sentence. Neither function is vague about what it accepts: one is a chain of
// `calc_type === "HVAC Cooling Load"`, the other of `discipline === "Mechanical" && calc_type === "…"`.
// That chain is an enumeration - stronger than any guess a name can support, and it cannot drift out of
// step with the code because it IS the code.
//
// ★AND A CONJUNCTION IS ONE BRANCH, SO ITS VALUES MUST TRAVEL TOGETHER. Picking `discipline` from the
// first branch and `calc_type` from the fourth would build a pair the function has no arm for, and the
// reply - "not available for Mechanical / Wire Sizing" - would look exactly like a product gap. Read the
// whole condition or none of it.
//
// Deliberately NOT read: `!==`, `||`, and any branch whose literal names a destructive verb. A negation
// says what a field is not, an alternation is two branches wearing one condition, and a probe must never
// pick the arm that deletes (the same rule pickOption already follows for a live option list).
const DESTRUCTIVE = /\b(delete|remove|purge|reset|destroy|revoke|wipe|drop|truncate|cancel|deactivate|disable)\b/i;
const _dispatch = new Map();
function dispatchBranch(fn) {
  if (_dispatch.has(fn)) return _dispatch.get(fn);
  const src = source(fn);
  const declared = new Set(declaredFields(fn).fields);
  const arrays = new Set(arrayFields(fn));
  const eligible = (f) => declared.has(f) && !arrays.has(f);
  let best = null;
  const out = {};
  // ★A GUARD WRITTEN AS A REJECTION IS STILL A WHITELIST, AND IT IS THE COMMONER SHAPE. resume-extract
  // guards `if (kind !== "image" && kind !== "text") return json({error: "kind must be 'image' or 'text'"})`
  // - a conjunction of `!==` against ONE field, which enumerates the allowed set exactly and completely.
  // Skipping every negation on the principle that "a negation says what a field is not" threw away the
  // most precise statement in the file: this one says what it is, twice over. The rule is narrow on
  // purpose - ALL the comparisons must be `!==` against the SAME field, so a mixed condition (which
  // really is saying something else) is still left alone.
  for (const m of src.matchAll(/(?:^|[^\w.])if\s*\(([^()]{4,300})\)/g)) {
    const cond = m[1];
    if (!/!==/.test(cond) || /\|\|/.test(cond)) continue;
    const neg = [...cond.matchAll(/([A-Za-z_]\w*)\s*!==\s*["'`]([^"'`\n]{1,60})["'`]/g)];
    const eq = [...cond.matchAll(/[^!=]===\s*["'`]/g)];
    if (neg.length < 2 || eq.length) continue;
    const field = neg[0][1];
    if (!neg.every((n) => n[1] === field) || !eligible(field) || field in out) continue;
    const allowed = neg.map((n) => n[2]).filter((v) => !DESTRUCTIVE.test(v));
    // ★AND A PROBE MUST NOT PICK THE ARM IT CANNOT HONESTLY FEED. `kind: "image"` obliges the request to
    // carry a real picture in a sibling field this reader has no way to recognise, so choosing it means
    // failing on the payload and reporting THAT as the function's fault. `text` is the same contract with
    // a payload a JSON probe can actually produce. Same family as pickOption's rule that a probe never
    // picks the option that WRITES: prefer the arm the probe can satisfy, and only then the first.
    const MEDIA = /^(image|photo|picture|audio|video|file|pdf|binary|attachment|voice|scan)$/i;
    const speakable = allowed.filter((v) => !MEDIA.test(v));
    if (allowed.length) out[field] = (speakable[0] || allowed[0]);
  }
  for (const m of src.matchAll(/(?:^|[^\w.])if\s*\(([^()]{4,300})\)\s*\{/g)) {
    const cond = m[1];
    if (/!==|!=|\|\|/.test(cond)) continue;
    const pairs = [];
    for (const c of cond.matchAll(/([A-Za-z_]\w*)\s*===\s*["'`]([^"'`\n]{1,60})["'`]/g)) {
      if (eligible(c[1]) && !DESTRUCTIVE.test(c[2]) && !pairs.some((p) => p[0] === c[1])) pairs.push([c[1], c[2]]);
    }
    // the FIRST arm that names a declared field is the function's own primary path; a later arm is an
    // alternative to it, not a better description of it
    if (pairs.length && (!best || pairs.length > best.length)) best = pairs;
    if (best && best.length >= 2) break;
  }
  for (const [f, v] of best || []) if (!(f in out)) out[f] = v;
  // `switch (field) { case "literal":` says the same thing in the other syntax, and fills in any field
  // the if-chain never mentioned
  for (const m of src.matchAll(/switch\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\{\s*(?:\/\/[^\n]*\n\s*)*case\s*["'`]([^"'`\n]{1,60})["'`]/g)) {
    if (eligible(m[1]) && !(m[1] in out) && !DESTRUCTIVE.test(m[2])) out[m[1]] = m[2];
  }
  _dispatch.set(fn, out);
  return out;
}

// ★A REPLY BUILT FROM A VARIABLE STILL DECLARES ITS SHAPE - just not on the stringify line. Four
// functions answered 200 and were recorded as "its source builds the reply from a variable rather than
// a literal, so nothing is claimed", which reads like a fault in them and was a gap in this reader. The
// same TypeScript that `declaredFields` already trusts for the REQUEST (`body: { … }`) is written for
// the RESPONSE too: voice-report-intent declares `let parsed: { report_types: string[]; recipient_hint:
// string | null; … }` and then answers `JSON.stringify(parsed)`. That is a contract, in the one form
// that cannot drift out of step with the code.
//
// AND THE HONEST LIMIT, WHICH IS WHY THIS DOES NOT TRY HARDER: project-orchestrator answers
// `json(out)` where `out = await runIntent(...)` and runIntent is typed
// `Promise<Record<string, unknown>>` - an OPEN record. It declares no fixed key set, so "the shape
// cannot be read" is the true verdict there, not a reader failure. Chasing it through the producer hop
// would only manufacture a key list the function never promised. A function whose shape is genuinely
// open has to earn its F row on its persisted effect instead.
// ★A CAP ON AN OBJECT LITERAL TRUNCATES THE ONE SHAPE THAT MATTERS (2026-09-10). Call sites were read
// with `\{([^}]{2,300})\}`, which stops at the first `}` and gives up past 300 characters - and a
// function's SUCCESS literal is reliably the longest object in its file (more keys, nested objects,
// explanatory comments), while its error literals are one line. asset-brain-query's success reply spans
// ~330 characters and nests `asset: { tag, name }`, so the reader skipped it entirely and judged the
// function against its 400-handler alone. Read the balanced braces instead of guessing a length: the
// object ends where it ends.
function objectAt(src, open, L = '{', R = '}') {
  if (src[open] !== L) return null;
  let depth = 0;
  for (let i = open; i < src.length && i < open + 8000; i++) {
    if (src[i] === L) depth++;
    else if (src[i] === R) { depth--; if (!depth) return src.slice(open + 1, i); }
  }
  return null;
}

// split an argument or parameter list on its TOP-LEVEL commas. `Record<string, string>` is one parameter
// and `{ a: 1, b: 2 }` is one argument; a plain `.split(',')` makes three of the pair and would name the
// wrong thing at every position. Angle brackets are counted too, because a parameter list is where
// generics live - the one place `<` is reliably a bracket rather than a comparison.
function splitArgs(text) {
  const out = [];
  let depth = 0, start = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if ('([{<'.includes(c)) depth++;
    else if (')]}>'.includes(c)) depth--;
    else if (c === ',' && depth === 0) { out.push(text.slice(start, i)); start = i + 1; }
  }
  out.push(text.slice(start));
  return out;
}

// ★AND A WORD BEFORE A COLON INSIDE A STRING IS NOT A KEY. `{ error: "Missing required fields: question,
// asset_id, hive_id" }` was read as declaring a key called `fields`, because the key pattern ran over the
// literal's string VALUES as well as its property names. That one phantom key was the entire contract
// asset-brain-query was then measured against - it answered 200 with answer/cited/narration/asset and was
// reported BAD for not returning `fields`, a word that exists only inside an error message. Strip the
// values before reading the names. Same family as the comment-stripping the i18n gate needed.
const keysOfObject = (body) => {
  const bare = String(body || '')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/\/\/[^\n]*/g, ' ')
    .replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`/g, '""');
  return [...bare.matchAll(/([A-Za-z_]\w*)\s*:/g)].map((m) => m[1]);
};

// ★WHEN A FUNCTION'S OWN SHAPE IS GENUINELY OPEN, ITS CONSUMER STILL WROTE THE CONTRACT DOWN (2026-09-10).
// Four functions answer `JSON.stringify(<variable>)` where the variable is a downstream service's return
// typed `Record<string, unknown>` - an open record, declaring no key set. The honest reading of the SOURCE
// is "the shape cannot be read", and that is where this reader stopped, leaving four working 200s unable
// to earn an F row at all.
//
// But a reply nobody reads is not a contract either, and these replies ARE read: hive.html invokes
// `ai-orchestrator` and then does `actions = data?.actions`, and renders `a.urgency`, `a.machine`,
// `a.action`. That IS the agreed shape - the same oracle as the REQUEST side, where a caller's own
// invoke body says what a well-formed request looks like. If the function stopped returning `actions`
// the page would break, which is exactly what a contract means.
//
// Used ONLY when the source declares nothing (see lensF), and it says so in its own verdict line, because
// a caller-derived shape is weaker evidence than a self-declared one and must not be quietly mixed in
// with it. Bounded at the NEXT invoke so one call's window never reads the next call's keys.
// ★AND A CALLER'S REPLY KEYS BELONG TO THAT CALLER'S REQUEST - THEY ARE ONE PAIR (2026-09-10). The first
// version read `actions` off hive.html's `data?.actions` and demanded it of a reply to a request this
// probe had composed itself. ai-orchestrator returns `actions` ONLY under `mode: "coach"` (its source:
// `if (mode === "coach") { … return … actions … }`), so a 200 from any other mode was reported BAD for
// not carrying a key it never promises there - a working function accused because two different calls
// were compared as one. Same error as taking `discipline` from one dispatch arm and `calc_type` from
// another: read the whole site, or none of it. So this returns the caller's own literal request fields
// ALONGSIDE the keys it reads back, and lensF sends the one before judging by the other.
const _callerContract = new Map();
function callerContract(fn) {
  if (_callerContract.has(fn)) return _callerContract.get(fn);
  const esc = fn.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
  const sites = [];
  for (const m of CALLERS.matchAll(new RegExp(`invoke(?:WithTimeout)?\\s*\\(\\s*['"\`]${esc}['"\`]`, 'g'))) {
    // the binding sits just BEFORE the call: `const { data, error } = await db.functions.invoke(…)`
    const before = CALLERS.slice(Math.max(0, m.index - 200), m.index);
    const bind = /(?:const|let|var)\s*\{([^}]{0,140})\}\s*=\s*(?:await\s+)?[^;{}]*$/.exec(before);
    const bound = bind ? splitArgs(bind[1]).map((s) => s.split(':').pop().trim()) : [];
    const resultVar = bound.find((n) => /^(data|result|res|out|payload|json)$/.test(n)) || 'data';

    // the request this very call makes: `{ body: { mode: 'coach', question, hive_id: HIVE_ID } }`.
    // Only STRING/number literals are adopted - a value held in a variable (`question`, `HIVE_ID`) is
    // this caller's runtime state, not a documented constant, and the existing readers already fill those.
    const literals = {};
    const after = CALLERS.slice(m.index + m[0].length, m.index + m[0].length + 900);
    const bodyAt = after.search(/\bbody\s*:\s*\{/);
    if (bodyAt >= 0) {
      const open = after.indexOf('{', bodyAt + 4);
      const obj = objectAt(after, open);
      if (obj !== null) {
        for (const p of splitArgs(obj)) {
          const kv = /^\s*([A-Za-z_]\w*)\s*:\s*(['"`])([^'"`]{1,60})\2\s*$/.exec(p);
          if (kv) literals[kv[1]] = kv[3];
        }
      }
    }

    let win = CALLERS.slice(m.index + m[0].length, m.index + 3000);
    const next = win.search(/\binvoke(?:WithTimeout)?\s*\(/);
    if (next > 0) win = win.slice(0, next);
    const keys = new Set();
    for (const k of win.matchAll(new RegExp(`\\b${resultVar}\\s*\\??\\.\\s*([A-Za-z_]\\w*)`, 'g'))) keys.add(k[1]);
    for (const d of win.matchAll(new RegExp(`(?:const|let|var)\\s*\\{([^}]{2,160})\\}\\s*=\\s*${resultVar}\\b`, 'g'))) {
      for (const n of splitArgs(d[1])) {
        const nm = n.split(/[:=]/)[0].trim();
        if (/^[A-Za-z_]\w*$/.test(nm)) keys.add(nm);
      }
    }
    // `error` is the SDK's envelope, not the function's shape; `then`/`catch` are promise plumbing
    const named = [...keys].filter((k) => !/^(error|then|catch|finally|status|statusText)$/.test(k));
    if (named.length) sites.push({ literals, keys: named });
  }
  // prefer a site that states its own request in literals - that is the one whose reply keys are
  // conditional on something this probe can reproduce
  sites.sort((a, b) => Object.keys(b.literals).length - Object.keys(a.literals).length);
  const out = sites[0] || { literals: {}, keys: [] };
  _callerContract.set(fn, out);
  return out;
}

// the keys a source says its REPLY carries. Lifted out of lensF so it can be pointed at another
// function's file - a ROUTER's declared shape is the shape of whatever it routes to.
function declaredResponseKeys(src) {
  // ★FIFTH VARIANT, AND THE ONE THAT NEEDED A TEST RATHER THAN A PREFIX: an outgoing payload does not
  // always announce itself with `body:`. resume-polish builds its model prompt as
  // `const userMsg = JSON.stringify({ role: context, bullets })` and passes it further down - a plain
  // assignment, indistinguishable by shape from a reply. What separates them is where the string GOES:
  // a reply reaches `new Response(…)`, a prompt never does. So name the variable and ask.
  const outboundFirstKeys = new Set();
  for (const m of src.matchAll(/(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*JSON\.stringify\(\s*\{\s*([a-zA-Z_]\w*)\s*[:,]/g)) {
    if (!new RegExp(`new Response\\s*\\([^;]{0,120}\\b${m[1]}\\b`).test(src)) outboundFirstKeys.add(m[2]);
  }
  return [...new Set([...src.matchAll(/(body\s*:\s*)?JSON\.stringify\(\s*\{\s*([a-zA-Z_][\w]*)\s*[:,]/g)]
    .filter((m) => !m[1]).map((m) => m[2]).filter((k) => !outboundFirstKeys.has(k))), ...responseKeysFromVariable(src)];
}

function responseKeysFromVariable(src) {
  const keys = new Set();
  const idents = new Set();
  for (const m of src.matchAll(/JSON\.stringify\(\s*([A-Za-z_]\w*)\s*[,)]/g)) idents.add(m[1]);
  // a response HELPER - `function json(data, …) { … JSON.stringify(data) … }` - hands the shape to its
  // CALL sites, so read the object literals passed there.
  // ★AND THE SAME HELPER IS AS OFTEN AN ARROW AS A `function`, AND ITS BODY IS NOT ALWAYS ARGUMENT ONE
  // (2026-09-10). Two spellings and one position were all assumed, and each assumption cost a real row:
  //   * resume-polish writes `const json = (body: unknown, status = 200) => new Response(JSON.stringify(
  //     body), …)`. Knowing only `function json(…) {…}`, the reader found no helper and fell back to
  //     scanning every `JSON.stringify({…})` in the file - which is where its OUTBOUND LLM PROMPTS live -
  //     so it demanded `role, current_summary, name, headline` of the reply and reported a good 200 BAD
  //     for not echoing back the message the function had SENT to the model.
  //   * voice-journal-agent writes `function json(corsHeaders, status, body)` and answers
  //     `json(corsHeaders, 200, { answer, lang, persona })`. The reply is argument THREE. A reader that
  //     always reads argument one saw `corsHeaders` and learned nothing.
  // So: find which PARAMETER the helper stringifies, remember its index, and read the argument at that
  // index. The position is written down in the function's own signature - there is no need to assume it.
  const helpers = [];
  for (const re of [/function\s+([A-Za-z_]\w*)\s*\(([\s\S]{0,300}?)\)\s*(?::[^{;]{0,80})?\{/g,
                    /(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*\(([\s\S]{0,300}?)\)\s*(?::[^=]{0,80})?=>/g]) {
    for (const m of src.matchAll(re)) {
      const params = splitArgs(m[2]).map((p) => (p.split(/[:=]/)[0] || '').trim().replace(/^\.\.\./, ''));
      const win = src.slice(m.index + m[0].length, m.index + m[0].length + 400);
      if (!/JSON\.stringify\s*\(/.test(win)) continue;
      const idx = params.findIndex((p) => p && new RegExp(`JSON\\.stringify\\(\\s*${p}\\s*[,)]`).test(win));
      if (idx >= 0) helpers.push({ name: m[1], idx });
    }
  }
  for (const h of helpers) {
    for (const c of src.matchAll(new RegExp(`\\b${h.name}\\s*\\(`, 'g'))) {
      const open = c.index + c[0].length - 1;
      const inner = objectAt(src, open, '(', ')');
      if (inner === null) continue;
      const arg = (splitArgs(inner)[h.idx] || '').trim();
      if (arg.startsWith('{')) { for (const k of keysOfObject(objectAt(arg, 0) ?? '')) keys.add(k); }
      else if (/^[A-Za-z_]\w*$/.test(arg)) idents.add(arg);
    }
  }
  for (const id of idents) {
    if (id === 'null' || id === 'undefined') continue;
    // `let parsed: { a: X; b: Y }` - the declaration, read the same way the request's `body:` is read
    for (const m of src.matchAll(new RegExp(`(?:let|const|var)\\s+${id}\\s*:\\s*\\{([^}]{2,400})\\}`, 'g'))) {
      for (const k of m[1].matchAll(/([A-Za-z_]\w*)\s*\??\s*:/g)) keys.add(k[1]);
    }
    // `const out = { a, b }` - the literal itself
    for (const m of src.matchAll(new RegExp(`(?:let|const|var)\\s+${id}\\s*=\\s*\\{([^}]{2,400})\\}`, 'g'))) {
      for (const k of m[1].matchAll(/([A-Za-z_]\w*)\s*[:,]/g)) keys.add(k[1]);
    }
  }
  return [...keys];
}

// which fields the function's OWN source treats as NUMBERS - `Number(x)`, `parseInt/parseFloat(x)`,
// `Number.isFinite(x)`, or a TypeScript field typed `x: number`. The twin of arrayFields() above, read
// from the same file. Restricted to names the body reader already declared, so a numeric LOCAL never
// gets invented into the payload.
const _numberFields = new Map();
function numberFields(fn) {
  if (_numberFields.has(fn)) return _numberFields.get(fn);
  const src = source(fn);
  const seen = new Set();
  const add = (f) => { if (f) seen.add(f); };
  // Number(body.x) / parseInt(b.x, 10) / Number.isFinite(x) - the property, or the bare local the
  // function assigned it to (functions do `const p = Number(body.p)` and then guard on `p`).
  for (const m of src.matchAll(/\b(?:Number|parseInt|parseFloat)\s*\(\s*(?:[A-Za-z_]\w*\s*\.\s*)?([A-Za-z_]\w*)/g)) add(m[1]);
  for (const m of src.matchAll(/\bNumber\.isFinite\s*\(\s*(?:[A-Za-z_]\w*\s*\.\s*)?([A-Za-z_]\w*)/g)) add(m[1]);
  for (const m of src.matchAll(/\b([A-Za-z_]\w*)\s*\??\s*:\s*number\b/g)) add(m[1]);
  const declaredNames = new Set(declaredFields(fn).fields);
  const out = [...seen].filter((f) => declaredNames.has(f));
  _numberFields.set(fn, out.slice(0, 8));
  return _numberFields.get(fn);
}

// A number that suits the NAME, because some pairs are ordered and a pair of 5s proves nothing.
// pf-calculator's whole subject is the gap between a warning level and a functional-failure level; sent
// two equal numbers it would compute a P-F interval across no interval at all.
function numberValueFor(field) {
  const f = String(field).toLowerCase();
  // ★A NUMBER CAN BE THE RIGHT TYPE AND STILL BE OUT OF RANGE (2026-09-10). `temperature` fell to the
  // generic tail and was sent as 5. Every chat provider caps it at 2, so all four of
  // voice-model-call's models answered 400 - and the function, which reported only the status, told
  // the caller "All models failed (rate limited or down)". Curl with temperature 0 got 200 from the
  // same function in the same minute, which is what separated MY request from the platform. Sampling
  // parameters have published ranges; a fixture that ignores them tests nothing but the validator.
  if (/^temperature$/.test(f)) return 0;
  if (/^top_p$|^presence_penalty$|^frequency_penalty$/.test(f)) return 1;
  if (/(^|_)(days|since_days|window|period)$/.test(f) || /_days$/.test(f)) return 365;
  if (/(^|_)(year)s?$/.test(f)) return 2026;
  if (/^p_|warn|warning|alert/.test(f) && /threshold|level|limit/.test(f)) return 4;
  if (/^f_|fail|functional|critical/.test(f) && /threshold|level|limit/.test(f)) return 8;
  if (/threshold|level/.test(f)) return 5;
  if (/limit|count|top_?k|^n_|size|page/.test(f)) return 5;
  return 5;
}

// an array field guarded by `.length === 0` needs a MEMBER, not an empty list; give it one shaped like the
// name asks for. send-report-email reads `reports.map(r => r.type/r.summary)`, so a bare string would throw
// inside the function rather than answer - the item carries the keys the name implies.
function nonEmptyItemFor(field, hive) {
  // ★A CHAT TURN IS A ROLE AND A CONTENT, NEVER A BARE STRING (2026-09-10). `messages` fell through to
  // the generic tail and was sent as ['probe'], so every provider in voice-model-call's chain rejected
  // the request and the function answered "All models failed (rate limited or down)" - a sentence that
  // reads as an upstream outage and was banked as one. It was not: resume-polish and resume-extract both
  // answered 200 from the SAME chain minutes either side of it. The word "failed" in a function's own
  // message describes what happened to the function, not who was at fault.
  if (/^messages$/i.test(field)) {
    return { role: 'user', content: 'Reply with the single word OK. This is a contract probe.' };
  }
  if (/report/i.test(field)) return { type: 'logbook', summary: 'A summary written by the contract prober.' };
  if (/reading|sensor|measure/i.test(field)) return { metric: 'temperature', value: 42, recorded_at: new Date().toISOString() };
  if (/text|sentence|chunk|input/i.test(field)) return realText(field, hive) || 'a sentence from the contract prober';
  if (/email|recipient/i.test(field)) return 'contract-prober@example.invalid';
  return realText(field, hive) || 'probe';
}

// ★A FUNCTION CAN HAND OVER ITS VOCABULARY IN A FIELD RATHER THAN IN A SENTENCE. platform-gateway answers
// {"error":"Unknown route 'status'","available":["asset_search", …]} - the whole list of routes it accepts,
// as structured data beside the prose. The reader only ever looked at the prose, so the probe re-sent the
// same wrong route until the loop gave up, while the answer sat one key away in the reply it had already
// parsed. A machine-readable list is MORE of an answer than a sentence, not less: fold it into the words
// the option reader sees, so both shapes are read the same way.
const withHints = (r) => {
  const msg = String(messageOf(r) || r.text || '');
  const j = r.json;
  if (!j || typeof j !== 'object') return msg;
  const lists = [];
  for (const k of ['available', 'allowed', 'options', 'accepted', 'valid', 'expected', 'supported', 'choices']) {
    const v = j[k];
    if (Array.isArray(v) && v.length) lists.push(v.filter((x) => typeof x === 'string').slice(0, 24).join(', '));
    else if (typeof v === 'string' && v.trim()) lists.push(v);
  }
  return lists.length ? `${msg} Available: ${lists.join(', ')}` : msg;
};

// ask, and keep asking until the function stops complaining about the shape of the question
async function askWellFormed(fn, hive, auth = token) {
  const body = { hive_id: hive, hiveId: hive, hive: hive };
  const query = {};
  let form = null;   // set once, if the function says it wants multipart rather than JSON
  // pre-fill from the function's own source, so the first ask is usually already the right question -
  // and build each value from the SENTENCE the name was read out of, not a synthesised "Missing <field>"
  const declared = declaredFields(fn);
  for (const f of declared.fields) {
    if (!(f in body)) body[f] = valueFor(f, declared.said.get(f) || `Missing ${f}`, hive);
  }
  // ...and where the function DISPATCHES on a field, its own arms are that field's vocabulary - a stronger
  // statement than any guess a name can support, so it overrides the prefill above. A live option list
  // ("Unknown 'x'. Available: …") still wins over both: the escalation loop below re-picks from it.
  for (const [f, v] of Object.entries(dispatchBranch(fn))) body[f] = v;
  // ...and a REAL caller's literal fields outrank both, because they are a request this platform actually
  // makes in production - and because the reply keys lensF may fall back on were read at that same call
  // site. `mode: 'coach'` is why hive.html gets `actions` back; asking without it and then demanding
  // `actions` compares two different calls. See callerContract.
  for (const [f, v] of Object.entries(callerContract(fn).literals)) body[f] = v;
  // ★AND THE SOURCE SAYS WHAT SHAPE IT WANTS, not just which names. send-report-email guards with
  // `!Array.isArray(reports) || reports.length === 0` and then complains "Missing required fields:
  // recipient_email, reports" - a sentence that names neither a type nor a list. Both fields were filled
  // with strings, the identical complaint came back, and the row was reported as never reaching its job.
  // The type is written down one line above the message, in the same file the names were already read from.
  for (const f of arrayFields(fn)) {
    if (!Array.isArray(body[f])) body[f] = [nonEmptyItemFor(f, hive)];
  }
  // ★AND THE SAME FILE SAYS WHICH FIELDS ARE NUMBERS - the array reader above had a twin missing for
  // months. pf-calculator writes `const p_threshold = Number(body.p_threshold)` and guards with
  // `!Number.isFinite(p_threshold)`, then answers "p_threshold and f_threshold must be finite numbers."
  // Both names were read correctly from source; both were then filled with the string default, because
  // the only numeric signal was a PROSE match and the prose says "numbers" while the pattern said
  // `\bnumber\b` - a plural away from working. So all three of this function's lenses came back
  // "the request never reached the claim" while the function spelled out the type twice, in code and in
  // English. Read the code: Number(x), parseInt/parseFloat(x), `x: number`, and Number.isFinite(x) are
  // each an unambiguous declaration, and unlike a sentence they cannot drift out of step with the guard.
  for (const f of numberFields(fn)) {
    if (typeof body[f] !== 'number') body[f] = numberValueFor(f);
  }
  // ★A BODY THAT CARRIES A PASSWORD IS AN IDENTITY, NOT A DESTINATION. `login` reads `b.email ?? b.username`
  // and `b.password`; the email rule above - written for send-report-email, where an unroutable address is
  // exactly right - handed it a fake one, so the probe spent the whole wave posting failed sign-ins at the
  // platform's own front door. That is worse than an unanswered row: this function's header describes a
  // per-(id,ip) lockout, so a probe that keeps guessing can lock the very account it needs. The presence of
  // a `password` field is the discriminator, and the credentials are the prober's own, already in this file.
  const credKeys = Object.keys(body).filter((k) => /^(password|pass|pwd)$/i.test(k));
  if (credKeys.length) {
    for (const k of credKeys) body[k] = PLAIN.password;
    for (const k of Object.keys(body)) {
      if (/^(e?mail|username|user|login|identifier)$/i.test(k)) body[k] = PLAIN.email;
    }
  }
  const filled = [];
  const tries = new Map();
  const seen = new Set();
  let r = await call(fn, { auth, body, query, form });
  for (let i = 0; i < 6; i++) {
    if (!(r.status === 400 || r.status === 422)) break;
    const said = withHints(r);
    if (ENTITLED.test(said)) break;                    // it is talking about me now, not about my body
    // ★THE SAME FIELD TWICE IS ONLY A DEAD END IF THE ANSWER IS ALSO THE SAME. Refusing to retry a field
    // gave up on `ai-gateway` at the exact moment it started being helpful: its second reply NAMED the
    // agents it accepts. A repeated complaint with new words is new information; a repeated complaint with
    // the same words is the dead end.
    if (seen.has(said)) break;
    seen.add(said);
    const fields = wantedFields(said);
    // ★THE WORD A FUNCTION USES FOR A THING IS NOT ALWAYS THE KEY IT READS. platform-gateway reads
    // `body.fn` but says "Unknown route 'status'", so the reader took the field to be `route`, set a
    // brand-new `route` key from the offered list, left `fn` holding the value that had just been
    // rejected, and got the identical complaint back until the loop gave up. What the message states
    // UNAMBIGUOUSLY is not the key - it is the VALUE it will not accept, quoted. So find whichever key is
    // holding that value and replace THAT one. The function's own vocabulary decides the new value; the
    // body decides where it goes.
    // ...and a function can reject the whole ENCODING rather than any field in it. "Expected
    // multipart/form-data with audio field" names both the format and the part it wants, and no amount of
    // filling in JSON keys will ever satisfy it. Switch languages once, then carry on as before.
    const wantsForm = /multipart\/form-data/i.test(said);
    if (wantsForm && !form) {
      const part = /with\s+(?:an?\s+)?["'`]?([A-Za-z_]\w*)["'`]?\s+(?:field|part|file)/i.exec(said);
      form = part ? part[1] : 'audio';
      if (!filled.includes(form)) filled.push(form);
      r = await call(fn, { auth, body, query, form });
      continue;
    }
    const rejected = /\b(?:unknown|invalid|unsupported|unrecognised|unrecognized)\b[^'"`\n]{0,24}["'`]([^'"`\n]{1,40})["'`]/i.exec(said);
    if (rejected) {
      const offered = optionsIn(said).filter((v) => v !== rejected[1]);
      const holder = Object.keys(body).find((k) => String(body[k]) === rejected[1]);
      if (offered.length && holder) {
        body[holder] = pickOption(offered);
        if (!filled.includes(holder)) filled.push(holder);
        r = await call(fn, { auth, body, query, form });
        continue;
      }
    }
    if (!fields.length) break;
    let added = 0;
    for (const field of fields) {
      const n = (tries.get(field) || 0) + 1;
      if (n > 2) continue;                             // twice is a fair hearing; a third is a loop
      tries.set(field, n);
      if (!filled.includes(field)) filled.push(field);
      // ★A DOTTED NAME IS A PATH, NOT A KEY. Two functions ask for `time_range.{from,to}` and one for
      // `window.days`, and setting a TOP-LEVEL key called "time_range.from" leaves the object they
      // actually read still missing - the same complaint comes back and the loop calls it a dead end.
      // The name the function used is the shape it wants.
      const path = field.replace(/[{}]/g, '').split('.').filter(Boolean);
      if (path.length > 1) {
        let node = body;
        for (let d = 0; d < path.length - 1; d++) {
          if (typeof node[path[d]] !== 'object' || node[path[d]] === null) node[path[d]] = {};
          node = node[path[d]];
        }
        node[path[path.length - 1]] = valueFor(path[path.length - 1], said, hive);
      } else if (new RegExp('\\b' + field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b[^.\\n]{0,20}query\\s*param', 'i').test(said)) {
        query[field] = valueFor(field, said, hive);   // it named the PLACE as well as the field
        delete body[field];
      } else {
        // ★THE REPAIR LOOP UNDID THE TYPE THE SOURCE HAD ALREADY DECLARED (2026-09-10). `messages` is
        // read out of voice-model-call's source as an ARRAY field and filled with a proper chat turn;
        // then a later complaint mentioning the field sent it back through valueFor(), which knows
        // only the sentence and not the source, and wrote a scalar over the array. The function's
        // provider then said, precisely, "'messages.0' : value must be an object with the
        // discriminator property: 'role'" - and every model in the chain answered 400, which the
        // function reported to its caller as "All models failed (rate limited or down)".
        // A repair may change a field's VALUE; it must not change its TYPE.
        const repaired = valueFor(field, said, hive);
        body[field] = (arrayFields(fn).includes(field) && !Array.isArray(repaired))
          ? [nonEmptyItemFor(field, hive)]
          : repaired;
      }
      added++;
    }
    if (!added) break;
    r = await call(fn, { auth, body, query, form });
  }
  return { r, body, query, form, filled };
}

async function lensI(fn) {
  if (!token) return { verdict: 'BAD', line: 'no user token could be minted, so nothing can speak for a signed-in person' };
  const asked = await askWellFormed(fn, FOREIGN);
  const r = asked.r;
  if (notDeployed(r)) return { verdict: 'n/a', line: 'not deployed locally' };
  if (r.status === 0) return { verdict: 'n/a', line: `no answer inside this probe's ${Math.round(TIMEOUT / 1000)}s budget - the prober gave up first, so nothing was learned` };
  const leaked = !!SENTINEL && r.text.includes(SENTINEL);
  if (leaked) return { verdict: 'BAD', line: `answered ${r.status} and the reply carried ${FOREIGN_NAME}'s own words back to a member of another hive ("${SENTINEL.slice(0, 40)}")` };
  const said = messageOf(r) || '';
  const how = asked.filled.length ? ` (after filling in ${asked.filled.join(', ')} at the function's own asking)` : '';
  if (r.status === 401 || r.status === 403) {
    return { verdict: 'ok', line: `refused a foreign-hive request with ${r.status}${how}${said ? ` and said so: "${said.slice(0, 62)}"` : ' (no sentence)'}` };
  }
  if (r.status === 429) return { verdict: 'n/a', line: `rate-limited before the entitlement question was reached: "${said.slice(0, 56)}"` };
  if (r.status === 405) return { verdict: 'n/a', line: 'answered 405 - this probe used the wrong method, so the question was never asked' };
  if (r.ok) return { verdict: 'ok', line: `answered ${r.status}${how} and returned none of ${FOREIGN_NAME}'s data (sentinel absent)` };
  if (ENTITLED.test(said)) return { verdict: 'ok', line: `refused a foreign-hive request with ${r.status}${how} in the caller's own words: "${said.slice(0, 60)}"` };
  // ★A 5xx IS A FAULT, NOT A REFUSAL - AND THE DIFFERENTIAL BELOW CANNOT TELL THEM APART (2026-09-10).
  // The comment on the next line has always said "still a 4xx" and nothing enforced it, so a 502 fell
  // through to the differential and resume-extract banked as `answered my own hive 200 and refused the
  // other with 502 - the only thing that changed was whose hive it named`. Two things had changed: the
  // hive, and whether the absent AI provider happened to fail that second. The function has NO hive
  // scoping to refuse with - its own source says it "reads NO hive-scoped data", is a "SOLO per-user
  // feature" keyed by auth_uid, and deliberately never trusts a client hive_id - so there was no
  // entitlement question there to pass. A differential is only evidence when both sides are the
  // PRODUCT answering; a server fault on one side makes it noise, and noise pointed the right way reads
  // exactly like proof. Refusal is a 4xx sentence about the caller, always.
  if (r.status >= 500) {
    return { verdict: 'n/a', line: `answered ${r.status} "${said.slice(0, 44)}" - a server-side fault, not a refusal, so the entitlement question was never reached` };
  }
  // still a 4xx, and it is not talking about the caller. Change ONE thing - whose hive - and ask again.
  // `token` explicitly, never a variable that could carry an elevated one: this is the REFUSAL lens's own
  // control - "can this same plain member reach their OWN hive?" - and it is only worth anything asked as
  // the same person whose refusal is being demonstrated one line above.
  const own = await call(fn, { auth: token, body: { ...asked.body, hive_id: MINE, hiveId: MINE, hive: MINE } });
  if (own.ok) {
    return { verdict: 'ok', line: `answered my own hive ${own.status} and refused the other with ${r.status}${how} - the only thing that changed was whose hive it named` };
  }
  const ownSaid = messageOf(own) || '';
  return { verdict: 'n/a', line: `answers both hives the same way (${r.status} "${said.slice(0, 40)}" / ${own.status} "${ownSaid.slice(0, 26)}") - a complaint about the request, not about the caller` };
}

// what a function says when the thing it depends on is the thing that failed
const PROVIDER = /\b(provider|upstream|model|openai|anthropic|gemini|claude|api key|apikey|service|unavailable|temporar|timeout|timed out|try again|rate limit|limit reached|quota|credit|embedding|dependency|offline|unreachable|failed to (?:reach|connect|fetch))\b/i;

async function lensA(fn) {
  // ★THE SAME MISTAKE THE REFUSAL LENS MADE. This asked once with a fixed body and graded whatever came
  // back, so 41 of 62 functions were recorded as "degraded legibly: 400" - where the 400 was
  // "Missing required field: question", a complaint about MY request. The request died on its shape and
  // never reached the dependency, which is the only thing this row is about. Ask properly first, then grade.
  const asked = await askWellFormed(fn, MINE);
  const r = asked.r;
  if (notDeployed(r)) return { verdict: 'n/a', line: 'not deployed locally' };
  const src = source(fn);
  const guarded = /catch\s*\(/.test(src) && /(fallback|degrad|retry|circuit|catch\s*\([\s\S]{0,400}?(return|new Response))/i.test(src);
  const said = messageOf(r);
  // ★MY TIMEOUT WAS SHORTER THAN THE PLATFORM'S OWN. `_shared/ai-chain.ts` bounds every provider call with
  // `AbortSignal.timeout(60000)` and allows one jittered retry pass before degrading to "{}", so a worst
  // case is ~2 minutes by design. This prober gives up at 35s - so "the call never returned" was the PROBE
  // giving up first, reported as three functions hanging. When the source shows a bounded call with a
  // degradation path, a timeout here is NOT evidence; when it shows no bound at all, it still is.
  if (r.status === 0) {
    const src = source(fn);
    const shared = /ai-chain|callAI|embedding-chain|audio-chain/.test(src);
    const bounded = /AbortSignal\.timeout\(|signal:\s*controller\.signal|setTimeout\(/.test(src) || shared;
    return bounded
      ? { verdict: 'n/a', line: `no answer inside this probe's ${Math.round(TIMEOUT / 1000)}s budget, and its provider call is bounded (${shared ? 'via the shared AI chain, 60s + one retry' : 'its own timeout'}) - the probe gave up first, so this is not evidence` }
      : { verdict: 'BAD', line: 'the call never returned and nothing in its source bounds it - a person would wait with no end and no message' };
  }
  if (!r.json) return { verdict: 'BAD', line: `answered ${r.status} with a body that is not JSON (${r.text.slice(0, 60).replace(/\s+/g, ' ')}) - a client can render nothing from it` };
  if (r.ok) return { verdict: guarded ? 'ok' : 'BAD', line: guarded ? `answered ${r.status} and its source catches and answers the failure path` : `answered ${r.status}, but its source has no catch that returns a response - a provider failure would reach the person raw` };
  // a 4xx still complaining about the request is a question that never reached the dependency
  if ((r.status === 400 || r.status === 422) && !PROVIDER.test(String(said || ''))) {
    return { verdict: 'n/a', line: `answered ${r.status} "${String(said || r.text).slice(0, 48)}" - the request never reached its dependency, so this says nothing about how it degrades` };
  }
  if (!said) return { verdict: 'BAD', line: `answered ${r.status} with JSON that carries no error/message a person could read` };
  if (!HUMAN(said)) return { verdict: 'BAD', line: `answered ${r.status} with "${said.slice(0, 60)}" - a code, not a sentence` };
  return { verdict: 'ok', line: `degraded legibly: ${r.status} "${said.slice(0, 66)}"${guarded ? '' : ' (source has no explicit catch - watch it)'}` };
}

async function lensF(fn) {
  // ★AND THE THIRD TIME, THE SAME ROOT. 44 of 62 functions were recorded as "answered 400 in its own
  // declared shape" - offered as proof that the function COMPLETES ITS DOCUMENTED JOB. A 400 completes
  // nothing; the envelope merely carries the complaint in the house style. All three lenses graded the
  // first reply without ever getting the request past the function's own shape check.
  let asked = await askWellFormed(fn, MINE);
  // ...and if it refuses because the CALLER is not senior enough, ask again as the person whose job it
  // is. F ONLY - see the note beside SUP. A supervisor is the documented caller of a supervisor-gated
  // function, so declining to ask as one measures the probe's credentials rather than the platform's
  // contract. lensI above keeps the plain member's token for ever (a refusal shown with an elevated
  // credential shows nothing), and lensA keeps it too (elevating would change the very path it grades).
  if ((asked.r.status === 401 || asked.r.status === 403) && NEEDS_SUPERVISOR.test(String(messageOf(asked.r) || ''))) {
    const st = await supervisorToken();
    if (st) {
      const retry = await askWellFormed(fn, SUP.hive, st);
      if (retry.r.status !== 401 && retry.r.status !== 403) { asked = retry; asked.asSupervisor = true; }
    }
  }
  // ...and if it refuses because the caller is not a MACHINE, ask again as the machine. F ONLY - see the
  // note beside serviceKey(). Same reasoning as the supervisor step, one rung further: a cron drainer's
  // documented caller is the service role, so a member's 403 says nothing about whether the job works.
  if ((asked.r.status === 401 || asked.r.status === 403) && NEEDS_SERVICE.test(String(messageOf(asked.r) || ''))) {
    const sk = serviceKey();
    if (sk) {
      const retry = await askWellFormed(fn, MINE, sk);
      if (retry.r.status !== 401 && retry.r.status !== 403) { asked = retry; asked.asService = true; }
    }
  }
  const r = asked.r;
  if (notDeployed(r)) return { verdict: 'n/a', line: 'not deployed locally' };
  const src = source(fn);
  // the same correction as the A lens: a body that never arrived because THIS probe gave up is not a
  // function with an unreadable shape
  if (r.status === 0) return { verdict: 'n/a', line: `no answer inside this probe's ${Math.round(TIMEOUT / 1000)}s budget - its shape cannot be judged from a call the prober abandoned` };
  // the shape the function itself declares it returns
  // ★A FUNCTION THAT ANSWERS THROUGH A SHARED ENVELOPE DECLARES ITS SHAPE THERE, NOT HERE. Reading only the
  // function's own file, this lens took `JSON.stringify({ title: … })` - a PUSH NOTIFICATION PAYLOAD in
  // notify-push, a prompt in resume-polish - as the declared response, then reported that the 401 it got
  // back "carried none of the keys its own source builds". Three functions were accused of a shape they
  // never claimed. All of them return through `_shared/envelope.ts`, whose body is
  // `{ ok, data, … }` on success and `{ ok, error: { code, message, detail }, … }` on failure - so when a
  // function imports the envelope, THAT is its declared shape. The same correction the caller haystack
  // needed: read the shared source, not just the file in front of you.
  // ★IMPORTING THE ENVELOPE IS NOT ANSWERING THROUGH IT. Three functions carry
  // `import { ok, fail } from "../_shared/envelope.ts"` and never call either - asset-brain-query's own
  // source says the success-path migration "follows". Demanding {ok, error, data} of them accused three
  // working functions of breaking a contract they have not adopted yet. Adoption is a CALL, not an import.
  const usesEnvelope = /_shared\/envelope\.ts/.test(src) && /\b(?:ok|fail)\s*\(/.test(src);
  // ★AND AN OUTGOING REQUEST BODY IS NOT A RESPONSE. ai-orchestrator calls a sibling service with
  // `body: JSON.stringify({ query: question, hive_id: hiveId, match_count: 3 })` - a payload it SENDS -
  // and this took `query` as a key it must RETURN, then reported a working 200 as breaking its own
  // contract. Fourth variant of the same lesson the envelope, the import-versus-call and the
  // error-helper corrections above already taught: read what the literal is FOR, not just that it is
  // there. A literal introduced by `body:` belongs to a fetch going out.
  // ★FIFTH VARIANT, AND THE ONE THAT NEEDED A TEST RATHER THAN A PREFIX: an outgoing payload does not
  // always announce itself with `body:`. resume-polish builds its model prompt as
  // `const userMsg = JSON.stringify({ role: context, bullets })` and passes it further down - a plain
  // assignment, indistinguishable by shape from a reply. What separates them is where the string GOES:
  // a reply reaches `new Response(…)`, a prompt never does. So name the variable and ask.
  const own = declaredResponseKeys(src);
  // ★AN ERROR HELPER'S LITERAL IS NOT THE SUCCESS SHAPE. `project-orchestrator` answers its success path
  // with `JSON.stringify(data)` - a variable, unreadable from here - and its only object literal anywhere is
  // the error helper's `{ error: … }`. Taking that as "the keys its own source builds" and then demanding
  // them of a 200 accused a working function of breaking a contract it never wrote. When a 2xx is being
  // judged, error-envelope keys are dropped; if nothing else was declared, the shape is simply unreadable.
  // ★AND IT IS THE WHOLE LITERAL THAT IS AN ERROR, NOT JUST THE WORD IN IT (2026-09-10). The filter below
  // struck out the NAMES `error`/`message`/`detail` and let their companions through, so
  // platform-gateway's `{ error: "Unknown route", code, available, trace_id }` still contributed
  // `code, available, trace_id` as "the keys its own source builds" - and a 200 that carried none of
  // them was reported BAD. Those three describe a refusal and nothing else; a reply that returned them
  // would be a failure. An object literal carrying an `error` key is an error literal, and none of its
  // keys says anything about what a success looks like. Drop the literal, not the word.
  const errKeys = new Set();
  for (const m of src.matchAll(/\berror\s*:/g)) {
    let depth = 0;
    for (let i = m.index; i >= 0 && i > m.index - 800; i--) {
      if (src[i] === '}') depth++;
      else if (src[i] === '{') {
        if (!depth) {
          const inner = objectAt(src, i);
          if (inner !== null && inner.length <= 800) for (const k of keysOfObject(inner)) errKeys.add(k);
          break;
        }
        depth--;
      }
    }
  }
  const success = own.filter((k) => !errKeys.has(k) && !/^(error|message|detail|reason|error_description)$/i.test(k));
  const keys = (usesEnvelope ? [...new Set(['ok', 'error', 'data', ...own])] : (r.ok ? success : own)).slice(0, 8);
  const shaped = !r.json ? false : (keys.length === 0 || keys.some((k) => Object.prototype.hasOwnProperty.call(r.json, k)) || Array.isArray(r.json));
  // ★BUILT AND NEVER CALLED. A name that appears only in its own file is a function nobody can reach.
  const mentions = (CALLERS.match(new RegExp(fn.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&'), 'g')) || []).length;
  const called = mentions > 1;
  if (!r.json) return { verdict: 'BAD', line: `answered ${r.status} with a non-JSON body - its documented shape cannot be read` };
  if (!called) return { verdict: 'BAD', line: `answered ${r.status}, but no page, script or sibling function names it - built and never called` };
  if (!r.ok) {
    // ★A QUOTA THIS PROBE ITSELF SPENT IS A FACT ABOUT THE PROBE. Sweeping 62 functions repeatedly runs
    // the platform's own per-hive and per-user AI limiters down, and after that every AI-backed function
    // answers 429. Reporting those as "the request never reached the claim" states something false about
    // the product - the request reached it perfectly, and the limiter did exactly its job. This is the
    // same distinction the timeout case already draws: say which side ran out.
    if (r.status === 429) {
      return { verdict: 'n/a', line: `answered 429 "${String(messageOf(r) || '').slice(0, 44)}" - rate-limited, and this probe's own sweep is what spent the quota, so the claim is untested rather than untrue` };
    }
    return { verdict: 'n/a', line: `answered ${r.status} "${String(messageOf(r) || '').slice(0, 44)}" after ${asked.filled.length ? 'filling in ' + asked.filled.join(', ') : 'a plain request'} - it never carried out its documented job here, so what it persists is unanswered` };
  }
  // the source said nothing about its shape - so ask the people who READ it. See responseKeysFromCallers.
  if (!keys.length) {
    // ★A ROUTER'S DECLARED SHAPE IS ITS TARGET'S (2026-09-10). platform-gateway exists to forward
    // `{ fn: 'X', payload: {…} }` to one of thirteen real routes and hand back what X said, so of course
    // its OWN source declares no key set - the shape is X's, by design, and calling that "unreadable" is
    // reading the wrong file. No page invokes it yet (its header says direct invokes keep working and new
    // code is "encouraged" through the gateway, with a ratchet tracking uptake), so the caller oracle is
    // empty too and the row would have stayed unanswerable for a function that is working exactly as
    // documented. When the request this probe sent names another function, read THAT function's shape.
    const routed = Object.values(asked.body || {})
      .filter((v) => typeof v === 'string' && v !== fn && ALL_FNS.includes(v))[0];
    if (routed) {
      const tKeys = declaredResponseKeys(source(routed)).filter((k) => !/^(error|message|detail|reason)$/i.test(k));
      const tMet = tKeys.filter((k) => Object.prototype.hasOwnProperty.call(r.json, k));
      if (tMet.length) {
        return { verdict: 'ok', line: `answered ${r.status} carrying ${tMet.slice(0, 3).join(', ')} - it is a ROUTER, so its declared shape is the shape of what it routes to (${routed}: ${tKeys.slice(0, 4).join(', ')}), and ${mentions - 1} caller(s) name it` };
      }
    }
    const contract = callerContract(fn);
    const byCaller = contract.keys;
    const asAsked = Object.keys(contract.literals).length
      ? ` (asked the way that caller asks: ${Object.entries(contract.literals).map(([k, v]) => `${k}=${v}`).join(', ')})` : '';
    if (byCaller.length) {
      const met = byCaller.filter((k) => Object.prototype.hasOwnProperty.call(r.json, k));
      if (met.length) {
        return { verdict: 'ok', line: `answered ${r.status} carrying ${met.slice(0, 3).join(', ')} - its own source declares an OPEN record, so this is measured against the shape its callers actually read off the reply (${byCaller.slice(0, 4).join(', ')})${asAsked}, and ${mentions - 1} caller(s) name it` };
      }
      return { verdict: 'BAD', line: `answered ${r.status} with none of the keys its callers read off it (${byCaller.slice(0, 4).join(', ')})${asAsked} - its source declares an open record, so the consumers are the only written contract, and this reply meets none of it` };
    }
    return { verdict: 'n/a', line: `answered ${r.status}, and its source builds the reply from a variable rather than a literal - the shape it declares cannot be read from here, and no caller reads a named key off it, so nothing is claimed` };
  }
  if (!shaped) return { verdict: 'BAD', line: `answered ${r.status} with none of the keys its own source builds (${keys.join(', ') || 'none declared'})` };
  return { verdict: 'ok', line: `answered ${r.status} in its own declared shape (${keys.slice(0, 3).join(', ') || 'array'}) and ${mentions - 1} caller(s) name it${asked.asSupervisor ? `, asked as ${SUP.name}, a supervisor of their own hive (this function refuses a plain member by design)` : ''}${asked.asService ? ', asked with the SERVICE key because this function names a machine as its caller (cron / service-role only) - so this proves the job runs, and says nothing about who may ask for it; the refusal lens above answers that, and only ever as a plain member' : ''}` };
}

// ── teeth, no network ─────────────────────────────────────────────────────────────────────────────
// ★SHOW THE QUESTION BEFORE TRUSTING THE ANSWER (2026-09-10). Seven separate wrong verdicts this wave
// were the reader misreading a source, and every one of them would have been obvious in a second if the
// request and the expected shape had been printable without spending a call. This prints what the probe
// WOULD send and what it would demand back, from source alone: no network, no database, no rate limit.
// The cheapest possible way to tell "this function is broken" from "I asked it the wrong thing".
if (args.includes('--show-request')) {
  for (const fn of FNS) {
    const d = declaredFields(fn);
    const body = { hive_id: '<hive>', hiveId: '<hive>', hive: '<hive>' };
    for (const f of d.fields) if (!(f in body)) body[f] = `<${f}>`;
    for (const [f, v] of Object.entries(dispatchBranch(fn))) body[f] = v;
    const contract = callerContract(fn);
    for (const [f, v] of Object.entries(contract.literals)) body[f] = v;
    const keys = declaredResponseKeys(source(fn));
    console.log(`\n── ${fn}`);
    console.log(`   declared fields : ${d.fields.join(', ') || '(none)'}`);
    console.log(`   arrays / numbers: ${arrayFields(fn).join(', ') || '-'} / ${numberFields(fn).join(', ') || '-'}`);
    console.log(`   dispatch        : ${JSON.stringify(dispatchBranch(fn)) || '{}'}`);
    console.log(`   caller literals : ${JSON.stringify(contract.literals)}  reads back: ${contract.keys.join(', ') || '-'}`);
    console.log(`   would send      : ${JSON.stringify(body)}`);
    console.log(`   would expect    : ${keys.join(', ') || '(source declares an open shape)'}`);
  }
  process.exit(0);
}

if (args.includes('--self-test')) {
  const fails = [];
  if (!/^[0-9a-f-]{36}$/.test(MINE)) fails.push(`the plain member's hive did not resolve (${MINE || 'empty'})`);
  if (!/^[0-9a-f-]{36}$/.test(FOREIGN)) fails.push('no foreign hive to ask about');
  if (MINE === FOREIGN) fails.push('the foreign hive is the member\'s own - the refusal lens would prove nothing');
  if (!SENTINEL) fails.push('no sentinel string could be lifted from the foreign hive, so a leak would be invisible');
  if (psql(`select count(*) from marketplace_platform_admins where worker_name = '${PLAIN.name}'`) !== '0') fails.push(`${PLAIN.name} is a platform admin and cannot demonstrate a refusal`);
  // the human-sentence oracle must reject what it is meant to reject, and accept a real sentence
  if (HUMAN('E_RATE_LIMIT')) fails.push('HUMAN accepted a bare error code');
  if (HUMAN('   ')) fails.push('HUMAN accepted whitespace');
  if (HUMAN('<html><body>500</body></html>')) fails.push('HUMAN accepted an HTML page');
  if (HUMAN('at handler (file:///src/index.ts:44:12)')) fails.push('HUMAN accepted a stack frame');
  if (!HUMAN('AI call limit reached for this hive. Try again in about 12 minutes.')) fails.push('HUMAN rejected a real sentence');
  if (!messageOf({ json: { error: { message: 'the provider did not answer' } } })) fails.push('messageOf cannot read a nested error message');
  // ★THE ORACLE THAT COST 44 ROWS. These mutations are the ones that were missing when a payload complaint
  // was banked as a refusal, so each is named after the reading it would have caught.
  if (ENTITLED.test('Missing or invalid op (must be "recall" or "store")')) fails.push('a complaint about the body is read as a refusal of the caller');
  if (ENTITLED.test('Missing required field: question')) fails.push('a missing-field complaint is read as a refusal of the caller');
  if (!ENTITLED.test('You are not a member of this hive')) fails.push('a real entitlement refusal is not recognised');
  if (!ENTITLED.test('Access denied for this resource')) fails.push('"access denied" is not recognised as a refusal');
  if (wantedField('Missing required field: question') !== 'question') fails.push(`the missing field is not read out of the complaint (${wantedField('Missing required field: question')})`);
  if (wantedField('Missing or invalid op (must be "recall" or "store")') !== 'op') fails.push(`"op" is not read out of its complaint (${wantedField('Missing or invalid op (must be "recall" or "store")')})`);
  if (wantedField('Missing agent') !== 'agent') fails.push('a bare "Missing agent" is not read');
  if (wantedField('everything is fine here')) fails.push('a field is being invented from a message that names none');
  // ★THE BUG THAT COST 98 CONTRACTS: a plural complaint read as one field called "s".
  const many = wantedFields('Missing required fields: question, asset_id, hive_id');
  if (many.join(',') !== 'question,asset_id,hive_id') fails.push(`a multi-field complaint reads as [${many}]`);
  if (many.includes('s')) fails.push('the word "fields" is still being mistaken for a field named "s"');
  const areReq = wantedFields('hive_id and machine are required');
  if (!(areReq.includes('hive_id') && areReq.includes('machine'))) fails.push(`"are required" is not read (${areReq})`);
  if (!wantedFields('config_id query param required').includes('config_id')) fails.push('a query-param complaint is not read');
  if (!wantedFields('Missing or empty transcript').includes('transcript')) fails.push('"Missing or empty X" is not read; the capture lands on the word "or"');
  if (wantedFields('Missing or empty transcript').includes('or')) fails.push('the word "or" is being taken as a field name');
  if (wantedFields('The request body is required').includes('body')) fails.push('the word "body" is being taken as a field name');
  if (valueFor('op', 'Missing or invalid op (must be "recall" or "store")', MINE) !== 'recall') fails.push('the probe would pick the option that WRITES over the one that reads');
  // ★AN OFFERED LIST MUST BE READ IN EVERY SHAPE THE PLATFORM WRITES IT. Four functions were reported
  // unanswerable while spelling out exactly what they wanted, because the reader knew "Available:" and
  // quoted options but not an UNQUOTED "one of a, b, c" or a plain "Use a, b, or c".
  for (const [field, msg, allowed] of [
    ['level',   'Missing or invalid level (must be one of day, week, month)',     ['day', 'week', 'month']],
    ['source',  'Missing or invalid source (must be one of sap_pm, maximo, csv)', ['sap_pm', 'maximo', 'csv']],
    ['table',   'Missing or invalid table (must be one of logbook, pm_assets)',   ['logbook', 'pm_assets']],
    ['section', 'Unknown section. Use parts, training, or jobs.',                 ['parts', 'training', 'jobs']],
    ['agent',   "Unknown agent 'status'. Available: asset, kpi",                  ['asset', 'kpi']],
    // ★A LIST SEPARATED BY SLASHES, WHOSE MEMBERS START WITH DIGITS. shift-planner-orchestrator states its
    // whole vocabulary in the complaint and BOTH halves of the reader threw it away - the splitter did not
    // know the slash, and the value filter demanded a leading letter.
    ['shift_window', 'shift_window must be one of 06-14 / 14-22 / 22-06',         ['06-14', '14-22', '22-06']],
    ['window',       'Missing required field: window (must be 06-14, 14-22, or 22-06)', ['06-14', '14-22', '22-06']],
    ['mode',         'mode must be one of read / write',                          ['read']],   // still prefers the reader
  ]) {
    const got = valueFor(field, msg, MINE);
    if (!allowed.includes(got)) fails.push(`"${field}" ignores the list its own complaint offers (chose ${JSON.stringify(got)})`);
  }
  // ...and a stated vocabulary must OUTRANK the database guess, or a recognised field name silently wins
  if (valueFor('status', 'status must be one of open, closed', MINE) !== 'open') {
    fails.push('a database guess pre-empts the vocabulary the function stated outright');
  }
  // ...while a complaint that offers NO list must still fall through to the lookup, not invent an option
  if (optionsIn('Missing required field: question').length) fails.push('options are being invented from a complaint that lists none');
  if (optionsIn('The request must be at least 3 characters').length) fails.push('a threshold sentence is being read as an option list');
  // an email-shaped field must look like an email - send-report-email validates it, and the lookup below
  // would otherwise hand it a person's NAME. Reserved .invalid TLD: a probe can never post real mail.
  for (const f of ['recipient_email', 'email', 'sender_email']) {
    if (!/^[^@\s]+@[^@\s]+\.invalid$/.test(String(valueFor(f, `Missing ${f}`, MINE)))) {
      fails.push(`"${f}" is not given an unroutable email-shaped value (${valueFor(f, `Missing ${f}`, MINE)})`);
    }
  }
  if (/@/.test(String(valueFor('recipient_name', 'Missing recipient_name', MINE)))) {
    fails.push('a non-email field is being given an email because its name merely contains "recipient"');
  }
  // an array field named in SOURCE must be sent as a NON-EMPTY array - `reports.length === 0` is a guard a
  // bare string and an empty list both fail, and the same complaint then returns for ever
  const _af = arrayFields('send-report-email');
  if (!_af.includes('reports')) fails.push(`send-report-email's Array.isArray(reports) guard is not read from source (${JSON.stringify(_af)})`);
  const _item = nonEmptyItemFor('reports', MINE);
  if (!_item || typeof _item !== 'object' || !_item.type) fails.push('an array of reports is not given a member carrying the keys the function reads');
  if (arrayFields('send-report-email').includes('hive_id')) fails.push('a plain string field is being sent as an array');
  // an id-shaped field must be a uuid, and where the hive HAS such a row it must be that row, not the hive
  const aid = valueFor('asset_id', 'Missing asset_id', FOREIGN);
  if (!/^[0-9a-f-]{36}$/.test(String(aid))) fails.push(`an id-shaped field is not given a uuid (${aid})`);
  if (psql(`select count(*) from asset_nodes where hive_id = '${FOREIGN}'`) !== '0' && aid === FOREIGN) {
    fails.push('asset_id fell back to the hive id while that hive has assets - no lookup happened');
  }
  if (valueFor('hive_id', 'Missing hive_id', FOREIGN) !== FOREIGN) fails.push('hive_id is not the hive itself');
  if (valueFor('limit', 'limit must be a number', MINE) !== 5) fails.push('a numeric field is being given a string');
  if (valueFor('agent', "Unknown agent 'status'. Available: asset, logbook", MINE) !== 'asset') fails.push('the list of agents a function offers is not read back');
  if (wantedField("Unknown agent 'status'. Available: asset") !== 'agent') fails.push('an "unknown <field>" complaint does not yield its field');
  // ★A 404 CARRYING THE FUNCTION'S OWN WORDS IS THE FUNCTION ANSWERING, NOT AN ABSENT ROUTE. Both
  // directions, or the fix trades one silent misreading for another.
  if (!notDeployed({ status: 404, json: null, text: 'Function not found' })) fails.push("the runtime's own \"Function not found\" is not read as an absent route");
  if (notDeployed({ status: 404, json: { error: 'Config not found' }, text: '{"error":"Config not found"}' })) fails.push('a function answering 404 about a ROW is being filed as not deployed');
  if (notDeployed({ status: 400, json: { error: 'Missing agent' }, text: '' })) fails.push('a 400 is being read as not deployed');
  if (!notDeployed({ status: 404, json: null, text: '' })) fails.push('an empty 404 is not read as an absent route');
  // a 429 is the limiter working; the summary must not file it as "the request never reached the claim"
  if (!/budget|gave up first|rate-limited|wrong method/.test("answered 429 \"AI call limit reached\" - rate-limited, and this probe's own sweep is what spent the quota, so the claim is untested rather than untrue")) {
    fails.push('a 429 line is not counted as rate-limited by the summary buckets');
  }
  if (PROVIDER.test('Missing required field: question')) fails.push('a missing-field complaint is read as a dependency failure');
  if (!PROVIDER.test('The AI provider did not answer. Try again in a moment.')) fails.push('a real dependency failure is not recognised');
  if (!PROVIDER.test('Per-user AI call limit reached (6/hour).')) fails.push('a rate-limit degradation is not recognised');
  // *AN IMPORT IS NOT AN ADOPTION. The first fixture imports the envelope and still answers with its
  // own object - exactly what asset-brain-query, ai-orchestrator and project-orchestrator do, and what
  // had this lens accuse all three of breaking a contract they never adopted. The second really calls it.
  const adopts = (s) => /_shared\/envelope\.ts/.test(s) && /\b(?:ok|fail)\s*\(/.test(s);
  if (adopts('import { ok, fail } from "../_shared/envelope.ts"; return new Response(JSON.stringify(body));')) {
    fails.push('a function that only IMPORTS the envelope is read as answering through it');
  }
  if (!adopts('import { ok } from "../_shared/envelope.ts"; return ok(req, { rows });')) {
    fails.push('a function that really answers through the envelope is not recognised');
  }
  // ★THE STATIC READER MUST FIND WHAT THE RUNTIME WOULD HAVE TOLD IT. 41 of the 62 functions write their
  // own "Missing …" strings, and reading them before the first call is what turns a row that was withdrawn
  // ("the request never reached the claim") into one that can be answered at all.
  const amsFields = declaredFields('agent-memory-store').fields;
  if (!amsFields.includes('op')) fails.push(`agent-memory-store's own source names 'op' and the static reader missed it (${amsFields})`);
  const abqFields = declaredFields('asset-brain-query').fields;
  if (!(abqFields.includes('question') && abqFields.includes('asset_id'))) {
    fails.push(`asset-brain-query declares question + asset_id in source; the reader found [${abqFields}]`);
  }
  if (declaredFields('_no_such_function_').fields.length) fails.push('fields were invented for a function that does not exist');
  // ★AND THE RESPONSE SHAPE IS DECLARED IN THE SAME LANGUAGE AS THE REQUEST. voice-report-intent writes
  // `let parsed: { report_types: string[]; … }` and answers `JSON.stringify(parsed)`; without the
  // variable resolver its 200 was recorded as "nothing is claimed".
  const _vri = responseKeysFromVariable(source('voice-report-intent'));
  if (!_vri.includes('report_types')) fails.push(`voice-report-intent declares report_types on its response variable; the reader found [${_vri}]`);
  // ...and the resolver must NOT invent one where the function declares an open record. project-orchestrator
  // returns Promise<Record<string, unknown>>; a key list here would be a contract it never wrote.
  if (responseKeysFromVariable(source('project-orchestrator')).length) {
    fails.push('keys were read off project-orchestrator, whose producer is typed Record<string, unknown> - an open record declares no shape');
  }
  // ★THE ELEVATION BOUNDARY, PINNED. The F lens may ask as a supervisor; the I lens never may, because a
  // refusal shown with an elevated credential shows nothing. This is the constraint most worth a teeth
  // test in the whole file, so it is asserted about the SOURCE rather than about my memory of it.
  const _self = readFileSync('tools/prove_fn_contracts.mjs', 'utf8');
  const _lensI = _self.slice(_self.indexOf('async function lensI'), _self.indexOf('async function lensA'));
  const _lensA = _self.slice(_self.indexOf('async function lensA'), _self.indexOf('async function lensF'));
  if (/supervisorToken|_supToken/.test(_lensI)) fails.push('the REFUSAL lens can reach an elevated token - a refusal proved that way proves nothing');
  // ...and every call it makes must NAME the plain member's token rather than take whatever `auth` holds.
  // Adding the supervisor path renamed `auth: token` to the shorthand `auth` across the file, which hit a
  // call inside this lens where no such variable exists - a crash, caught by running it, but the same edit
  // in a scope that DID have an `auth` would have silently asked the refusal question with someone else's
  // credentials and passed. The shorthand is banned here; the token is spelled out.
  if (/\{\s*auth\s*[,}]/.test(_lensI)) fails.push('the refusal lens passes a bare `auth` shorthand - it must name `auth: token` so no other credential can reach it');
  if (/\{\s*auth\s*[,}]/.test(_lensA)) fails.push('the degradation lens passes a bare `auth` shorthand - it must name `auth: token`');
  // ★AND THE SAME BOUNDARY FOR THE SERVICE KEY, which is stricter still: a supervisor is at least a
  // person inside one hive, while the service role bypasses RLS entirely. A refusal or a degradation
  // demonstrated with it is worth nothing at all, so neither lens may so much as name it.
  if (/serviceKey|SUPABASE_SERVICE_ROLE_KEY/.test(_lensI)) fails.push('the refusal lens reaches for the SERVICE key - a refusal shown with the credential that bypasses RLS shows nothing');
  if (/serviceKey|SUPABASE_SERVICE_ROLE_KEY/.test(_lensA)) fails.push('the degradation lens reaches for the SERVICE key - it must grade the path a person actually walks');
  if (!/serviceKey\(\)/.test(_self.slice(_self.indexOf('async function lensF')))) fails.push('the service-caller escalation is gone from lensF - a cron-only job has no human caller, so F cannot be answered without it');
  if (/supervisorToken|_supToken/.test(_lensA)) fails.push('the degradation lens can elevate, which changes the very path it grades');
  if (SUP && psql(`select count(*) from marketplace_platform_admins where worker_name = '${SUP.name}'`) !== '0') {
    fails.push(`the elevated persona (${SUP.name}) is a platform admin - a pass would be about admin rights, not the supervisor contract`);
  }
  if (SUP && psql(`select count(*) from hive_members where worker_name = '${SUP.name}' and hive_id = '${SUP.hive}' and role = 'supervisor' and status = 'active'`) !== '1') {
    fails.push('the elevated persona is not actually an active supervisor of the hive it is asked about');
  }
  // ★THE MESSAGES STILL UNANSWERED, PINNED HERE SO THE READER IS MEASURED AGAINST THE REAL CORPUS rather
  // than against shapes I invented. Each is quoted verbatim from a live reply during the 2026-09-09 sweep.
  for (const [msg, want] of [
    ['payload missing', 'payload'],                                    // resume-extract, name-FIRST
    ['Missing or too short transcript', 'transcript'],                 // voice-logbook-entry
    ['Missing or invalid texts array', 'texts'],                       // voice-embeddings
    ['image must be a data: URL or https:// URL', 'image'],            // resume-extract, second hop
  ]) {
    if (!wantedFields(msg).includes(want)) fails.push(`"${msg}" does not yield ${want} (got ${JSON.stringify(wantedFields(msg))})`);
  }
  // ...and prose that names no field must still name none, or the reader invents work for itself
  for (const msg of [
    'Enter your username and password to sign in.',
    'Add a title or part number first, then AI can help.',
    'Choose the hive and the person whose password you are resetting.',
  ]) {
    const got = wantedFields(msg);
    if (got.some((f) => /^(sign|help|password|reset)$/i.test(f))) fails.push(`"${msg}" is being mined for a field that is really a verb (${got})`);
  }
  // ★THE "NEVER PICK THE OPTION THAT WRITES" RULE MUST SURVIVE A HYPHENATED NAME. These are the real
  // routes platform-gateway offers; picking the first would have this probe sending mail and ingesting
  // PDFs to find out whether a gateway routes.
  const gwRoutes = ['voice-transcribe', 'send-report-email', 'pdf-ingest', 'semantic-search', 'intelligence-api'];
  const picked = pickOption(gwRoutes);
  if (/send|email|ingest|transcribe/.test(picked)) fails.push(`the probe picked a side-effecting route (${picked})`);
  if (!/search|api/.test(picked)) fails.push(`the probe did not prefer a reading route (${picked})`);
  if (pickOption(['store', 'recall']) !== 'recall') fails.push('the plain read/write preference regressed');
  if (pickOption(['delete-hive', 'purge-all']) !== 'delete-hive') fails.push('an all-writes list must still yield its first option, not nothing');
  // the audio fixture must be a real WAV, or "multipart" merely trades one unanswerable request for another
  if (WAV_SILENCE.slice(0, 4).toString() !== 'RIFF' || WAV_SILENCE.slice(8, 12).toString() !== 'WAVE') {
    fails.push('the inlined audio is not a RIFF/WAVE file');
  }
  if (WAV_SILENCE.readUInt32LE(4) !== WAV_SILENCE.length - 8) fails.push('the WAV header declares the wrong chunk size');
  if (WAV_SILENCE.readUInt32LE(40) !== WAV_SILENCE.length - 44) fails.push('the WAV data chunk length does not match its payload');
  if (WAV_SILENCE.length < 200) fails.push('the audio fixture is too short to be decodable');
  // and the part name is read out of the complaint, not assumed
  const _partOf = (s2) => { const m2 = /with\s+(?:an?\s+)?["'`]?([A-Za-z_]\w*)["'`]?\s+(?:field|part|file)/i.exec(s2); return m2 ? m2[1] : 'audio'; };
  if (_partOf('Expected multipart/form-data with audio field') !== 'audio') fails.push('the multipart part name is not read from the complaint');
  if (_partOf('Expected multipart/form-data with recording field') !== 'recording') fails.push('a differently-named multipart part is not read');
  // ★A REAL FIELD NAME THAT HAPPENS TO BE A STOPWORD. The prose stoplist must keep striking "parameter" out
  // of a SENTENCE, and must never strike it out of `body.parameter`, which is what pf-calculator reads.
  const pfc = declaredFields('pf-calculator').fields;
  if (!pfc.includes('parameter')) fails.push(`pf-calculator reads body.parameter; the prose stoplist struck it from the code reader (${pfc})`);
  if (!pfc.includes('asset_id')) fails.push(`pf-calculator's asset_id is not read (${pfc})`);
  if (wantedFields('Missing required parameter: asset_id').includes('parameter')) {
    fails.push('the word "parameter" is being taken as a field name out of PROSE - the stoplist must still hold there');
  }
  // a value the function will re-validate must satisfy the pattern it states
  if (!/^[A-Za-z0-9_]{1,40}$/.test(String(valueFor('parameter', 'The parameter name is wrong. Use letters, digits and underscore, up to 40 long.', MINE)))) {
    fails.push('the parameter value does not satisfy the name pattern the function spells out');
  }
  // a top-level date pair is the same shape as one nested inside time_range
  const _from = String(valueFor('from', 'Those from and to dates are not valid', MINE));
  const _to = String(valueFor('to', 'Those from and to dates are not valid', MINE));
  if (!/^\d{4}-\d{2}-\d{2}/.test(_from) || !/^\d{4}-\d{2}-\d{2}/.test(_to)) fails.push(`a top-level date field is not given a date (${_from} .. ${_to})`);
  if (new Date(_from) >= new Date(_to)) fails.push('the window does not start before it ends, so it can never return anything');
  // ...and when two branches are offered, take the one whose fixture the probe actually holds
  if (pickOption(['image', 'text']) !== 'text') fails.push('the probe owes a photograph when a sentence would do');
  if (pickOption(['audio', 'transcript']) !== 'transcript') fails.push('a binary medium is being preferred over a text one');
  if (pickOption(['image', 'photo']) !== 'image') fails.push('an all-media list must still yield its first option, not nothing');
  // a function that deliberately keeps its field name out of the sentence still reaches for it in code
  const pg = declaredFields('platform-gateway').fields;
  if (!pg.includes('fn')) fails.push(`platform-gateway reads body.fn and never names it in prose; the reader found [${pg}]`);
  // a vocabulary handed over as a FIELD is read the same as one written into the sentence
  const gwHint = withHints({ status: 400, text: '', json: { error: "Unknown route 'status'", available: ['asset_search', 'kpi'] } });
  if (!optionsIn(gwHint).includes('asset_search')) fails.push(`a structured "available" list is not read (${gwHint})`);
  if (valueFor('route', gwHint, MINE) === 'status') fails.push('the probe re-sends the route the function just rejected');
  if (withHints({ status: 400, text: 'plain', json: null }) !== 'plain') fails.push('a reply with no structured hint is being rewritten');
  if (/Available/.test(withHints({ status: 400, text: '', json: { error: 'Missing agent' } }))) {
    fails.push('an "Available:" list is being invented for a reply that carries none');
  }
  // a function that names its body in TypeScript but never in English is still declaring its contract
  const ocr = declaredFields('gcash-receipt-ocr').fields;
  if (!ocr.includes('image_data_url')) fails.push(`gcash-receipt-ocr declares image_data_url in its body type; the reader found [${ocr}]`);
  const vle2 = declaredFields('voice-logbook-entry').fields;
  if (!vle2.includes('transcript')) fails.push(`a destructured body does not yield its fields (${vle2})`);
  // an image field must get something that actually decodes as an image, in both directions
  if (!/^data:image\/png;base64,/.test(String(valueFor('image_data_url', 'image_data_url missing', MINE)))) {
    fails.push('an image field is not given a decodable image');
  }
  if (Buffer.from(PNG_1PX.split(',')[1], 'base64').slice(0, 8).toString('hex') !== '89504e470d0a1a0a') {
    fails.push('the inlined PNG is not a PNG - its signature bytes are wrong');
  }
  if (/^data:image/.test(String(valueFor('question', 'Missing question', MINE)))) {
    fails.push('a plain text field is being handed an image');
  }
  // ...and the SENTENCE each name was read out of is kept, or the pre-fill throws away every hint the
  // function wrote down at the exact moment it is most useful
  const vle = declaredFields('voice-logbook-entry');
  if (!vle.fields.includes('transcript')) fails.push(`"Missing or too short transcript" does not yield its field (${vle.fields})`);
  if (!/too short/i.test(vle.said.get('transcript') || '')) fails.push('the complaint that named the field was not kept beside it');
  if (String(valueFor('transcript', vle.said.get('transcript') || '', MINE)).length < 20) {
    fails.push('a field the function calls too short is still pre-filled with something short');
  }
  // ★AND AN ERROR HELPER'S LITERAL IS NOT THE SUCCESS SHAPE. A source whose only object literal is
  // `{ error: … }` declares nothing about what a 200 looks like, and demanding `error` of a 200 accused
  // three working functions. On a success, error-envelope keys are dropped from the expectation.
  const declared = (src) => [...new Set([...src.matchAll(/JSON\.stringify\(\s*\{\s*([a-zA-Z_][\w]*)\s*[:,]/g)].map((m) => m[1]))];
  const onlyErr = declared('return new Response(JSON.stringify({ error: e }));');
  if (onlyErr.filter((k) => !/^(error|message|detail|reason|error_description)$/i.test(k)).length) {
    fails.push('an error-only literal is still being read as a declared success shape');
  }
  if (!declared('return new Response(JSON.stringify({ rows: r, total: n }));').includes('rows')) {
    fails.push('a real success literal is not being read as the declared shape');
  }
  // ── the four reader corrections of 2026-09-10, each pinned by the exact shape that fooled it ──
  // a word before a colon INSIDE a string is not a key (asset-brain-query's "Missing required fields:")
  if (keysOfObject('error: "Missing required fields: question, asset_id"').includes('fields')) {
    fails.push('a word inside a string value is still being read as a declared key');
  }
  // a helper whose body is argument THREE (voice-journal-agent) must be read at that position
  const _vja = responseKeysFromVariable(
    'function json(corsHeaders: Record<string, string>, status: number, body: unknown) {\n'
    + '  return new Response(JSON.stringify(body), { status });\n}\n'
    + 'return json(corsHeaders, 200, { answer: clean, lang, persona: personaKey });');
  if (!_vja.includes('answer')) fails.push(`a response helper whose body is argument 3 is unread (got [${_vja}])`);
  // an arrow helper is a helper (resume-polish), and an outbound prompt is not a reply
  const _rp = responseKeysFromVariable(
    'const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });\n'
    + 'const userMsg = JSON.stringify({ role: context, bullets });\n'
    + 'return json({ bullets: clamped });');
  if (!_rp.includes('bullets')) fails.push('an arrow-form response helper is unread');
  // a parameter list is split on TOP-LEVEL commas only - Record<string, string> is ONE parameter
  if (splitArgs('corsHeaders: Record<string, string>, status: number, body: unknown').length !== 3) {
    fails.push('a generic type argument is being split as if it were another parameter');
  }
  // an error literal's COMPANIONS are not the success shape either (platform-gateway's code/available/trace_id)
  const _errco = (() => {
    const s = 'return json({ error: "Unknown route", code: "unknown_route", available: routes, trace_id: t });';
    const out = new Set();
    for (const m of s.matchAll(/\berror\s*:/g)) {
      let depth = 0;
      for (let i = m.index; i >= 0; i--) {
        if (s[i] === '}') depth++;
        else if (s[i] === '{') { if (!depth) { for (const k of keysOfObject(objectAt(s, i) ?? '')) out.add(k); break; } depth--; }
      }
    }
    return out;
  })();
  for (const k of ['code', 'available', 'trace_id']) {
    if (!_errco.has(k)) fails.push(`"${k}" travels with an error literal and is not being recognised as one`);
  }
  // a function that dispatches on a field declares that field's vocabulary, and a REJECTION list
  // (`kind !== "image" && kind !== "text"`) is a whitelist - resume-extract's, read from its real source
  const _kind = dispatchBranch('resume-extract').kind;
  if (_kind !== 'text') fails.push(`resume-extract's kind should be read as the feedable arm 'text', got ${_kind}`);
  // an array-shaped LOCAL is not a request field, and the real one must survive the filter that removes it
  if (!arrayFields('send-report-email').includes('reports')) {
    fails.push('send-report-email.reports is a declared array field and is no longer being read - the reason arrayFields exists');
  }
  for (const junk of ['COMPRESSOR_HP_CFM', 'WATER_SPEC_VOL']) {
    if (arrayFields('engineering-calc-agent').includes(junk)) {
      fails.push(`"${junk}" is an internal constant table being invented into the request payload`);
    }
  }
  console.log(fails.length ? 'FAIL fn-contracts self-test - ' + fails.join('; ')
    : `self-test OK: plain member of ${MINE.slice(0, 8)} asks about ${FOREIGN_NAME} (${FOREIGN.slice(0, 8)}), sentinel "${SENTINEL.slice(0, 28)}", the sentence oracle rejects codes, stacks and HTML`);
  process.exit(fails.length ? 1 : 0);
}

// ── the run ───────────────────────────────────────────────────────────────────────────────────────
if (!token) { console.log('FAIL fn-contracts - could not mint a user token; every lens here speaks for a signed-in person'); process.exit(1); }
const LENSES = { I: lensI, A: lensA, F: lensF };
const run = ONLY_LENS ? { [ONLY_LENS]: LENSES[ONLY_LENS] } : LENSES;
const list = LIMIT ? FNS.slice(0, LIMIT) : FNS;
console.log(`asking ${list.length} function(s) x ${Object.keys(run).length} lens(es) as ${PLAIN.name}, a plain member of ${MINE.slice(0, 8)}`);
const results = [];
let bad = 0; let na = 0;
for (const fn of list) {
  for (const [lens, f] of Object.entries(run)) {
    const r = await f(fn);
    if (r.verdict === 'BAD') bad++;
    if (r.verdict === 'n/a') na++;
    results.push({ fn, lens, ...r });
    console.log(`  ${r.verdict === 'ok' ? 'ok ' : r.verdict === 'n/a' ? 'n/a' : 'BAD'} ${lens} ${fn.padEnd(30)} ${r.line}`);
  }
}
try { mkdirSync('.tmp', { recursive: true }); } catch (e) { void e; }
// ★A NARROWED RE-PROBE MUST NOT CLOBBER THE FULL SWEEP'S RESULTS (2026-09-09). A 62-function sweep wrote
// 186 verdicts here; two `--fn hierarchical-summarizer` runs to confirm one fix overwrote the file with
// THREE, and the bank that followed found 2 bankable instead of 126 - the sweep's whole evidence gone, with
// nothing to say it had ever been there. A selection writes to its own name, exactly as the journey prover
// already does, so the broad run's bank survives the narrow run that checks one repair.
const outFile = `.tmp/fn_contracts${ONLY_FN.length ? '_' + ONLY_FN.join('-').slice(0, 40) : ''}${ONLY_LENS ? '_' + ONLY_LENS : ''}.json`;
writeFileSync(outFile, JSON.stringify({ asked: results.length, bad, na, results }, null, 2));
// ★A LABEL IS A CLAIM. This printed every n/a as "not deployed locally", which was true of four of them and
// false of the other 108 - a summary line asserting a cause it had not established. Count the reasons apart.
const undeployed = results.filter((r) => /not deployed locally/.test(r.line)).length;
const proberFailed = results.filter((r) => /budget|gave up first|rate-limited|wrong method/.test(r.line)).length;
console.log(`${bad ? 'FAIL' : 'PASS'} fn-contracts - ${results.length - bad - na}/${results.length - na} contract(s) hold  ·  `
  + `${na} unanswered: ${undeployed} not deployed here, ${proberFailed} where THIS PROBE ran out of patience or was `
  + `rate-limited, ${na - undeployed - proberFailed} where the request never reached the claim  ·  ${outFile}`);
process.exitCode = bad ? 1 : 0;
