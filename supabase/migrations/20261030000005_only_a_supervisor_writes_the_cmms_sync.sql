-- ANY MEMBER COULD REWRITE THE PLANT CMMS'S WORK ORDERS - THE SYNC TABLE THAT IS PUSHED TO SAP.
--
-- Found 2026-10-30 walking Wave HS lens L2 on integrations.html (the hive at thirty). The integrations page is a
-- supervisor's tool - a worker meets a "supervisor-only" wall - and every client write to external_sync lives on it:
-- the CMMS import (upsert), its rollback (delete) and the conflict resolution's "Keep WorkHive", which writes OUR status
-- onto the external work order "and SAP will receive the update on next push". The table's only policy was
-- external_sync_hive_rw, FOR ALL to every active member, so through the API any worker of the hive could change, add or
-- delete the plant CMMS's work orders - and the next push would carry it into SAP.
--
-- THE RULE: every member keeps READING the sync (asset-hub, logbook and plant-connections show CMMS references); only a
-- supervisor of the hive WRITES it. The CMMS edge functions (cmms-sync, cmms-webhook-receiver, cmms-push-completion) run
-- as the service role and are unaffected.

DROP POLICY IF EXISTS external_sync_hive_rw ON public.external_sync;
DROP POLICY IF EXISTS external_sync_member_read ON public.external_sync;
DROP POLICY IF EXISTS external_sync_supervisor_write ON public.external_sync;

CREATE POLICY external_sync_member_read ON public.external_sync
  AS PERMISSIVE FOR SELECT TO public
  USING ((SELECT auth.uid()) IS NOT NULL AND hive_id IN (SELECT public.user_hive_ids()));

CREATE POLICY external_sync_supervisor_write ON public.external_sync
  AS PERMISSIVE FOR ALL TO public
  USING ((SELECT auth.uid()) IS NOT NULL AND hive_id IN (SELECT public.user_supervisor_hive_ids()))
  WITH CHECK ((SELECT auth.uid()) IS NOT NULL AND hive_id IN (SELECT public.user_supervisor_hive_ids()));
