// prove_one_vocabulary.mjs — the CE `one_vocabulary` oracle, measured on rendered surfaces.
//
// THE ORACLE: "one concept, one word, across every surface that shows it — 'credits' is not 'points'
// three screens later."
//
// ★THE HARD PART IS DECIDING WHAT COUNTS AS DRIFT, because English is not the enemy. A page may use
// "job" in prose and "Open Jobs" in a tile without anything being wrong. Drift is when the SAME CONCEPT
// is given DIFFERENT NAMES on surfaces a person moves between — so this checks concept GROUPS whose
// members are genuinely interchangeable, and only in LABEL positions (tile labels, headings, pills,
// chips), never in body prose. A body-wide keyword sweep on this platform reads its own marketing copy
// and its guide text, an error already recorded in this bank.
//
// ★THE GROUPS ARE THE ONES THE ROADMAP ITSELF NAMES, not ones I invented:
//   · SEVERITY — alert-hub's CI#1: "Severity vocabulary is one vocabulary shared with hive and
//     analytics — critical here is critical there."
//   · REWARD — achievements/community/marketplace: "XP is not money", and a credits-chip drift is the
//     precedent this whole bank was built after.
//   · PERSON — the role vocabulary already carries an explicit alias map ({worker: field}), which is
//     CONTROLLED drift; this checks the rendered word, not the map.
//   · LATENESS, ASSET, TEAM — the everyday synonyms a maintenance product slides between.
//
// ★AND A GROUP APPEARING ON ONE PAGE ONLY IS NOT DRIFT. Drift needs two surfaces disagreeing, so a
// concept found on a single page ABSTAINS rather than passing or failing: there is nothing to be
// consistent WITH.
//
// USAGE:  node tools/prove_one_vocabulary.mjs
// OUTPUT: one_vocabulary_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

// concept -> interchangeable words. The FIRST is treated as canonical only for reporting; the oracle
// is about agreement between surfaces, not about which word wins.
const GROUPS = {
  severity: ['critical', 'urgent', 'severe', 'high priority'],
  reward: ['xp', 'points', 'credits'],
  person: ['worker', 'technician', 'field', 'operator', 'staff'],
  lateness: ['overdue', 'late', 'past due', 'behind schedule'],
  asset: ['asset', 'equipment', 'machine'],
  team: ['hive', 'team', 'crew'],
};

const scan = async (page) => page.evaluate((GROUPS) => {
  // ★LABEL POSITIONS ONLY. A concept named differently in a tile label is drift a person walks into; the
  // same word inside a paragraph of guide copy is prose. This is the narrowing that keeps the check from
  // reading the platform's own marketing text back at it.
  const LABEL_SEL = '.sc-label, .oh-tile-lbl, .kpi-label, .stat-label, .pill, .chip, .status-pill, '
    + '[class*="-label"], [class*="-lbl"], [class*="pill"], [class*="chip"], [class*="tag"], '
    + 'h1, h2, h3, h4, th, label, [role="tab"], .phase-tab';
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.height > 0 && r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const labels = [];
  for (const el of document.querySelectorAll(LABEL_SEL)) {
    if (!vis(el)) continue;
    // ★THE AMC BRIEF'S LABELS BELONG TO A NAMED FEATURE, and phrase-stripping could not reach them: the
    // element says just "Crew", so nothing in the TEXT reveals that it is the Autonomous Maintenance
    // Crew's stat rather than a synonym for the tenant. Only the surrounding markup knows, so the
    // exclusion is scoped by container (`.amc-*`) rather than by wording.
    if (el.closest('[class*="amc"], [id*="amc"]')) continue;
    const t = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
    if (t && t.length <= 60) labels.push(t);
  }
  // ★A PROPER NOUN THAT CONTAINS THE WORD IS NOT THE WORD. Two of the five drifts this oracle reported
  // were feature names, and renaming either would have made the product WORSE:
  //   · engineering-design's "Machine Design" is an engineering DISCIPLINE, sitting beside Civil and
  //     Electrical. "Asset Design" is not a thing.
  //   · alert-hub's "Crew" is the stat label inside the AMC brief - Autonomous Maintenance CREW - a
  //     feature name, not the tenant noun.
  // Ian settled the real drift (2026-08-19: "asset" everywhere, "hive" everywhere) and these two were
  // the residue that kept both concepts reading MIXED afterwards. They are stripped before matching, so
  // the oracle judges the vocabulary and not the brand.
  const PROPER = [/machine\s+design/ig, /autonomous\s+maintenance\s+crew/ig, /AMC.{0,12}crew/ig];
  let joined = labels.join(' | ');
  for (const re of PROPER) joined = joined.replace(re, ' ');
  const blob = ' ' + joined + ' ';
  const found = {};
  for (const [concept, words] of Object.entries(GROUPS)) {
    const hits = words.filter((w) => new RegExp('(^|[^a-z])' + w.replace(/ /g, '\\s+') + '([^a-z]|$)', 'i').test(blob));
    if (hits.length) found[concept] = hits;
  }
  return { found, labelCount: labels.length };
}, GROUPS);

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, pages: {}, concepts: {} };

  for (const name of PAGES) {
    const page = await ctx.newPage();
    try {
      await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(5500);
      const r = await scan(page);
      out.pages[name] = r;
      console.log(`  ${name.padEnd(19)} labels=${String(r.labelCount).padStart(3)} `
        + Object.entries(r.found).map(([c, w]) => `${c}:${w.join('/')}`).join('  '));
    } catch (e) { out.pages[name] = { error: String(e.message || e).slice(0, 120) }; }
    await page.close();
  }
  await browser.close();

  // Per concept: which word does each page use? Drift = two pages using DIFFERENT words for it.
  for (const concept of Object.keys(GROUPS)) {
    const usage = {};
    for (const [pg, r] of Object.entries(out.pages)) {
      const w = (r.found || {})[concept];
      if (w && w.length) usage[pg] = w;
    }
    const pages = Object.keys(usage);
    const words = new Set(pages.flatMap((p) => usage[p]));
    // ★A PAGE USING TWO WORDS FROM A GROUP IS DEFINING, NOT DRIFTING — and counting distinct words
    // across the roster conflated the two. pm-scheduler renders "Overdue" as its label and "Past due
    // date" as that label's SUB: the second word EXPLAINS the first, which is the behaviour the
    // number_explained oracle actively asks for. Every page in that group says "overdue"; one page also
    // says what it means, and my first rule called that drift.
    // Drift is two surfaces that share NO word for the concept — a person moving between them meets a
    // different name with nothing connecting the two.
    const sets = pages.map((p) => new Set(usage[p]));
    let disjoint = null;
    for (let i = 0; i < sets.length && !disjoint; i++) {
      for (let j = i + 1; j < sets.length; j++) {
        if (![...sets[i]].some((w) => sets[j].has(w))) { disjoint = [pages[i], pages[j]]; break; }
      }
    }
    let verdict;
    if (pages.length < 2) verdict = 'ABSTAIN';           // nothing to be consistent WITH
    else if (!disjoint) verdict = 'CONSISTENT';
    else verdict = 'MIXED';
    out.concepts[concept] = { verdict, pages: pages.length, words: [...words], usage,
      disjointPair: disjoint };
    console.log(`\n  ${verdict.padEnd(10)} ${concept.padEnd(9)} across ${pages.length} page(s): `
      + [...words].join(' / '));
  }
  writeFileSync(path.join(ROOT, 'one_vocabulary_report.json'), JSON.stringify(out, null, 1));
  const mixed = Object.entries(out.concepts).filter(([, v]) => v.verdict === 'MIXED');
  console.log(`\n  ${mixed.length} concept(s) MIXED across surfaces`);
};
run().catch((e) => { console.error(e); process.exit(1); });
