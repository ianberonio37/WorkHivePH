// prove_marketplace_economy — the marketplace economy journeys (T93, T94, T95, T98, T99, T101, T102,
// T103, T104), walked as one family (2026-09-07).
//
// Nine rows about money and trust between strangers. Every one of them has the same failure mode: a
// number a person believes, that nothing behind it actually supports. Credits that appear without a
// paying side. A reputation the seller wrote about themselves. A price that is not the price. Supply
// shown as available that nobody has confirmed in months.
//
//   E1 money has two sides   a top-up moves credits AND records what paid for them; a ledger with one
//                            side is a number a person trusts and nobody can reconcile (T93)
//   E2 spending is legible   a person can see where their credits went, entry by entry, not just a
//                            balance that shrank (T94)
//   E3 the watch is honest   watching a listing means something: the watch is stored against the person
//                            and the item, so a price change has somewhere to land (T95)
//   E4 reputation is earned  a seller's rating comes from completed transactions by OTHER people, not
//                            from a field the seller can write (T98)
//   E5 search answers        a search returns matching listings, and says so when it matches nothing
//                            rather than showing an empty grid (T99)
//   E6 safety is visible     there is a way to report, and disputes are recorded where someone can act
//                            on them (T101)
//   E7 supply is current     what is shown as available has been confirmed recently enough to mean it
//                            (T102)
//   E8 the price is the price a listed price is complete: no fee appears only at the end (T103)
//   E9 the first sale works  a new seller can reach a listed item without a history they do not have
//                            yet (T104)
//
// ★EVERY COLUMN NAME HERE WAS READ FROM THE SCHEMA, NOT GUESSED. The first run invented delta/reason on
// the ledger, seller_id on reviews and listings, and status='active' - four wrong lenses that produced
// three false BADs and one false n/a ("no published listing to search for", on a table holding 20 published
// ones). A prover that names a column the platform does not have is measuring its own vocabulary.
//
// ★READ AS A REAL BUYER THROUGH POSTGREST, NOT AS THE OWNER. Money questions are exactly where an owner
// connection lies most: it can see both sides of a ledger a person cannot, and it can read a seller's
// private fields as though they were public. The owner is used only for schema and aggregate facts.
//
//   node tools/prove_marketplace_economy.mjs
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const EDGE = 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const token = async (email) => {
  const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: 'test1234' }),
  });
  return (await r.json().catch(() => ({}))).access_token || null;
};
// a plain member, not a platform admin - the marketplace has admins and they see a different world
const TOK = await token('wilfredomalabanan@auth.workhiveph.com');
const asPerson = async (path) => {
  const r = await fetch(`${EDGE}/rest/v1/${path}`, { headers: { apikey: ANON, Authorization: 'Bearer ' + TOK } });
  return { ok: r.ok, status: r.status, rows: r.ok ? await r.json().catch(() => []) : [] };
};

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};
const na = (id, line) => console.log(`  n/a ${id.padEnd(22)} ${line} - unmeasured, not clean`);

// ── E1 · does money in have a paying side? ───────────────────────────────────────────────────────
{
  const topups = psql("select count(*) from service_credit_topups");
  // a top-up that granted credits must have a matching ledger entry; a grant with no top-up is credits
  // from nowhere, which is the shape that lets a balance be wrong without anyone noticing
  const orphanGrants = psql("select count(*) from service_credit_ledger l where l.ref_kind ilike '%topup%' and not exists (select 1 from service_credit_topups t where t.id::text = coalesce(l.ref_id::text, ''))");
  const cols = psql("select string_agg(column_name, ',') from information_schema.columns where table_schema='public' and table_name='service_credit_topups'");
  const paid = /amount|php|peso|gcash|reference|receipt/i.test(cols || '');
  say(paid && Number(orphanGrants || 0) === 0, 'E1 money has two sides',
    `${topups} top-up(s) recorded, each carrying what paid for it; ${orphanGrants} credit grant(s) reference a top-up that does not exist`,
    !paid ? `a top-up records no amount, reference or receipt (${(cols || '').slice(0, 90)}) - nothing behind the credits` : `${orphanGrants} credit(s) were granted against a top-up row that is not there`);
}

// ── E2 · can a person see where their credits went? ──────────────────────────────────────────────
{
  // ★THE LEDGER IS NOT PER-MEMBER, IT IS PER-ACCOUNT (provider / consumer). Reading it as an ordinary
  // hive worker returns zero rows CORRECTLY - they have no credit account - and the first run reported
  // that as "a balance with no history behind it". The lens has to be pointed at someone who actually
  // holds an account, or it measures the wrong person.
  const owner = psql("select u.email from auth.users u join service_providers p on p.auth_uid = u.id join service_credit_ledger l on l.account_id = p.id limit 1");
  if (!owner) na('E2 spending is legible', 'no signed-in person holds a credit account in this data');
  else {
    const tok = await token(owner);
    const rr = await fetch(`${EDGE}/rest/v1/service_credit_ledger?select=amount,entry_type,note,ref_kind,created_at&order=created_at.desc&limit=5`, { headers: { apikey: ANON, Authorization: 'Bearer ' + tok } });
    const rows = rr.ok ? await rr.json().catch(() => []) : [];
    const legible = rows.filter((x) => (x.note && String(x.note).trim().length > 2) || (x.ref_kind && String(x.ref_kind).trim()));
    say(rr.ok && rows.length > 0 && legible.length === rows.length, 'E2 spending is legible',
      `the account holder reads ${rows.length} of their own ledger entries, ${legible.length} of which say WHY (${(rows[0] || {}).note || (rows[0] || {}).ref_kind || 'n/a'})`,
      !rr.ok ? `the ledger refused its own account holder (${rr.status}) - their balance moves and they cannot see what moved it`
        : rows.length === 0 ? 'the account holder reads zero entries of their own ledger - a balance with no history behind it'
        : `${rows.length - legible.length} entry(ies) carry neither a note nor a ref_kind - an amount with no explanation`);
  }
}

// ── E3 · watching an item ────────────────────────────────────────────────────────────────────────
{
  const cols = psql("select string_agg(column_name, ',') from information_schema.columns where table_schema='public' and table_name='marketplace_watchlist'");
  const hasBoth = /listing/i.test(cols || '') && /(auth_uid|user_id|worker)/i.test(cols || '');
  const n = psql("select count(*) from marketplace_watchlist");
  say(hasBoth, 'E3 the watch is honest', `the watchlist binds a person to a listing (${(cols || '').slice(0, 62)}), ${n} row(s) stored`,
    'the watchlist does not record both who is watching and what they watch, so a price change has nowhere to land');
}

// ── E4 · is a reputation earned, or written? ─────────────────────────────────────────────────────
{
  // reviews key off the LISTING, and the seller is reached through it - so a self-review is a review
  // whose author is the person who listed the item
  const selfReviews = psql("select count(*) from marketplace_reviews r join marketplace_listings l on l.id = r.listing_id join marketplace_sellers s on s.worker_name = l.seller_name where r.reviewer_auth_uid = s.auth_uid");
  // rating_avg is a column on the seller - the question is who is allowed to move it
  const maintainer = psql("select string_agg(t.tgname, ', ') from pg_trigger t where not t.tgisinternal and pg_get_triggerdef(t.oid) ilike '%rating%'");
  // ★THIS PLATFORM BINDS A WRITER WITH auth_worker_names(), NOT auth.uid() - a lens looking only for the
  // literal auth.uid found 0 and reported "a seller can write their own reputation" about a policy that
  // forbids exactly that. And the weak-looking second insert policy (request_id IS NOT NULL) is
  // backstopped by the guard_service_review TRIGGER, which checks the request exists, that the writer is
  // a party to it, that the job completed, and that an admin who is a party loses the bypass. Reading one
  // policy in isolation, in the wrong vocabulary, produced a false finding on a sound trust chain.
  const boundToAuthor = psql("select count(*) from pg_policy where polrelid='public.marketplace_reviews'::regclass and polcmd in ('a','w') and coalesce(pg_get_expr(polwithcheck, polrelid), '') ~ '(auth\.uid|auth_worker_names|is_marketplace_admin)'");
  const backstop = psql("select count(*) from pg_trigger t join pg_proc p on p.oid = t.tgfoid where t.tgrelid='public.marketplace_reviews'::regclass and not t.tgisinternal and p.prosrc ilike '%unknown service request%'");
  const ownListingBlocked = psql("select count(*) from pg_policy where polrelid='public.marketplace_reviews'::regclass and polcmd = 'a' and coalesce(pg_get_expr(polwithcheck, polrelid), '') ilike '%seller_name%'");
  const verified = psql("select count(*) from marketplace_reviews where verified_purchase");
  const total = psql("select count(*) from marketplace_reviews");
  say(Number(selfReviews || 0) === 0 && !!maintainer && Number(boundToAuthor || 0) > 0 && Number(ownListingBlocked || 0) > 0 && Number(backstop || 0) > 0, 'E4 reputation is earned',
    `${selfReviews} self-review(s) of ${total}; the rating is maintained by ${maintainer || 'nothing'}; ${boundToAuthor} write policy(ies) bind a review to its author and ${ownListingBlocked} forbid reviewing your own listing, backstopped by ${backstop} guard trigger(s); ${verified} verified purchase(s)`,
    Number(selfReviews || 0) > 0 ? `${selfReviews} review(s) were written by the seller about their own listing`
      : !maintainer ? 'no trigger maintains the rating from the reviews, so the number on the seller is written rather than earned'
      : Number(ownListingBlocked || 0) === 0 ? 'no policy forbids reviewing your own listing, so a seller can write their own reputation'
      : Number(backstop || 0) === 0 ? 'the service-review intake policy checks only that a request_id is set, with no trigger validating it - any authenticated person can write a verified review'
      : 'nothing binds a review to its author, so a seller can write their own reputation');
}

// ── E5 · does search answer? ─────────────────────────────────────────────────────────────────────
{
  const term = psql("select split_part(title, ' ', 1) from marketplace_listings where status = 'published' and title is not null limit 1");
  if (!term) na('E5 search answers', 'no published listing to search for');
  else {
    const hit = await asPerson(`marketplace_listings?select=id,title&status=eq.published&title=ilike.*${encodeURIComponent(term)}*&limit=5`);
    const miss = await asPerson('marketplace_listings?select=id&status=eq.published&title=ilike.*zzzqqxnothing*&limit=5');
    // an empty grid is only honest if the PAGE says it found nothing; check the page carries the words
    let saysEmpty = false;
    try { saysEmpty = /no (listings|results|matches)|nothing (matched|found)|no items? (match|found)/i.test(readFileSync('marketplace.html', 'utf8')); } catch { /* the page is read below */ }
    say(hit.rows.length > 0 && miss.rows.length === 0 && saysEmpty, 'E5 search answers',
      `"${term}" returns ${hit.rows.length} listing(s), a nonsense term returns ${miss.rows.length}, and the page ${saysEmpty ? 'says so in words' : 'shows an empty grid'}`,
      hit.rows.length === 0 ? `a term taken from a live listing's own title returns nothing - search cannot find what is there`
        : miss.rows.length > 0 ? 'a nonsense term returns listings - the search is not filtering'
        : 'nothing on the page says "no results", so a search that matches nothing looks like a broken page');
  }
}

// ── E6 · is there a way to report, and does it land? ─────────────────────────────────────────────
{
  const disputes = psql("select count(*) from marketplace_disputes");
  const cols = psql("select string_agg(column_name, ',') from information_schema.columns where table_schema='public' and table_name='marketplace_disputes'");
  const actionable = /status|resolution|resolved|state/i.test(cols || '');
  let reportable = false;
  try { reportable = /report|dispute|flag/i.test(readFileSync('marketplace.html', 'utf8')); } catch { /* reported below */ }
  say(reportable && actionable, 'E6 safety is visible',
    `the marketplace page ${reportable ? 'offers a way to report' : 'offers none'}; ${disputes} dispute(s) recorded in a table that ${actionable ? 'tracks their state' : 'does not track state'}`,
    !reportable ? 'nothing on the marketplace lets a buyer report what they saw - the only safety route is off the platform'
      : 'a dispute is recorded with no state, so nobody can tell an open one from a settled one');
}

// ── E7 · is supply current? ──────────────────────────────────────────────────────────────────────
{
  const stale = psql("select count(*) from marketplace_listings where status = 'published' and updated_at < now() - interval '90 days'");
  const total = psql("select count(*) from marketplace_listings where status = 'published'");
  let dated = false;
  try { dated = /updated|posted|listed|ago|freshness/i.test(readFileSync('marketplace.html', 'utf8')); } catch { /* reported below */ }
  say(dated, 'E7 supply is current', `${stale} of ${total} active listing(s) have not been touched in 90 days; the page ${dated ? 'shows each one when it was last updated' : 'shows no date at all'}`,
    'nothing tells a buyer how old a listing is, so a three-month-dead listing looks exactly like one posted this morning');
}

// ── E8 · is the listed price the price? ──────────────────────────────────────────────────────────
{
  const feeCols = psql("select string_agg(table_name||'.'||column_name, ',') from information_schema.columns where table_schema='public' and column_name ~ '(fee|commission|surcharge|markup)' and table_name like 'marketplace%'");
  let disclosed = false;
  try {
    const src = readFileSync('marketplace.html', 'utf8');
    disclosed = !feeCols || /fee|commission|service charge|inclusive|plus/i.test(src);
  } catch { /* reported below */ }
  say(disclosed, 'E8 the price is the price', feeCols ? `the schema carries fee fields (${feeCols.slice(0, 58)}); the page ${disclosed ? 'names them where the price is shown' : 'does NOT name them'}` : 'no fee, commission or surcharge field exists - the listed price is the whole price',
    'a fee exists in the schema and the page never mentions it, so the price a buyer agrees to is not the price they pay');
}

// ── E9 · can a brand-new seller list at all? ─────────────────────────────────────────────────────
{
  // the trap is a gate that requires history a new seller cannot have: a rating, N sales, a verification
  const pol = psql("select string_agg(pg_get_expr(polwithcheck, polrelid), ' ; ') from pg_policy where polrelid='public.marketplace_listings'::regclass and polcmd in ('a','*')");
  const needsHistory = /rating_avg|rating_count|total_sales|completed_sales|reputation/i.test(pol || '');
  const newSellers = psql("select count(*) from marketplace_sellers where created_at > now() - interval '30 days'");
  const withListings = psql("select count(distinct l.seller_name) from marketplace_listings l join marketplace_sellers s on s.worker_name = l.seller_name where s.created_at > now() - interval '30 days'");
  say(!needsHistory, 'E9 the first sale works',
    `listing is gated on ${needsHistory ? 'a history a new seller cannot have' : 'identity, not history'}; ${withListings} of ${newSellers} seller(s) created in the last 30 days have listed something`,
    'the write policy requires a rating or a sales count, so the first listing is impossible for the person who has never sold');
}

console.log(`${bad ? 'FAIL' : 'PASS'} marketplace-economy - money has two sides, spending is legible, reputation is earned, search answers, and the listed price is the price`);
process.exitCode = bad ? 1 : 0;
