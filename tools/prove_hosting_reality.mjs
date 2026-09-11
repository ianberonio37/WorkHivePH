// prove_hosting_reality — the HOSTING & DEPLOYMENT layer of the LAYER-UX wave (§LX, 2026-09-06).
// All four lenses in one walk, asked of the DEPLOYED ORIGIN, because that is the only place this layer
// exists. Nothing local can answer any of them.
//
//   H1 alive        a feature that works locally is dead in production because the origin sends no
//                   header for it. This is not hypothetical here: the repo shipped a Cloudflare
//                   `_headers` and a `netlify.toml` to a VERCEL host, which reads neither, so no CSP,
//                   no Permissions-Policy and no X-Frame-Options had ever been served.
//   H2 reachable    the link you were given 404s in production and opens fine for the person who wrote
//                   it - every internal link on the public pages must resolve where a stranger clicks it
//   H3 carried      a redirect loses what you arrived with: the query, the anchor, the invite code
//   H4 kept         an asset is re-downloaded every visit because the origin never told the browser to
//                   keep it - an immutable asset served with no cache directive is a bill the person
//                   pays in data on a Philippine mobile plan
//
// Read-only GETs against a public website.
//
//   node tools/prove_hosting_reality.mjs
//   node tools/prove_hosting_reality.mjs --origin http://127.0.0.1:5000/workhive
import { readFileSync } from 'node:fs';

const ORIGIN = (() => { const i = process.argv.indexOf('--origin'); return i >= 0 ? process.argv[i + 1] : 'https://workhiveph.com'; })();
const TIMEOUT = 20000;

const get = async (url, opts = {}) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT);
  try {
    const r = await fetch(url, { redirect: opts.follow === false ? 'manual' : 'follow', signal: ctl.signal });
    const h = {};
    r.headers.forEach((v, k) => { h[k.toLowerCase()] = v; });
    const body = opts.body === false ? '' : await r.text();
    return { status: r.status, h, body, url: r.url };
  } catch (e) { return { status: 0, h: {}, body: '', err: String(e).slice(0, 60) }; }
  finally { clearTimeout(t); }
};

let bad = 0;

// ── H1 · the security headers the config promises ────────────────────────────────────────────────
{
  const r = await get(`${ORIGIN}/index.html`);
  const want = ['content-security-policy', 'x-frame-options', 'x-content-type-options',
                'referrer-policy', 'permissions-policy'];
  const missing = want.filter((k) => !r.h[k]);
  if (missing.length) bad++;
  console.log(`  ${missing.length ? 'BAD' : 'ok '} H1 alive                 ${want.length - missing.length}/${want.length} security header(s) served${missing.length ? ' · missing: ' + missing.join(', ') : ''} (server: ${r.h.server || '?'})`);
  if (missing.length) console.log('        a feature relying on any of these is dead in production and nothing local can tell you');
}

// ── H2 · every internal link a stranger is given actually resolves ───────────────────────────────
{
  const r = await get(`${ORIGIN}/index.html`);
  const links = [...new Set([...r.body.matchAll(/href="(\/[^"#?]*)"/g)].map((m) => m[1]))]
    .filter((u) => !/\.(png|jpg|jpeg|svg|ico|webp|woff2?|css|js)$/i.test(u))
    .slice(0, 24);
  const dead = [];
  for (const u of links) {
    const rr = await get(ORIGIN + u, { body: false });
    if (rr.status >= 400 || rr.status === 0) dead.push(`${u} -> ${rr.status || rr.err}`);
  }
  if (dead.length) bad++;
  console.log(`  ${dead.length ? 'BAD' : 'ok '} H2 reachable             ${links.length - dead.length}/${links.length} internal link(s) resolve where a stranger clicks them`);
  for (const d of dead.slice(0, 5)) console.log(`        ${d}`);
}

// ── H3 · a redirect carries what the person arrived with ─────────────────────────────────────────
{
  // the shapes a real arrival takes: an invite code, a deep link with an anchor, a tracked campaign
  const cases = [
    ['/?invite=ABC123', 'invite=ABC123'],
    ['/index.html?signin=1&return=hive.html', 'return=hive.html'],
    ['/learn/?utm_source=probe', 'utm_source=probe'],
  ];
  const lost = [];
  for (const [path, needle] of cases) {
    const r = await get(ORIGIN + path, { body: false });
    if (r.status === 0) { lost.push(`${path} unreachable (${r.err})`); continue; }
    // the query must survive to whatever URL we ended on
    if (r.url && !r.url.includes(needle.split('=')[0])) lost.push(`${path} arrived at ${r.url.slice(0, 70)} without ${needle}`);
  }
  if (lost.length) bad++;
  console.log(`  ${lost.length ? 'BAD' : 'ok '} H3 carried               ${cases.length - lost.length}/${cases.length} arrival(s) keep what the person came with`);
  for (const l of lost.slice(0, 4)) console.log(`        ${l}`);
}

// ── H4 · an immutable asset is allowed to stay in the browser ────────────────────────────────────
{
  const r = await get(`${ORIGIN}/index.html`);
  const assets = [...new Set([...r.body.matchAll(/(?:src|href)="(\/[^"]+\.(?:png|jpg|jpeg|svg|ico|webp|woff2|css|js))"/g)].map((m) => m[1]))].slice(0, 10);
  const uncached = [];
  for (const a of assets) {
    const rr = await get(ORIGIN + a, { body: false });
    const cc = rr.h['cache-control'] || '';
    // an asset with no max-age, or max-age=0, is re-fetched on every visit
    const m = cc.match(/max-age=(\d+)/);
    if (!cc || !m || Number(m[1]) < 3600) uncached.push(`${a} · cache-control: ${cc || '(none)'}`);
  }
  if (uncached.length) bad++;
  console.log(`  ${uncached.length ? 'BAD' : 'ok '} H4 kept                  ${assets.length - uncached.length}/${assets.length} asset(s) the browser is allowed to keep for an hour or more`);
  for (const u of uncached.slice(0, 5)) console.log(`        ${u.slice(0, 150)}`);
}

console.log(`${bad ? 'FAIL' : 'PASS'} hosting-reality - what the DEPLOYED origin actually hands a person: headers served, links resolving, arrivals carried, assets keepable @ ${ORIGIN}`);
process.exitCode = bad ? 1 : 0;
