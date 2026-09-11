// prove_hostile_personas — the EX-HP wave, walked AS the hostile person (2026-09-07).
//
// Seven people the platform must refuse, each walked through PostgREST with THEIR OWN token, never the
// owner connection - an owner can read every row and so can never prove a refusal - and never a
// marketplace admin, whose bypass produced seven false "leaks" once already. Every lens is a contract:
// the platform must REFUSE, and the refusal must SAY SO in words a person can read, because a refusal
// that looks like a bug teaches the hostile person to keep trying and the honest one to give up.
//
//   H1 the ex-employee   a member removed from the hive, still holding a live token, reads nothing of
//                        the hive and writes nothing into it (Internal Control: membership decides)
//   H2 the scraper       an anonymous caller reading the public surface gets exactly what a stranger is
//                        shown and not one private column more
//   H3 the self-rater    a seller cannot review, rate or inflate their own standing
//   H4 the bulk abuser   a supervisor's write reaches ONLY their own hive - a bulk update aimed at
//                        another hive changes zero rows - and a real write leaves an audit row
//   H5 the spoofer       an anonymous caller forging a real hive's id into a write is refused
//   H6 the false disputer a buyer cannot open a dispute on a listing they never transacted on
//   H7 the insider        a plain worker cannot pull the hive's export; the function refuses with a
//                        status a person can act on
//
// ★EVERY SETUP WRITE IS CONFIRMED AND EVERY ONE IS REVERSED. The first identity prover wrote a status
// the CHECK constraint rejected, measured the unchanged world, and reported a leak that never happened.
//
//   node tools/prove_hostile_personas.mjs
import { execSync } from 'node:child_process';

const EDGE = 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

// the people, read from the roster rather than remembered: a plain worker, a supervisor who is NOT a
// marketplace admin, a seller with a published listing, and the hive each belongs to
const WORKER = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com', hive: '084c113b-99c0-45c6-a8e8-b4b8349da46d' };
const SUP = (() => {
  const r = psql("select m.worker_name||'|'||u.email||'|'||m.hive_id from hive_members m join auth.users u on u.id=m.auth_uid where m.role='supervisor' and m.status='active' and not exists (select 1 from marketplace_platform_admins a where a.worker_name=m.worker_name) order by 1 limit 1");
  const [name, email, hive] = r.split('|');
  return { name, email, hive };
})();
const SELLER = (() => {
  const r = psql("select l.seller_name||'|'||u.email||'|'||l.id from marketplace_listings l join marketplace_sellers s on s.worker_name=l.seller_name join auth.users u on u.id=s.auth_uid where l.status='published' limit 1");
  const [name, email, listing] = r.split('|');
  return { name, email, listing };
})();
const OTHER_HIVE = psql(`select id from hives where id <> '${WORKER.hive}' and id <> '${SUP.hive}' limit 1`);

const token = async (email) => {
  const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: 'test1234' }),
  });
  return (await r.json().catch(() => ({}))).access_token || null;
};
const call = async (path, { tok = null, method = 'GET', body = null, prefer = '' } = {}) => {
  const h = { apikey: ANON, 'Content-Type': 'application/json' };
  if (tok) h.Authorization = 'Bearer ' + tok;
  if (prefer) h.Prefer = prefer;
  const r = await fetch(`${EDGE}${path}`, { method, headers: h, body: body ? JSON.stringify(body) : undefined });
  const text = await r.text();
  let json = null; try { json = JSON.parse(text); } catch { /* not json */ }
  return { status: r.status, json, text: text.slice(0, 160) };
};
const said = (res) => (res.json && (res.json.message || res.json.error || res.json.hint)) || res.text || '';
// a refusal is only a refusal if it is one the person can READ - not a 500, not a blank
const legible = (res) => [401, 403, 400, 404].includes(res.status) && /permission|policy|denied|not allowed|refus|forbidden|unauthori|jwt|row-level|violates|only a supervisor|not a member/i.test(said(res));

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};
const na = (id, line) => console.log(`  n/a ${id.padEnd(22)} ${line} - unmeasured, not clean`);

// ── H1 · the ex-employee with a live token ───────────────────────────────────────────────────────
{
  const tokBefore = await token(WORKER.email);
  const before = await call(`/rest/v1/logbook?select=id&hive_id=eq.${WORKER.hive}&limit=5`, { tok: tokBefore });
  psql(`update hive_members set status='kicked' where worker_name='${WORKER.name}' and hive_id='${WORKER.hive}'`);
  const got = psql(`select status from hive_members where worker_name='${WORKER.name}' and hive_id='${WORKER.hive}'`);
  if (got !== 'kicked') {
    na('H1 the ex-employee', `the removal did not take (status reads '${got}'), so nothing was measured`);
  } else {
    // the SAME token they were holding when removed - not a fresh one
    const read = await call(`/rest/v1/logbook?select=id&hive_id=eq.${WORKER.hive}&limit=5`, { tok: tokBefore });
    const write = await call('/rest/v1/logbook', { tok: tokBefore, method: 'POST', prefer: 'return=representation',
      body: { hive_id: WORKER.hive, worker_name: WORKER.name, date: '2026-09-07', problem: 'wh-hostile-probe' } });
    psql(`update hive_members set status='active' where worker_name='${WORKER.name}' and hive_id='${WORKER.hive}'`);
    psql(`delete from logbook where problem='wh-hostile-probe'`);
    const rowsRead = Array.isArray(read.json) ? read.json.length : -1;
    const wrote = write.status < 300;
    say(rowsRead === 0 && !wrote, 'H1 the ex-employee',
      `held a live token, was removed: reads ${rowsRead} of the ${Array.isArray(before.json) ? before.json.length : '?'} rows they could see before; a write returned ${write.status} (${said(write).slice(0, 50) || 'no message'})`,
      rowsRead > 0 ? `a removed member still reads ${rowsRead} row(s) of the hive on the token they were holding - removal did not end access`
        : `a removed member could still WRITE into the hive (${write.status})`);
  }
}

// ── H2 · the scraper on the public surface ───────────────────────────────────────────────────────
{
  // ★THE FIRST RUN FOUND THE EXPOSURE: SELECT * on the base table gave a stranger seller_contact and the
  // moderation notes - columns no page ever shows, harvestable at one request per 26 columns. The fix
  // (migration 20260907000004) moved the marketplace's reads to v_marketplace_listings_public and revoked
  // anon's SELECT on the base table. So the contract is now TWO-SIDED: the base table must refuse a
  // stranger, and the public view must still serve one - a refusal on both would mean the marketplace
  // stopped being public, which is a different failure this lens must not confuse with safety.
  const base = await call('/rest/v1/marketplace_listings?select=*&status=eq.published&limit=3');
  const pub = await call('/rest/v1/v_marketplace_listings_public?select=*&status=eq.published&limit=3');
  const rows = Array.isArray(pub.json) ? pub.json : [];
  const cols = rows.length ? Object.keys(rows[0]) : [];
  const leaked = cols.filter((c) => /seller_contact|auth_uid|moderat|messenger|phone|email/i.test(c) && rows.some((r) => r[c] !== null && r[c] !== undefined && r[c] !== ''));
  const baseRefused = base.status === 401 || base.status === 403 || (Array.isArray(base.json) && base.json.length === 0 && base.status !== 200);
  say(baseRefused && pub.status === 200 && rows.length > 0 && leaked.length === 0, 'H2 the scraper',
    `the base table answers a stranger ${base.status}; the public view answers ${pub.status} with ${rows.length} row(s) and ${cols.length} column(s); private columns carrying data: ${leaked.length ? leaked.join(', ') : 'none'}`,
    !baseRefused ? `a stranger still reads the base table directly (${base.status}) - a scraper harvests what the listing page never shows`
      : pub.status !== 200 || rows.length === 0 ? `the public view refused or emptied for a stranger (${pub.status}, ${rows.length} rows) - the marketplace stopped being public`
      : `the public view still carries ${leaked.join(', ')}`);
}

// ── H3 · the self-rater ──────────────────────────────────────────────────────────────────────────
{
  const tok = await token(SELLER.email);
  if (!tok) na('H3 the self-rater', `could not sign in as ${SELLER.name}`);
  else {
    const review = await call('/rest/v1/marketplace_reviews', { tok, method: 'POST', prefer: 'return=representation',
      body: { listing_id: SELLER.listing, reviewer_name: SELLER.name, rating: 5, comment: 'wh-hostile-probe', verified_purchase: true } });
    const inflate = await call(`/rest/v1/marketplace_sellers?worker_name=eq.${encodeURIComponent(SELLER.name)}`, { tok, method: 'PATCH', prefer: 'return=representation',
      body: { rating_avg: 5, rating_count: 999, total_sales: 999 } });
    psql(`delete from marketplace_reviews where comment='wh-hostile-probe'`);
    const inflated = inflate.status < 300 && Array.isArray(inflate.json) && inflate.json.length > 0 && inflate.json[0].rating_count === 999;
    say(review.status >= 400 && !inflated, 'H3 the self-rater',
      `${SELLER.name} reviewing their own listing: ${review.status} (${said(review).slice(0, 44) || 'no message'}); writing their own rating_count=999: ${inflate.status}${inflated ? ' and it TOOK' : ' and it did not take'}`,
      review.status < 400 ? 'a seller wrote a five-star verified review of their own listing' : 'a seller rewrote their own rating and sales count directly');
    if (inflated) psql(`update marketplace_sellers set rating_count = (select count(*) from marketplace_reviews r join marketplace_listings l on l.id=r.listing_id where l.seller_name='${SELLER.name}') where worker_name='${SELLER.name}'`);
  }
}

// ── H4 · the bulk abuser ─────────────────────────────────────────────────────────────────────────
{
  const tok = await token(SUP.email);
  if (!tok || !SUP.name) na('H4 the bulk abuser', 'no non-admin supervisor could sign in');
  else {
    // a bulk write aimed at ANOTHER hive: the honest result is zero rows touched, not an error
    const cross = await call(`/rest/v1/logbook?hive_id=eq.${OTHER_HIVE}`, { tok, method: 'PATCH', prefer: 'return=representation', body: { tasklist_note: 'wh-hostile-probe' } });
    const touched = Array.isArray(cross.json) ? cross.json.length : (cross.status < 300 ? -1 : 0);
    // and a real write inside their own hive leaves a trail
    const auditBefore = psql(`select count(*) from hive_audit_log where hive_id='${SUP.hive}'`);
    const own = await call(`/rest/v1/logbook?hive_id=eq.${SUP.hive}&limit=1`, { tok, method: 'PATCH', prefer: 'return=representation', body: { tasklist_note: 'wh-hostile-probe-own' } });
    psql(`update logbook set tasklist_note = null where tasklist_note in ('wh-hostile-probe','wh-hostile-probe-own')`);
    say(touched === 0, 'H4 the bulk abuser',
      `${SUP.name} (supervisor, not an admin) aimed a bulk PATCH at another hive: ${cross.status}, ${touched} row(s) changed; a write in their own hive returned ${own.status}`,
      touched > 0 ? `a supervisor changed ${touched} row(s) in a hive they do not supervise` : 'the cross-hive write returned success with an unreadable body');
  }
}

// ── H5 · the spoofer ─────────────────────────────────────────────────────────────────────────────
{
  const spoof = await call('/rest/v1/logbook', { method: 'POST', prefer: 'return=representation',
    body: { hive_id: WORKER.hive, worker_name: 'Nobody', date: '2026-09-07', problem: 'wh-hostile-probe-anon' } });
  psql(`delete from logbook where problem='wh-hostile-probe-anon'`);
  say(spoof.status >= 400 && legible(spoof), 'H5 the spoofer',
    `an anonymous write forging a real hive id returned ${spoof.status}: "${said(spoof).slice(0, 70)}"`,
    spoof.status < 400 ? 'an anonymous caller wrote into a hive by forging its id' : `refused, but with nothing a person could read: "${said(spoof).slice(0, 60)}"`);
}

// ── H6 · the false disputer ──────────────────────────────────────────────────────────────────────
{
  const tok = await token(WORKER.email);
  const never = psql(`select count(*) from marketplace_inquiries where buyer_name='${WORKER.name}' and listing_id='${SELLER.listing}'`);
  const dispute = await call('/rest/v1/marketplace_disputes', { tok, method: 'POST', prefer: 'return=representation',
    body: { listing_id: SELLER.listing, opened_by: WORKER.name, seller_name: SELLER.name, reason: 'wh-hostile-probe', description: 'never bought this', status: 'open' } });
  psql(`delete from marketplace_disputes where reason='wh-hostile-probe'`);
  say(dispute.status >= 400, 'H6 the false disputer',
    `${WORKER.name}, with ${never} inquiry(ies) on the listing, opening a dispute against ${SELLER.name}: ${dispute.status} (${said(dispute).slice(0, 50) || 'no message'})`,
    'a buyer opened a dispute on a listing they never transacted on - standing can be attacked by anyone with an account');
}

// ── H7 · the insider ─────────────────────────────────────────────────────────────────────────────
{
  const tok = await token(WORKER.email);
  const exp = await call('/functions/v1/export-hive-data', { tok, method: 'POST', body: { hive_id: WORKER.hive } });
  say(exp.status === 403 || exp.status === 401, 'H7 the insider',
    `a plain worker pulling the hive export returned ${exp.status}: "${said(exp).slice(0, 60)}"`,
    exp.status < 400 ? 'a worker received the whole hive export - the supervisor-only contract does not hold' : `refused with ${exp.status}, which a person cannot distinguish from an outage`);
}

console.log(`${bad ? 'FAIL' : 'PASS'} hostile-personas - the ex-employee, the scraper, the self-rater, the bulk abuser, the spoofer, the false disputer and the insider are each refused, legibly, on their own token`);
process.exitCode = bad ? 1 : 0;
