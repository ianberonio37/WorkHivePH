/**
 * CMMS Integration — Canonical Field Mappings
 * =============================================
 * Single source of truth for all status codes, work order type codes,
 * and field name mappings across every CMMS system WorkHive supports.
 *
 * IMPORT THIS — never define these locally in an edge function.
 * Any edge function that defines its own STATUS_MAP or TYPE_MAP will
 * diverge silently when codes are added here. validate_cmms_contracts.py
 * enforces this: it fails if a local copy is found alongside an import.
 *
 * Usage:
 *   import { STATUS_MAP, TYPE_MAP, DEFAULT_FIELD_MAPS } from "../_shared/mappings.ts";
 */

// ---------------------------------------------------------------------------
// Status code normalization
// Maps each CMMS system's raw status codes to WorkHive's canonical values.
// WorkHive canonical: "Open" | "Closed" | "Cancelled"
// ---------------------------------------------------------------------------

export const STATUS_MAP: Record<string, Record<string, string>> = {
  sap_pm: {
    I0001: "Open",
    I0002: "Open",
    I0008: "Open",
    I0045: "Closed",
    I0076: "Cancelled",
  },
  maximo: {
    WAPPR: "Open",
    APPR:  "Open",
    INPRG: "Open",
    COMP:  "Closed",
    CLOSE: "Closed",
    CAN:   "Cancelled",
  },
  generic: {
    open:      "Open",
    closed:    "Closed",
    cancelled: "Cancelled",
  },
};

// ---------------------------------------------------------------------------
// Work order type normalization
// Maps each CMMS system's order type codes to WorkHive maintenance types.
// WorkHive canonical: "Preventive Maintenance" | "Breakdown / Corrective"
// ---------------------------------------------------------------------------

export const TYPE_MAP: Record<string, Record<string, string>> = {
  sap_pm: {
    PM01: "Preventive Maintenance",
    PM02: "Breakdown / Corrective",
    PM03: "Breakdown / Corrective",
  },
  maximo: {
    PM: "Preventive Maintenance",
    CM: "Breakdown / Corrective",
    EM: "Breakdown / Corrective",
  },
  generic: {
    preventive: "Preventive Maintenance",
    corrective: "Breakdown / Corrective",
    emergency:  "Breakdown / Corrective",
    // 2026-10-12: the two other logbook types, so a generic inspection is not filed as a breakdown by the default
    inspection: "Inspection",
    project:    "Project Work",
    // the abbreviations real exports use (W4340: a 3,030-row event log typed PM / CM / EM) - 2026-10-12
    PM:         "Preventive Maintenance",
    CM:         "Breakdown / Corrective",
    EM:         "Breakdown / Corrective",
  },
};

// ---------------------------------------------------------------------------
// Default field maps per CMMS system
// These are the column names in each CMMS export that map to WorkHive fields.
// Stored in integration_configs.field_map — overridable per hive.
// ---------------------------------------------------------------------------

export interface FieldMap {
  external_id?:      string;
  machine?:          string;
  status?:           string;
  maintenance_type?: string;
  problem?:          string;
  root_cause?:       string;
  action?:           string;
  actual_hours?:     string;
  created_at?:       string;
  closed_at?:        string;
}

export const DEFAULT_FIELD_MAPS: Record<string, FieldMap> = {
  sap_pm: {
    external_id:      "AUFNR",
    machine:          "EQUNR",
    status:           "ISTAT",
    maintenance_type: "AUART",
    problem:          "LTXT",
    actual_hours:     "ARBEI",
    created_at:       "ERDAT",
    closed_at:        "RUCKMDAT",
  },
  maximo: {
    external_id:      "WONUM",
    machine:          "ASSETNUM",
    status:           "STATUS",
    maintenance_type: "WORKTYPE",
    problem:          "DESCRIPTION",
    actual_hours:     "ACTLABHRS",
    created_at:       "REPORTDATE",
    closed_at:        "ACTFINISH",
  },
  generic: {
    external_id:      "work_order_no",
    machine:          "asset_tag",
    status:           "status",
    maintenance_type: "type",
    problem:          "description",
    actual_hours:     "actual_hours",
    created_at:       "created_date",
    closed_at:        "closed_date",
  },
};

// ---------------------------------------------------------------------------
// WorkHive target tables per entity type
// ---------------------------------------------------------------------------

export const ENTITY_TABLE_MAP: Record<string, string> = {
  work_order:  "logbook",
  asset:       "assets",
  pm_schedule: "pm_assets",
  inventory:   "inventory_items",
};

// ---------------------------------------------------------------------------
// Normalisation helpers (used by both cmms-sync and cmms-webhook-receiver)
// ---------------------------------------------------------------------------

// ★THE DEFAULTS WERE UNREACHABLE (2026-10-12, UFAI edge walk W4331). These read `MAP[...] ?? raw ?? default` - but
// every caller passes a STRING (String(x ?? "")), and a string is never nullish, so the default never applied and an
// unmapped code went through RAW. For status that is fatal: external_sync.status is CHECK-constrained to the three
// values below, so one SAP "TECO" (technically complete - the commonest SAP completion code, not in the map) failed
// cmms-sync's whole 200-row batch upsert. For type it is quiet: a logbook row typed "" or "PM04" that no KPI counts.
// The webhook learned the status half on 2026-09-09 with a local clamp; cmms-sync never did. One clamp, here, for both.

/** the only values external_sync.status (a CHECK constraint) and the logbook accept */
export const CANONICAL_STATUSES = ["Open", "Closed", "Cancelled"];
/** the maintenance types the logbook, analytics and PM compliance count */
export const CANONICAL_TYPES = ["Preventive Maintenance", "Breakdown / Corrective", "Inspection", "Project Work"];
/** a raw status the map does not know that still says the work is finished (SAP TECO/CNF, Maximo CLOSE ...) */
export const CLOSING_HINT = /\b(TECO|CLSD|CLOSED?|COMP|COMPLETED?|FINISH(ED)?|DONE|CNF)\b/i;

const _canon = (list: string[], raw: string) => list.find((c) => c.toLowerCase() === raw.trim().toLowerCase());
// ★A CODE IS A CODE WHATEVER ITS CASE, AND A FIELD IS NEVER A PROTOTYPE KEY (2026-10-12, W4340). `MAP[sys]?.[raw]`
// was exact - "Preventive" and "pm" missed and fell to the default - and answered a function for "constructor".
// Own keys only, exact first, then case-folded; integrations.html's import does the same.
function _mapGet(map: Record<string, string> | undefined, raw: string): string | undefined {
  if (!map) return undefined;
  const r = raw.trim();
  if (Object.prototype.hasOwnProperty.call(map, r)) return map[r];
  const k = Object.keys(map).find((x) => x.toLowerCase() === r.toLowerCase());
  return k === undefined ? undefined : map[k];
}

/** a CMMS status code -> one of CANONICAL_STATUSES; never anything else. Keep the raw code beside it (status_raw). */
export function normaliseStatus(systemType: string, rawStatus: string): string {
  const raw = String(rawStatus ?? "");
  return _mapGet(STATUS_MAP[systemType], raw) ?? _canon(CANONICAL_STATUSES, raw) ?? (CLOSING_HINT.test(raw) ? "Closed" : "Open");
}

/** a CMMS order type -> one of CANONICAL_TYPES; an unknown or missing type is corrective work (the intended default).
 *  Keep the raw code beside it (type_raw). */
export function normaliseType(systemType: string, rawType: string): string {
  const raw = String(rawType ?? "");
  return _mapGet(TYPE_MAP[systemType], raw) ?? _canon(CANONICAL_TYPES, raw) ?? "Breakdown / Corrective";
}

// ★EVERY CONNECTOR A PERSON MADE SYNCED NOTHING (2026-10-12, W4331). cmms-sync read `config.field_map || {}`; the column
// defaults to '{}' and integrations.html never sets it, so a connector created on the page had an EMPTY map: every
// field read "", every work order had no external id, every row was dropped as unusable - and the run reported
// success with "Synced 0 records". Only the seeded mocks, which carry an explicit map, ever synced. The comment on
// DEFAULT_FIELD_MAPS says it plainly - "overridable per hive" - so the defaults ARE the map, and a hive's own entries
// override them one field at a time (a blank override is no override).
export function effectiveFieldMap(systemType: string, configured: unknown): FieldMap {
  const out: Record<string, string> = { ...(DEFAULT_FIELD_MAPS[systemType] || DEFAULT_FIELD_MAPS.generic) } as Record<string, string>;
  if (configured && typeof configured === "object" && !Array.isArray(configured)) {
    for (const [k, v] of Object.entries(configured as Record<string, unknown>)) {
      if (typeof v === "string" && v.trim()) out[k] = v.trim();
    }
  }
  return out as FieldMap;
}

// ---------------------------------------------------------------------------
// Reverse status map — WorkHive canonical status -> the CMMS's OWN status code,
// for cmms-push-completion (WorkHive -> CMMS). The push must send the code the
// external system expects (SAP I0045 / Maximo COMP), not the literal "Closed",
// or the CMMS rejects/ignores it. One canonical code per WorkHive status per
// system (inverting STATUS_MAP is ambiguous — several CMMS codes map to "Open").
// ---------------------------------------------------------------------------

export const REVERSE_STATUS_MAP: Record<string, Record<string, string>> = {
  sap_pm:  { Open: "I0001", Closed: "I0045", Cancelled: "I0076" },
  maximo:  { Open: "APPR",  Closed: "COMP",  Cancelled: "CAN"   },
  generic: { Open: "open",  Closed: "closed", Cancelled: "cancelled" },
};

/** WorkHive status -> the CMMS system's own status code (falls back to the input). */
export function toCmmsStatus(systemType: string, whStatus: string): string {
  return REVERSE_STATUS_MAP[systemType]?.[whStatus] ?? whStatus;
}

// ---------------------------------------------------------------------------
// Inventory (SAP MM / material master) field maps — MATNR is the dedup key.
// Used by cmms-sync when entity_type = "inventory". WorkHive inventory_items
// canonical: part_number, qty_on_hand, min_qty, name.
// ---------------------------------------------------------------------------

export interface InventoryFieldMap {
  part_number?: string;
  qty_on_hand?: string;
  min_qty?:     string;
  name?:        string;
}

export const DEFAULT_INVENTORY_FIELD_MAPS: Record<string, InventoryFieldMap> = {
  sap_pm:  { part_number: "MATNR", qty_on_hand: "MENGE", min_qty: "MINBE", name: "MAKTX" },
  maximo:  { part_number: "ITEMNUM", qty_on_hand: "CURBAL", min_qty: "MINLEVEL", name: "DESCRIPTION" },
  generic: { part_number: "part_number", qty_on_hand: "qty_on_hand", min_qty: "min_qty", name: "name" },
};
