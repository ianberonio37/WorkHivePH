// w3_journey_walk.body.js - LIVE a W3-JN whole journey through the Playwright MCP (2026-10-07).
//
// WHY THIS EXISTS. 190 W3-JN rows sat open on `tools/prove_full_journeys.mjs`, the Playwright-LIBRARY prover Ian
// retracted on 2026-09-15 ("I thought we are using relevant live MCPs?"). Those rows' manifest instrument is
// `playwright-mcp + postgres-mcp`. Re-writing the prover's 1,800 lines of hard-won journey semantics (casting rules,
// hop reachability, settle logic, conditions, role pairs, the J12 conversion, the J13 voice dispatch) as a second copy
// would be two hand-kept versions of one rule - the defect, not the safeguard. So this file runs THE PROVER'S OWN CODE
// inside the MCP's own browser: it fetches the prover's source from the local seeder, takes the span from
// `const PLATFORM_ADMINS` up to the self-test block, and evaluates it with shims for the three things a browser vm
// cannot have:
//   - psql      -> answered ONLY from P.psql, a cache whose every value was read through the POSTGRES MCP by the
//                  driver (exact SQL text as key). A miss is recorded in `need` and answers null (walk mode) or ''
//                  (collect mode, so the cast loaders do not crash while the list of needed SQL is gathered).
//   - psqlAs    -> null. The prover reads a chain AS the person with `set local role` in a multi-statement psql call;
//                  the postgres MCP takes one read-only statement, so the chain is read through the owner
//                  connection (the prover's own fallback) and the receipt says so. The person-side evidence is the
//                  walk: every page rendered that person's own data in their own session.
//   - files     -> readFileSync / readdirSync served from a map the walker prefetches from the seeder.
// The page walking itself - newContext, sign-in, settle, READ, PERFORM, the per-step fit record - is the prover's code,
// run against `page.context().browser()`.
//
//   P (.tmp/w3_args.json): { id, mode: 'collect'|'walk', psql: {sql: text}, files: [paths], rows: [registry rows] }
//   collect -> { need: [sql...] }   walk -> the story result, and the steps POSTed to /api/w4/steps as <id>
async (page) => {
  let P = {};
  try {
    const ar = await page.request.get('http://localhost:5000/workhive/.tmp/w3_args.json', { timeout: 5000 });
    if (ar.ok()) P = await ar.json();
  } catch (e) { void e; }
  const SEED = 'http://localhost:5000/workhive';
  const get = async (p) => {
    const r = await page.request.get(`${SEED}/${p}`, { timeout: 20000 });
    if (!r.ok()) throw new Error(`GET ${p} -> ${r.status()}`);
    return r.text();
  };
  const mode = P.mode || 'collect';
  const need = new Set();
  const CACHE = P.psql || {};
  // ★A POST-WALK EFFECT CANNOT COME FROM A PRE-WALK CACHE (2026-10-13, the six J13 rows). A story that PERFORMS an
  // action reads, after its browser has closed, what that action left behind (J13: the audit row its voice dispatch
  // wrote) and then deletes it. Every value in CACHE was read through the postgres MCP BEFORE the walk, so answering
  // those two statements from it would report the pre-walk 0 as the walk's effect and claim a delete nobody ran.
  // Once every context the walk opened has closed, a statement about the walk's own mark is DEFERRED: it answers
  // null here, is returned in `deferred`, and the driver asks it through the postgres MCP after the walk
  // (tools/w3_journey_drive.py complete) - and runs the reversal itself.
  const WALK_MARK = 'wh-journey-walk';
  const deferred = [];
  let openCtx = 0, postWalk = false;
  const psql = (sql) => {
    if (mode === 'walk' && postWalk && String(sql).includes(WALK_MARK)) { deferred.push(sql); return null; }
    if (Object.prototype.hasOwnProperty.call(CACHE, sql)) return CACHE[sql];
    need.add(sql);
    return mode === 'collect' ? '' : null;
  };
  const psqlAs = () => null;

  const src = await get('tools/prove_full_journeys.mjs');
  const lines = src.split('\n');
  const a = lines.findIndex((l) => l.startsWith('const PLATFORM_ADMINS'));
  const b = lines.findIndex((l) => l.startsWith("if (args.includes('--self-test'))"));
  if (a < 0 || b < 0 || b <= a) return { problems: [`could not find the prover span (${a}..${b})`] };
  let span = lines.slice(a, b).join('\n');
  // the prover's own psqlAs is replaced by the shim above (it needs a multi-statement role switch)
  span = span.replace(/^const psqlAs = \(worker, sql\) => \{/m, 'const __proverPsqlAs = (worker, sql) => {');

  const FILES = {};
  for (const f of P.files || []) { try { FILES[f] = await get(f); } catch (e) { FILES[f] = null; } }
  FILES['trajectory_registry.json'] = JSON.stringify({ trajectories: P.rows || [] });
  const readFileSync = (f) => { if (FILES[f] == null) throw new Error('ENOENT (not prefetched): ' + f); return FILES[f]; };
  const readdirSync = () => (P.files || []).filter((f) => f.endsWith('.html') && !f.includes('/'));
  const writeFileSync = () => {}; const mkdirSync = () => {};

  // the per-step overlap record: the generated browser audit + the prover's own issuesOf
  const auditJs = await get('tools/phone_fit_audit.browser.js');
  const fitSrc = await get('tools/phone_fit_audit.mjs');
  const fl = fitSrc.split('\n');
  const i0 = fl.findIndex((l) => l.startsWith('export function issuesOf'));
  const i1 = fl.findIndex((l, i) => i > i0 && l.startsWith('/**'));
  const fitIssues = (0, eval)('(' + fl.slice(i0, i1).join('\n').replace(/^export function issuesOf/, 'function issuesOf') + ')');
  const fitRecord = async (pg, VIS, step) => {
    try {
      await pg.evaluate(auditJs);
      return await pg.evaluate((s) => window.__W4_AUDIT(null, { step: s }), step);
    } catch (e) {
      return { error: String(e).slice(0, 120), step, outside: [], clipped: [], wrapped: [], spill: [], overflowEl: [], occlusion: [], overflow: 0, findings: 0 };
    }
  };

  const process = { exit: (c) => { throw new Error('prover exit ' + c); }, env: {}, argv: [], exitCode: 0 };
  const ORIGIN = SEED;   // localhost: no saved zoom (see w4_navhub_walk.body.js)
  const SUPA = 'http://127.0.0.1:54321';
  const args = []; const argOf = () => null;
  const ONLY_ARCH = null, ONLY_TIER = null, ONLY_VERT = null, ONLY_MOMENT = null, ONLY_COND = null, LIMIT = 0;

  let api;
  try {
    api = new Function('psql', 'psqlAs', 'readFileSync', 'readdirSync', 'writeFileSync', 'mkdirSync', 'fitRecord', 'fitIssues',
      'process', 'ORIGIN', 'SUPA', 'args', 'argOf', 'ONLY_ARCH', 'ONLY_TIER', 'ONLY_VERT', 'ONLY_MOMENT', 'ONLY_COND', 'LIMIT',
      span + '\nreturn { loadCast, stories, walk, readChain, hiveSpanDays, EFFECT, MOMENTS_NEEDED };')(
      psql, psqlAs, readFileSync, readdirSync, writeFileSync, mkdirSync, fitRecord, fitIssues,
      process, ORIGIN, SUPA, args, argOf, ONLY_ARCH, ONLY_TIER, ONLY_VERT, ONLY_MOMENT, ONLY_COND, LIMIT);
  } catch (e) {
    return { mode, need: [...need], problems: ['the prover span did not evaluate: ' + String(e.message || e).slice(0, 200)] };
  }

  let story = null;
  let all = [];
  try {
    const cast = api.loadCast();
    all = api.stories(cast);
    story = all.find((s) => s.id === P.id) || null;
  } catch (e) {
    return { mode, need: [...need], problems: ['casting failed: ' + String(e.message || e).slice(0, 200)] };
  }
  // collect for MANY rows in one pass (P.ids): one batched postgres-MCP read then answers all of them
  if (mode === 'collect' && Array.isArray(P.ids) && P.ids.length) {
    const cast = [];
    for (const s of all.filter((x) => P.ids.includes(x.id))) {
      try { api.readChain(s.baseArchetype, s.hiveId, s.identity); } catch (e) { void e; }
      try { if (api.MOMENTS_NEEDED[s.moment]) api.hiveSpanDays(s.hiveId); } catch (e) { void e; }
      cast.push(`${s.id}:${s.identity ? s.identity.name : 'NONE'}`);
    }
    try {
      await page.request.post('http://localhost:5000/api/w4/steps',
        { data: { id: P.id + '-collect', steps: [], records: { need: [...need] } }, timeout: 10000 });
    } catch (e) { void e; }
    return { mode, id: P.id, rows: cast.length, need: need.size, uncast: cast.filter((c) => c.endsWith(":NONE")) };
  }
  if (!story) return { mode, need: [...need], problems: [`no story for ${P.id} (is the row in P.rows, wave W3-JN?)`] };

  if (mode === 'collect') {
    // ask, without walking, for everything the end of walk() will read: the chain and the hive's history span
    try { api.readChain(story.baseArchetype, story.hiveId, story.identity); } catch (e) { void e; }
    try { if (api.MOMENTS_NEEDED[story.moment]) api.hiveSpanDays(story.hiveId); } catch (e) { void e; }
    // hand the list to the driver through the seeder, so the SQL is never re-typed (it is the cache key)
    try {
      await page.request.post('http://localhost:5000/api/w4/steps',
        { data: { id: P.id + '-collect', steps: [], records: { need: [...need] } }, timeout: 10000 });
    } catch (e) { void e; }
    return { mode, id: P.id, need: [...need].map((s) => s.slice(0, 90)), cast: story.identity && story.identity.name, hiveId: story.hiveId,
             archetype: story.archetype, moment: story.moment, condition: story.condition, device: story.device,
             partner: story.partner && story.partner.name };
  }

  // ★NO LIVE MODEL CALL DURING A JOURNEY (2026-10-07). shift-brain's first open of a shift with no fresh plan
  // invokes shift-planner-orchestrator, whose briefing is an LLM call - a reproduction of this very walk spent one
  // (Manila, 22-06). Ian's rule: live model calls only on the LM Grounding/Routing rows, spend stated first. Every
  // page the walk opens answers that one function 503 from a PAGE route - page routes run before context routes,
  // so the prover's own offline-3g `**/*` handler (which would `continue()` the call to the network) never sees it.
  const stub = { n: 0 };
  const STUB_PAT = '**/functions/v1/shift-planner-orchestrator**';
  const stubPage = async (pg) => {
    await pg.route(STUB_PAT, (r) => { stub.n++; return r.fulfill({ status: 503, contentType: 'application/json',
      body: JSON.stringify({ error: 'stubbed for the journey walk: no live model call' }) }); });
    return pg;
  };
  const realBrowser = page.context().browser();
  // every context the walk opens is counted, so the moment the last one closes is the moment the walk is over
  const wrapCtx = (c) => { openCtx++; let closed = false; return new Proxy(c, { get(t, k) {
    if (k === 'newPage') return async (...a) => stubPage(await t.newPage(...a));
    if (k === 'close') return async (...a) => {
      try { return await t.close(...a); } finally { if (!closed) { closed = true; openCtx--; if (openCtx <= 0) postWalk = true; } } };
    const v = t[k]; return typeof v === 'function' ? v.bind(t) : v; } }); };
  const browserProxy = new Proxy(realBrowser, { get(t, k) {
    if (k === 'newContext') return async (...a) => wrapCtx(await t.newContext(...a));
    const v = t[k]; return typeof v === 'function' ? v.bind(t) : v; } });
  let res;
  try {
    res = await api.walk(browserProxy, story);
  } catch (e) {
    return { mode, id: P.id, need: [...need], problems: ['the walk threw: ' + String(e.message || e).slice(0, 200)] };
  }
  const steps = (res.steps || []).map((s) => ({
    page: s.page, chars: s.chars || 0, landed: s.landed, loadError: s.loadError || null, lang: s.lang,
    identityKept: !(story.identity && !s.walkedBy && s.landed === s.page && s.hive && s.hive !== story.hiveId),
    own: s.own || 0, hub: s.hub || 0, settledBy: s.settledBy, walkedBy: s.walkedBy || null,
    performed: s.performed || null,
    offlineShell: !!s.offlineShell, signInWall: !!s.signInWall, notice: (s.platformNotice || [])[0] || null,
    errBanner: (s.errBanner || [])[0] || null, rest: (s.rest || []).slice(0, 3),
    fit: s.fit ? { findings: s.fit.findings || 0, occlusion: [], overflowEl: [], wrapped: [], lines: s.fit.lines || [] } : null,
  }));
  let wrote = null;
  try {
    const r = await page.request.post('http://localhost:5000/api/w4/steps', {
      data: { id: P.id, steps, records: { result: { ok: res.ok, unbuilt: res.unbuilt, problems: res.problems, notes: res.notes,
        summary: res.summary, metrics: res.metrics, modelStubbed: stub.n, deferred }, story: { id: story.id, archetype: story.archetype, tier: story.tier,
        vertical: story.vertical, device: story.device, language: story.language, condition: story.condition,
        moment: story.moment, cast: story.identity && story.identity.name, partner: story.partner && story.partner.name },
        psqlMisses: [...need] } },
      timeout: 10000,
    });
    wrote = r.ok() ? (await r.json()).path : `POST /api/w4/steps -> ${r.status()}`;
  } catch (e) { wrote = 'could not POST: ' + String(e.message || e).slice(0, 80); }
  return { mode, id: P.id, wrote, ok: res.ok, unbuilt: res.unbuilt, summary: res.summary, problems: res.problems, modelStubbed: stub.n,
           deferred: deferred.map((s) => s.slice(0, 160)),
           notes: (res.notes || []).map((n) => String(n).slice(0, 160)), psqlMisses: [...need],
           steps: steps.map((s) => `${s.page} ${s.chars}c own=${s.own} hub=${s.hub} ${s.settledBy || ''}${s.fit ? ' fit=' + s.fit.findings : ''}${s.offlineShell ? ' OFFLINE-SHELL' : ''}${s.signInWall ? ' SIGN-IN-WALL' : ''}${s.chars < 300 && (s.notice || s.errBanner) ? ' [' + String(s.notice || s.errBanner).slice(0, 80) + ']' : ''}${s.chars < 300 && s.rest.length ? ' rest=' + s.rest.join(',') : ''}`) };
}
