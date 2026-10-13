/* ============================================================================
 * tw_public_build.mjs - compile the Tailwind Play CDN's CSS ONCE for the public pages, one sheet per config family
 * ============================================================================
 * 2026-10-13. The learn articles, the 60 calculator pages (and their generator's staging copies), about / privacy /
 * terms and the public roadmap all loaded Tailwind's Play CDN: a ~400 KB script that blocks render, is fetched cold on
 * every first visit, and then generates the page's CSS on the main thread. Read through the audit lens
 * (tools/w4_cwv_mcp.js: Slow 4G, CPU 4x, a 390 phone) a learn article painted its largest element at ~4.7 s, and the
 * CDN alone was ~2.2 s of render-blocking time. The nine app pages left the CDN earlier (tools/tw_extract_build.mjs ->
 * wh-tw.css); these are the rest.
 *
 * The pages do not share one tailwind.config, so they cannot share one sheet: `text-sm` is 0.95rem under the pinned
 * type ramp and 0.875rem under the stock one. Families are told apart by EVALUATING each page's config, so two configs
 * that differ only in whitespace or comments are one family.
 *
 * Tailwind still writes every rule. A harvest page carries the family's exact config, the same CDN, every class token
 * the family's pages use (class attributes, every string literal in their scripts and in the local scripts they load)
 * and their raw source for the CDN's own extractor; the CSS the CDN injects is saved verbatim. Nothing is hand-written.
 * A class the harvest sees but no page uses compiles to a rule nothing matches, so over-collecting is inert, while
 * missing one would leave an element unstyled - which is why the harvest is greedy and `verify` exists.
 *
 *   node tools/tw_public_build.mjs plan                 list the CDN pages and their families -> tools/tw_pub_families.json
 *   node tools/tw_public_build.mjs build [--family F]   compile one sheet per family -> /wh-tw-pub-<family>.css
 *   node tools/tw_public_build.mjs verify [--family F] [--match S] [--limit N]
 *   node tools/tw_public_build.mjs apply [--family F]   swap the CDN + config scripts for the sheet's <link> (idempotent)
 *
 * `verify` loads each page twice in headless Chromium, as it is on disk (the CDN) and with the swap applied in flight,
 * and fails the page unless all four hold:
 *   1. the stylesheets apply in the same order. The CDN appends its <style> to the END of <head>, so the link goes
 *      there too; anywhere earlier and the page's own rules would start winning ties they used to lose;
 *   2. every rule the CDN generated for the page is in the sheet, in the same relative order (a defaults rule may carry
 *      extra --tw-* variables, which nothing reads unless a utility on the page does);
 *   3. every element's computed style, and its ::before / ::after, is identical at 390 and at 1280;
 *   4. no console error appears that the CDN load did not have.
 * Only localhost and the Tailwind CDN are reachable in both loads: fonts and analytics are blocked, and the public
 * roadmap's read of the PRODUCTION database is answered from a fixture, so nothing leaves the machine and the two
 * loads differ only in where the CSS comes from.
 * ==========================================================================*/
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import crypto from 'crypto';

const ORIGIN = 'http://localhost:5000';
const MANIFEST = 'tools/tw_pub_families.json';
const CDN = 'https://cdn.tailwindcss.com';
const CDN_TAG = /<script src="https:\/\/cdn\.tailwindcss\.com"><\/script>/g;
const ANY_CDN = /cdn\.tailwindcss\.com/;
const CONFIG_TAG = /<script>\s*tailwind\.config\s*=[\s\S]*?<\/script>/g;
const SKIP_DIRS = new Set(['node_modules', '_fixtures', 'test-data-seeder', 'video_marketing_app', 'promo_posters', 'test-runs']);
// Family names, keyed by the evaluated config's hash (from the first `plan`, 2026-10-13; an unnamed family is
// fam-<hash>, and `apply` refuses it until it is named here).
const NAMES = {
  '0407aa73': 'ramp',      // the pinned six-step type ramp + full palette: build_pillar_pages.HEAD_ASSETS - pillar pages,
                           //   35 learn articles, the 60 calculators and their staging copies (155 pages)
  '799c1d62': 'article',   // stock type scale + three brand colours: tools/scaffold_article.py (19 learn articles)
  'f32c85a0': 'site',      // stock type scale + full palette: learn hub, about, privacy, terms (hand-authored)
  'e7fd04b3': 'feedback',  // 'site' + Poppins as font-sans: the public roadmap
};
const LINK = (name) => `<link rel="stylesheet" href="/wh-tw-pub-${name}.css"><!-- Tailwind, compiled per config: tools/tw_public_build.mjs -->`;

const args = process.argv.slice(2);
const cmd = args[0];
const opt = (k, d = null) => { const i = args.indexOf('--' + k); return i > 0 && i + 1 < args.length ? args[i + 1] : d; };

const h8 = (s) => crypto.createHash('sha256').update(s).digest('hex').slice(0, 8);
const stable = (v) => Array.isArray(v) ? '[' + v.map(stable).join(',') + ']'
  : (v && typeof v === 'object') ? '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + stable(v[k])).join(',') + '}'
  : JSON.stringify(v);

function htmlFiles(dir = '.', out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith('.') || SKIP_DIRS.has(e.name)) continue;
    const p = dir === '.' ? e.name : dir + '/' + e.name;
    if (e.isDirectory()) htmlFiles(p, out);
    else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}

// Run the page's own config script in an empty sandbox. It must only assign tailwind.config: if it touched anything
// else, deleting the script in `apply` would delete that too, so the page is refused rather than guessed at.
function evalConfig(src) {
  const ctx = { tailwind: {} };
  vm.createContext(ctx);
  vm.runInContext(src.replace(/^<script>|<\/script>$/g, ''), ctx, { timeout: 1000 });
  const extra = Object.keys(ctx).filter((k) => k !== 'tailwind').concat(Object.keys(ctx.tailwind).filter((k) => k !== 'config'));
  if (extra.length) throw new Error('the config script also sets ' + extra.join(', '));
  return ctx.tailwind.config;
}

function pageInfo(file) {
  const html = fs.readFileSync(file, 'utf8');
  const linked = html.match(/href="\/wh-tw-pub-([\w-]+)\.css"/);
  if (linked) return { file, state: 'migrated', name: linked[1] };
  if (!ANY_CDN.test(html)) return null;
  const tags = html.match(CDN_TAG) || [];
  const cfgs = html.match(CONFIG_TAG) || [];
  if (tags.length !== 1) return { file, state: 'refused', why: `${tags.length} exact CDN tags (the swap only knows one)` };
  if (cfgs.length > 1) return { file, state: 'refused', why: `${cfgs.length} config scripts` };
  let config = {}, src = '';
  if (cfgs.length) {
    src = cfgs[0];
    try { config = evalConfig(src); } catch (e) { return { file, state: 'refused', why: 'config: ' + e.message }; }
  }
  const hash = h8(stable(config));
  return { file, state: 'cdn', hash, name: NAMES[hash] || 'fam-' + hash, src, config };
}

function loadManifest() { try { return JSON.parse(fs.readFileSync(MANIFEST, 'utf8')); } catch { return { families: {} }; } }
function saveManifest(m) { fs.writeFileSync(MANIFEST, JSON.stringify(m, null, 1) + '\n'); }

function allPages() { return htmlFiles().map(pageInfo).filter(Boolean); }
function familyPages(name, pages = allPages()) { return pages.filter((p) => p.name === name && p.state !== 'refused'); }

// ── harvest ──────────────────────────────────────────────────────────────────
// The classes a page can carry - class attributes (also inside template literals), className assignments and
// classList.add/remove/toggle/replace arguments. tools/validate_tw_public_sheets.py reads pages with the SAME
// patterns (class_use); a class it finds must be compiled into the sheet or recorded here as the page's own.
const P_ATTR = /\bclass\s*=\s*(?:"([^"]*)"|'([^']*)')/g;
const P_CLASSNAME = /\bclassName\s*\+?=\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`)/g;
const P_CLASSLIST = /classList\.(?:add|remove|toggle|replace)\s*\(([^)]*)\)/g;
const P_STR = /["'`]([^"'`]*)["'`]/g;
const TOKEN = /^[!-]?[A-Za-z0-9@\[*][A-Za-z0-9_\-:/.\[\]%#&>*(),]*$/;
function classUse(text, out = new Set()) {
  const vals = [];
  for (const m of text.matchAll(P_ATTR)) vals.push(m[1] ?? m[2]);
  for (const m of text.matchAll(P_CLASSNAME)) vals.push(m[1] ?? m[2] ?? m[3]);
  for (const m of text.matchAll(P_CLASSLIST)) for (const s of m[1].matchAll(P_STR)) vals.push(s[1]);
  for (const v of vals) for (const t of v.replace(/\$\{[^}]*\}?/g, ' ').split(/\s+/)) if (TOKEN.test(t)) out.add(t);
  return out;
}
function addClassTokens(str, set) { for (const t of String(str).split(/\s+/)) if (t && t.length <= 160) set.add(t); }
function addLiteralTokens(js, all, classAttr) {
  for (const m of js.matchAll(/'((?:\\.|[^'\\\n])*)'|"((?:\\.|[^"\\\n])*)"|`((?:\\.|[^`\\])*)`/g)) {
    const s = m[1] ?? m[2] ?? m[3] ?? '';
    for (const c of s.matchAll(/class(?:Name)?\s*=\s*\\?["']([^"'\\]*)/g)) { addClassTokens(c[1].replace(/\$\{[^}]*\}?/g, ' '), classAttr); }
    addClassTokens(s.replace(/\$\{[^}]*\}?/g, ' '), all);
  }
}
function harvest(files) {
  const all = new Set(), classAttr = new Set(), lines = new Set(), scripts = new Set();
  const take = (text) => { for (const l of text.split(/\r?\n/)) { const t = l.trim(); if (t) lines.add(t); } };
  for (const f of files) {
    const t = fs.readFileSync(f, 'utf8');
    take(t);
    classUse(t, classAttr);
    for (const m of t.matchAll(/\bclass\s*=\s*("([^"]*)"|'([^']*)')/g)) addClassTokens(m[2] ?? m[3], all);
    for (const m of t.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
      const src = m[1].match(/\bsrc\s*=\s*["']([^"']+)["']/);
      if (src && !/^(https?:)?\/\//i.test(src[1])) {
        const p = src[1].startsWith('/') ? src[1].slice(1) : path.posix.normalize(path.posix.join(path.posix.dirname(f), src[1]));
        scripts.add(p.split('?')[0]);
      }
      if (m[2].trim() && !/application\/ld\+json/i.test(m[1])) addLiteralTokens(m[2], all, new Set());
    }
  }
  for (const s of scripts) {
    let t; try { t = fs.readFileSync(s, 'utf8'); } catch { continue; }
    take(t); addLiteralTokens(t, all, new Set()); classUse(t, classAttr);
  }
  for (const c of classAttr) all.add(c);
  return { all, classAttr, lines, scripts: [...scripts].sort() };
}

const escAttr = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// Class names a stylesheet's selectors name, unescaped (`.sm\:px-8` -> sm:px-8, `.\32xl` -> 2xl).
function cssClassNames(css) {
  const out = new Set();
  const bodyless = css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\{[^{}]*\}/g, '{}');
  for (const m of bodyless.matchAll(/\.((?:\\[0-9a-fA-F]{1,6} ?|\\[^\n0-9a-fA-F]|[A-Za-z0-9_-]|[^\x00-\x7F])+)/g)) {
    out.add(m[1].replace(/\\([0-9a-fA-F]{1,6}) ?/g, (_, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\(.)/g, '$1'));
  }
  return out;
}

async function compile(browser, fam, config, tokens, lines) {
  const toks = [...tokens].sort();
  const divs = [];
  for (let i = 0; i < toks.length; i += 40) divs.push(`<div class="${escAttr(toks.slice(i, i + 40).join(' '))}"></div>`);
  // The raw source goes in as inert text for the CDN's own extractor; `<` is swapped so no tag inside can end the block.
  const raw = [...lines].join('\n').replace(/</g, '\u2039');
  const html = `<!doctype html><html><head><meta charset="utf-8"><script src="${CDN}"></script><script>tailwind.config = ${JSON.stringify(config)};</script></head>`
    + `<body><div hidden>${divs.join('')}</div><script type="text/plain">${raw}</script></body></html>`;
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  let version = '';
  page.on('response', (r) => { const m = r.url().match(/cdn\.tailwindcss\.com\/(\d+\.\d+\.\d+)/); if (m) version = m[1]; });
  await page.setContent(html, { waitUntil: 'load', timeout: 120000 });
  let last = -1, still = 0, css = '';
  for (let i = 0; i < 240 && still < 4; i++) {
    await page.waitForTimeout(250);
    css = await page.evaluate(() => [...document.querySelectorAll('style')].map((s) => s.textContent).join('\n'));
    if (css.length && css.length === last) still++; else { still = 0; last = css.length; }
  }
  await ctx.close();
  if (!css.includes('--tw-')) throw new Error(`${fam}: the CDN produced no Tailwind CSS (${css.length} bytes)`);
  if (!version) { const m = css.match(/tailwindcss v(\d+\.\d+\.\d+)/); if (m) version = m[1]; }
  return { css, version };
}

async function cmdBuild() {
  const { chromium } = await import('playwright');
  const pages = allPages();
  const m = loadManifest();
  const want = opt('family');
  const fams = [...new Set(pages.filter((p) => p.state !== 'refused').map((p) => p.name))].filter((n) => !want || n === want).sort();
  const browser = await chromium.launch();
  try {
    for (const name of fams) {
      const members = familyPages(name, pages);
      const rec = m.families[name] || {};
      const cdnMember = members.find((p) => p.state === 'cdn');
      const config = cdnMember ? cdnMember.config : rec.config;
      if (!config) throw new Error(`${name}: no member still carries its config and the manifest has none`);
      // keep the most-annotated copy of the config (the generator's carries the reasons for its values)
      const src = cdnMember ? members.filter((p) => p.src).sort((x, y) => y.src.length - x.src.length)[0].src : rec.config_src;
      const files = members.map((p) => p.file).sort();
      const h = harvest(files);
      const t0 = Date.now();
      const { css, version } = await compile(browser, name, config, h.all, h.lines);
      const sheet = `wh-tw-pub-${name}.css`;
      const head = `/* ${sheet} - generated by tools/tw_public_build.mjs from the Tailwind Play CDN (v${version}) with the "${name}"\n`
        + `   config below. Do not edit by hand. A class added to a page that links this sheet needs a rebuild:\n`
        + `     node tools/tw_public_build.mjs build --family ${name}\n`
        + `   and the tw-public-sheets gate fails until it is done.\n`
        + `   config: ${JSON.stringify(config)} */\n`;
      fs.writeFileSync(sheet, head + css + (css.endsWith('\n') ? '' : '\n'));
      const names = cssClassNames(css);
      const nonUtil = [...h.classAttr].filter((c) => !names.has(c)).sort();   // the pages' own classes
      m.families[name] = {
        sheet, config_hash: h8(stable(config)), config, config_src: src, cdn_version: version,
        pages: files, local_scripts: h.scripts, harvested_tokens: h.all.size, class_tokens: h.classAttr.size,
        bytes: Buffer.byteLength(head + css), classes_in_sheet: names.size, non_utility_classes: nonUtil,
      };
      console.log(`${name.padEnd(10)} ${files.length} pages  ${h.all.size} tokens -> ${sheet} ${(Buffer.byteLength(css) / 1024).toFixed(1)} KB, `
        + `${names.size} classes, v${version}, ${((Date.now() - t0) / 1000).toFixed(1)} s`);
    }
  } finally { await browser.close(); }
  m.generated = new Date().toISOString();
  saveManifest(m);
}

// ── the swap ─────────────────────────────────────────────────────────────────
// Remove a tag; when it sits alone on its line, the whole line goes with it.
function cut(html, start, len) {
  let s = start, e = start + len;
  const ls = html.lastIndexOf('\n', s - 1) + 1;
  const nl = html.indexOf('\n', e);
  const le = nl === -1 ? html.length : nl;
  if (/^[ \t]*$/.test(html.slice(ls, s)) && /^[ \t]*\r?$/.test(html.slice(e, le))) { s = ls; e = nl === -1 ? html.length : nl + 1; }
  return html.slice(0, s) + html.slice(e);
}
function swapped(html, name) {
  CDN_TAG.lastIndex = 0; CONFIG_TAG.lastIndex = 0;
  const tags = [...html.matchAll(CDN_TAG)];
  if (tags.length !== 1) throw new Error(`${tags.length} CDN tags`);
  let out = cut(html, tags[0].index, tags[0][0].length);
  CONFIG_TAG.lastIndex = 0;
  const cfgs = [...out.matchAll(CONFIG_TAG)];
  if (cfgs.length > 1) throw new Error(`${cfgs.length} config scripts`);
  if (cfgs.length) out = cut(out, cfgs[0].index, cfgs[0][0].length);
  const heads = [...out.matchAll(/<\/head>/gi)];
  if (heads.length !== 1) throw new Error(`${heads.length} </head>`);
  const at = heads[0].index;
  const eol = out.includes('\r\n') ? '\r\n' : '\n';
  const ls = out.lastIndexOf('\n', at - 1) + 1;
  // The link is the LAST thing in <head>, on its own line at column 0 - the same bytes the generators emit
  // (build_pillar_pages.TW_LINK_RAMP, scaffold_article.py), and the line the </head> sweeps insert above.
  if (!/^[ \t]*$/.test(out.slice(ls, at))) return out.slice(0, at) + LINK(name) + out.slice(at);
  return out.slice(0, ls) + LINK(name) + eol + out.slice(ls);
}

function cmdApply() {
  const want = opt('family');
  let n = 0;
  for (const p of allPages()) {
    if (p.state !== 'cdn' || (want && p.name !== want)) continue;
    if (!NAMES[p.hash]) throw new Error(`${p.file}: family ${p.name} has no name yet - name it in NAMES first`);
    if (!fs.existsSync(`wh-tw-pub-${p.name}.css`)) throw new Error(`${p.file}: wh-tw-pub-${p.name}.css is not built`);
    const before = fs.readFileSync(p.file, 'utf8');
    fs.writeFileSync(p.file, swapped(before, p.name));
    n++;
  }
  console.log(`swapped ${n} page(s)`);
}

function cmdPlan() {
  const pages = allPages();
  const m = loadManifest();
  const fams = {};
  for (const p of pages) { (fams[p.state === 'refused' ? '!refused' : p.name] ||= []).push(p); }
  for (const [name, ps] of Object.entries(fams).sort()) {
    const first = ps.find((p) => p.config) || ps[0];
    const groups = {};
    for (const p of ps) { const k = p.file.split('/').slice(0, p.file.split('/').length > 2 ? 1 : 0).join('/') || '(root)'; groups[k] = (groups[k] || 0) + 1; }
    console.log(`\n${name}  ${ps.length} page(s)  ${JSON.stringify(groups)}${first.hash ? '  hash ' + first.hash : ''}`);
    if (name === '!refused') { for (const p of ps) console.log('   ', p.file, '-', p.why); continue; }
    if (first.config) console.log('   config', stable(first.config).slice(0, 400));
    for (const p of ps.slice(0, 4)) console.log('   ', p.file, p.state);
    if (name !== '!refused' && first.config) {
      m.families[name] = Object.assign(m.families[name] || {}, { config_hash: first.hash, config: first.config, config_src: first.src, pages: ps.map((p) => p.file).sort() });
    }
  }
  saveManifest(m);
}

// ── verify ───────────────────────────────────────────────────────────────────
const FEEDBACK_FIXTURE = [
  { id: '00000000-0000-4000-8000-000000000001', created_at: new Date(Date.now() - 3 * 864e5).toISOString(), kind: 'bug', subject: 'Fixture: the roadmap renders', body: 'A row served by the parity harness so the item template is drawn in both loads.', status: 'planned', upvotes: 4 },
  { id: '00000000-0000-4000-8000-000000000002', created_at: new Date(Date.now() - 9 * 864e5).toISOString(), kind: 'feature', subject: 'Fixture: a second row', body: 'x'.repeat(300), status: 'in_progress', upvotes: 1 },
];
async function stub(ctx) {
  await ctx.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith(ORIGIN) || u.startsWith(CDN)) return route.continue();
    if (/\.supabase\.co\/rest\/v1\/platform_feedback\?/.test(u)) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(FEEDBACK_FIXTURE) });
    if (/\.supabase\.co\/rest\/v1\/platform_feedback_votes\?/.test(u)) return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    return route.abort();
  });
}
function snapshotFn() {
  const isTwStyle = (n) => n.tagName === 'STYLE' && /^\s*(\/\*[\s\S]*?\*\/\s*)*\*,\s*::before,\s*::after\s*\{/.test(n.textContent) && n.textContent.slice(0, 2000).includes('--tw-');
  const isTwLink = (n) => n.tagName === 'LINK' && /\/wh-tw-pub-[\w-]+\.css$/.test(n.href);
  for (const a of document.getAnimations()) { try { a.finish(); } catch (e) { a.pause(); a.currentTime = 0; } }
  const order = [...document.styleSheets].map((s) => {
    const n = s.ownerNode;
    if (!n) return '?';
    if (isTwStyle(n) || isTwLink(n)) return 'TW';
    if (n.tagName === 'LINK') return 'link:' + n.getAttribute('href') + '|' + (n.getAttribute('media') || '');
    return 'style:' + n.textContent.length + ':' + n.textContent.trim().slice(0, 32);
  });
  const flat = (rules, ctx) => {
    const out = [];
    for (const r of rules) {
      const k = r.constructor.name;
      if ((k === 'CSSMediaRule' || k === 'CSSSupportsRule' || k === 'CSSContainerRule' || k === 'CSSLayerBlockRule') && r.cssRules) out.push(...flat(r.cssRules, ctx + '@' + (r.conditionText || r.name || '') + '|'));
      else if (k === 'CSSStyleRule') { const d = []; for (let i = 0; i < r.style.length; i++) { const p = r.style[i]; d.push(p + ':' + r.style.getPropertyValue(p) + (r.style.getPropertyPriority(p) ? '!' : '')); } out.push({ c: ctx, s: r.selectorText, d }); }
      else out.push({ c: ctx, raw: r.cssText });
    }
    return out;
  };
  const rules = [...document.styleSheets].filter((s) => s.ownerNode && (isTwStyle(s.ownerNode) || isTwLink(s.ownerNode))).flatMap((s) => flat(s.cssRules, ''));
  const sig = (cs) => { let s = ''; for (let i = 0; i < cs.length; i++) { const p = cs[i]; if (p.startsWith('--')) continue; s += p + ':' + cs.getPropertyValue(p) + ';'; } return s; };
  const fnv = (str) => { let h = 0x811c9dc5; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193); } return (h >>> 0).toString(36); };
  const els = [document.documentElement, document.body, ...document.body.querySelectorAll('*')];
  const sigs = els.map((el) => {
    let s = sig(getComputedStyle(el));
    for (const ps of ['::before', '::after']) { const c = getComputedStyle(el, ps); if (c.content !== 'none' && c.content !== 'normal') s += ps + sig(c); }
    return s;
  });
  window.__twSigs = sigs;
  const label = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  return { order, rules, els: els.map((el, i) => [label(el), fnv(sigs[i])]) };
}
async function loadOnce(browser, url, html, vp, waitTw) {
  const ctx = await browser.newContext({ viewport: { width: vp, height: vp < 600 ? 844 : 800 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
  await stub(ctx);
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().replace(/\s+/g, ' ').slice(0, 160)); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + String(e.message).slice(0, 160)));
  await page.route(url, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html }));
  await page.goto(url, { waitUntil: 'load', timeout: 90000 });
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  if (waitTw) {
    let last = -1, still = 0;
    for (let i = 0; i < 60 && still < 3; i++) {
      await page.waitForTimeout(200);
      const n = await page.evaluate(() => [...document.querySelectorAll('style')].reduce((a, s) => a + s.textContent.length, 0));
      if (n === last) still++; else { still = 0; last = n; }
    }
  } else await page.waitForTimeout(400);
  const snap = await page.evaluate(snapshotFn);
  return { ctx, page, snap, errors };
}
function sameRule(a, b) {
  if (a.c !== b.c) return false;
  if (a.raw !== undefined || b.raw !== undefined) return a.raw === b.raw;
  if (a.s !== b.s) return false;
  const bd = new Set(b.d);
  if (!a.d.every((x) => bd.has(x))) return false;
  const ad = new Set(a.d);
  return b.d.every((x) => ad.has(x) || x.startsWith('--tw-'));
}
// Every rule the CDN wrote for the page must be in the sheet. Their relative order can legitimately differ in one
// place: Tailwind orders the values of ONE utility (max-w-3xl / max-w-4xl, mb-1 / mb-1.5) by the order it first met
// them, so a page and the family-wide harvest can tie-break differently. That order decides a winner only when ONE
// element carries both rules' classes and they set a common property - so an inverted pair is returned as a
// candidate and the page itself is asked whether any element has both classes.
const lastClass = (sel) => { const all = [...String(sel).matchAll(/\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[A-Za-z0-9_-])+)/g)]; return all.length ? all[all.length - 1][1].replace(/\\([0-9a-fA-F]{1,6}) ?/g, (_, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\(.)/g, '$1') : null; };
const propsOf = (r) => new Set((r.d || []).map((x) => x.slice(0, x.indexOf(':'))).filter((p) => !p.startsWith('--')));
function ruleParity(A, B) {
  const missing = [], at = [], used = new Set();
  for (const r of A) {
    const k = B.findIndex((x, i) => !used.has(i) && sameRule(r, x));
    at.push(k);
    if (k < 0) missing.push(r.raw || (r.c + r.s + '{' + r.d.join(';') + '}')); else used.add(k);
  }
  const pairs = [];
  for (let i = 0; i < A.length; i++) for (let j = i + 1; j < A.length; j++) {
    if (at[i] < 0 || at[j] < 0 || at[i] < at[j] || A[i].c !== A[j].c || !A[i].s || !A[j].s) continue;
    const pi = propsOf(A[i]), shared = [...propsOf(A[j])].filter((p) => pi.has(p));
    const ci = lastClass(A[i].s), cj = lastClass(A[j].s);
    if (shared.length && ci && cj && ci !== cj) pairs.push([ci, cj, shared[0]]);
  }
  return { missing, pairs };
}
async function cmdVerify() {
  const { chromium } = await import('playwright');
  const want = opt('family'), match = opt('match'), limit = +opt('limit', '0');
  let pages = allPages().filter((p) => p.state === 'cdn' && (!want || p.name === want) && (!match || p.file.includes(match)));
  if (limit) {   // spread the sample across the family rather than taking its first N
    const step = pages.length / limit;
    pages = Array.from({ length: Math.min(limit, pages.length) }, (_, i) => pages[Math.floor(i * step)]);
  }
  const vps = (opt('vp', '390,1280')).split(',').map(Number);
  const browser = await chromium.launch();
  const results = [];
  let fails = 0;
  try {
    for (const p of pages) {
      if (!fs.existsSync(`wh-tw-pub-${p.name}.css`)) throw new Error(`wh-tw-pub-${p.name}.css is not built`);
      const url = `${ORIGIN}/${p.file}`;
      const orig = fs.readFileSync(p.file, 'utf8');
      const next = swapped(orig, p.name);
      const rec = { file: p.file, family: p.name, problems: [] };
      for (const vp of vps) {
        const a = await loadOnce(browser, url, orig, vp, true);
        const b = await loadOnce(browser, url, next, vp, false);
        try {
          if (JSON.stringify(a.snap.order) !== JSON.stringify(b.snap.order)) rec.problems.push(`@${vp} stylesheet order: CDN ${JSON.stringify(a.snap.order)} vs sheet ${JSON.stringify(b.snap.order)}`);
          if (vp === vps[0]) {
            if (!a.snap.rules.length) rec.problems.push('the CDN load produced no Tailwind rules (was the CDN reachable?)');
            const { missing, pairs } = ruleParity(a.snap.rules, b.snap.rules);
            if (missing.length) rec.problems.push(`${missing.length} rule(s) the CDN generated are not in the sheet: ${missing.slice(0, 4).join(' || ').slice(0, 600)}`);
            const live = await a.page.evaluate((ps) => ps.filter(([x, y]) => [...document.querySelectorAll('[class]')].some((el) => el.classList.contains(x) && el.classList.contains(y))), pairs);
            if (live.length) rec.problems.push(`${live.length} element(s) carry two utilities whose order flipped: ${live.slice(0, 4).map((p) => p.join(' / ')).join(' || ')}`);
            rec.cdn_rules = a.snap.rules.length; rec.sheet_rules = b.snap.rules.length; rec.tie_pairs = pairs.length; rec.tie_pairs_live = live.length;
          }
          if (a.snap.els.length !== b.snap.els.length) rec.problems.push(`@${vp} element count ${a.snap.els.length} vs ${b.snap.els.length}`);
          else {
            const diff = [];
            for (let i = 0; i < a.snap.els.length; i++) if (a.snap.els[i][1] !== b.snap.els[i][1]) diff.push(i);
            if (diff.length) {
              const pick = diff.slice(0, 3);
              const sa = await a.page.evaluate((ix) => ix.map((i) => window.__twSigs[i]), pick);
              const sb = await b.page.evaluate((ix) => ix.map((i) => window.__twSigs[i]), pick);
              const detail = pick.map((i, n) => {
                const pa = Object.fromEntries(sa[n].split(';').filter(Boolean).map((x) => [x.slice(0, x.indexOf(':')), x.slice(x.indexOf(':') + 1)]));
                const pb = Object.fromEntries(sb[n].split(';').filter(Boolean).map((x) => [x.slice(0, x.indexOf(':')), x.slice(x.indexOf(':') + 1)]));
                const props = [...new Set([...Object.keys(pa), ...Object.keys(pb)])].filter((k) => pa[k] !== pb[k]).slice(0, 4);
                return `${a.snap.els[i][0]} ${props.map((k) => `${k}: ${pa[k]} -> ${pb[k]}`).join(', ')}`;
              });
              rec.problems.push(`@${vp} ${diff.length} of ${a.snap.els.length} elements differ: ${detail.join(' || ').slice(0, 700)}`);
            }
            rec[`els_${vp}`] = a.snap.els.length;
          }
          const fresh = b.errors.filter((e) => !a.errors.includes(e));
          if (fresh.length) rec.problems.push(`@${vp} new console error(s): ${fresh.slice(0, 3).join(' || ')}`);
        } finally { await a.ctx.close(); await b.ctx.close(); }
      }
      if (rec.problems.length) fails++;
      results.push(rec);
      console.log(`${rec.problems.length ? 'FAIL' : 'ok  '} ${p.name.padEnd(9)} ${p.file}  rules ${rec.cdn_rules}/${rec.sheet_rules}  els ${vps.map((v) => rec['els_' + v]).join('/')}`
        + (rec.problems.length ? '\n      ' + rec.problems.join('\n      ') : ''));
    }
  } finally { await browser.close(); }
  fs.mkdirSync('.tmp/tw_pub', { recursive: true });
  fs.writeFileSync('.tmp/tw_pub/verify.json', JSON.stringify({ at: new Date().toISOString(), viewports: vps, pages: results }, null, 1));
  console.log(`\n${results.length - fails}/${results.length} pages at parity -> .tmp/tw_pub/verify.json`);
  process.exitCode = fails ? 1 : 0;
}

// swap-file IN OUT FAMILY: the swap on one file, for proving a generator's new output equals the swap of its old one.
function cmdSwapFile() {
  const [, inp, outp, name] = args;
  fs.writeFileSync(outp, swapped(fs.readFileSync(inp, 'utf8'), name));
}

if (cmd === 'plan') cmdPlan();
else if (cmd === 'build') await cmdBuild();
else if (cmd === 'verify') await cmdVerify();
else if (cmd === 'apply') cmdApply();
else if (cmd === 'swap-file') cmdSwapFile();
else { console.log('usage: node tools/tw_public_build.mjs plan | build [--family F] | verify [--family F] [--match S] [--limit N] [--vp 390,1280] | apply [--family F] | swap-file IN OUT FAMILY'); process.exitCode = 2; }
