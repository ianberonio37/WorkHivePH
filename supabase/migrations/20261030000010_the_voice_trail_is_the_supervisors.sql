-- HS L1/L2 (2026-10-30, the hive at thirty - found walking audit-log.html's two trails): ai_audit_log is the voice trail
-- audit-log.html shows beside the hive's own audit log, and the page says "Only supervisors can open the audit log". Its
-- policies said otherwise:
--   * READ: `hive_id IN (hive_members of auth.uid())` - ANY membership row, of ANY status. A worker, and a member who had
--     been removed or had left, read the hive's whole voice trail through the API (who did what, by voice, and the
--     payload of each action). The cost log, the reply feedback and the agentic traces behind the same supervisor pages
--     were narrowed to the hive's active supervisor (or a platform admin) on 2026-10-14 (20261014000004); this trail was
--     left behind.
--   * WRITE: the same any-membership check, and worker_name taken as sent - a member (or a removed one) could write an
--     entry into the hive's compliance trail under a supervisor's name.
-- Now: the trail is read by the hive's ACTIVE supervisor or a platform admin; it is written by an ACTIVE member, and the
-- name on the entry is the writer's own membership name (bound server-side, as the platform's other trails are). The
-- only writer is voice-handler.js, signed in as the member who spoke; the only reader is audit-log.html, a supervisor's
-- page. A service-role write (auth.uid() null) is left as it is sent.

DROP POLICY IF EXISTS ai_audit_log_hive_select ON public.ai_audit_log;
CREATE POLICY ai_audit_log_hive_select ON public.ai_audit_log AS PERMISSIVE FOR SELECT TO authenticated
  USING ((( SELECT auth.uid() AS uid) IS NOT NULL) AND (is_platform_admin() OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
     FROM hive_members hm
    WHERE ((hm.hive_id = ai_audit_log.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text) AND (hm.role = 'supervisor'::text)))))));

DROP POLICY IF EXISTS ai_audit_log_hive_insert ON public.ai_audit_log;
CREATE POLICY ai_audit_log_hive_insert ON public.ai_audit_log AS PERMISSIVE FOR INSERT TO authenticated
  WITH CHECK ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1
     FROM hive_members hm
    WHERE ((hm.hive_id = ai_audit_log.hive_id) AND (hm.auth_uid = ( SELECT auth.uid() AS uid)) AND (hm.status = 'active'::text)))));

-- the name on a voice entry is the writer's own, never the one the request carried
CREATE OR REPLACE FUNCTION public.bind_ai_audit_log_actor()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
   WHERE hive_id = NEW.hive_id AND auth_uid = auth.uid() AND status = 'active'
   LIMIT 1;
  IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  RETURN NEW;
END;
$function$;
REVOKE ALL ON FUNCTION public.bind_ai_audit_log_actor() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_bind_ai_audit_log_actor ON public.ai_audit_log;
CREATE TRIGGER trg_bind_ai_audit_log_actor BEFORE INSERT ON public.ai_audit_log
  FOR EACH ROW EXECUTE FUNCTION public.bind_ai_audit_log_actor();
