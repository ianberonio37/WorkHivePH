// arc_w_visual_sweep.mjs — Arc W (VISUAL UI/UX) R1: the 9-lens baseline + ratchet sweep.
//
// WHAT IT DOES (roadmap R1): signs in once per role (reusing the Arc-K recipe — ONE source of
// truth, no drift), then navigates EVERY registered page at BOTH the mobile (390px) and desktop
// (1280px) viewport, runs ARC_W_PROBE on each, scores the 9 lenses, and rolls the per-lens
// violation counts into a platform scoreboard. With --accept it freezes/ratchets arc_w_baseline.json
// (every per-lens floor is a forward-only CEILING — visual quality can only improve, never rot).
//
// REUSE (WAT #1 — never rebuild): signIn / makeHelpers / ACCOUNTS / SEEDER / HIVE come straight
// from live_page_journeys.mjs (the Arc-K recipe); the page list + primary role per page is derived
// from the JOURNEYS registry (so the ~25-page denominator stays in lockstep with Arc K/V — add a
// page there, it's swept here automatically). The probe/scorers live in arc_w_visual.mjs.
//
// USAGE:
//   node tools/arc_w_visual_sweep.mjs                       # full sweep, writes arc_w_results.json
//   node tools/arc_w_visual_sweep.mjs --page marketplace.html
//   node tools/arc_w_visual_sweep.mjs --accept              # freeze/ratchet arc_w_baseline.json
//   node tools/arc_w_visual_sweep.mjs --accept --update-baseline   # (re)bank the baseline
//   node tools/arc_w_visual_sweep.mjs --headed              # watch it

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { JOURNEYS } from './live_page_journeys.registry.mjs';
import { signIn, SEEDER, HIVE } from './live_page_journeys.mjs';
import { ARC_W_PROBE, scoreArcW, rollupArcW } from './arc_w_visual.mjs';

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const RESULTS = 'arc_w_results.json';
const BASELINE = 'arc_w_baseline.json';
const VIEWPORTS = [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 780 }];

// The per-lens ceilings the ratchet enforces. Each must NOT rise above baseline (+tol). tol=0 by
// default — every proxy is deterministic computed-style; if a lens proves jittery across two runs
// we bump its tol here (the Arc V calibration discipline). lens_floor is the headline ceiling.
const CEILINGS = [
  'lens_floor', 'depth_floor', 'focal_floor', 'whitespace_floor', 'grouping_floor', 'color_floor', 'icon_floor',
  'consistency_radius_variants', 'consistency_pad_variants', 'consistency_combo_variants', 'consistency_shadow_variants_max',
];
const TOL = 0;

// M/S lens is the one signal the page-probe can't read at rest (you can't observe :active without
// pressing). Snapshot it statically from components.css so the baseline carries the control-state
// FLOOR (target UP — W1 adds :active/:focus-visible + re-banks; validate_arc_w_visual.py then
// fails if a state rule is later lost). Skeleton + reduced-motion are regression guards.
function snapshotMS() {
  try {
    const css = readFileSync('components.css', 'utf8');
    return {
      active_rules: (css.match(/:active\b/g) || []).length,
      focus_visible_rules: (css.match(/:focus-visible\b/g) || []).length,
      has_skeleton: css.includes('.wh-skeleton'),
      has_reduced_motion: css.includes('prefers-reduced-motion'),
    };
  } catch (e) { return null; }
}

(async () => {
  // page list + primary role from the registry (single source of truth, mirrors effortless_sweep).
  const pageRole = {};
  for (const j of JOURNEYS) { if (!j.external && !pageRole[j.page]) pageRole[j.page] = j.role; }
  let pages = Object.keys(pageRole);
  if (PAGE_ONLY) pages = pages.filter(p => p === PAGE_ONLY);
  if (!pages.length) { console.error(`[W] no pages match (page=${PAGE_ONLY}). Registered: ${Object.keys(pageRole).length}`); process.exit(2); }

  const browser = await chromium.launch({ headless: !HEADED });
  const rolesNeeded = [...new Set(pages.map(p => pageRole[p]))];
  const contexts = {};
  for (const role of rolesNeeded) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
    const si = await signIn(ctx, role);
    console.log(`[W] sign-in ${role.padEnd(11)}: ${si.ok ? (si.anon ? 'ANON (no session)' : 'OK') : 'FAIL ' + si.err}`);
    contexts[role] = ctx;
  }

  const records = [];
  for (const pg of pages) {
    const role = pageRole[pg];
    const ctx = contexts[role] || contexts[rolesNeeded[0]];
    for (const vp of VIEWPORTS) {
      const page = await ctx.newPage();
      let raw = null, err = null;
      try {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(`${SEEDER}/workhive/${pg}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        // CONTENT-STABILITY settle (2026-07-21) — the fixed 2200ms wait was a fixed-wait RACE:
        // asset-hub's live+snapshot data wave sometimes outlasts it, so the probe read the pre-data
        // shell (cards 0 → focal false-fail vs the banked floor-0 baseline) while the live page is
        // healthy (84 cards). Same fix family_rubric_sweep.mjs proved: require 3 stable reads
        // (400ms apart) of the content fingerprint AND a >=2.2s elapsed floor (never settle on the
        // initial skeleton), cap 8s. Fast pages exit at the floor; slow data waves get real time.
        await page.evaluate(async () => {
          const fp = () => document.body.innerText.length + '|' +
            document.querySelectorAll('[class*="card"],[class*="tile"],[class*="panel"]').length;
          const t0 = Date.now();
          let last = fp(), stable = 0;
          while (Date.now() - t0 < 8000) {
            await new Promise(r => setTimeout(r, 400));
            const now = fp();
            stable = (now === last) ? stable + 1 : 0;
            last = now;
            if (stable >= 3 && Date.now() - t0 >= 2200) break;
          }
        });
        raw = await page.evaluate(ARC_W_PROBE);
      } catch (e) { err = String(e).slice(0, 140); }
      await page.close();
      const scored = raw ? scoreArcW(raw) : { __err: err || 'navigate-failed' };
      records.push({ page: pg, role, viewport: vp.name, scored, err });
      const lf = scored.__err ? `ERR ${scored.__err}` :
        `cards ${String(scored.cards).padStart(3)} flat ${String(scored.flat).padStart(3)} focal ${scored.focalRatio} gRatio ${scored.groupingRatio ?? '?'} wsF ${scored.whitespace_floor} peers ${scored.maxPeerPanels} hues ${scored.distinctAccentHues} icons ${scored.iconSources} -> floor ${scored.lens_floor}`;
      console.log(`  ${pg.padEnd(24)} ${vp.name.padEnd(8)} ${lf}`);
    }
  }

  for (const c of Object.values(contexts)) await c.close();
  await browser.close();

  const roll = rollupArcW(records);
  const out = { ran: new Date().toISOString(), seeder: SEEDER, hive: HIVE, viewports: VIEWPORTS.map(v => v.name), summary: roll, records };

  // per-page rollup (the vision-judge ranking surface — worst lens_floor first).
  const perPage = {};
  for (const r of records) {
    if (r.scored.__err) continue;
    const p = (perPage[r.page] = perPage[r.page] || { page: r.page, lens_floor: 0, flat: 0, depth_floor: 0, whitespace_floor: 0, grouping_floor: 0, color_floor: 0, focal_floor: 0, icon_floor: 0, maxPeerPanels: 0, distinctAccentHues: 0, focalRatio_min: 99 });
    p.lens_floor += r.scored.lens_floor; p.flat += r.scored.flat;
    p.depth_floor += r.scored.depth_floor; p.whitespace_floor += r.scored.whitespace_floor;
    p.grouping_floor += r.scored.grouping_floor; p.color_floor += r.scored.color_floor;
    p.focal_floor += r.scored.focal_floor; p.icon_floor += r.scored.icon_floor;
    p.maxPeerPanels = Math.max(p.maxPeerPanels, r.scored.maxPeerPanels);
    p.distinctAccentHues = Math.max(p.distinctAccentHues, r.scored.distinctAccentHues);
    if (r.scored.focalRatio > 0) p.focalRatio_min = Math.min(p.focalRatio_min, r.scored.focalRatio);
  }
  out.per_page = Object.values(perPage).sort((a, b) => b.lens_floor - a.lens_floor);

  console.log('\n' + '='.repeat(72));
  console.log('ARC W — VISUAL UI/UX (9-lens visual-quality scoreboard)');
  console.log('='.repeat(72));
  console.log(`  pages probed     : ${roll.pages_probed}  (×${VIEWPORTS.length} viewports = ${roll.records} records, ${roll.errored} errored)`);
  console.log(`  HEADLINE lens_floor : ${roll.lens_floor}  (sum of all gated lens violations — drive → 0)`);
  console.log(`    D depth_floor      : ${roll.depth_floor}   (flat coplanar card-like surfaces)`);
  console.log(`    H focal_floor      : ${roll.focal_floor}   (pages w/ max÷median font < 2.3×)`);
  console.log(`    W whitespace_floor : ${roll.whitespace_floor}   (page-vp w/ grouping-ratio <1.5 = no breathing room between groups)`);
  console.log(`    G grouping_floor   : ${roll.grouping_floor}   (peer-panels over 6 per column)`);
  console.log(`    T color_floor      : ${roll.color_floor}   (accent hues over 3 per view)`);
  console.log(`    I icon_floor       : ${roll.icon_floor}   (icon sources over 1 per view)`);
  console.log(`  C consistency (cross-page variant spread — ceiling, must not grow):`);
  console.log(`    radius ${roll.consistency_radius_variants} · pad ${roll.consistency_pad_variants} · combo ${roll.consistency_combo_variants} · shadow-variants(max/page) ${roll.consistency_shadow_variants_max}`);
  console.log(`  info: ${roll.total_cards} card-like els (${roll.total_flat} flat) · ${roll.total_status_hue_misuse} status-hue-misuse`);
  console.log(`\n  worst pages (lens_floor):`);
  for (const p of out.per_page.slice(0, 12)) {
    console.log(`    ${p.page.padEnd(24)} floor ${String(p.lens_floor).padStart(3)} · flat ${String(p.flat).padStart(3)} · peers ${p.maxPeerPanels} · hues ${p.distinctAccentHues} · focal-min ${p.focalRatio_min === 99 ? '-' : p.focalRatio_min}`);
  }

  // ── forward-only ratchet: every per-lens floor is a CEILING (visual quality can't rot) ──
  if (ACCEPT) {
    if (UPDATE_BASELINE || !existsSync(BASELINE)) {
      const banked = { tol: TOL, set: new Date().toISOString(), pages_probed: roll.pages_probed, records: roll.records };
      for (const k of CEILINGS) banked[k] = roll[k];
      banked.ms = snapshotMS();
      writeFileSync(BASELINE, JSON.stringify(banked, null, 2));
      console.log(`\n[W] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: ` + CEILINGS.map(k => `${k}<=${roll[k]}`).join(' '));
    } else {
      const b = JSON.parse(readFileSync(BASELINE, 'utf8'));
      const tol = b.tol ?? TOL;
      let failed = false;
      for (const k of CEILINGS) {
        if (b[k] != null && roll[k] > b[k] + tol) { console.error(`\n[W] RATCHET FAIL: ${k} ${roll[k]} > baseline ${b[k]} (+${tol} tol)`); failed = true; }
      }
      if (failed) { writeFileSync(RESULTS, JSON.stringify(out, null, 2)); process.exit(1); }
      console.log(`\n[W] ratchet OK: ` + CEILINGS.map(k => `${k} ${roll[k]}<=${b[k]}`).join(' · '));
    }
  }

  writeFileSync(RESULTS, JSON.stringify(out, null, 2));
  console.log(`\n  -> wrote ${RESULTS} (${records.length} records over ${roll.pages_probed} pages)`);
})();
