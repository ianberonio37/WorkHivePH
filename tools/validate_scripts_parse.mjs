/* validate_scripts_parse.mjs - every shared script and every inline script on every served page PARSES (2026-10-15).
 *
 * WHY. A comment written inside offline-banner.js's CSS - "(a `top` transition ...)" - closed the JavaScript template
 * literal that sheet lives in. The file stopped parsing, the shared offline banner died on every page that loads it, and
 * the console blamed utils.js. The lesson was already in memory ("a BACKTICK in a comment broke the page"); a lesson
 * that depends on remembering does not happen, so this is the gate. verify_page_parses.mjs answers the same question in
 * a browser, page by page; this one is static, takes a second, and runs on every board.
 *
 * WHAT. Root *.js (the shared scripts), and the classic inline <script> blocks of the root pages, learn/<slug>/index.html
 * and tools/<calculator>/index.html - each compiled with node:vm (parse only, nothing runs). Skipped: src= scripts (their
 * file is checked on its own), type=module, and data blocks (ld+json, application/json, templates).
 *
 *   node tools/validate_scripts_parse.mjs              # the gate
 *   node tools/validate_scripts_parse.mjs --self-test  # the backtick case and a broken quote must fail; clean code passes
 */
import { readFileSync, readdirSync, existsSync, statSync, writeFileSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..');
const CLASSIC = (attrs) => {
  const t = (attrs.match(/\btype\s*=\s*["']?([^"'\s>]+)/i) || [])[1];
  return !t || /^(text|application)\/(javascript|ecmascript)$/i.test(t);
};

export function scriptProblems(name, src, isHtml, opts = {}) {
  const out = [];
  if (!isHtml) {
    // an ES module (import/export at top level) is not a classic script: node --check parses it as what it is
    // (a .js file is CommonJS to node, so the copy it checks carries .mjs - live-state-runner.js is imported by browsers)
    if (/^\s*(import|export)\b/m.test(src)) {
      const tmp = join(tmpdir(), `scripts-parse-${process.pid}-${Math.random().toString(36).slice(2)}.mjs`);
      try { writeFileSync(tmp, src); execFileSync(process.execPath, ['--check', tmp], { stdio: 'pipe' }); }
      catch (e) { out.push(`${name}: ${String(e.stderr || e.message).split('\n').find((l) => /Error/.test(l)) || 'does not parse'}`); }
      finally { try { unlinkSync(tmp); } catch (_) { /* gone already */ } }
      return out;
    }
    try { new vm.Script(src, { filename: name }); } catch (e) { out.push(`${name}: ${e.message}`); }
    return out;
  }
  // an HTML comment that MENTIONS a script tag ("before the <script> block runs") is not one: blank the comments first,
  // keeping their newlines so line numbers stay true
  src = src.replace(/<!--[\s\S]*?-->/g, (c) => c.replace(/[^\n]/g, ' '));
  const re = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
  let m;
  while ((m = re.exec(src))) {
    const attrs = m[1];
    if (/\bsrc\s*=/.test(attrs) || !CLASSIC(attrs) || !m[2].trim()) continue;
    try { new vm.Script(m[2], { filename: name }); }
    catch (e) { out.push(`${name}:${src.slice(0, m.index).split('\n').length}: inline script - ${e.message}`); }
  }
  // ★AN INLINE HANDLER IS A SCRIPT TOO (2026-10-21, SL L3 walk). An edit left onclick="setPhase('diagnostic', true)\" on
  // all four analytics phase tabs: the attribute's code ended in a backslash, every tab threw "Invalid or unexpected
  // token" when pressed, and this gate - which compiled only <script> blocks - passed. Every on* attribute in the
  // markup is compiled as the function body the browser makes of it. The markup is read with its scripts and styles
  // blanked (a script's template strings BUILD handlers from data and are checked as that script), and only inside a
  // tag (text that merely says "onclick=" is not one).
  const markup = src.replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, (s) => s.replace(/[^\n]/g, ' '))
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, (s) => s.replace(/[^\n]/g, ' '));
  const ATTR = /\s(on[a-z]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi;
  let a;
  while ((a = ATTR.exec(markup))) {
    if (markup.lastIndexOf('<', a.index) < markup.lastIndexOf('>', a.index)) continue;
    const code = decodeEntities(a[2] != null ? a[2] : a[3]);
    try { new vm.Script('(function (event) {\n' + code + '\n})', { filename: name }); }
    catch (e) { out.push(`${name}:${markup.slice(0, a.index).split('\n').length}: ${a[1]} handler - ${e.message}`); }
  }
  return out;
}

// the browser decodes an attribute's character references before it compiles the handler
function decodeEntities(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|quot|apos|lt|gt|amp|nbsp);/gi, (m, e) => {
    const k = e.toLowerCase();
    if (k[0] === '#') return String.fromCodePoint(k[1] === 'x' ? parseInt(k.slice(2), 16) : parseInt(k.slice(1), 10));
    return { quot: '"', apos: "'", lt: '<', gt: '>', amp: '&', nbsp: ' ' }[k];
  });
}

function files() {
  const out = [];
  for (const f of readdirSync(ROOT)) {
    if (/\.(js|html)$/.test(f) && !f.startsWith('zz_') && statSync(join(ROOT, f)).isFile()) out.push(join(ROOT, f));
  }
  for (const dir of ['learn', 'tools']) {
    const base = join(ROOT, dir);
    if (!existsSync(base)) continue;
    for (const d of readdirSync(base)) {
      const p = join(base, d, 'index.html');
      if (existsSync(p)) out.push(p);
    }
  }
  return out;
}

function selfTest() {
  const tpl = 'const STYLE = `\n  /* the page moves (a `top`\n  transition) */\n  body { margin: 0; }\n`;';
  const ok = 'const STYLE = `\n  /* the page moves (a transition on top) */\n  body { margin: 0; }\n`;';
  const html = (js) => `<html><body><script>${js}</script><script type="application/ld+json">{"a":1}</script>` +
    `<script type="module">import x from "./x.js";</script><script src="utils.js"></script></body></html>`;
  const cases = [
    ['the backtick inside a template-literal sheet (offline-banner.js, 2026-10-15)', scriptProblems('t.js', tpl, false).length === 1],
    ['the same sheet without the backtick', scriptProblems('t.js', ok, false).length === 0],
    ["a lost escape in an inline script (day\\'s -> day's)", scriptProblems('p.html', html("var s = 'day's';"), true).length === 1],
    ['a clean page with JSON-LD, a module and a src script', scriptProblems('p.html', html('var s = 1;'), true).length === 0],
    ['a comment that mentions a <script> tag', scriptProblems('p.html', '<!-- must be in the DOM before the <script> block runs --><script>var s = 1;</script>', true).length === 0],
    ['a handler that ends in a stray backslash (analytics phase tabs, 2026-10-21)',
      scriptProblems('p.html', '<button onclick="setPhase(\'diagnostic\', true)\\">Why</button>', true).length === 1],
    ['a clean handler written with character references',
      scriptProblems('p.html', '<button onclick="go(&quot;a&quot;, 1 &amp;&amp; 2)">Go</button>', true).length === 0],
    ['a handler BUILT inside a script template is that script\'s, not markup',
      scriptProblems('p.html', '<script>var h = `<b onclick="f(\'${x}\')">`;</script>', true).length === 0],
  ];
  const bad = cases.filter(([, pass]) => !pass);
  for (const [name, pass] of cases) console.log(`  ${pass ? 'ok  ' : 'FAIL'} ${name}`);
  console.log(`${bad.length ? 'FAIL' : 'PASS'} scripts-parse self-test - ${cases.length - bad.length}/${cases.length}`);
  return bad.length ? 1 : 0;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  if (process.argv.includes('--self-test')) process.exit(selfTest());
  const all = files();
  const problems = all.flatMap((f) => scriptProblems(relative(ROOT, f).replace(/\\/g, '/'), readFileSync(f, 'utf8'), f.endsWith('.html'), { path: f }));
  for (const p of problems) console.log('  FAIL ' + p);
  console.log(problems.length
    ? `FAIL scripts-parse - ${problems.length} script(s) do not parse`
    : `PASS scripts-parse - ${all.length} files: every shared script and every classic inline script parses`);
  process.exit(problems.length ? 1 : 0);
}
