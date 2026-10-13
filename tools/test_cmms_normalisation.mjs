/**
 * test_cmms_normalisation.mjs — the CMMS code tables CLAMP, and a connector's field map has DEFAULTS.
 *
 * WHY (2026-10-12, UFAI edge walk W4331). Three defects lived in _shared/mappings.ts's neighbourhood:
 *   - `MAP[...] ?? raw ?? default`: every caller passes a string, a string is never nullish, so the default never applied.
 *     An unmapped STATUS went to external_sync raw, where a CHECK allows only Open/Closed/Cancelled - one SAP "TECO"
 *     (technically complete, the commonest SAP completion code) failed cmms-sync's whole 200-row batch.
 *   - the same line for TYPE stored "" or "PM04" as a logbook maintenance type that no KPI counts.
 *   - cmms-sync read `config.field_map || {}`; the column defaults to '{}' and integrations.html never sets it, so every
 *     connector a person made mapped every field to "" and synced nothing, reporting success.
 *
 * This imports the REAL module (Node strips the TypeScript types; mappings.ts is pure) and pins every case, then
 * proves its own teeth: the pre-fix expressions, run on the same inputs, must fail the cases that motivated the fix.
 *
 *   node tools/test_cmms_normalisation.mjs
 */
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';

// the REAL source, loaded as an ES module: Node strips the types from a .mts file (a .ts under no "type":"module"
// package.json loads as CommonJS and fails on `export`), so the file is copied verbatim beside a temp name
const dir = mkdtempSync(join(tmpdir(), 'wh-mappings-'));
const copy = join(dir, 'mappings.mts');
writeFileSync(copy, readFileSync('supabase/functions/_shared/mappings.ts', 'utf8'));
let M;
try { M = await import(pathToFileURL(copy).href); } finally { rmSync(dir, { recursive: true, force: true }); }
const { normaliseStatus, normaliseType, effectiveFieldMap, STATUS_MAP, TYPE_MAP, DEFAULT_FIELD_MAPS } = M;

const LEGAL = ['Open', 'Closed', 'Cancelled'];
const TYPES = ['Preventive Maintenance', 'Breakdown / Corrective', 'Inspection', 'Project Work'];
let failed = 0;
const eq = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failed++; console.log(`  FAIL ${name}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); }
};

// status: mapped codes keep their mapping; anything else is clamped, and nothing outside the three ever comes back
eq('SAP I0045 maps to Closed', normaliseStatus('sap_pm', 'I0045'), 'Closed');
eq('SAP TECO (unmapped, closing) clamps to Closed', normaliseStatus('sap_pm', 'TECO'), 'Closed');
eq('SAP CNF (unmapped, closing) clamps to Closed', normaliseStatus('sap_pm', 'CNF'), 'Closed');
eq('Maximo WAPPR maps to Open', normaliseStatus('maximo', 'WAPPR'), 'Open');
eq('an unknown code clamps to Open', normaliseStatus('sap_pm', 'XYZ1'), 'Open');
eq('an empty status clamps to Open', normaliseStatus('generic', ''), 'Open');
eq('a canonical value passes, any case', normaliseStatus('generic', 'CANCELLED'), 'Cancelled');
for (const [sys, raw] of [['sap_pm', 'TECO'], ['maximo', 'HOLD'], ['generic', 'in-progress'], ['generic', ''], ['nope', 'x']]) {
  if (!LEGAL.includes(normaliseStatus(sys, raw))) { failed++; console.log(`  FAIL status ${sys}/${raw} left the legal set`); }
}

// type: unknown or missing is corrective work; the two other logbook types are recognised
eq('SAP PM01 maps to Preventive', normaliseType('sap_pm', 'PM01'), 'Preventive Maintenance');
eq('an empty type is corrective', normaliseType('generic', ''), 'Breakdown / Corrective');
eq('an unknown SAP type is corrective', normaliseType('sap_pm', 'PM04'), 'Breakdown / Corrective');
eq('a generic inspection is an Inspection', normaliseType('generic', 'inspection'), 'Inspection');
eq('a canonical type passes, any case', normaliseType('maximo', 'project work'), 'Project Work');
for (const raw of ['', 'PM09', 'whatever']) {
  if (!TYPES.includes(normaliseType('sap_pm', raw))) { failed++; console.log(`  FAIL type ${raw} left the canonical set`); }
}

// a code is a code whatever its case, and a field is never a prototype key (2026-10-12, W4340: a real 3,030-row export
// typed its work PM / CM / EM - 1,073 preventive jobs fell to the corrective default)
eq('generic PM is preventive', normaliseType('generic', 'PM'), 'Preventive Maintenance');
eq('generic pm (any case) is preventive', normaliseType('generic', 'pm'), 'Preventive Maintenance');
eq('generic EM is corrective', normaliseType('generic', 'EM'), 'Breakdown / Corrective');
eq('a capitalised generic word maps', normaliseType('generic', 'Preventive'), 'Preventive Maintenance');
eq('a lowercase SAP code maps', normaliseType('sap_pm', 'pm01'), 'Preventive Maintenance');
eq('a status code in another case maps', normaliseStatus('sap_pm', 'i0045'), 'Closed');
eq('"constructor" is not a type', normaliseType('generic', 'constructor'), 'Breakdown / Corrective');
eq('"toString" is not a status', normaliseStatus('maximo', 'toString'), 'Open');

// field map: '{}' (the column default, what the page saves) is the defaults; an override replaces one field only
eq('an empty field map is the defaults', effectiveFieldMap('generic', {}), DEFAULT_FIELD_MAPS.generic);
eq('a null field map is the defaults', effectiveFieldMap('maximo', null), DEFAULT_FIELD_MAPS.maximo);
const ov = effectiveFieldMap('generic', { status: 'state', machine: '  ' });
eq('an override replaces its field', ov.status, 'state');
eq('a blank override is no override', ov.machine, DEFAULT_FIELD_MAPS.generic.machine);
eq('other fields keep their default', ov.external_id, DEFAULT_FIELD_MAPS.generic.external_id);
eq('an unknown system falls back to the generic map', effectiveFieldMap('odoo', {}), DEFAULT_FIELD_MAPS.generic);

// TEETH: the pre-fix expressions on the inputs that motivated the fix
const oldStatus = (sys, raw) => STATUS_MAP[sys]?.[raw] ?? raw ?? 'Open';
const oldType = (sys, raw) => TYPE_MAP[sys]?.[raw] ?? raw ?? 'Breakdown / Corrective';
const oldMap = (cfg) => cfg || {};
const teeth = [
  ['old status lets TECO through raw', LEGAL.includes(oldStatus('sap_pm', 'TECO'))],
  ['old type stores an empty type', TYPES.includes(oldType('generic', ''))],
  ['old field map is empty for a page-made connector', !!oldMap({}).external_id],
  // the exact-key lookup of 2026-10-12 morning, before case-folding: 'Preventive' and 'pm' missed, 'constructor' hit
  ['exact lookup files a capitalised Preventive as preventive',
   ((TYPE_MAP.generic || {})['Preventive'] ?? null) === 'Preventive Maintenance'],
  ['exact lookup answers "constructor" with a type',
   TYPES.includes(((sys, raw) => TYPE_MAP[sys]?.[raw] ?? 'Breakdown / Corrective')('generic', 'constructor'))],
];
for (const [name, passed] of teeth) {
  if (passed) { failed++; console.log(`  FAIL teeth: ${name} - the old code would pass this test`); }
}

if (failed) { console.log(`FAIL cmms-normalisation: ${failed} check(s) failed`); process.exit(1); }
console.log('PASS cmms-normalisation: statuses clamp to Open/Closed/Cancelled, types to the four logbook types, an empty field map is the defaults, a code maps whatever its case and a field is never a prototype key - and the pre-fix code fails all five teeth');
