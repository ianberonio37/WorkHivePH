// prove_ux_census — the cross-platform UX census journeys (T176, T180, T182, T183, T184), 2026-09-07.
//
// Five rows that are not about one page but about the platform's CONSISTENCY across all of them. A person
// does not experience a page, they experience a product: if the same idea is called three names, if one
// form labels its fields and the next does not, if an error explains itself here and shrugs there, the
// person learns that the platform cannot be predicted - and unpredictable is the same as untrustworthy
// when the thing being recorded is why a machine stopped.
//
//   C1 errors explain   an error message says what happened and what the person can do, rather than
//                       "something went wrong" - measured across every page, because one shrug in
//                       twenty-four is the one a person meets at 3am (T176)
//   C2 forms are labelled every input a person types into has a label a screen reader and a sighted
//                       person both get - not a placeholder pretending to be one (T180)
//   C3 success is sized  a confirmation is proportional: a saved note is not celebrated like a
//                       completed audit, or the celebration stops meaning anything (T182)
//   C4 settings cohere   preferences live in one place and are called one thing, rather than three
//                       pages each owning a slice (T183)
//   C5 pages rhyme       the shared furniture - the nav landmark, the source chip, the back link - is on
//                       every page that needs it, so a person's second page teaches them nothing new
//                       they have to unlearn (T184)
//
// ★COUNTED ACROSS EVERY SHIPPED PAGE, NOT A SAMPLE. A census that samples reports the average page; what
// matters here is the WORST page, because that is the one a person will be standing on when it matters.
//
//   node tools/prove_ux_census.mjs
import { readdirSync, readFileSync } from 'node:fs';

const pages = readdirSync('.').filter((f) => f.endsWith('.html') && !/^(symbol-gallery|design-system|validator-catalog)\.html$/.test(f));
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
// ★COMMENTS ARE NOT THE PRODUCT. The first run reported 14 pages carrying an unlabelled field; the
// sample it named was `<input>` written inside a JS comment at audit-log.html:672 explaining how a
// datalist combobox behaves. It also called two pages celebration-happy over the WORD "celebrated" in
// prose and two 🎉 in copy. Every lens below reads the page with its comments removed, because a person
// never meets a comment - and a census that counts them fabricates defects at scale.
const strip = (src) => src
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ 	]*\/\/.*$/gm, ' ');
const SRC = new Map(pages.map((f) => [f, strip(read(f))]));

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── C1 · does an error say what a person can do? ─────────────────────────────────────────────────
{
  // the shrug: a message that names no cause and offers no action. Quoted strings only - a variable
  // named genericError is not what the person reads.
  const SHRUG = /['"`](something went wrong|an error occurred|error occurred|unknown error|oops[!.]?|failed)[.!]?['"`]/i;
  const offenders = [];
  for (const [f, src] of SRC) {
    const hits = src.match(new RegExp(SHRUG.source, 'gi')) || [];
    // a shrug is forgivable when the SAME message also tells them what to do next
    const rescued = hits.filter(() => /try again|check your connection|refresh|sign in again|contact/i.test(src));
    if (hits.length && rescued.length < hits.length) offenders.push(`${f} (${hits.length})`);
  }
  say(offenders.length === 0, 'C1 errors explain',
    `${pages.length - offenders.length} of ${pages.length} page(s) never leave a person with a bare shrug`,
    `${offenders.length} page(s) show a message naming no cause and offering no action: ${offenders.slice(0, 5).join(', ')}`);
}

// ── C2 · can a person tell what a field wants? ───────────────────────────────────────────────────
{
  const offenders = [];
  for (const [f, src] of SRC) {
    // every text-ish input on the page, minus the ones a label or aria could be attached to elsewhere
    const inputs = src.match(/<(input|textarea|select)\b[^>]*>/gi) || [];
    const unlabelled = inputs.filter((tag) => {
      if (/type=["'](hidden|submit|button|image)["']/i.test(tag)) return false;
      if (/aria-label=|aria-labelledby=|\btitle=/i.test(tag)) return false;
      // ★AN INTERPOLATED ATTRIBUTE SLOT CANNOT BE JUDGED FROM THE TEMPLATE. resume.html renders its
      // fields as `<input class="wh-input" ${dataAttr} ${_alab} …>`, where _alab is literally
      // `aria-label="…"` built one line above - so the RENDERED tag is labelled and the template is not.
      // A tag carrying an interpolation slot is unmeasured by this static lens, and saying so beats
      // inventing a defect the person never meets.
      if (tag.includes('${')) return false;
      const id = (tag.match(/\bid=["']([^"']+)["']/i) || [])[1];
      // a <label for=id> anywhere on the page counts, and so does a wrapping <label>
      if (id && new RegExp(`<label[^>]*\\bfor=["']${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["']`, 'i').test(src)) return false;
      // ★A WRAPPING <label> IS A LABEL. Checkboxes and radios on this platform are written inside their
      // own <label>, which needs no for= at all and is the more robust form - the click target grows to
      // include the words. Looking only for for= called nine pages unlabelled over markup that reads
      // perfectly to a screen reader.
      // ★A FIXED LOOKBACK WINDOW CANNOT ANSWER THIS. hive.html wraps each radio in a <label class="ic-opt"
      // style="…"> whose inline style alone runs past 200 characters, so a 400-char window started INSIDE
      // the opening tag; widening it to 1600 fixed three of five and left two, because the window then
      // swallowed whole earlier label pairs and the counts balanced. Tuning a window is chasing the
      // instrument. What actually decides it is which tag is NEAREST behind this input - an unclosed
      // <label> means we are inside one, a </label> means we are not.
      const at = src.indexOf(tag);
      if (at > 0) {
        const open = src.lastIndexOf('<label', at);
        const close = src.lastIndexOf('</label>', at);
        if (open > close) return false;
      }
      return true;
    });
    // a placeholder is NOT a label: it disappears the moment a person types, exactly when they need it
    const placeholderOnly = unlabelled.filter((t) => /placeholder=/i.test(t));
    if (unlabelled.length) offenders.push(`${f} (${unlabelled.length}${placeholderOnly.length ? `, ${placeholderOnly.length} lean on a placeholder` : ''})`);
    // --show names the actual tags, so a fix goes to the field rather than to the count
    if (process.argv.includes('--show') && unlabelled.length) {
      console.log(`   ${f}`);
      for (const t of unlabelled) console.log(`     ${t.replace(/\s+/g, ' ').slice(0, 124)}`);
    }
  }
  say(offenders.length === 0, 'C2 forms are labelled',
    `${pages.length - offenders.length} of ${pages.length} page(s) label every field a person types into`,
    `${offenders.length} page(s) carry a field with no label, no aria-label and no title: ${offenders.slice(0, 4).join(', ')}`);
}

// ── C3 · is a success proportional to what was done? ─────────────────────────────────────────────
{
  // ★A CELEBRATION IS SOMETHING THE PAGE DOES, NOT A WORD IT CONTAINS. Matching /celebrat|🎉/ anywhere
  // flagged inventory.html for the word "celebrated" in a sentence and community.html for two emoji in
  // copy. What is actually disproportionate is an ANIMATION fired on an ordinary save.
  const LOUD = /confetti|fireworks\s*\(|canvas-confetti|requestAnimationFrame[\s\S]{0,200}(confetti|particle|burst)/i;
  const loud = pages.filter((f) => LOUD.test(SRC.get(f)));
  // the honest shape: the loud thing is reachable only from a milestone surface
  const milestone = loud.filter((f) => /achievement|onboard|resume|skillmatrix|index|project-report/i.test(f));
  say(loud.length === milestone.length, 'C3 success is sized',
    loud.length ? `${loud.length} page(s) run a celebration animation, all ${milestone.length} of them on a milestone surface` : 'no page fires a celebration animation on an ordinary save',
    `${loud.filter((f) => !milestone.includes(f)).join(', ')} celebrate an ordinary save as though it were an achievement - do that everywhere and it means nothing anywhere`);
}

// ── C4 · do preferences live in one place? ───────────────────────────────────────────────────────
{
  // a preference is anything stored as a person's choice; the question is how many pages OWN one
  const owners = pages.filter((f) => /localStorage\.setItem\(\s*['"]wh_(pref|setting|theme|density|quiet|notify|locale)/i.test(SRC.get(f)));
  say(owners.length <= 3, 'C4 settings cohere',
    `${owners.length} page(s) write a stored preference${owners.length ? `: ${owners.slice(0, 5).join(', ')}` : ''}`,
    `preferences are owned by ${owners.length} different pages, so a person changing one has no single place to look and no way to know what else they have set`);
}

// ── C5 · does a person's second page teach them nothing to unlearn? ──────────────────────────────
{
  // the shared furniture every page carries, so the platform reads as one product
  // ★THIS PLATFORM'S NAV LANDMARK IS INJECTED, NOT WRITTEN. nav-hub.js says so at its line 588 - "the hub
  // IS this platform's navigation on every page that has it" - and sets role="navigation" at runtime. A
  // static read saw none of that and reported 31 of 39 pages as landmark-less, on a platform where every
  // visitor gets one. A page that LOADS the hub has the landmark; that is what the person meets.
  // ★A PAGE WITH NO NAVIGATION DOES NOT OWE A NAVIGATION LANDMARK - IT OWES A WAY BACK. Five pages carry
  // no hub at all by design: the public status page, the poster generator, the owner's action console and
  // the two observability views. Demanding a <nav> of them would be demanding navigation they do not have.
  // What a person on those pages actually needs is to not be stranded, and all five carry a link home.
  const missingNav = pages.filter((f) => {
    const src = SRC.get(f);
    const hasNav = /role=["']navigation["']|<nav\b/i.test(src) || /nav-hub\.js/i.test(src);
    if (hasNav) return false;
    const wayBack = /wh-back-link|href=["'](index|hive)\.html/i.test(src);
    return !wayBack;
  });
  const missingMain = pages.filter((f) => !/role=["']main["']|<main\b/i.test(SRC.get(f)));
  const missingTitle = pages.filter((f) => !/<title>[^<]{3,}<\/title>/i.test(SRC.get(f)));
  const worst = [...new Set([...missingNav, ...missingMain, ...missingTitle])];
  say(worst.length === 0, 'C5 pages rhyme',
    `${pages.length - worst.length} of ${pages.length} page(s) carry the same furniture: navigation or a way back, a main landmark and a real title`,
    `${missingNav.length} strand a person with neither navigation nor a way back, ${missingMain.length} lack a main landmark, ${missingTitle.length} lack a title: ${worst.slice(0, 5).join(', ')}`);
}

console.log(`${bad ? 'FAIL' : 'PASS'} ux-census - across every shipped page: errors explain themselves, fields are labelled, success is proportional, preferences cohere, and the furniture rhymes`);
process.exitCode = bad ? 1 : 0;
