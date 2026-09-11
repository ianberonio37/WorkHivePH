// browser_slot — this host has ONE usable browser slot, and every prover that opens one must take it.
//
// The platform suite runs gates CONCURRENTLY (its own timeout comments say so: "under gate concurrency they
// slow markedly"). On an 8GB box with ~0.2GB free that means two or three Playwright gates sharing the
// memory of one - and this session measured what that does to evidence: the same page read 4,995 characters
// alone and 658 beside another walk, the same journey read "5 own threads" and "no way onward at all", and a
// wedged docker engine froze a six-journey walk at zero CPU. Findings produced under that contention are
// findings about the contention.
//
// A lock file makes the overlap impossible rather than merely discouraged. Waiters queue; they do not race.
// The lock is the same one tools/drive_journey_wave.sh takes, so a manual drive and a suite gate cannot
// collide either. A stale lock (its holder gone) is ignored, so a killed prover never blocks the host.
//
//   import { takeBrowserSlot } from './browser_slot.mjs';
//   await takeBrowserSlot('content-ufai');      // resolves when the slot is ours; released on exit
import { readFileSync, writeFileSync, unlinkSync, existsSync, mkdirSync } from 'node:fs';

const LOCK = '.tmp/jn_drive.lock';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function holderAlive() {
  if (!existsSync(LOCK)) return false;
  const pid = Number((() => { try { return readFileSync(LOCK, 'utf8').trim(); } catch { return ''; } })());
  if (!pid) return false;
  try { process.kill(pid, 0); return true; } catch { return false; }   // ESRCH => stale lock
}

export async function takeBrowserSlot(label, { waitMs = 45 * 60 * 1000 } = {}) {
  try { mkdirSync('.tmp', { recursive: true }); } catch (e) { void e; }
  const t0 = Date.now();
  let waited = false;
  while (holderAlive()) {
    if (Date.now() - t0 > waitMs) {
      console.log(`  the browser slot never freed in ${Math.round(waitMs / 60000)} min - ${label} did not run`);
      process.exit(1);
    }
    if (!waited) { console.log(`  waiting for the browser slot (held by pid ${readFileSync(LOCK, 'utf8').trim()}) - ${label}`); waited = true; }
    await sleep(15000);
  }
  writeFileSync(LOCK, String(process.pid));
  if (waited) console.log(`  the slot is ours after ${Math.round((Date.now() - t0) / 1000)}s - ${label}`);
  const release = () => { try { if (existsSync(LOCK) && readFileSync(LOCK, 'utf8').trim() === String(process.pid)) unlinkSync(LOCK); } catch (e) { void e; } };
  process.on('exit', release);
  for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(sig, () => { release(); process.exit(130); });
  process.on('uncaughtException', (e) => { release(); throw e; });
  return release;
}
