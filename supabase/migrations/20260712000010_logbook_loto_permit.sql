-- LOGBOOK arc Extension 3 (2026-07-12) — LOTO / Permit-to-Work as a FIRST-CLASS logbook field.
-- Before this, LOTO was only detectable by regex over free-text problem/category (shift-handover
-- lotoRx) — accidental, not deliberate, and not queryable. A maintenance logbook's isolation record
-- is safety- + compliance-critical (RA 11058 / DOLE DO 198-18 permit-to-work; ISO 45001 operational
-- control): a corrective/repair entry must be able to state, deliberately and queryably, that the
-- asset was locked/tagged out and under which permit.
--
-- Additive + non-destructive (safe to apply live): a boolean flag + an optional permit reference.
ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS loto_applied boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS permit_reference text;

COMMENT ON COLUMN public.logbook.loto_applied IS
  'Lock-Out/Tag-Out (energy isolation) was applied for this job — deliberate safety record, not regex-inferred.';
COMMENT ON COLUMN public.logbook.permit_reference IS
  'Permit-to-Work reference number/id under which the isolation was authorized (optional free text).';

-- Expose the new fields on the canonical view so shift-handover, the audit export, and any
-- consumer read LOTO deliberately (not via regex). Appended columns only (CREATE OR REPLACE safe).
CREATE OR REPLACE VIEW public.v_logbook_truth AS
 SELECT l.id, l.hive_id, l.worker_name, l.created_at, l.closed_at, l.date, l.status,
    l.maintenance_type, l.category, l.machine, l.problem, l.action, l.root_cause,
    l.failure_consequence, l.downtime_hours, l.production_output, l.parts_used, l.readings_json,
    l.knowledge, l.tasklist_acknowledged, l.tasklist_note, l.photo, l.pm_completion_id,
    l.wo_state, l.wo_assigned_to, l.asset_node_id,
    n.tag AS asset_tag, n.name AS asset_node_name, n.iso_class AS asset_iso_class,
    n.criticality AS asset_criticality, n.location AS asset_location,
    (l.maintenance_type ~* '(corrective|breakdown)'::text) AS is_corrective,
    l.loto_applied, l.permit_reference
   FROM logbook l
     LEFT JOIN asset_nodes n ON n.id = l.asset_node_id;
