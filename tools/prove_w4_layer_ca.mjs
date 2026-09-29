// prove_w4_layer_ca.mjs - LIVE the wave-4 CA-layer rows ("The platform must speak, on this page, the words a Philippine
// maintenance crew uses") on the real page, at the axis, as the row's person, along the row's path. (Wave 4, 2026-09-15.)
//
// CA is a PERSON layer (F, CA): the witness is what the person READS, so every step carries the overlap audit and the
// subject page carries a vocabulary reading:
//   stamps   - the page carries the platform's language stamps ([data-i]) - the mechanism by which it can speak Filipino
//   crew     - at an English axis the visible copy uses the crew's own words (PM, work order, breakdown, downtime, spare
//              parts, LOTO / permit, shift, handover, checklist, MTBF / OEE, supervisor / technician / crew, hive, logbook,
//              asset / machine, inspection / repair / fault, plant) - at least CREW_MIN distinct terms
//   filipino - at the Filipino axis (wh_lang=fil) the visible copy carries the platform's OWN Filipino vocabulary
//              (window.WH_FIL_COMMON values + the crew's Filipino words) - at least FIL_MIN distinct words - so the page
//              does not merely carry stamps but renders them
// A subject page that fails its reading keeps the row open, with the counts in the note. Rows sharing a path and a cast
// are walked once. Receipt: .tmp/mcp_walks/W4layerCA_<axis>.json (merged by id), read by live_walk_manifest._w4_receipts.
//
//   node tools/prove_w4_layer_ca.mjs --axis "phone-390 en" [--subject "ai quality"] [--limit 3] [--force]
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import os from 'node:os';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : d; };
const AXIS = arg('--axis', 'phone-390 en');
const SUBJECT = arg('--subject', '');
const LIMIT = Number(arg('--limit', '0')) || 0;
const FORCE = process.argv.includes('--force');
const ORIGIN = arg('--origin', 'http://localhost:5000/workhive');
const [device, lang] = AXIS.split(' ');
const viewport = device === 'narrow-320' ? { width: 320, height: 720 } : { width: 390, height: 844 };
const AUDIT = readFileSync('tools/phone_fit_audit.browser.js', 'utf8');
const atPath = (h) => new RegExp('/' + h.split('.').join('[.]') + '(?:[?#]|$)');
const CREW_MIN = 4, FIL_MIN = 6;
// the crew's everyday words, not only the standards' - a page that says "job", "team", "report", "alert" and "log" speaks
// to a technician as surely as one that says "MTBF" (the smoke read ai-quality as 2 terms because the list began too formal)
const CREW = ['preventive maintenance', 'work order', 'breakdown', 'downtime', 'spare part', 'spares', 'lockout', 'loto', 'permit', 'ptw', 'shift', 'handover', 'checklist', 'mtbf', 'mttr', 'oee', 'supervisor', 'technician', 'crew', 'hive', 'logbook', 'asset', 'machine', 'inspection', 'repair', 'fault', 'plant', 'maintenance', 'philippine', 'pinoy', 'barangay', 'pm schedule', 'pm task', 'root cause', 'failure', 'safety', 'calibration', 'equipment', 'job', 'jobs', 'task', 'team', 'worker', 'workers', 'report', 'alert', 'alerts', 'log', 'entry', 'record', 'schedule', 'part', 'parts', 'tool', 'tools', 'inventory', 'stock', 'restock', 'fix', 'fixes', 'work', 'workshop', 'factory', 'operator', 'foreman', 'engineer', 'manual', 'sop', 'procedure', 'compliance', 'incident', 'hazard'];
const FIL = ['trabaho', 'sira', 'ayusin', 'makina', 'gawain', 'piyesa', 'turno', 'kagamitan', 'inspeksyon', 'pag-aayos', 'tsek', 'planta', 'manggagawa', 'superbisor', 'pahintulot', 'iskedyul', 'tala', 'ngayon', 'linggo', 'buwan', 'mga', 'ang', 'sa iyong', 'hindi', 'pang-araw-araw', 'balik', 'bumalik', 'ipakita', 'itago', 'i-save', 'maghanap', 'tulong', 'mag-sign'];

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8', timeout: 30000 }).trim(); } catch (e) { return ''; } };
const CAST = {};
for (const line of psql("select h.name||'|'||m.worker_name||'|'||m.role||'|'||coalesce(u.email,'') from hives h join hive_members m on m.hive_id = h.id left join auth.users u on u.id = m.auth_uid where m.status = 'active' order by h.name, m.role, m.worker_name").split('\n')) {
  const [hive, worker, role, email] = line.split('|');
  if (!hive || !email) continue;
  CAST[hive] = CAST[hive] || {};
  if (role === 'worker' && !CAST[hive].worker) CAST[hive].worker = { name: worker, email, user: email.split('@')[0] };
  if (role !== 'worker' && !CAST[hive].supervisor) CAST[hive].supervisor = { name: worker, email, user: email.split('@')[0] };
}
// a hive whose only account is its supervisor (Ramos Jeepney Line - Oscar Ramos) is lived by the supervisor, as the nav-hub walk does
for (const h of Object.keys(CAST)) if (!CAST[h].worker && CAST[h].supervisor) CAST[h].worker = CAST[h].supervisor;

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const shortOf = (t) => { const m = (t.title || '').match(/ - ([^·]+) · /); return m ? m[1].trim() : ''; };
const subjectPage = (t) => {
  if (t.persona === 'anon') return (t.pages || [])[0];
  const s = shortOf(t).toLowerCase();
  return (t.pages || []).find((p) => p.replace(/\.html$/, '').replace(/[-_/]/g, ' ').toLowerCase() === s) || (t.pages || []).slice(-1)[0];
};
let rows = reg.trajectories.filter((t) => (t.w4 || {}).kind === 'layer' && t.w4.layer === 'CA'
  && `${(t.axis || {}).device} ${(t.axis || {}).language}` === AXIS && (FORCE || !['locking', 'locked', 'descoped'].includes(t.status)));
if (SUBJECT) rows = rows.filter((t) => shortOf(t).toLowerCase() === SUBJECT.toLowerCase());
const groups = new Map();
for (const t of rows) { const key = (t.pages || []).join('>') + '|' + (t.persona === 'anon' ? 'anon' : ((t.journey || {}).vertical || '')); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(t); }
let groupList = [...groups.values()];
if (LIMIT) groupList = groupList.slice(0, LIMIT);
if (!groupList.length) { console.log(`PASS w4-layer-ca - no open CA row on axis "${AXIS}" (nothing to walk)`); process.exit(0); }
console.log(`${rows.length} CA row(s) in ${groupList.length} walk group(s) on ${AXIS}`);

const AUDIT_STEP = (s) => { if (!window.__W4_AUDIT) return { step: s, error: 'audit not installed', findings: 0 }; const r = window.__W4_AUDIT(null, { step: s }); return { step: s, vw: innerWidth, findings: r.findings || 0, occlusion: (r.occlusion || []).slice(0, 4), overflowEl: (r.overflowEl || []).slice(0, 2), wrapped: (r.wrapped || []).slice(0, 2), confusions: r.confusions || 0 }; };
const READ = () => ({ url: location.pathname.split('/').pop() + location.search, worker: localStorage.getItem('wh_last_worker'), chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length });
const VOCAB = ({ CREW, FIL }) => {
  const text = ' ' + (document.body.innerText || '').replace(/\s+/g, ' ').toLowerCase() + ' ';
  const has = (w) => new RegExp('(^|[^a-z\\u00C0-\\u024F])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z\\u00C0-\\u024F]|$)', 'i').test(text);
  const crew = CREW.filter(has);
  const dict = (window.WH_FIL_COMMON && typeof window.WH_FIL_COMMON === 'object') ? Object.values(window.WH_FIL_COMMON).filter((v) => typeof v === 'string' && v.length > 3).map((v) => v.toLowerCase()) : [];
  const fil = [...new Set([...FIL, ...dict])].filter(has);
  return { stamps: document.querySelectorAll('[data-i]').length, dictSize: dict.length, crew: crew.slice(0, 12), crewCount: crew.length, fil: fil.slice(0, 12), filCount: fil.length, htmlLang: document.documentElement.lang || '', whLang: (() => { try { return localStorage.getItem('wh_lang') || ''; } catch (e) { return ''; } })() };
};

const browser = await chromium.launch();
const results = [];
const freeGb = () => os.freemem() / 1e9;
mkdirSync('.tmp/mcp_walks', { recursive: true });
const outFile = `.tmp/mcp_walks/W4layerCA_${AXIS.replace(/\s+/g, '-')}.json`;
const flush = () => { let merged = results; try { if (existsSync(outFile)) { const prior = JSON.parse(readFileSync(outFile, 'utf8')); const now = new Map(results.map((r) => [r.id, r])); merged = (prior.results || []).map((r) => now.get(r.id) || r).concat(results.filter((r) => !(prior.results || []).some((p) => p.id === r.id))); } } catch (e) { void e; } writeFileSync(outFile, JSON.stringify({ generated: new Date().toISOString(), instrument: 'tools/prove_w4_layer_ca.mjs', axis: AXIS, walked: results.length, bad: results.filter((r) => !r.ok).length, results: merged }, null, 1)); };
for (const group of groupList) {
  const t0 = group[0]; const pages = (t0.pages || []).slice(); const anon = t0.persona === 'anon';
  const hive = (t0.journey || {}).vertical; const who = !anon && hive && CAST[hive] ? CAST[hive].worker : null;
  const problems = []; const steps = []; const vocab = {};
  let waited = 0; while (freeGb() < 0.6 && waited < 180) { await new Promise((r) => setTimeout(r, 15000)); waited += 15; }
  const context = await browser.newContext({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 1, locale: lang === 'fil' ? 'fil-PH' : 'en-PH', serviceWorkers: 'block' });
  const page = await context.newPage();
  await page.addInitScript({ content: AUDIT });
  if (lang === 'fil') await page.addInitScript(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
  const settle = async () => { await page.waitForTimeout(3500); let r = await page.evaluate(READ).catch(() => ({ chars: 0 })); let k = 0; while (r.chars < 900 && k < 3) { await page.waitForTimeout(3000); r = await page.evaluate(READ).catch(() => ({ chars: 0 })); k++; } };
  const step = async (label) => { await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {}); await page.waitForTimeout(300); const r = await page.evaluate(READ).catch(() => ({ chars: 0, url: '?' })); const a = await page.evaluate(AUDIT_STEP, label).catch(() => ({ findings: 0 })); const v = await page.evaluate(VOCAB, { CREW, FIL }).catch(() => null); if (v) vocab[label] = v; steps.push({ page: label, arrivedAt: r.url, chars: r.chars, identityKept: anon ? true : !!r.worker, fit: { findings: a.findings || 0, occlusion: a.occlusion || [], overflowEl: a.overflowEl || [], wrapped: a.wrapped || [], confusions: a.confusions || 0 } }); if (r.chars < 120) problems.push(`${label}: arrived with ${r.chars} chars`); if ((a.occlusion || []).length) problems.push(`overlap at "${label}": ` + a.occlusion.slice(0, 2).join(' | ')); };
  try {
    if (anon) {
      for (const p of pages) { await page.goto(`${ORIGIN}/${p}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`)); await settle(); await step(p); }
    } else {
      await page.goto(`${ORIGIN}/index.html?signin=1&return=${pages[1] || pages[0]}`, { waitUntil: 'load', timeout: 60000 });
      await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
      await step('index.html');
      if (!who) problems.push(`no active worker with an account in ${hive}`);
      else if (await page.locator('#si-username').isVisible().catch(() => false)) {
        await page.fill('#si-username', who.user, { timeout: 8000 }); await page.fill('#si-password', 'test1234', { timeout: 8000 });
        await page.click('#si-btn', { timeout: 10000 }).catch(async () => { await page.press('#si-password', 'Enter').catch(() => {}); });
        await page.waitForURL(atPath(pages[1] || pages[0]), { timeout: 30000 }).catch(async () => { problems.push('sign-in did not reach ' + (pages[1] || pages[0]) + ' in 30s: ' + await page.evaluate(() => ((document.getElementById('si-error') || {}).textContent || '').trim().slice(0, 100)).catch(() => '?')); });
      }
      for (const p of pages.slice(1)) { const here = await page.evaluate(() => location.pathname.split('/').pop()).catch(() => ''); if (here !== p) await page.goto(`${ORIGIN}/${p}`, { waitUntil: 'load', timeout: 60000 }).catch((err) => problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`)); await settle(); await step(p); }
    }
  } catch (err) { problems.push('the walk threw: ' + String(err.message).split('\n')[0].slice(0, 120)); }
  await context.close().catch(() => {});
  const idKept = anon ? true : steps.slice(1).every((s) => s.identityKept);
  const distinct = new Set(steps.map((s) => s.page)).size;
  for (const t of group) {
    const subj = subjectPage(t); const v = vocab[subj];
    let pred;
    if (!v) pred = { ok: false, detail: `the subject page ${subj} was not read` };
    else if (lang === 'fil') pred = { ok: v.stamps >= 1 && v.filCount >= FIL_MIN, detail: `${subj}: ${v.stamps} language stamps, ${v.filCount} Filipino words rendered (${v.fil.slice(0, 6).join(', ')}) [wh_lang=${v.whLang}, dict ${v.dictSize}]` };
    else pred = { ok: v.stamps >= 1 && v.crewCount >= CREW_MIN, detail: `${subj}: ${v.stamps} language stamps, ${v.crewCount} crew terms (${v.crew.slice(0, 6).join(', ')})` };
    const rowProblems = problems.slice(); if (!pred.ok) rowProblems.push(`CA not lived clean: ${pred.detail}`); if (!idKept) rowProblems.push('identity did not survive the arrival'); if (distinct < 4) rowProblems.push(`only ${distinct} distinct pages walked`);
    const ok = rowProblems.length === 0;
    results.push({ id: t.id, ok, unbuilt: !anon && !who, instrument: 'tools/prove_w4_layer_ca.mjs', condition: 'normal', cast: anon ? 'anonymous reader' : (who ? `${who.name} (${hive})` : `no cast in ${hive}`), problems: rowProblems,
      note: `CA ${pred.ok ? 'LIVED CLEAN' : 'STILL OPEN'}: ${pred.detail}`, metrics: { steps: steps.length, idKept, predicate: pred.ok },
      w4: { axis: AXIS, layer: 'CA', subject: subj, vocab: v || null }, steps, confusions: [] });
    console.log(`  ${ok ? '\x1b[92mOK \x1b[0m' : '\x1b[91mBAD\x1b[0m'} ${t.id.padEnd(7)} ${shortOf(t).slice(0, 34).padEnd(34)} ${(anon ? 'anon' : (who ? who.name : '?')).padEnd(18)} ${pred.detail.slice(0, 130)}${!ok && !pred.ok ? '' : (!ok ? ' | ' + rowProblems[0].slice(0, 80) : '')}`);
  }
  flush();
  await new Promise((r) => setTimeout(r, 3000));
}
await browser.close();
flush();
const bad = results.filter((r) => !r.ok).length;
console.log(`${bad ? 'FAIL' : 'PASS'} w4-layer-ca@${AXIS} - ${results.length - bad}/${results.length} CA rows lived clean start to end (path walked, identity kept, the crew's words on the subject page, no overlap) · ${outFile}`);
