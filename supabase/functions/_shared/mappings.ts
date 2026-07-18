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

export function normaliseStatus(systemType: string, rawStatus: string): string {
  return STATUS_MAP[systemType]?.[rawStatus] ?? rawStatus ?? "Open";
}

export function normaliseType(systemType: string, rawType: string): string {
  return TYPE_MAP[systemType]?.[rawType] ?? rawType ?? "Breakdown / Corrective";
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
