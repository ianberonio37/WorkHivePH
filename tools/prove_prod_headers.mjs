// prove_prod_headers — the `_headers is prod-only` lens of the live-walk wave (2026-09-06).
//
// `_headers` is a Cloudflare Pages directive file. Nothing local serves it: the seeder on 127.0.0.1:5000 does not
// read it, so every promise it makes is unverifiable here and has already shipped three prod-only defects that
// nothing local could reproduce - Permissions-Policy denying camera, microphone and then geolocation site-wide
// (three shipped features dead in production), and a CSP that predated GA4 so the analytics we deliberately ship
// was silently blocked. The only honest instrument is the deployed origin itself.
//
// This is a READ-ONLY GET against a public website. It asserts, for each rule in `_headers`, that the response
// actually carries what the file promises - and for the CSP, that every host the pages genuinely load from is
// present in the directive that governs it.
//
//   node tools/prove_prod_headers.mjs                     # the whole file's promises
//   node tools/prove_prod_headers.mjs --origin http://...  # somewhere else
import { readFileSync } from 'node:fs';

const ORIGIN = (() => { const i = process.argv.indexOf('--origin'); return i >= 0 ? process.argv[i + 1] : 'https://workhiveph.com'; })();
const TIMEOUT = 20000;

// ── parse _headers into [{ pattern, headers: {name: value} }] ────────────────────────────────────
const blocks = [];
let cur = null;
for (const raw of readFileSync('_headers', 'utf8').split(/\r?\n/)) {
  const line = raw.replace(/\s+$/, '');
  if (!line.trim() || line.trim().startsWith('#')) continue;
  if (!/^\s/.test(line)) { cur = { pattern: line.trim(), headers: {} }; blocks.push(cur); continue; }
  const m = line.trim().match(/^([A-Za-z0-9-]+):\s*(.*)$/);
  if (m && cur) cur.headers[m[1].toLowerCase()] = m[2];
}

// one representative real path per pattern - a wildcard cannot be fetched
const SAMPLE = {
  '/*': '/index.html',
  '/*.html': '/index.html',
  '/sw.js': '/sw.js',
  '/*.md': '/README.md',
  '/*.png': '/icon-192.png',
  '/*.ico': '/favicon.ico',
};

const get = async (path) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT);
  try {
    const r = await fetch(ORIGIN + path, { method: 'GET', redirect: 'follow', signal: ctl.signal });
    const h = {};
    r.headers.forEach((v, k) => { h[k.toLowerCase()] = v; });
    return { status: r.status, h };
  } catch (e) { return { status: 0, err: String(e).slice(0, 70), h: {} }; }
  finally { clearTimeout(t); }
};

// ★A CSP IS A LIST OF PROMISES ABOUT WHAT THE PAGES ACTUALLY LOAD. Checking that the header EXISTS is the
// check that let GA4 ship dead: the header was present and simply did not name googletagmanager. So each host
// the shipped pages really use is asserted against the directive that governs it, by name.
const CSP_MUST = [
  ['script-src', 'https://cdn.tailwindcss.com', 'Tailwind CDN, on nearly every page'],
  ['script-src', 'https://www.googletagmanager.com', 'GA4 - shipped deliberately (wh-ga4.js); absent here it is dead in prod'],
  ['script-src', 'https://challenges.cloudflare.com', 'Turnstile - the documented configure-to-enable switch'],
  ['script-src', 'https://cdn.plot.ly', 'analytics charts'],
  ['connect-src', 'https://hzyvnjtisfgbksicrouu.supabase.co', 'the database every signed-in page reads'],
  ['connect-src', 'https://workhive-assistant.ian-beronio37.workers.dev', 'the assistant worker'],
  ['connect-src', 'https://tiles.openfreemap.org', 'the service map tiles'],
  ['connect-src', 'https://engineering-calc-api.onrender.com', 'the calculator API'],
  ['frame-src', 'https://challenges.cloudflare.com', 'the Turnstile challenge iframe'],
  ['font-src', 'https://fonts.gstatic.com', 'the web fonts'],
  ['frame-ancestors', "'none'", 'clickjacking'],
];
const PERMS_MUST = [['camera', 'the logbook photo capture and QR scan'], ['microphone', 'the voice journal'], ['geolocation', 'the live location share on an active service job']];

let bad = 0, n = 0, skipped = 0;
console.log(`  origin ${ORIGIN}`);
for (const b of blocks) {
  const path = SAMPLE[b.pattern] || (b.pattern.includes('*') ? null : b.pattern);
  if (!path) { skipped++; continue; }
  const r = await get(path);
  if (r.status === 0) { console.log(`  ERR  ${b.pattern.padEnd(18)} ${path} unreachable: ${r.err}`); bad++; n++; continue; }
  if (r.status === 404) { console.log(`  n/a  ${b.pattern.padEnd(18)} ${path} is not deployed (404) - nothing to assert`); skipped++; continue; }
  for (const [name, want] of Object.entries(b.headers)) {
    n++;
    const got = r.h[name];
    let ok = !!got;
    const notes = [];
    if (!got) notes.push('header absent');
    else if (name === 'content-security-policy') {
      for (const [dir, host, why] of CSP_MUST) {
        const m = got.match(new RegExp(dir + "\\s+([^;]*)"));
        const has = m && m[1].includes(host);
        if (!has) { ok = false; notes.push(`${dir} is missing ${host} (${why})`); }
      }
    } else if (name === 'permissions-policy') {
      for (const [feat, why] of PERMS_MUST) {
        const m = got.match(new RegExp(feat + "=\\(([^)]*)\\)"));
        if (!m) { ok = false; notes.push(`${feat} not named at all (${why})`); }
        else if (!/self/.test(m[1])) { ok = false; notes.push(`${feat}=(${m[1]}) denies our OWN pages - ${why} dies in prod`); }
      }
    } else if (got.trim().toLowerCase() !== want.trim().toLowerCase()) {
      ok = false; notes.push(`serves "${got.slice(0, 60)}" but _headers promises "${want.slice(0, 60)}"`);
    }
    if (!ok) bad++;
    console.log(`  ${ok ? 'ok  ' : 'BAD '} ${b.pattern.padEnd(18)} ${name}${ok ? '' : ' :: ' + notes.join(' | ').slice(0, 170)}`);
  }
}
console.log(`${bad ? 'FAIL' : 'PASS'} prod-headers - ${n - bad}/${n} promises in _headers are actually served by ${ORIGIN} (${skipped} pattern(s) with no fetchable sample)`);
process.exit(bad ? 1 : 0);
