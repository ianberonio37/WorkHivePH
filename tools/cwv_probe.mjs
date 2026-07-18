// tools/cwv_probe.mjs — LIVE Core Web Vitals probe for the PUBLIC marketing surfaces.
//
// The slow HALF of the two-tool CWV scorer (the perf-skill pattern):
//   tools/cwv_probe.mjs  →  cwv_measurements.json  →  tools/cwv_gate.py (fast ratchet)
//
// Drives headless MOBILE Chromium across the catalog-derived public URLs (index.html +
// the 38 /learn articles + hub/about/privacy/terms), measures LCP/INP/CLS, takes the
// MEDIAN of N runs, and writes cwv_measurements.json for cwv_gate.py to ratchet.
//
// HONESTY (perf-skill lessons, 2026-06-22 — each guards a way a green CWV can LIE):
//   - Observers install at NAV-START via addInitScript (buffered:true) — late post-load
//     injection over-counts CLS/LCP ("Live-injected CWV is late-capture"); this is the
//     honest path the skill endorses.
//   - INP needs a TRUSTED interaction: a synthetic el.click() never yields INP (Chromium
//     only assigns interactionId to trusted input). We drive a real page.mouse.click on a
//     non-navigating element (heading / <summary> / button), then read INP.
//   - CLS is FROZEN before the INP click (a driven click adds shift a passive user never sees).
//   - LOCAL LCP is OPTIMISTIC vs PH-4G prod → stamped env:"local" / lcp_local_optimistic:true
//     (a local pass is necessary-not-sufficient; true field CWV is Layer B).
//   - Fresh context per run so transferSize!=0 (a warm cache reports 0 KB, not a 0 KB page).
//
// Surfaces come from `python tools/cwv_gate.py --surfaces` (the SAME catalog-derived list
// the gate ratchets) so the probe and the gate can never drift apart.
//
// Usage:
//   node tools/cwv_probe.mjs                       # measure all public surfaces, median-of-3
//   node tools/cwv_probe.mjs --runs 5
//   node tools/cwv_probe.mjs --limit 3             # first 3 surfaces only (smoke test)
//   node tools/cwv_probe.mjs --base http://127.0.0.1:5000
//   node tools/cwv_probe.mjs --headed

import { chromium } from 'playwright';
import { writeFileSync, readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

// ---- args ----
const argv = process.argv.slice(2);
function argVal(flag, def) {
  const i = argv.indexOf(flag);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : def;
}
const RUNS = parseInt(argVal('--runs', '3'), 10);
const LIMIT = parseInt(argVal('--limit', '0'), 10);
const BASE = argVal('--base', 'http://127.0.0.1:5000');
const HEADED = argv.includes('--headed');

const THRESHOLDS = { lcp_ms: 2500, inp_ms: 200, cls: 0.1 };
const VIEWPORT = { width: 390, height: 780 }; // mobile-first field size (matches platform perf tooling)

// Installed at nav-start in the page context — buffered observers survive to first read.
function INIT() {
  window.__cwv = { lcp: null, cls: 0, inp: null };
  try {
    new PerformanceObserver((l) => {
      const es = l.getEntries();
      const last = es[es.length - 1];
      if (last) window.__cwv.lcp = last.renderTime || last.loadTime || last.startTime;
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (e) { /* unsupported */ }
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cwv.cls += e.value;
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) { /* unsupported */ }
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.interactionId > 0) {
          const d = e.duration;
          if (window.__cwv.inp === null || d > window.__cwv.inp) window.__cwv.inp = d;
        }
      }
    }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
  } catch (e) { /* unsupported */ }
}

function median(arr) {
  const v = arr.filter((x) => x !== null && x !== undefined && !Number.isNaN(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

function surfaceToUrl(base, surface) {
  // "index.html" -> /workhive/ ; "learn/<slug>/index.html" -> /workhive/learn/<slug>/
  const p = surface.replace(/index\.html$/, '');
  return base.replace(/\/$/, '') + '/workhive/' + p;
}

function getSurfaces() {
  const out = execSync('python tools/cwv_gate.py --surfaces', { cwd: ROOT, encoding: 'utf-8' });
  const list = JSON.parse(out.trim());
  return LIMIT > 0 ? list.slice(0, LIMIT) : list;
}

// Measure one navigation in an EXISTING page (caller owns its lifecycle + the context's
// cache state). Observers are installed at context level (addInitScript) before the page exists.
async function measureOnce(page, url) {
  const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
  // Let the network + main thread go IDLE before the INP click. INP must be measured on a
  // SETTLED page (the lab convention): a click fired while late scripts (floating-ai.js,
  // Supabase init, the feedback FAB injection) are still executing inflates INP via INPUT
  // DELAY — a measurement artifact, NOT a real slow handler (verified: contended click 600ms
  // vs settled click 24ms on the same no-handler H1). networkidle may not fire if a page
  // holds a persistent connection, so cap it and fall through to a fixed settle.
  try { await page.waitForLoadState('networkidle', { timeout: 2500 }); } catch (e) { /* persistent conn */ }
  await page.waitForTimeout(1800);
  // FREEZE LCP + CLS before the INP interaction (a driven click adds shift a passive user never sees)
  const pre = await page.evaluate(() => ({ lcp: window.__cwv.lcp, cls: window.__cwv.cls }));
  // TRUSTED INP interaction — a non-navigating element in the viewport
  const target = await page.evaluate(() => {
    // Prefer genuinely interactive elements (a click with real processing → measurable INP);
    // fall back to headings (a fast no-handler click may be <16ms → INP legitimately unmeasured).
    const cands = Array.from(document.querySelectorAll('button, summary, [onclick], main h2, article h2, h1'));
    for (const el of cands) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.top >= 0 && r.top <= window.innerHeight - 10) {
        return { x: r.x + r.width / 2, y: r.y + Math.min(r.height / 2, 18) };
      }
    }
    return null;
  });
  if (target) await page.mouse.click(target.x, target.y);
  else await page.mouse.click(Math.round(VIEWPORT.width / 2), Math.round(VIEWPORT.height / 2));
  await page.waitForTimeout(700);
  const inp = await page.evaluate(() => window.__cwv.inp);
  return { lcp: pre.lcp, cls: pre.cls, inp, status: resp ? resp.status() : null };
}

const NOTE = 'Local Flask seeder, MOBILE viewport. lcp_ms = median of warm-cache runs (code-intrinsic '
  + 'render pipeline, isolates WorkHive from this machine\'s CDN latency). lcp_cold_ms = first-visit '
  + 'cold-cache LCP (dominated by the render-blocking Tailwind CDN fetch — a separate known perf item). '
  + 'Local LCP is optimistic vs PH-4G prod (a local pass is necessary-not-sufficient); true field CWV is Layer B.';

async function main() {
  const surfaces = getSurfaces();
  const dest = join(ROOT, 'cwv_measurements.json');
  const RELAUNCH_EVERY = 8;
  const FRESH = argv.includes('--fresh');

  // Resume: reuse rows from a COMPATIBLE prior run (same RUNS, a full non-limit run) so a
  // crash OR a periodic browser relaunch continues instead of restarting from scratch.
  const pages = [];
  const done = new Set();
  if (!FRESH) {
    try {
      const prev = JSON.parse(readFileSync(dest, 'utf-8'));
      if (prev && prev.runs_per_page === RUNS && !prev.limited && Array.isArray(prev.pages)) {
        for (const p of prev.pages) {
          if (p.surface && p.samples === RUNS) { pages.push(p); done.add(p.surface); }
        }
      }
    } catch (e) { /* no compatible prior run on disk */ }
  }
  const remaining = surfaces.filter((s) => !done.has(s));
  // --max N: process at most N remaining surfaces this invocation, then exit cleanly so the
  // OS fully reaps Chromium handles (the cure for ERR_INSUFFICIENT_RESOURCES on a long sweep).
  // Re-run (without --fresh) to resume the rest. Drive the full set in chunks of ~8.
  const MAX = parseInt(argVal('--max', '0'), 10);
  const todo = MAX > 0 ? remaining.slice(0, MAX) : remaining;

  function writeOut(complete) {
    writeFileSync(dest, JSON.stringify({
      generated_at: new Date().toISOString(), env: 'local', cache: 'warm-median',
      lcp_local_optimistic: true, base: BASE, viewport: VIEWPORT, runs_per_page: RUNS,
      limited: LIMIT > 0, complete, thresholds: THRESHOLDS, note: NOTE, pages,
    }, null, 2), 'utf-8');
  }

  console.log(`\n  CWV PROBE · ${surfaces.length} public surfaces × ${RUNS} runs · ${BASE}/workhive/`);
  if (done.size) console.log(`  resuming: ${done.size} already measured · ${remaining.length} to go${MAX > 0 ? ` · this chunk: ${todo.length}` : ''}`);
  console.log('  ' + '='.repeat(64));

  let browser = await chromium.launch({ headless: !HEADED });
  let sinceRelaunch = 0;
  let idx = done.size;
  for (const surface of todo) {
    idx++;
    const url = surfaceToUrl(BASE, surface);
    const lcps = [], clss = [], inps = [];
    let lastStatus = null, transferKB = null, lcpCold = null;
    // ONE context per surface: cache warms after the first nav so measured LCP reflects
    // WorkHive's render pipeline, not this machine's cdn.tailwindcss.com round-trip.
    const context = await browser.newContext({ viewport: VIEWPORT, isMobile: true, hasTouch: true });
    await context.addInitScript(INIT);
    try {
      // warm-up nav (COLD cache) — populates the context cache AND captures the real
      // first-visit weight + cold LCP (informational; the render-blocking Tailwind CDN
      // first-load cost is a separate, known perf-track item, not the ratchet metric).
      try {
        const w = await context.newPage();
        const resp = await w.goto(url, { waitUntil: 'load', timeout: 30000 });
        await w.waitForTimeout(1200);
        lastStatus = resp ? resp.status() : null;
        const cold = await w.evaluate(() => {
          const n = performance.getEntriesByType('navigation')[0];
          return { transferKB: n ? Math.round((n.transferSize || 0) / 1024) : null, lcp: window.__cwv.lcp };
        });
        transferKB = cold.transferKB;
        lcpCold = cold.lcp != null ? Math.round(cold.lcp) : null;
        await w.close();
      } catch (e) {
        console.log(`    \x1b[91mWARM-UP ERR\x1b[0m ${surface}: ${String(e.message).split('\n')[0]}`);
      }
      // measured runs (WARM cache → stable, code-intrinsic CWV)
      for (let r = 0; r < RUNS; r++) {
        const page = await context.newPage();
        try {
          const m = await measureOnce(page, url);
          if (m.lcp != null) lcps.push(m.lcp);
          if (m.cls != null) clss.push(m.cls);
          if (m.inp != null) inps.push(m.inp);
          if (m.status != null) lastStatus = m.status;
        } catch (e) {
          console.log(`    \x1b[91mERR\x1b[0m  ${surface} run ${r + 1}: ${String(e.message).split('\n')[0]}`);
        } finally {
          await page.close();
        }
      }
    } finally {
      await context.close();
    }
    const lcp_ms = median(lcps);
    const cls = median(clss);
    const inp_ms = median(inps);
    const row = {
      surface, url,
      lcp_ms: lcp_ms != null ? Math.round(lcp_ms) : null,
      inp_ms: inp_ms != null ? Math.round(inp_ms) : null,
      inp_measured: inp_ms != null,
      cls: cls != null ? Math.round(cls * 1000) / 1000 : null,
      lcp_cold_ms: lcpCold,
      transferKB,
      http_status: lastStatus,
      samples: RUNS,
      lcp_samples: lcps.map((x) => Math.round(x)),
      cls_samples: clss.map((x) => Math.round(x * 1000) / 1000),
      inp_samples: inps.map((x) => Math.round(x)),
    };
    pages.push(row);
    const flag = (v, t) => (v == null ? '\x1b[90m—\x1b[0m' : v > t ? `\x1b[91m${v}\x1b[0m` : `\x1b[92m${v}\x1b[0m`);
    console.log(
      `    [${String(idx).padStart(2)}/${surfaces.length}] ${surface.replace(/\/index\.html$/, '').padEnd(52)}` +
      ` LCP=${flag(row.lcp_ms, THRESHOLDS.lcp_ms)}ms INP=${flag(row.inp_ms, THRESHOLDS.inp_ms)}ms CLS=${flag(row.cls, THRESHOLDS.cls)}`
    );
    writeOut(false);                         // persist after EVERY surface — crash-safe + resumable
    if (++sinceRelaunch >= RELAUNCH_EVERY) {  // bound Chromium memory across all 43 surfaces
      await browser.close();
      browser = await chromium.launch({ headless: !HEADED });
      sinceRelaunch = 0;
    }
  }
  await browser.close();
  writeOut(pages.length >= surfaces.length);  // complete only when ALL surfaces measured

  const over = (k, t) => pages.filter((p) => p[k] != null && (k === 'inp_ms' ? p.inp_measured : true) && p[k] > t).length;
  console.log('  ' + '-'.repeat(64));
  console.log(`  measured ${pages.length} surfaces → ${dest.replace(ROOT, '.')}`);
  console.log(`  over threshold:  LCP ${over('lcp_ms', THRESHOLDS.lcp_ms)} · INP ${over('inp_ms', THRESHOLDS.inp_ms)} · CLS ${over('cls', THRESHOLDS.cls)}`);
  console.log(`  next:  python tools/cwv_gate.py --update-baseline   (establish ratchet)\n`);
}

main().catch((e) => { console.error(e); process.exit(1); });
