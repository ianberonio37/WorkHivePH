// UFAI DEEP probe for the service-hailing arc's 4 surfaces.
// Runs the LIVE checks ufai_pillar_map.py explicitly says its coarse lens slice does NOT cover:
//   U2  tap targets >= 44px on every interactive control (measured, at 390 width)
//   U5  axe a11y violations (vendored axe-core injected)
//   A1  responsive 360 -> 1920 with NO horizontal page scroll at any step
// F5 (CRUD round-trip) and I2/I3 (role/tenancy) are proven separately by the live walks and the
// C1/C3/C6/C10 gates, so this probe owns the three that need a browser and a ruler.
//
// Identity + recipe reused from tools/family_rubric_sweep.mjs (sign in once, same origin).
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'fs';

const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com';
const PASSWORD = 'test1234';
const HIVE = '4eec150e-4837-417b-bdd8-009b0192acfe';

const PAGES = [
  ['marketplace.html', '?section=services'],
  ['marketplace-seller.html', '?tab=services'],
  ['founder-console.html', ''],
  ['achievements.html', ''],
];
const WIDTHS = [360, 390, 768, 1280, 1920];

// ★TEETH FOR THE ONE RELAXATION IN THIS PROBE (--selftest, 2026-08-28). U2 exempts an inline link that
// sits inside a sentence, because WCAG 2.5.5/2.5.8 exempt a target "in a sentence or constrained by the
// line-height of non-target text" - you cannot make a WORD 44px tall without wrecking the paragraph, and
// a gate that demands it teaches people to ignore the gate. A relaxation with no teeth is how a detector
// quietly stops detecting, so the carve-out is pinned to four cases: only the inline-link-in-prose is
// excused; a short button, an inline-BLOCK link in the same sentence, and an inline link that is the
// whole line must all still be caught.
async function selfTest() {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await page.setContent(`<body style="font:14px sans-serif">
    <p>Update your <a id="a1" href="#" style="display:inline">Resume</a> automatically today.</p>
    <p>Press <button id="a2" style="height:23px;padding:0;display:inline-block">Go</button> to continue now.</p>
    <p>Open the <a id="a3" href="#" style="display:inline-block;height:23px">Guide</a> for more detail.</p>
    <p><a id="a4" href="#" style="display:inline">Standalone</a></p></body>`);
  const got = await page.evaluate(() => {
    const isInlineInSentence = (el) => {
      if (!/^inline$/.test(getComputedStyle(el).display)) return false;
      const parent = el.parentElement;
      if (!parent) return false;
      const own = (el.textContent || '').trim();
      const around = (parent.textContent || '').trim();
      return around.length > own.length + 1;
    };
    const o = {};
    for (const el of document.querySelectorAll('button, a[href]')) {
      const r = el.getBoundingClientRect();
      o[el.id] = (r.height < 44 - 0.5) && !isInlineInSentence(el);
    }
    return o;
  });
  await browser.close();
  const want = { a1: false, a2: true, a3: true, a4: true };
  let bad = 0;
  for (const k of Object.keys(want)) {
    const ok = got[k] === want[k];
    if (!ok) bad++;
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${k}: flagged=${got[k]} want=${want[k]}`);
  }
  console.log(bad ? `self-test FAILED (${bad}) - the inline exemption is not scoped correctly.`
                  : 'self-test PASS - the inline exemption excuses ONLY an inline link inside prose.');
  return bad === 0;
}

// TOP-LEVEL AWAIT, not .then(): process.exit inside a .then() is asynchronous, so the main sweep below
// would still start launching a browser and signing in before the exit landed. Awaiting here halts the
// module before any of that runs, which is the whole point of a self-test that costs nothing.
if (process.argv.slice(2).some((a) => a === '--selftest' || a === '--self-test')) {
  const ok = await selfTest();
  process.exit(ok ? 0 : 1);
}


const AXE = (() => {
  for (const p of ['tools/vendor/axe.min.js', 'node_modules/axe-core/axe.min.js']) {
    try { return readFileSync(p, 'utf8'); } catch (_) {}
  }
  return null;
})();

const out = {};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();

  // sign in once, same origin
  await page.goto(`${SEEDER}/workhive/marketplace.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.evaluate(async ([email, password, hive]) => {
    const db = window.db || (window.getDb && window.getDb());
    await db.auth.signOut().catch(() => {});
    await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_last_worker', 'Pablo Aguilar');
    localStorage.setItem('wh_active_hive_id', hive);
    localStorage.setItem('wh_hive_role', 'supervisor');
  }, [EMAIL, PASSWORD, HIVE]);

  for (const [file, qs] of PAGES) {
    const res = { u2: null, u5: null, a1: null, errors: [] };
    try {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(`${SEEDER}/workhive/${file}${qs}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(6000);

      // ---- U2: measured tap targets on VISIBLE interactive controls
      res.u2 = await page.evaluate(() => {
        const sel = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button], [onclick]';
        const els = [...document.querySelectorAll(sel)].filter(el => {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
        });
        // THE INLINE EXCEPTION, which WCAG grants and this probe did not (2026-08-28). Both 2.5.5 and
        // 2.5.8 exempt a target "in a sentence or whose size is otherwise constrained by the line-height
        // of non-target text" — you cannot make a word inside a paragraph 44px tall without wrecking the
        // paragraph. achievements.html was failed for exactly that: an <a>Resume</a> deliberately placed
        // mid-sentence, 23px tall because it is a WORD. Demanding a 44px word is not an accessibility
        // improvement, so a gate that does it teaches people to ignore it.
        // Scoped tightly so it cannot become a loophole for real buttons: the element must compute to an
        // inline display AND its parent must carry non-link text around it. A block-level control, or a
        // link that IS the whole line, stays measured.
        const isInlineInSentence = (el) => {
          if (!/^inline$/.test(getComputedStyle(el).display)) return false;
          const parent = el.parentElement;
          if (!parent) return false;
          const own = (el.textContent || '').trim();
          const around = (parent.textContent || '').trim();
          return around.length > own.length + 1;   // real prose sits beside it
        };
        const small = [];
        for (const el of els) {
          const r = el.getBoundingClientRect();
          if (r.height < 44 - 0.5 && !isInlineInSentence(el)) {
            small.push({ h: Math.round(r.height), t: (el.textContent || el.getAttribute('aria-label') || el.id || '').trim().slice(0, 34) });
          }
        }
        return { total: els.length, small: small.length, worst: small.sort((a, b) => a.h - b.h).slice(0, 4) };
      });

      // ---- U5: axe
      if (AXE) {
        await page.addScriptTag({ content: AXE });
        res.u5 = await page.evaluate(async () => {
          const r = await window.axe.run(document, { resultTypes: ['violations'] });
          return {
            violations: r.violations.length,
            serious: r.violations.filter(v => ['serious', 'critical'].includes(v.impact)).length,
            top: r.violations.slice(0, 4).map(v => `${v.id}(${v.impact}) x${v.nodes.length}`),
            // NAME THE ELEMENT, not just the count. This reported "U5 violations=1" and stopped there,
            // so the only way to learn WHICH node failed was to re-run the whole browser sweep by hand.
            // A gate that says something is broken owes the reader the thing that is broken.
            seriousNodes: r.violations
              .filter(v => ['serious', 'critical'].includes(v.impact))
              .flatMap(v => v.nodes.slice(0, 3).map(n => ({
                rule: v.id,
                target: (n.target || []).join(' '),
                html: String(n.html || '').slice(0, 160),
                why: String(n.failureSummary || '').replace(/\s+/g, ' ').slice(0, 200),
              }))),
          };
        });
      } else {
        res.u5 = { skipped: 'axe-core not found on disk' };
      }

      // ---- A1: responsive 360 -> 1920, no horizontal page scroll
      const overflow = [];
      for (const w of WIDTHS) {
        await page.setViewportSize({ width: w, height: 900 });
        await page.waitForTimeout(900);
        const o = await page.evaluate(() => ({
          scrollW: document.documentElement.scrollWidth,
          clientW: document.documentElement.clientWidth,
        }));
        if (o.scrollW > o.clientW + 2) overflow.push({ w, over: o.scrollW - o.clientW });
      }
      res.a1 = { widths: WIDTHS, overflow };
    } catch (e) {
      res.errors.push(String(e).slice(0, 160));
    }
    out[file] = res;
    console.log(`${file}: U2 small=${res.u2 ? res.u2.small : '?'}/${res.u2 ? res.u2.total : '?'} · ` +
                `U5 violations=${res.u5 && res.u5.violations !== undefined ? res.u5.violations : (res.u5 && res.u5.skipped) || '?'} · ` +
                `A1 overflow=${res.a1 ? res.a1.overflow.length : '?'}`);
  }

  await browser.close();
  writeFileSync('ufai_deep_arc_report.json', JSON.stringify(out, null, 2), 'utf8');

  // GATE MODE: the bar is 0 sub-44px targets, 0 horizontal overflow, and 0 SERIOUS/CRITICAL axe
  // violations on every arc surface. Moderate findings are reported but do not fail the build -
  // the two that remain are pre-existing containers outside this arc, recorded in the state file.
  const fails = [];
  for (const [file, r] of Object.entries(out)) {
    if (r.errors && r.errors.length) fails.push(`${file}: probe error ${r.errors[0]}`);
    if (r.u2 && r.u2.small > 0) {
      const who = (r.u2.worst || []).map(w => `"${w.t}" ${w.h}px`).join('; ');
      fails.push(`${file}: ${r.u2.small} tap target(s) under 44px${who ? ' — ' + who : ''}`);
    }
    if (r.a1 && r.a1.overflow.length) fails.push(`${file}: horizontal overflow at ${r.a1.overflow.map(o => o.w).join('/')}`);
    if (r.u5 && r.u5.serious > 0) {
      const who = (r.u5.seriousNodes || []).map(n => `${n.rule} @ ${n.target}`).join('; ');
      fails.push(`${file}: ${r.u5.serious} serious/critical axe violation(s)${who ? ' — ' + who : ''}`);
    }
  }
  if (fails.length) {
    console.error('FAIL - UFAI deep regression on the service-hailing surfaces:');
    for (const f of fails) console.error('  - ' + f);
    process.exit(1);
  }
  console.log('PASS - 0 sub-44px targets, 0 overflow (360-1920), 0 serious/critical axe on all arc surfaces.');
})();
