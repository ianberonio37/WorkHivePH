// test_kpi_calc.mjs - the OEE and MTBF & MTTR calculators' arithmetic and advice (kpi-calc.js, ENH-P 2026-10-23).
//
// Held to the pages' own worked examples (tools/build_calc_pages.py CALC_DATA "oee-calculator" / "mtbf-calculator"):
// OEE 90% x 95% x 98% = 83.8%; MTBF 4,000 h / 5 failures = 800 h, MTTR 40 h / 5 = 8 h, availability 800/808 = 99.0%.
// And to what a person is told: the factor furthest below its world-class level, what reaching it would do to OEE,
// how many hours between failures one hour less repair is worth (M / (R - 1)), and the refusals of numbers that cannot
// be true.
//
//   node tools/test_kpi_calc.mjs [path/to/kpi-calc.js]
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const K = require(process.argv[2] ? path.resolve(process.argv[2]) : path.join(ROOT, 'kpi-calc.js'));

const fails = [];
const near = (name, got, want, tol = 1e-3) => { if (!(Math.abs(got - want) <= tol)) fails.push(`${name}: got ${got}, want ${want}`); };
const ok = (name, cond) => { if (!cond) fails.push(name); };

// OEE: the worked example, as percentages and as the shift records the calculator opens with
const p = K.oee({ mode: 'percent', a_pct: 90, p_pct: 95, q_pct: 98 });
near('OEE from 90/95/98 is 83.8%', p.oee, 0.8379);
const d = K.oee(K.DEF.oee);
near('the opening shift records give availability 90%', d.a, 0.9);
near('...performance 95%', d.p, 0.95);
near('...quality 98%', d.q, 0.98, 1e-3);
near('...and OEE 83.8%', d.oee, 0.838, 1e-3);
ok('quality is the biggest loss in the worked example (98% against 99.9%)', d.loss === 'q');
near('reaching 99.9% quality would lift OEE to 85.4%', d.lifted, 0.9 * 0.95 * 0.999, 1e-4);
ok('the advice names the rejects and the world-class level', /Quality is the biggest loss: 410 of 20,520 units were rejects/.test(d.advice) && /99\.9%/.test(d.advice));
const avail = K.oee({ mode: 'records', planned_min: 480, down_min: 144, ideal_s: 1, units: 19000, good: 18900 });
ok('a line that lost 144 of 480 minutes is told availability is the loss', avail.loss === 'a' && /144 of 480 planned minutes/.test(avail.advice));
const good = K.oee({ mode: 'percent', a_pct: 95, p_pct: 95, q_pct: 99.5 });
ok('an OEE at the 85% benchmark is told to hold it', /At or above the 85%/.test(good.advice));
ok('downtime longer than the planned time is refused', K.oee({ mode: 'records', planned_min: 60, down_min: 60, ideal_s: 1, units: 10, good: 10 }).errors.length === 1);
ok('more good units than units is refused', K.oee({ mode: 'records', planned_min: 60, down_min: 0, ideal_s: 1, units: 10, good: 11 }).errors.some((e) => /Good units/.test(e)));
ok('a percentage over 100 is refused', K.oee({ mode: 'percent', a_pct: 120, p_pct: 90, q_pct: 90 }).errors.length === 1);
const fast = K.oee({ mode: 'records', planned_min: 60, down_min: 0, ideal_s: 2, units: 3000, good: 3000 });
ok('a line faster than its ideal cycle time is computed and warned about', fast.p > 1 && fast.warnings.length === 1);

// MTBF & MTTR: the worked example
const m = K.mtbf(K.DEF.mtbf);
near('MTBF 4000/5 = 800 h', m.mtbf, 800);
near('MTTR 40/5 = 8 h', m.mttr, 8);
near('availability 800/808 = 99.0%', m.avail, 800 / 808);
near('an hour less repair is worth 800/7 = 114 h more between failures', m.hourWorth, 800 / 7);
ok('the advice says so in words', /gains as much availability as 114 more hours between failures/.test(m.advice));
// the equivalence itself: an hour off each repair and M/(R-1) more hours of running give the same availability
const M = 800, R = 8, X = M / (R - 1);
near('M/(R-1) is the exact equivalence', M / (M + R - 1), (M + X) / (M + X + R), 1e-12);
ok('no failures: MTBF is at least the operating hours, MTTR not yet', K.mtbf({ op_h: 2000, failures: 0, repair_h: 0 }).noFailures === true);
ok('a fraction of a failure is refused', K.mtbf({ op_h: 100, failures: 1.5, repair_h: 2 }).errors.length === 1);
ok('no repair time recorded is called out', /flatters the asset/.test(K.mtbf({ op_h: 100, failures: 2, repair_h: 0 }).advice));
ok('short repairs point at failing less', /failing less/.test(K.mtbf({ op_h: 1000, failures: 4, repair_h: 2 }).advice));

// a link round-trips a calculation
const t = K.encode({ v: 1, k: 'oee', mode: 'percent', a_pct: 90, p_pct: 95, q_pct: 98 });
ok('the link is URL-safe', /^[A-Za-z0-9_-]+$/.test(t));
ok('the link round-trips', JSON.stringify(K.decode(t)) === JSON.stringify({ v: 1, k: 'oee', mode: 'percent', a_pct: 90, p_pct: 95, q_pct: 98 }));
ok('a damaged link opens nothing', K.decode('!!') === null && K.decode('') === null);

if (fails.length) {
  console.log('FAIL kpi-calc - ' + fails.length + ' check(s):');
  for (const f of fails) console.log('  - ' + f);
  process.exit(1);
}
console.log('PASS kpi-calc - the OEE and MTBF & MTTR pages\' worked examples come out (83.8%; 800 h, 8 h, 99.0%), the advice names the '
  + 'biggest loss and what fixing it is worth, impossible numbers are refused, and a link round-trips');
