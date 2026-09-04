/**
 * Does a lost visitor get told, and get somewhere? (T155, 2026-08-28)
 *
 * Netlify serves index.html at status 404 for every unknown path, path preserved — SEO-correct,
 * and for a long time it meant the visitor at /old-bookmark saw the full homepage with not one
 * word about their dead link. index.html now detects the foreign path and prepends a notice.
 *
 * ★THE NOTICE'S FIRST VERSION ENDED "use the navigation or search below" AND THIS PAGE HAS NO
 * SEARCH BOX. The single message whose entire job is helping someone who is lost was pointing at
 * something that does not exist. It now carries a real search that hands off to the learn hub's
 * own filter via ?q= — so this prover asserts the WHOLE promise, not the notice's existence:
 * it fires on foreign paths, stays silent on real ones, and its search actually reaches guides.
 *
 * ★IT SERVES ITS OWN SUBJECT. The local seeder returns a hard Flask 404 for unknown paths, so the
 * netlify rewrite — the exact condition the notice detects — cannot be reproduced against it. This
 * starts a throwaway static server implementing netlify.toml's two rules (force-404 /_fixtures/*,
 * then /* -> index.html at 404), which is why the walk is faithful rather than approximate.
 *
 * USAGE:  node tools/prove_404_notice_helps.mjs
 * Exit 1 on any failed assertion.
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PORT = 5198;
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
                '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
                '.svg': 'image/svg+xml', '.webp': 'image/webp', '.ico': 'image/x-icon' };

// ★IT ALSO SERVES UNDER /workhive/, because the notice has a SECOND branch nobody could reach.
// index.html computes its form action as '/workhive' + '/learn/' when the path starts with that
// prefix (the local seeder mounts the site there) and '' + '/learn/' otherwise. The seeder itself
// hard-404s unknown paths, so the netlify rewrite that triggers the notice cannot happen under it,
// and the prefixed branch would have shipped untested behind a gate that looked complete. Serving
// both mounts here is the cheapest way to make that branch reachable.
const PREFIX = '/workhive';

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0].split('#')[0]);
  if (p === PREFIX || p.startsWith(PREFIX + '/')) p = p.slice(PREFIX.length) || '/';
  const target = path.join(ROOT, p);
  let file = null;
  if (!p.startsWith('/_fixtures/')) {
    try {
      if (fs.statSync(target).isDirectory()) {
        const idx = path.join(target, 'index.html');
        if (fs.existsSync(idx)) file = idx;
      } else file = target;
    } catch { file = null; }
  }
  if (file) {
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(fs.readFileSync(file));
  } else {                                   // netlify.toml's catch-all: the homepage, at 404
    res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(fs.readFileSync(path.join(ROOT, 'index.html')));
  }
});

const fails = [];
const check = (ok, what, got) => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${what}${ok ? '' : `  (got: ${got})`}`);
  if (!ok) fails.push(what);
};

await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
const B = `http://127.0.0.1:${PORT}`;
const browser = await chromium.launch();
const ctx = await browser.newContext({ serviceWorkers: 'block' });
const page = await ctx.newPage();

const readNotice = () => page.evaluate(() => {
  const d = document.querySelector('div[role="alert"]');
  if (!d) return null;
  const q = d.querySelector('input[name="q"]'), f = d.querySelector('form');
  return { value: q ? q.value : null, action: f ? f.getAttribute('action') : null,
           namesPath: (d.textContent || '').includes(location.pathname),
           labelled: !!d.querySelector('label[for="wh-404-q"]'),
           submit: !!d.querySelector('button[type="submit"]') };
});

console.log('404-notice-helps - is a lost visitor told, and taken somewhere?\n');

// 1. a foreign path speaks, names ITSELF, and pre-fills the slug the visitor asked for
await page.goto(`${B}/learn/oee/`, { waitUntil: 'domcontentloaded' });
const n = await readNotice();
check(!!n, 'a foreign path raises the notice', String(n));
if (n) {
  check(n.namesPath, 'the notice names the dead path', 'path not quoted');
  check(n.value === 'oee', 'the search is pre-filled from the slug', JSON.stringify(n.value));
  check(!!n.action && n.action.endsWith('/learn/'), 'it submits to the learn hub', n.action);
  check(n.labelled && n.submit, 'the field is labelled and submittable', JSON.stringify(n));
}

// 2. the promise is KEPT: submitting reaches guides, not an empty hub
await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
                   page.click('div[role="alert"] button[type="submit"]')]);
await page.waitForTimeout(400);
check(page.url().includes('/learn/?q=oee'), 'submitting lands on the seeded hub', page.url());
check((await page.inputValue('#lh-search')) === 'oee', 'the hub seeds its own search box',
      await page.inputValue('#lh-search'));
const shown = await page.evaluate(() => document.querySelectorAll('.article-card:not(.lh-hidden)').length);
check(shown > 0, 'the search actually reaches guides', `${shown} cards`);

// 3. a slug matching nothing says so - an honest empty beats a pretend
await page.goto(`${B}/learn/?q=zzz-no-such-guide`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(400);
const empty = await page.evaluate(() => {
  const e = document.getElementById('lh-empty');
  return e && e.classList.contains('show') ? (e.textContent || '').trim() : null;
});
check(!!empty, 'a no-match search states it found nothing', String(empty));

// 4. the SAME promise under the /workhive prefix, whose form action is built by a different branch
await page.goto(`${B}/workhive/learn/oee/`, { waitUntil: 'domcontentloaded' });
const pre = await readNotice();
check(!!pre, 'a foreign path under /workhive raises the notice too', String(pre));
check(!!pre && pre.value === 'oee', 'the prefixed notice pre-fills the slug', pre && JSON.stringify(pre.value));
check(!!pre && pre.action === '/workhive/learn/',
      'the prefixed form targets the prefixed hub, not the root one', pre && pre.action);

// 5. every real page stays silent - a false 404 notice would be worse than none, and the two
//    mount roots must BOTH be recognised or every visitor to the local site is told they are lost
for (const p of ['/', '/index.html', '/learn/', '/learn/free-pm-checklist-templates/',
                 '/workhive/', '/workhive/index.html']) {
  await page.goto(B + p, { waitUntil: 'domcontentloaded' });
  check((await readNotice()) === null, `a real page stays silent: ${p}`, 'notice PRESENT');
}

await browser.close();
server.close();
console.log(`\n  ${fails.length ? `FAIL: ${fails.length} assertion(s)` : 'PASS: the lost visitor is told, and taken somewhere'}`);
process.exit(fails.length ? 1 : 0);
