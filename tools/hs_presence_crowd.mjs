// hs_presence_crowd.mjs - Wave HS H1 "presence at thirty": put the thirty-member hive online.
//
// The presence rows on community.html and hive.html were only ever seen with one or two people online. This signs in the
// hive's active members (each as themselves, their own session and their own realtime connection) and has each join the
// two presence channels exactly as the pages do - keyed by display name, the payload carrying the account - and stay for
// --hold seconds, so a person walking the page with the MCP sees the row a full shift produces. --leave-after makes a
// third of them leave halfway, so "stays current as people come and go" can be read too.
//
//   node tools/hs_presence_crowd.mjs --exclude "Ernesto Villareal" --hold 300
//   node tools/hs_presence_crowd.mjs --count 10 --hold 120 --leave-after 60
//
// Local stack only (127.0.0.1:54321, the local publishable key); every member's password is the seed's.
import { execSync } from 'node:child_process';
import { createClient } from '@supabase/supabase-js';

const HIVE = '30303030-3030-4030-8030-303030303030';
const URL = 'http://127.0.0.1:54321';
const KEY = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';
const arg = (k, d) => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : d; };
const HOLD = Number(arg('--hold', '240')) * 1000;
const COUNT = Number(arg('--count', '29'));
const LEAVE = Number(arg('--leave-after', '0')) * 1000;
const EXCLUDE = new Set(String(arg('--exclude', '')).split(',').map((s) => s.trim()).filter(Boolean));
const CHANNELS = ['hive-community-presence:' + HIVE, 'hive-presence:' + HIVE];
// --listen-logbook (HS H3): each member also holds the board's feed channel - logbook INSERTs for the hive, as hive.html
// subscribes - and counts what arrives, so a shift's burst can be measured as thirty open boards receive it
const LISTEN = process.argv.includes('--listen-logbook');
const received = new Map();

const rows = execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -F "|" -c "select hm.worker_name, u.email, hm.auth_uid from hive_members hm join auth.users u on u.id = hm.auth_uid where hm.hive_id = '${HIVE}' and hm.status = 'active' order by hm.worker_name"`, { encoding: 'utf8' })
  .trim().split('\n').map((l) => l.split('|')).filter((r) => r.length === 3 && !EXCLUDE.has(r[0])).slice(0, COUNT);

const people = [];
for (const [name, email, uid] of rows) {
  const db = createClient(URL, KEY, { auth: { persistSession: false, autoRefreshToken: false } });
  const { error } = await db.auth.signInWithPassword({ email, password: 'test1234' });
  if (error) { console.log(`  ${name}: could not sign in (${error.message})`); continue; }
  db.realtime.setAuth((await db.auth.getSession()).data.session.access_token);
  const chans = [];
  for (const ch of CHANNELS) {
    const c = db.channel(ch, { config: { presence: { key: name } } });
    await new Promise((resolve) => {
      const t = setTimeout(resolve, 10000);
      c.subscribe(async (status) => {
        if (status === 'SUBSCRIBED') { await c.track({ worker_name: name, auth_uid: uid, at: Date.now() }); clearTimeout(t); resolve(); }
      });
    });
    chans.push(c);
  }
  if (LISTEN) {
    received.set(name, 0);
    const f = db.channel('hive-feed:' + HIVE)
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'logbook', filter: 'hive_id=eq.' + HIVE }, () => { received.set(name, received.get(name) + 1); });
    await new Promise((resolve) => { const t = setTimeout(resolve, 10000); f.subscribe((s) => { if (s === 'SUBSCRIBED') { clearTimeout(t); resolve(); } }); });
    chans.push(f);
  }
  people.push({ name, db, chans });
}
console.log(`online: ${people.length} members on ${CHANNELS.length} presence channels, holding ${HOLD / 1000}s`);

if (LEAVE && LEAVE < HOLD) {
  setTimeout(async () => {
    const leaving = people.splice(0, Math.floor(people.length / 3));
    for (const p of leaving) { for (const c of p.chans) await p.db.removeChannel(c); }
    console.log(`left: ${leaving.length} (${leaving.map((p) => p.name).join(', ')}); ${people.length} still online`);
  }, LEAVE);
}
setTimeout(async () => {
  if (LISTEN) {
    const v = [...received.values()];
    console.log(`logbook inserts received per member: min ${Math.min(...v)}, max ${Math.max(...v)}, total ${v.reduce((a, b) => a + b, 0)} across ${v.length}`);
  }
  for (const p of people) { for (const c of p.chans) await p.db.removeChannel(c); }
  console.log('all left');
  process.exit(0);
}, HOLD);
