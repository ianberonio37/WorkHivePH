-- Companion UX bug (found live in the voice deepwalk, 2026-07-20): fetch_active_alerts(p_hive_id) FAILs at
-- runtime with SQLSTATE 42804 "Returned type numeric does not match expected type real in column 6"
-- (deviation_percent). anomaly_alerts.deviation_percent is numeric, but the RPC's RETURNS TABLE declares it
-- real, so EVERY call errors and the companion silently gets NO proactive alerts ("NO ALERTS FOUND") — the
-- proactive-alert surface is dead. Minimal fix: cast the source column to real so the returned type matches
-- the declared signature (keeps the real return type its JS consumer already reads; no signature change).

CREATE OR REPLACE FUNCTION public.fetch_active_alerts(p_hive_id uuid)
 RETURNS TABLE(alert_id bigint, alert_type text, severity text, description text, action_suggested text, deviation_percent real, detected_at timestamp with time zone)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.user_can_access_hive(p_hive_id) then return; end if;
  return query
  select aa.id, aa.alert_type, aa.severity, aa.description, aa.action_suggested,
         aa.deviation_percent::real,          -- FIX: source is numeric; declared return is real
         aa.detected_at
  from anomaly_alerts aa
  where aa.hive_id = p_hive_id
    and (aa.suppressed_until is null or aa.suppressed_until < now())
    and aa.acknowledged_at is null
  order by case when aa.severity = 'critical' then 1 when aa.severity = 'high' then 2 when aa.severity = 'medium' then 3 else 4 end,
           aa.detected_at desc
  limit 10;
end;
$function$;
