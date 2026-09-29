// check_inline_scripts.js - every <script> without src in an HTML page must parse. Exit 1 and print the
// offenders if any does not; otherwise print what was and was not checked.
//
// ★A PAGE WHOSE INLINE SCRIPT DOES NOT PARSE IS NOT A PAGE (2026-09-15): a copy edit through a heredoc left an
// unescaped apostrophe in achievements.html's main script; the detector was clean, the precache gate green, and
// the walk measured a page stuck at "Computing..." with 629 characters.
//
// ★A TYPED <script> IS NOT ALWAYS JAVASCRIPT (2026-09-16, W46283). The first version refused the first public
// page it ever saw - "#1 Unexpected token ':'" - because `<script type="application/ld+json">` matches "an
// inline script" and JSON is not a JavaScript program. Skipping typed scripts wholesale would be worse:
// `type="module"` IS JavaScript and is exactly the class this rule exists to catch. So the type decides the
// grammar, and the JSON blocks are still checked - as JSON, which is stricter than not checking them.
//
// ★AN EMPTY JSON BLOCK IS A PLACEHOLDER, NOT A SYNTAX ERROR (2026-09-17, W45951). marketplace-seller-profile
// carries `<script type="application/ld+json" id="seller-ld-json"></script>` and fills it at runtime from the
// seller it loaded (injectJsonLd) - the ordinary way to publish structured data you do not have until the fetch
// returns. JSON.parse('') throws "Unexpected end of JSON input", so the rule refused a page for using the
// pattern correctly. Empty blocks are counted separately rather than folded into the pass count.
//
// ★A <script> INSIDE AN HTML COMMENT IS NOT A SCRIPT (2026-09-17, W46021). The check used to run one regex over
// the raw file, so report-sender.html's comment - "Add Contact bottom sheet - must be in DOM before the
// <script> block runs" - opened a script block that swallowed markup until the next real </script>, and the page
// was refused for "Unexpected identifier 'runs'". The page is legal HTML: a browser in the data state treats
// `<!--` as a comment and never tokenises what is inside it as markup. Fixing the PAGE to suit the regex would
// have been tuning the page to the instrument. So this walks the file the way the tokenizer does, alternating
// between two states, which also gets the converse right: inside a script's raw-text body `<!--` is just text
// and must NOT start a comment.
const fs = require('fs');

const JS = /^(module|text\/javascript|application\/javascript|text\/ecmascript|application\/ecmascript|text\/babel|text\/jsx)$/i;
const JSON_T = /^(application\/ld\+json|application\/json|importmap|speculationrules)$/i;

function blocks(html) {
  // Two states, like the tokenizer: DATA (comments are comments) and the raw-text body of a script.
  const out = [];
  let k = 0;
  while (k < html.length) {
    const lt = html.indexOf('<', k);
    if (lt < 0) break;
    if (html.startsWith('<!--', lt)) {
      const end = html.indexOf('-->', lt + 4);
      k = end < 0 ? html.length : end + 3;
      continue;
    }
    const m = /^<script\b([^>]*)>/i.exec(html.slice(lt));
    if (!m) { k = lt + 1; continue; }
    const bodyStart = lt + m[0].length;
    const close = html.slice(bodyStart).search(/<\/script\s*>/i);
    const bodyEnd = close < 0 ? html.length : bodyStart + close;
    out.push({ attrs: m[1], body: html.slice(bodyStart, bodyEnd) });
    k = close < 0 ? html.length : bodyEnd + html.slice(bodyEnd).match(/<\/script\s*>/i)[0].length;
  }
  return out;
}

const html = fs.readFileSync(process.argv[2], 'utf8');
let i = 0, j = 0, empty = 0, skipped = 0, sourced = 0;
const bad = [];

for (const b of blocks(html)) {
  if (/\bsrc=/i.test(b.attrs)) { sourced++; continue; }
  const t = ((/\btype=["']([^"']*)["']/.exec(b.attrs) || [])[1] || '').trim();
  if (!t || JS.test(t)) {
    i++;
    try { new Function(b.body); }
    catch (e) { bad.push('script #' + i + ' (' + (t || 'untyped') + ') ' + e.message); }
  } else if (JSON_T.test(t)) {
    if (!b.body.trim()) { empty++; }
    else {
      j++;
      try { JSON.parse(b.body); }
      catch (e) { bad.push('json block #' + j + ' (' + t + ') ' + e.message); }
    }
  } else {
    skipped++;
  }
}

if (bad.length) { console.log(bad.join('; ')); process.exit(1); }
console.log(i + ' inline script(s) parse, ' + j + ' JSON block(s) parse, ' + empty +
            ' empty placeholder(s), ' + skipped + ' non-executable skipped, ' + sourced + ' sourced');
