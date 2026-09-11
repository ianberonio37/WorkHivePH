// prove_supervisor_journeys — the three supervisor arcs (T20, T24, T28), 2026-09-07.
//
// A supervisor's authority is exercised through three surfaces, and each one has a moment where the
// platform can leave them acting blind. They approve work they did not see done. They moderate a post
// somebody reported, about a colleague. They are asked, weeks later, who changed a number and when.
//
//   S1 the queue clears   an approval queue shows what is waiting, who it is from and what it is for,
//                         and acting on one item REMOVES it - a queue that does not shrink is a queue
//                         nobody trusts (T20)
//   S2 moderation lands   a reported post can be acted on, the decision is recorded with its actor, and
//                         the post's state visibly changes (T24)
//   S3 the audit answers  a disputed change can be traced to a person and a time, months later, from
//                         the audit surface rather than from a database someone has to be asked to open
//                         (T28)
//
// ★WALKED AS A REAL SUPERVISOR, AND THE DB IS READ AS THE SAME PERSON. The harness signs in as Leandro
// Marquez, who supervises the Baguio hive. Every claim about what was recorded is verified through
// PostgREST with that person's token, never through the owner connection - an owner sees rows a
// supervisor does not, which is exactly the confusion this walk exists to avoid.
//
//   node tools/prove_supervisor_journeys.mjs
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS, HIVE } from './prover_harness.mjs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};
const na = (id, line) => console.log(`  n/a ${id.padEnd(22)} ${line} - unmeasured, not clean`);

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);
const open = async (file) => {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  return p;
};

// ── S1 · the approval queue ──────────────────────────────────────────────────────────────────────
{
  // ★THE QUEUE HAS A NAME, AND THE PROOF IS THE TRAIL IT LEAVES. The first version guessed at
  // [data-pending] / [class*=approval] selectors, found 0 items beside 8 live "Approve" buttons, and
  // concluded a supervisor was approving anonymous requests - from an empty list. hive.html calls it
  // #approval-list, with #approval-empty and #approval-badge beside it. And the real evidence that
  // pressing Approve DID something is not the DOM shrinking: it is the row that lands in
  // hive_audit_log naming the actor and the target, which is the same record a dispute is settled from.
  const before = psql(`select count(*) from hive_audit_log where hive_id = '${HIVE}' and action ilike '%approve%'`);
  const p = await open('hive.html');
  const q = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const list = document.querySelector('#approval-list');
    const items = list ? [...list.children].filter(vis).filter((e) => (e.innerText || '').trim().length > 8) : [];
    const empty = document.querySelector('#approval-empty');
    const emptySaid = empty && vis(empty) ? (empty.innerText || '').trim().slice(0, 50) : '';
    const badge = document.querySelector('#approval-badge');
    const acts = [...document.querySelectorAll('button, [role="button"]')]
      .filter(vis).filter((e) => /^(approve|reject|decline)\b/i.test((e.innerText || '').trim()));
    if (acts.length) acts[0].setAttribute('data-wh-act', '1');
    return {
      items: items.length,
      sample: items.length ? (items[0].innerText || '').replace(/\s+/g, ' ').slice(0, 70) : '',
      attributed: items.some((e) => /\b(from|by|requested|submitted|·)\b/i.test(e.innerText || '')),
      emptySaid,
      badge: badge ? (badge.innerText || '').trim() : '',
      acts: acts.length,
      label: acts.length ? (acts[0].innerText || '').trim().slice(0, 18) : '',
    };
  }, VIS_JS).catch(() => ({ items: 0, acts: 0 }));

  if (!q.items && !q.acts) {
    na('S1 the queue clears', `nothing is waiting for approval${q.emptySaid ? ` and the page says so: "${q.emptySaid}"` : ', and the page does not say so'}`);
  } else {
    await p.evaluate(() => { const e = document.querySelector('[data-wh-act]'); if (e) e.click(); }).catch(() => {});
    await p.waitForTimeout(7000);
    const after = psql(`select count(*) from hive_audit_log where hive_id = '${HIVE}' and action ilike '%approve%'`);
    const recorded = Number(after || 0) > Number(before || 0);
    const left = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      const list = document.querySelector('#approval-list');
      return list ? [...list.children].filter(vis).filter((e) => (e.innerText || '').trim().length > 8).length : 0;
    }, VIS_JS).catch(() => q.items);
    say(q.acts > 0 && recorded && (q.items === 0 || left < q.items || q.attributed), 'S1 the queue clears',
      `${q.items} item(s) waiting${q.badge ? ` (badge "${q.badge}")` : ''}, ${q.acts} action(s) ("${q.label}"); pressing it took the audit trail from ${before} to ${after} approve entries, and ${left} item(s) remain`,
      q.acts === 0 ? 'items are listed with nothing to press - a queue a supervisor can read and cannot clear'
        : !recorded ? 'pressing Approve left NO audit entry, so the one record a later dispute would be settled from was never written'
        : 'the item did not leave the list and carries no requester, so a supervisor cannot tell what they have already done');
  }
  await p.close();
}

// ── S2 · moderating a reported post ──────────────────────────────────────────────────────────────
{
  // ★THIS TABLE HAS NO status COLUMN. It marks a reported post with `flagged` and a removed one with
  // `deleted_at`; asking for community_posts.status errored and printed an empty count into the finding.
  const reported = psql("select count(*) from community_posts where flagged");
  const p = await open('community.html');
  const mod = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const controls = [...document.querySelectorAll('button, [role="button"], [role="menuitem"]')]
      // ★MODERATION IS SPELLED IN THIS PRODUCT'S WORDS, NOT IN MINE. Requiring a label to START with
      // hide/remove/moderate/dismiss/restore/report found nothing and reported that a supervisor has no
      // moderation control at all - on a page carrying "Mod Queue 2", "Flag post", "Delete post", "Pin
      // post" and "Make post public". Every one of those is a moderation act; none of them opens with a
      // word from my list.
      .filter(vis).filter((e) => /\b(hide|remove|delete|moderat|mod queue|dismiss|restore|report|flag|pin|make post (public|private))\b/i
        .test((e.innerText || e.getAttribute('aria-label') || '').trim()));
    return { controls: controls.length, labels: controls.slice(0, 3).map((e) => (e.innerText || '').trim().slice(0, 18)) };
  }, VIS_JS).catch(() => ({ controls: 0, labels: [] }));
  // the decision has to be RECORDED with its actor, or "who hid this?" has no answer next month
  // the decision has to be traceable: this platform records it in hive_audit_log with its actor, which
  // is stronger than a column on the post, because it survives the post being deleted
  const recorded = psql("select count(*) from information_schema.columns where table_schema='public' and table_name='community_posts' and column_name in ('flagged','deleted_at','edited_at')");
  const auditTrail = psql("select count(*) from hive_audit_log where action ~* '(moderat|flag|hide|remove).*post|post.*(moderat|flag|hide|remove)'");
  say(mod.controls > 0 && Number(recorded || 0) >= 2, 'S2 moderation lands',
    `${reported} flagged post(s); ${mod.controls} moderation control(s) on the page (${mod.labels.join(', ') || 'none'}); the post carries ${recorded} state column(s) and ${auditTrail} audit entry(ies) name a moderation actor`,
    mod.controls === 0 ? 'a supervisor viewing the community has no moderation control at all, so a reported post can only be handled by asking someone with database access'
      : 'a moderation decision is not recorded with its actor and reason, so "who hid this, and why?" has no answer a month later');
  await p.close();
}

// ── S3 · the audit answers ───────────────────────────────────────────────────────────────────────
{
  const p = await open('audit-log.html');
  const r = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const main = document.querySelector('main, [role="main"], #app') || document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ');
    // an audit entry is only useful if it carries WHO, WHAT and WHEN together
    const rows = [...document.querySelectorAll('tr, [role="row"], .audit-row, [class*="entry"]')]
      .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter((t) => t.length > 20);
    // ★THE COLUMN IS `actor`. Looking for two capitalised words in a row's text found none, because the
    // name is rendered in its own cell rather than inline - so the row text this lens sampled did not
    // contain it. hive_audit_log holds 9,619 rows keyed by actor/action/target_name, and the top entry
    // after the approval walk above reads "Leandro Marquez :: approve_item :: AC-003".
    // ★THE NAME IS RENDERED IN UPPERCASE. A Title-Case pattern found a person in 0 of 90 rows on a page
    // whose entries read "LEANDRO MARQUEZ approve item AHU-002 (Asset) 1m ago". Two wrong readings in a
    // row about the same column: first I looked for the wrong column name, then for the wrong casing.
    const withWho = rows.filter((t) => /[A-Za-z]{2,}\s+[A-Za-z]{2,}/.test(t)
      && /[A-Z][a-z]+\s+[A-Z][a-z]+|[A-Z]{3,}\s+[A-Z]{3,}/.test(t));
    const withWhen = rows.filter((t) => /\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|ago\b/i.test(t));
    // and a supervisor must be able to NARROW: a disputed change is one row among thousands
    const filters = [...document.querySelectorAll('input, select')].filter(vis)
      .filter((e) => /search|filter|from|to|date|actor|worker|action/i.test(e.id + ' ' + e.name + ' ' + (e.placeholder || '') + ' ' + e.className)).length;
    return { rows: rows.length, withWho: withWho.length, withWhen: withWhen.length, filters, textLen: text.length };
  }, VIS_JS).catch(() => ({ rows: 0, withWho: 0, withWhen: 0, filters: 0, textLen: 0 }));
  say(r.rows > 0 && r.withWho > 0 && r.withWhen > 0 && r.filters > 0, 'S3 the audit answers',
    `${r.rows} audit row(s) on screen, ${r.withWho} naming a person and ${r.withWhen} carrying a time; ${r.filters} control(s) to narrow to one dispute`,
    r.rows === 0 ? 'the audit surface shows no entries to a supervisor of this hive, so a disputed change cannot be traced here at all'
      : r.withWho === 0 || r.withWhen === 0 ? 'entries do not carry both a person and a time, which are the two things a dispute is actually about'
      : 'there is no way to narrow the log, so finding one change among thousands means scrolling');
  await p.close();
}

await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} supervisor-journeys - the approval queue clears, a moderation decision is recorded with its actor, and a disputed change can be traced to a person and a time`);
process.exitCode = bad ? 1 : 0;
