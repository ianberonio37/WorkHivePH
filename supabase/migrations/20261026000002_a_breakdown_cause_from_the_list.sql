-- ============================================================================
-- A BREAKDOWN CAUSE THE ANALYTICS CAN GROUP (BRH.10 AI, BRH552-559, 2026-10-26)
--
-- The logbook form offers 12 causes. Three writers stored the cause as said
-- instead: the voice entry (voice-logbook-entry asked the model for "diagnosed
-- cause if mentioned"), the CSV import (integrations.html) and the CMMS sync
-- (cmms-sync). Every reader groups by the exact text - repeat failures
-- (descriptive.py, machine x cause), the Pareto (diagnostic.py), the
-- failure-signature scan's repeat_failure (lower-cased text) and multi_symptom
-- (distinct texts), ai-orchestrator's patterns, batch-risk-scoring's repeats -
-- so a reworded cause hid a real repeat and one cause said three ways raised a
-- false multi-symptom alert.
--
-- The fix keeps what was said beside a cause from the list, at the one place
-- every writer passes through:
--   root_cause       one of the form's 12 causes (or empty when none was given)
--   root_cause_note  the cause in the words it was given, when they were not
--                    already a listed cause
-- A cause matching the list in any case is stored in the list's spelling. Any
-- other text moves to root_cause_note and root_cause takes the listed cause its
-- words name (wh_listed_root_cause), or 'Unknown' when they name none - never
-- a guess dressed as a finding.
-- ============================================================================

ALTER TABLE public.logbook ADD COLUMN IF NOT EXISTS root_cause_note text;
COMMENT ON COLUMN public.logbook.root_cause_note IS
  'The breakdown cause in the words it was given (voice, import, CMMS sync), kept beside root_cause, which always holds one of the form''s 12 causes. BRH.10 AI, 20261026000002.';

-- The form's 12 causes, in the form's own spelling. A cause in other words is mapped by the mechanism or cause it
-- names, in this order: a lubrication word outranks the wear it led to, contamination outranks a blockage, and the
-- human and design causes come last, so "a lubrication interval was missed" files as Lubrication Failure.
CREATE OR REPLACE FUNCTION public.wh_listed_root_cause(p_said text)
 RETURNS text
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO 'pg_catalog'
AS $function$
  WITH s AS (SELECT btrim(coalesce(p_said, '')) AS t),
  listed(cause) AS (VALUES ('Wear'), ('Lubrication Failure'), ('Vibration / Fatigue'), ('Misalignment'), ('Overload'),
                           ('Contamination / Dirt'), ('Corrosion'), ('Electrical Fault'), ('Mechanical Damage'),
                           ('Human Error'), ('Design Issue'), ('Unknown'))
  SELECT CASE
    WHEN (SELECT t FROM s) = '' THEN NULL
    WHEN EXISTS (SELECT 1 FROM listed, s WHERE lower(cause) = lower(t))
      THEN (SELECT cause FROM listed, s WHERE lower(cause) = lower(t))
    WHEN (SELECT t FROM s) ~* '(lubric|grease|greasing|oil (level|starv|degrad|leak)|low oil|no oil|ran dry|run dry|running dry|dry[- ]run)'
      THEN 'Lubrication Failure'
    WHEN (SELECT t FROM s) ~* '(contamin|dirt|dust|debris|clog|foul|scale|sludge|particle|ingress|strainer|blocked)'
      THEN 'Contamination / Dirt'
    WHEN (SELECT t FROM s) ~* '(corro|rust|pitting|oxidi)'
      THEN 'Corrosion'
    WHEN (SELECT t FROM s) ~* '(electric|short[- ]circuit|insulation|winding|contactor|relay|fuse|breaker trip|wiring|voltage|phase loss|earth fault|ground fault|motor burn)'
      THEN 'Electrical Fault'
    WHEN (SELECT t FROM s) ~* '(misalign|alignment|soft foot)'
      THEN 'Misalignment'
    WHEN (SELECT t FROM s) ~* '(vibrat|fatigue|crack|resonan|unbalanc|imbalanc|loosen)'
      THEN 'Vibration / Fatigue'
    WHEN (SELECT t FROM s) ~* '(overload|over[- ]?current|over[- ]?pressur|excessive load|jammed|jam\M)'
      THEN 'Overload'
    WHEN (SELECT t FROM s) ~* '(broken|impact|bent|damage|snapped|dent|scored|scoring|stuck|seized)'
      THEN 'Mechanical Damage'
    WHEN (SELECT t FROM s) ~* '(wear|worn|aged|ageing|aging|degrad|erod|erosion|harden|service life|end of life|deteriorat|abras)'
      THEN 'Wear'
    WHEN (SELECT t FROM s) ~* '(operator|human|wrong|incorrect|improper|missed|forgot|not followed|started with|left (open|closed))'
      THEN 'Human Error'
    WHEN (SELECT t FROM s) ~* '(design|undersized|oversized|specification)'
      THEN 'Design Issue'
    ELSE 'Unknown'
  END
$function$;

CREATE OR REPLACE FUNCTION public.logbook_keep_said_cause()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_listed text;
BEGIN
  IF NEW.root_cause IS NULL OR btrim(NEW.root_cause) = '' THEN
    RETURN NEW;
  END IF;
  v_listed := public.wh_listed_root_cause(NEW.root_cause);
  IF NEW.root_cause = v_listed THEN
    RETURN NEW;
  END IF;
  IF lower(btrim(NEW.root_cause)) <> lower(v_listed) AND coalesce(btrim(NEW.root_cause_note), '') = '' THEN
    NEW.root_cause_note := left(btrim(NEW.root_cause), 500);   -- what was said, kept
  END IF;
  NEW.root_cause := v_listed;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_logbook_listed_cause ON public.logbook;
CREATE TRIGGER trg_logbook_listed_cause
  BEFORE INSERT OR UPDATE OF root_cause ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.logbook_keep_said_cause();

-- The causes already stored in other words (0 in production on 2026-10-26; locally the AI eval bench's voice runs).
-- Re-filing a closed entry's cause onto the list is the system's, not a person's amendment, so the post-close audit
-- does not record it.
ALTER TABLE public.logbook DISABLE TRIGGER trg_logbook_post_close_audit;
UPDATE public.logbook
   SET root_cause = root_cause
 WHERE root_cause IS NOT NULL AND btrim(root_cause) <> ''
   AND root_cause IS DISTINCT FROM public.wh_listed_root_cause(root_cause);
ALTER TABLE public.logbook ENABLE TRIGGER trg_logbook_post_close_audit;
