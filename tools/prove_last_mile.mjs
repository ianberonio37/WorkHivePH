// prove_last_mile — the remaining journeys (T100, T123, T192, T197), 2026-09-07.
//
// Four rows left over from every other cluster, sharing only that each is about a moment the platform
// does not control: an AI writes on someone's behalf, a person pastes from somewhere else, a release
// lands under them, and one dependency fails while the rest keeps working.
//
//   M1 the assist is honest  an AI that improves a listing must be declared as AI and leave the person
//                            in charge of the result - a seller who did not know a machine wrote their
//                            description cannot stand behind it (T100)
//   M2 paste is not fought   nothing blocks paste, and fields a browser can fill are labelled so it
//                            fills them correctly - a person copying a part number out of a PDF should
//                            not be retyping it, and autofill should not put a phone number in a bin
//                            location (T123)
//   M3 the release is felt   a deploy that changes what a person sees tells them, and an installed PWA
//                            is not left serving yesterday's app forever (T192)
//   M4 storage fails alone   when the media layer is down, the pages that do not need it keep working,
//                            and the ones that do say what is missing rather than hanging (T197)
//
// ★M4 ACTUALLY STOPS THE CONTAINER. A dependency failure reasoned about is not a dependency failure
// observed - the storage service is stopped, the platform is read, and it is started again.
//
//   node tools/prove_last_mile.mjs
import { execSync } from 'node:child_process';
import { readdirSync, readFileSync, existsSync } from 'node:fs';

const sh = (cmd) => { try { return execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch { return ''; } };
const psql = (sql) => sh(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`);
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const pages = readdirSync('.').filter((f) => f.endsWith('.html'));
const anyPage = (rx) => pages.filter((f) => rx.test(read(f)));
const fnSrc = (d) => read(`supabase/functions/${d}/index.ts`);

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── M1 · an assist that admits what it is ────────────────────────────────────────────────────────
{
  const assist = existsSync('supabase/functions/marketplace-listing-assist');
  const src = assist ? fnSrc('marketplace-listing-assist') : '';
  const seller = read('marketplace-seller.html');
  // declared: the person is told a machine wrote it, in the interface, not only in a function comment
  const declared = /ai|assist|suggest|generated/i.test(seller) && /\b(ai|assistant|suggested|draft)\b/i.test(seller);
  // and editable: a suggestion the person cannot change is a machine publishing under their name
  const editable = /<textarea|contenteditable|value=/i.test(seller);
  // and it must not invent a claim about the goods - the grounding is the listing's own fields
  const grounded = /title|category|condition|price|part_number/i.test(src);
  say(assist && declared && editable && grounded, 'M1 the assist is honest',
    `the listing assist ${assist ? 'ships' : 'does NOT exist'}; the seller page ${declared ? 'names it as AI' : 'does NOT say a machine wrote it'}, the result ${editable ? 'stays editable' : 'is NOT editable'}, and the function is grounded in the listing's own fields (${grounded})`,
    !assist ? 'there is no listing assist, so this lens is about a feature that does not exist'
      : !declared ? 'a machine writes the description and the seller is never told, so they publish words they did not write and cannot stand behind'
      : 'the suggestion cannot be edited, which makes it a machine publishing under a person\\u2019s name');
}

// ── M2 · paste and autofill ──────────────────────────────────────────────────────────────────────
{
  // fighting paste is the cardinal sin here: a person copying a part number out of a PDF
  const blocksPaste = pages.filter((f) => /onpaste\s*=\s*["']?\s*return false|preventDefault\(\)[^}]{0,60}paste|addEventListener\(\s*['"]paste['"][^)]*preventDefault/i.test(read(f)));
  // autofill needs the browser to know what a field IS, or it fills a bin location with a phone number
  const withAutocomplete = pages.filter((f) => /autocomplete=/i.test(read(f)));
  // and the fields that must NOT be autofilled from a previous person's session say so
  const guardsList = pages.filter((f) => /autocomplete=["']off["']/i.test(read(f)));
  say(blocksPaste.length === 0 && withAutocomplete.length > 0, 'M2 paste is not fought',
    `${blocksPaste.length} page(s) block paste; ${withAutocomplete.length} page(s) tell the browser what their fields are, ${guardsList.length} of them opting a field out deliberately`,
    blocksPaste.length ? `${blocksPaste.slice(0, 3).join(', ')} cancel a paste event, so a person who copied a part number has to retype it by hand`
      : 'no page declares what its fields are, so a browser filling them guesses - which is how a phone number lands in a bin location');
}

// ── M3 · a release the person can feel ───────────────────────────────────────────────────────────
{
  const sw = read('sw.js');
  // ★sw.js KEEPS ITS BUMP HISTORY AS COMMENTED-OUT COPIES OF THIS EXACT LINE, above the live one. The
  // first version of this lens matched the first occurrence and reported the shell as v283 while the
  // ACTIVE cache was v319 - a retired value printed as current fact. Read the line that is not commented.
  const versioned = /^const CACHE_NAME\s*=\s*['"]workhive-shell-v(\d+)/m.exec(sw);
  // an installed PWA must be TOLD a new version is waiting, not silently left on the old one
  const announces = /waiting|updatefound|new version|refresh to update|registration\.waiting/i.test(read('nav-hub.js') + read('utils.js') + sw);
  // and a person must be able to say WHICH version they are on when reporting a problem
  const quotable = /whBuildVersion|app v|build/i.test(read('utils.js'));
  say(!!versioned && announces && quotable, 'M3 the release is felt',
    `the shell is at v${versioned ? versioned[1] : '?'}; a waiting update ${announces ? 'is announced to the person' : 'is NOT announced'}; the version ${quotable ? 'is quotable when they report a problem' : 'cannot be quoted'}`,
    !versioned ? 'the service worker carries no version, so a changed shell never re-primes and an installed device serves yesterday forever'
      : !announces ? 'a new version installs silently and waits, so a person keeps using the old app with no idea one is ready'
      : 'a person cannot say which build they are on, so a bug report cannot be tied to a release');
}

// ── M4 · the media layer fails alone ─────────────────────────────────────────────────────────────
{
  const name = 'supabase_storage_workhive';
  const wasUp = sh(`docker ps --filter name=${name} --format "{{.Names}}"`) === name;
  if (!wasUp) {
    console.log('  n/a M4 storage fails alone  the storage container is not running, so its failure cannot be distinguished from its absence - unmeasured, not clean');
  } else {
    // ★STOP IT FOR REAL. Reasoning about a dependency failure is not observing one.
    sh(`docker stop ${name}`);
    const dbStillUp = psql('select 1') === '1';
    // ★AN EMPTY STATUS CODE IS NOT A STATUS CODE. The first run printed "the API returned " with nothing
    // after it, which reads as a measurement and is an absence. Use fetch, which cannot come back blank,
    // and say plainly when the call itself failed.
    let edgeStillUp;
    try {
      const r = await fetch('http://127.0.0.1:54321/rest/v1/', { headers: { apikey: process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ' } });
      edgeStillUp = String(r.status);
    } catch (e) { edgeStillUp = `no answer (${String(e).slice(0, 40)})`; }
    sh(`docker start ${name}`);
    const backUp = sh(`docker ps --filter name=${name} --format "{{.Names}}"`) === name;
    // and the pages that DO need media must say what is missing rather than hanging on a broken image
    const handlesMissing = anyPage(/onerror=|image (unavailable|failed)|could not load (the )?(image|photo)|no photo/i);
    say(dbStillUp && backUp && handlesMissing.length > 0, 'M4 storage fails alone',
      `with storage stopped, the database ${dbStillUp ? 'kept answering' : 'went down WITH it'} and the API returned ${edgeStillUp}; ${handlesMissing.length} page(s) handle an image that will not load; storage ${backUp ? 'restarted cleanly' : 'did NOT come back'}`,
      !dbStillUp ? 'stopping the media layer took the database with it, so one dependency failing is the whole platform failing'
        : !backUp ? 'the storage container did not restart, and this probe has left the platform worse than it found it'
        : 'no page handles an image that will not load, so a storage outage shows a person broken pictures with no explanation');
  }
}

console.log(`${bad ? 'FAIL' : 'PASS'} last-mile - the assist admits what it is, paste is not fought, a release is felt, and the media layer can fail on its own`);
process.exitCode = bad ? 1 : 0;
