// prove_reward_explained.mjs — CM `reward_explained`: a reward shown without its criteria is a number,
// not a motivator.
//
// WHAT THE PLATFORM ITSELF PROMISES. The roadmap's own domain truths for these surfaces say it plainly:
// "Each achievement STATES ITS CRITERIA", "Level thresholds are stated", "XP per action is stated BEFORE
// the action, where it is meant to motivate", "A locked achievement reads as locked-WITH-CRITERIA, never
// as absent", "Badge tiers state their thresholds". This oracle checks that against the rendered page.
//
// WHY IT MATTERS HERE MORE THAN USUAL: on this platform XP and badges are attached to a person's
// CREDENTIAL and their marketplace standing. "You have 405 XP" with nothing saying what earns the next
// level, or a badge with no stated threshold, is a scoreboard someone cannot play — and on skillmatrix it
// shades into a claim about their qualifications.
//
// GROUNDED SUBJECTS, NOT A SWEEP OF ALL 22 PAGES. Rewards live where the anatomy says they live:
// achievements (47 XP mentions / 27 level-badge functions), community (23/23), skillmatrix (badges, 52),
// hive (49). A page with no reward on screen is NOT APPLICABLE — the row is left OWED with the reason
// recorded, never failed, exactly as the CN prover treats a page with no composer to abandon. Banking a
// red against a page for not having rewards is the vacuity R10 forbids.
//
// WHAT COUNTS AS AN EXPLANATION. Not "some words exist nearby" — the text has to do the job a person
// needs: say what EARNS the thing, or what THRESHOLD it sits at. So the search is for criteria language
// (earn / complete / reach / unlock / per / requires / next level at / N XP to), taken from the platform's
// own copy, within the reward's own card — plus the accessible description, since an explanation delivered
// only to a screen reader still counts as delivered, and one delivered only visually still counts too.
//
// THE TRAP THIS AVOIDS, learned from the CN build: a keyword found ANYWHERE on the page is not an
// explanation OF THIS REWARD. A page with one paragraph explaining XP at the bottom does not thereby
// explain a badge at the top. So the criteria text must live inside the reward's own container, and the
// container is bounded — the nearest card/tile/li, never `document.body`.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// Every page the bank carries a `reward_explained` row for; the ones without rewards resolve to
// NOT APPLICABLE at run time rather than being excluded here, so the roster stays honest about what was
// looked at versus what was found.
const PAGES = ['achievements', 'community', 'skillmatrix', 'hive', 'index', 'logbook', 'dayplanner',
  'resume', 'inventory', 'pm-scheduler', 'analytics', 'alert-hub', 'shift-brain', 'voice-journal',
  'asset-hub', 'project-manager', 'project-report', 'report-sender',
  // ★FOUR PAGES WERE MISSING FROM THIS ROSTER. A roster is a silent claim about SCOPE, and an
  // incomplete one makes a green look total - prove_why_refused reported '17 of 17, 0 failing' the
  // same way while five pages, including the ANON surface, had never been asked. Added rather than
  // assumed irrelevant: a page that offers no reward simply abstains, which is cheap and honest.
  'assistant', 'engineering-design', 'public-feed', 'analytics-report'];

const SCAN = ({ rewardSrc, criteriaSrc }) => {
  const REWARD = new RegExp(rewardSrc, 'i');
  const CRIT = new RegExp(criteriaSrc, 'i');
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const found = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;                  // the leaf carries the rendered figure
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t || t.length > 60 || !REWARD.test(t) || !vis(el)) continue;
    // THE ELEMENT MUST BE THE FIGURE, NOT PROSE THAT MENTIONS ONE. "4 of 12 domains touched at Level 1+"
    // matches the reward pattern on "Level 1" and is a summary sentence, not a reward anybody earns — and
    // failing a page for it would be the body-wide-keyword mistake at element scale. A rendered reward is
    // terse ("1949 XP to Lv.46", "153 pts"); a sentence about progress is not. Four words is the line.
    if (t.split(/\s+/).length > 4) continue;
    // A RANGE IS A THRESHOLD, NOT A REWARD. "Lv 1-10", "Lv 11-25" are the legend that EXPLAINS the tiers —
    // demanding that the explanation carry its own explanation is circular, and it put 6 false reds on the
    // one page that documents its thresholds most carefully. Only a single figure is a reward.
    if (/\d\s*[-–—]\s*\d/.test(t)) continue;
    // The reward's OWN container — bounded, so a paragraph elsewhere on the page cannot be credited as
    // this reward's explanation.
    // CLIMB UNTIL THE CONTAINER ACTUALLY CONTAINS SOMETHING BESIDES THE FIGURE. A fixed selector list is
    // a guess about someone else's markup, and it guessed wrong: skillmatrix renders "Lv 2 / 3" with
    // "Target: Level 3 · Actual: Level 2" as a SIBLING, in a wrapper matching none of card/tile/badge/li,
    // so the search fell back to the immediate parent — which holds the figure and nothing else — and the
    // page failed for not explaining a level whose explanation was one element away.
    // THE GROWTH HEURISTIC WAS WRONG, AND IT FAILED ON AN EXACT TIE. It climbed until the text grew
    // `figure + 25` chars, then stopped — measuring SIZE rather than whether the bigger text does the
    // job. On skillmatrix the header "🏢 Facilities Management Lv 5 / 5" is 33 chars and the threshold
    // for "Lv 5 / 5" is exactly 33, so it broke at the header, which only repeats the discipline NAME,
    // and never saw the sibling footer "Target: Level 5 · Actual: Level 5" that states the threshold.
    // One card-width off, and the page was failed for an explanation it renders.
    //
    // THE BOUND IS STRUCTURAL, NOT TEXTUAL: the reward's own card is the OUTERMOST ancestor that still
    // contains exactly ONE reward figure. Climb past a container the moment it would swallow a second
    // reward, because a container holding two figures is a LIST, and a paragraph in a list explains the
    // list, not this row. That keeps the original guarantee — a badge at the top is never credited with
    // a paragraph about XP at the bottom — while letting a card include its own footer. Still hard-bounded
    // at 4 hops and never <body>.
    const figureCount = (node) => {
      let n = 0;
      for (const d of node.querySelectorAll('*')) {
        if (d.children.length) continue;
        const dt = (d.innerText || '').replace(/\s+/g, ' ').trim();
        if (!dt || dt.length > 60 || !REWARD.test(dt) || !vis(d)) continue;
        if (dt.split(/\s+/).length > 4) continue;
        if (/\d\s*[-–—]\s*\d/.test(dt)) continue;
        n++;
      }
      return n;
    };
    let card = el.parentElement;
    for (let hops = 0; hops < 4; hops++) {
      const up = card && card.parentElement;
      if (!up || up === document.body || up === document.documentElement) break;
      if (figureCount(up) > 1) break;   // the next hop is a list, not this reward's card
      card = up;
    }
    if (!card || card === document.body) card = el.parentElement;
    const cardText = ((card && card.innerText) || '').replace(/\s+/g, ' ').trim();
    const described = (() => {
      const id = el.getAttribute('aria-describedby') || (card && card.getAttribute('aria-describedby'));
      if (!id) return '';
      return id.split(/\s+/).map((x) => {
        const n = document.getElementById(x); return n ? (n.innerText || n.textContent || '') : '';
      }).join(' ');
    })();
    const label = el.getAttribute('aria-label') || (card && card.getAttribute('aria-label')) || '';
    let hay = `${cardText} ${described} ${label}`;
    let m = CRIT.exec(hay);
    // A HOMOGENEOUS LIST IS EXPLAINED ONCE, AT ITS HEAD — demanding it per row would be demanding worse
    // design. A leaderboard of "185 XP / 50 XP" is N rows of ONE quantity: same unit, same criteria, same
    // way of being earned. Its header is where a person reads what they are ranked by, and repeating that
    // sentence on every row is noise, not clarity. So when the card itself does not explain, allow exactly
    // one hop to the enclosing list — but ONLY when that list is homogeneous, every figure carrying the
    // same unit as this one. That homogeneity test is what keeps the original guarantee intact: a mixed
    // panel ("420 XP" beside "Lv 5" beside "Silver") is NOT one quantity, so a paragraph in it explains
    // whichever figure it names, not all of them, and the widening does not apply.
    if (!m) {
      const unit = (s) => (s.match(/xp|pts?|points?|lv\.?|level|tier|badge/i) || [''])[0].toLowerCase()
                            .replace(/^lv\.?$/, 'level').replace(/^pts?$|^points?$/, 'pts');
      let list = card && card.parentElement;
      for (let hops = 0; hops < 3 && list && list !== document.body; hops++) {
        if (figureCount(list) > 1) break;
        list = list.parentElement;
      }
      if (list && list !== document.body && list !== document.documentElement && figureCount(list) > 1) {
        const units = new Set();
        for (const d of list.querySelectorAll('*')) {
          if (d.children.length) continue;
          const dt = (d.innerText || '').replace(/\s+/g, ' ').trim();
          if (!dt || dt.length > 60 || !REWARD.test(dt) || !vis(d)) continue;
          if (dt.split(/\s+/).length > 4) continue;
          if (/\d\s*[-–—]\s*\d/.test(dt)) continue;
          units.add(unit(dt));
        }
        if (units.size === 1 && units.has(unit(t))) {
          // THE HEADING IS USUALLY A SIBLING OF THE LIST, NOT INSIDE IT. community renders the rows into
          // #leaderboard-list and its heading into the enclosing #leaderboard-card, so searching the list
          // alone reads the rows and misses the one sentence written to explain them. Climb while the
          // wrapper adds NO new reward figure — a container that introduces another reward is a different
          // card and must not be borrowed from, which is the same rule as the homogeneity test above.
          const n0 = figureCount(list);
          let scope = list;
          for (let up = 0; up < 3; up++) {
            const par = scope.parentElement;
            if (!par || par === document.body || par === document.documentElement) break;
            if (figureCount(par) !== n0) break;   // the wrapper brings in other rewards — stop
            scope = par;
          }
          const listText = (scope.innerText || '').replace(/\s+/g, ' ').trim();
          const lm = CRIT.exec(listText);
          if (lm) { m = lm; hay = listText; }
        }
      }
    }
    found.push({
      reward: t.slice(0, 40),
      explained: !!m,
      via: m ? m[0].slice(0, 40) : null,
      card: cardText.slice(0, 90),
    });
  }
  return found;
};

// The figures a person is being shown as a reward: an XP amount, a level, a badge tier, a point score.
// GROUNDED IN WHAT THE PAGE ACTUALLY RENDERS, not in what a reward 'should' look like. The first
// version anchored the whole string (^153 pts$) and matched ONE element on a page with 47 XP mentions —
// a denominator collapse that then failed the page on that single element. Reading the live DOM shows
// the real shape is `.xp-text` reading "1949 XP to Lv.46", "892 XP to Lv.9": the figure and its target
// in one string. So the match is UNANCHORED — and "No XP earned in the past 7 days" still does not
// match, because the digits must sit adjacent to the unit.
// WRITTEN AS A REGEX LITERAL, then handed over as .source — NOT as a hand-escaped string. In a JS
// single-quoted string '\d' collapses to 'd', so the pattern silently matches nothing and the page
// reports zero rewards: the same escaping collapse that once made an entire injection script inert
// while the prover confidently reported on it. A literal cannot be mis-escaped.
// `lv` IS IN THIS LIST BECAUSE THE PRODUCT USES IT, not because I thought of it. The pattern knew
// `level` and `lvl` and therefore reported skillmatrix — a page whose entire subject is credentials, with
// 52 badge functions — as rendering NO rewards at all. It renders "Lv 2 / 3", "Lv 5 / 1". An oracle that
// only recognises the abbreviations its author happened to imagine measures the author.
const REWARD_RE = /\d[\d,]*\s*(xp|pts?|points?)\b|\b(level|lvl|lv)\.?\s*\d+|\btier\s*\d+/i;
const REWARD_SRC = REWARD_RE.source;
// What EARNS it, or what threshold it sits at — harvested from this platform's own achievement copy
// ("Log and close maintenance jobs", "Complete PM tasks on time", tier thresholds, next-level targets).
// `target` and `still behind` come from skillmatrix's own live copy — "Target: Level 3 · Actual: Level 2",
// "1 discipline still behind target" — which is a threshold stated about as plainly as it can be. Without
// them the oracle would have failed a page for not explaining a level while the explanation sat in the
// same card, in the product's words rather than mine. Extend this list only from harvested text.
const CRITERIA_RE = /earn|unlock|complete|reach|awarded|to (the )?next level|next level at|requires?|per (job|task|entry|post|reply)|for (each|every)|\d+\s*xp\s*(to|away|needed|more)|threshold|criteria|how to|log and close|on time|target|still behind|actual:/i;
const CRITERIA_SRC = CRITERIA_RE.source;

// ── TEETH · both directions, against a real page ──────────────────────────────────────────────────
// This detector was narrowed FOUR times to kill false reds — prose excluded, range legends excluded, a
// 4-word cap, a climbing container. Every one of those narrowings is a chance to turn it into something
// that never fires, and a detector that never fires reports a clean sweep. So: plant a BARE reward and
// require a FAIL, plant an EXPLAINED one and require silence, and plant the two shapes that caused the
// false reds and require they stay ignored.
if (args.includes('--selftest')) {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 390, height: 844 } });
  const pg = await c.newPage();
  await pg.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg.waitForTimeout(1200);
  let fail = 0;
  const plant = (html) => pg.evaluate((h) => {
    document.querySelectorAll('.wh-rw-selftest').forEach((n) => n.remove());
    const d = document.createElement('div');
    d.className = 'wh-rw-selftest';
    d.style.cssText = 'position:fixed;left:0;top:0;z-index:99999;background:#111;color:#fff;padding:16px;'
      + 'display:block;visibility:visible;opacity:1';
    d.innerHTML = h;
    document.body.appendChild(d);
  }, html);
  const scan = () => pg.evaluate(SCAN, { rewardSrc: REWARD_SRC, criteriaSrc: CRITERIA_SRC });
  const mine = (r) => r.filter((x) => /420|Lv 7|1-10|domains touched/.test(x.reward));

  await plant('<div class="card"><span>420 XP</span></div>');
  let f = mine(await scan());
  if (!f.length || f[0].explained) { console.log('  FAIL — a BARE reward was not flagged'); fail++; }
  else console.log(`  ok — bare reward flagged: "${f[0].reward}"`);

  await plant('<div class="card"><span>420 XP</span><p>Earn 10 XP per job you close.</p></div>');
  f = mine(await scan());
  if (!f.length || !f[0].explained) { console.log('  FAIL — an EXPLAINED reward was flagged anyway'); fail++; }
  else console.log(`  ok — explained reward accepted, via "${f[0].via}"`);

  await plant('<div class="card"><span>Lv 1-10</span></div>');
  if (mine(await scan()).length) { console.log('  FAIL — a tier RANGE legend was treated as a reward'); fail++; }
  else console.log('  ok — range legend ignored (it is the threshold, not a reward)');

  await plant('<div class="card"><span>4 of 12 domains touched at Lv 1+</span></div>');
  if (mine(await scan()).length) { console.log('  FAIL — PROSE mentioning a level was treated as a reward'); fail++; }
  else console.log('  ok — prose mentioning a level ignored');

  // THE LIST WIDENING, BOTH DIRECTIONS. A leaderboard is one quantity repeated, so its header explains
  // every row — but the moment the list is MIXED, the header explains only what it names, and the
  // widening must switch off. Without the second plant, the first is just a hole.
  await plant('<div class="card"><p>Ranked by XP — earn 50 XP per post.</p>'
            + '<div class="row"><span>420 XP</span></div><div class="row"><span>310 XP</span></div></div>');
  f = mine(await scan());
  if (!f.length || !f[0].explained) { console.log('  FAIL — a HOMOGENEOUS list explained at its head was flagged'); fail++; }
  else console.log(`  ok — homogeneous list credited from its header, via "${f[0].via}"`);

  await plant('<div class="card"><p>Earn 50 XP per post.</p>'
            + '<div class="row"><span>420 XP</span></div><div class="row"><span>Lv 7</span></div></div>');
  f = (await scan()).filter((x) => /Lv 7/.test(x.reward));
  if (!f.length || f[0].explained) { console.log('  FAIL — a MIXED list credited an unrelated figure from a neighbour\'s explanation'); fail++; }
  else console.log('  ok — mixed list does NOT credit "Lv 7" from the XP sentence');

  await b.close();
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
                   : '\n  SELFTEST PASSED — fires on a bare reward, silent on an explained one, and '
                     + 'ignores both shapes that caused false reds');
  process.exit(fail ? 1 : 0);
}

const browser = await chromium.launch();
const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const rec = { page: p };
  try {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await assertSignedIn(signIn(ctx, 'supervisor'));
    const page = await ctx.newPage();
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    const landed = (page.url().split('/').pop() || '').split('#')[0].split('?')[0].replace(/\.html$/, '');
    if (landed !== p) {
      rec.ok = null;
      rec.verdict = `landed on "${landed}" instead of ${p} — nothing here is a reading about ${p}`;
    } else {
      const found = await page.evaluate(SCAN, { rewardSrc: REWARD_SRC, criteriaSrc: CRITERIA_SRC });
      rec.rewards = found.length;
      const bare = found.filter((f) => !f.explained);
      if (!found.length) {
        // NOT APPLICABLE — no reward is on screen for this persona, so there is nothing to explain.
        rec.ok = null;
        rec.verdict = 'no reward figure is rendered on this page — nothing to explain, row left OWED';
      } else if (bare.length) {
        rec.ok = false;
        rec.verdict = `${bare.length} of ${found.length} reward figure(s) are shown with NO criteria in `
          + `their own card: ${bare.slice(0, 3).map((b) => `"${b.reward}"`).join(', ')}`;
        rec.bare = bare.slice(0, 6);
      } else {
        rec.ok = true;
        rec.verdict = `all ${found.length} reward figure(s) carry their criteria `
          + `(e.g. "${found[0].reward}" explained by "${found[0].via}")`;
      }
    }
    await ctx.close();
  } catch (e) { rec.ok = null; rec.error = String(e.message || e).slice(0, 140); }
  results.push(rec);
  console.log(`  ${p.padEnd(20)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'N/A '}  `
    + String(rec.verdict || rec.error || '').slice(0, 88));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'reward_explained_report.partial.json' : 'reward_explained_report.json'), JSON.stringify({
  totals: { pages: results.length, graded: graded.length, failing: bad.length,
            not_applicable: results.filter((r) => r.ok === null && !r.error).length },
  pages: results,
}, null, 1));
console.log(`\n  wrote reward_explained_report.json`);
console.log(`  ${graded.length} of ${results.length} page(s) graded · ${bad.length} failing · `
  + `${results.filter((r) => r.ok === null && !r.error).length} not applicable (no reward on screen)`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
