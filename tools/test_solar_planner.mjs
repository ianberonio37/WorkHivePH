// test_solar_planner.mjs - the solar power-station planner's sizing chain against hand-worked cases (ENH-S, 2026-10-22).
// Each expected value below was worked by hand from the method in solar-planner.js's header (losses: inverter 93%,
// wiring 97%, battery round trip 95% LiFePO4 / 85% lead-acid; module derate 85%; inverter x1.25 and a 2x surge
// rating; the lowest of 12/24/48 V keeping both DC currents within 100 A; controller x1.25), not read back from the
// code - so a changed constant or a broken step fails here.
//   node tools/test_solar_planner.mjs        exit 0 = every case holds
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const P = require('../solar-planner.js');

let fails = 0, n = 0;
const near = (got, want, tol, what) => {
  n++;
  const ok = typeof want === 'number' ? Math.abs(got - want) <= tol : got === want;
  if (!ok) { fails++; console.log(`  FAIL ${what}: got ${got}, want ${want}`); }
};
const A = (name, watts, qty, hours, surge) => ({ name, watts, qty, hours, surge });

// 1. a small home: six LED bulbs, two fans, an inverter-type fridge, a TV, phones, a 1/2 HP pump - Manila, one day,
//    LiFePO4, 550 Wp panels, the rainy-season margin
{
  const r = P.plan({ appliances: [A('LED bulb', 9, 6, 6, 1), A('Electric fan', 60, 2, 8, 2), A('Refrigerator (inverter type)', 80, 1, 24, 1.5),
                                  A('LED TV', 50, 1, 5, 1), A('Phone charging', 10, 3, 3, 1), A('Water pump', 450, 1, 1, 3)],
                     psh: 4.5, days: 1, chemistry: 'lifepo4', panelWp: 550, margin: 1.25 });
  near(r.loadWh, 3994, 0.01, 'home: load Wh');
  near(r.peakW, 784, 0.01, 'home: running W');
  near(r.surgeW, 1684, 0.01, 'home: start W (pump +900)');
  near(r.surgeFrom, 'Water pump', 0, 'home: the start that sets the surge');
  near(r.inverter.sizeW, 1000, 0, 'home: inverter (980 W needed)');
  near(r.batteryOutWh, 4427.45, 0.05, 'home: battery out Wh');
  near(r.arrayInWh, 4660.47, 0.05, 'home: array in Wh');
  near(r.arrayWpNeed, 1523.03, 0.05, 'home: Wp needed');
  near(r.panels, 3, 0, 'home: panels');
  near(r.systemV, 24, 0, 'home: 24 V (12 V would need 172 A of charge current)');
  near(r.bankWh, 5534.31, 0.05, 'home: bank Wh');
  near(r.bankAh, 230.60, 0.05, 'home: bank Ah at 24 V');
  near(r.controller.amps, 85.94, 0.01, 'home: charge current');
  near(r.controller.sizeA, 100, 0, 'home: controller size');
  near(r.controller.count, 1, 0, 'home: one controller');
  near(r.cost.total, 135138.5, 1, 'home: cost');
}
// 2. one non-inverter fridge on lead-acid, two days, Davao, no margin, 400 Wp panels
{
  const r = P.plan({ appliances: [A('Refrigerator', 120, 1, 24, 3)], psh: 4.9, days: 2, chemistry: 'leadacid', panelWp: 400, margin: 1 });
  near(r.loadWh, 2880, 0.01, 'fridge: load Wh');
  near(r.surgeW, 360, 0.01, 'fridge: start W (3x)');
  near(r.inverter.sizeW, 300, 0, 'fridge: inverter (surge 360 needs a 2x rating of 180)');
  near(r.arrayWpNeed, 901.79, 0.05, 'fridge: Wp needed');
  near(r.panels, 3, 0, 'fridge: panels');
  near(r.systemV, 24, 0, 'fridge: 24 V');
  near(r.bankWh, 12770.2, 0.1, 'fridge: bank Wh (2 days / 50% DoD)');
  near(r.bankAh, 532.09, 0.05, 'fridge: bank Ah');
  near(r.controller.sizeA, 80, 0, 'fridge: controller (62.5 A)');
  near(r.cost.total, 134787.0, 1, 'fridge: cost');
}
// 3. two non-inverter aircons and ten bulbs: 48 V, and a charge current past one 100 A controller
{
  const r = P.plan({ appliances: [A('Aircon', 900, 2, 8, 3), A('LED bulb', 9, 10, 6, 1)], psh: 4.5, days: 1, chemistry: 'lifepo4', panelWp: 550, margin: 1.25 });
  near(r.loadWh, 14940, 0.01, 'aircon: load Wh');
  near(r.surgeW, 3690, 0.01, 'aircon: start W (one unit starts at a time)');
  near(r.inverter.sizeW, 3000, 0, 'aircon: inverter (2362.5 W needed)');
  near(r.panels, 11, 0, 'aircon: panels');
  near(r.systemV, 48, 0, 'aircon: 48 V');
  near(r.controller.count, 2, 0, 'aircon: two controllers (157.6 A)');
  near(r.bankAh, 431.29, 0.05, 'aircon: bank Ah at 48 V');
}
// 4. past the largest inverter: said, not sized
{
  const r = P.plan({ appliances: [A('Welder', 15000, 1, 1, 1)], psh: 4.5, days: 1 });
  near(r.inverter.tooBig, true, 0, 'big: inverter past 12,000 W is said, not sized');
}
// 5. nothing listed: zeros, no division by zero
{
  const r = P.plan({ appliances: [] });
  near(r.loadWh, 0, 0, 'empty: load'); near(r.panels, 0, 0, 'empty: panels'); near(r.cost.total, 0.0, 0.001, 'empty: cost');
}
// 6. a shared link carries the whole plan back, accents and all
{
  const st = { v: 1, a: [["Ref (Tita's) ñ", 80, 1, 24, 1.5]], loc: 2, psh: 4.2, days: 2, chem: 'leadacid', wp: 450, margin: 1, prices: { panelPerWp: 13 } };
  const back = P.decode(P.encode(st));
  near(JSON.stringify(back), JSON.stringify(st), 0, 'link: round trip');
  near(P.decode('not-a-plan'), null, 0, 'link: a broken link is no plan');
}
console.log(fails ? `FAIL - ${fails} of ${n} checks` : `PASS - ${n} checks: the sizing chain holds every hand-worked case`);
process.exit(fails ? 1 : 0);
