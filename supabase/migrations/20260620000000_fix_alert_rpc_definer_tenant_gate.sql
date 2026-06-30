-- Arc G (Data/DB UFAI) — keystone flywheel fix: cross-tenant IDOR in two DEFINER RPCs.
--
-- THE BUG (found by the Arc G per-DEFINER tenant-gate sweep, 2026-06-20):
--   acknowledge_alert(p_alert_id) and suppress_alert(p_alert_id, p_hours) are SECURITY DEFINER,
--   GRANTed EXECUTE to anon + authenticated, and UPDATE anomaly_alerts by a client-supplied,
--   ENUMERABLE bigint id with NO ownership/tenancy check. A SECURITY DEFINER function runs as its
--   owner and BYPASSES Row-Level Security; anomaly_alerts does NOT have FORCE ROW LEVEL SECURITY
--   (0 of 147 tables do), and its anomaly_alerts_hive_access policy only gates SELECT. So any
--   authenticated (or even anonymous) caller could acknowledge or SUPPRESS *any* hive's anomaly
--   alerts via PostgREST /rest/v1/rpc/... — e.g. suppress a victim hive's critical equipment-failure
--   alert so it never surfaces. Cross-tenant IDOR / BOLA. (The aggregate Arc E "DEFINER gated" check
--   missed it because it is a per-object, parameter-driven IDOR, not a search_path/orphan-RLS gap.)
--
-- THE FIX: self-gate each UPDATE by hive membership, mirroring the table's own RLS predicate
--   (EXISTS hive_members hm WHERE hm.hive_id = a.hive_id AND hm.auth_uid = auth.uid() AND active).
--   auth.uid() returns the CALLER's uid even inside a DEFINER function (it reads request.jwt.claims,
--   set per-request by PostgREST), so the gate correctly scopes to the caller. A non-member (or anon,
--   whose auth.uid() is NULL) matches 0 rows -> {ok:false, not authorized}. Also drop anon EXECUTE:
--   acknowledging/suppressing an alert is a member action, never an anonymous one (least privilege).
--   No app code calls these RPCs today (dormant), so this is pure hardening with zero breakage risk.

create or replace function public.acknowledge_alert(p_alert_id bigint)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
declare v_rows int;
begin
  update anomaly_alerts a
  set acknowledged_at = now()
  where a.id = p_alert_id
    and exists (
      select 1 from hive_members hm
      where hm.hive_id = a.hive_id and hm.auth_uid = auth.uid() and hm.status = 'active'
    );
  get diagnostics v_rows = row_count;
  if v_rows = 0 then
    return json_build_object('ok', false, 'error', 'not found or not authorized', 'alert_id', p_alert_id);
  end if;
  return json_build_object('ok', true, 'alert_id', p_alert_id);
end;
$function$;

create or replace function public.suppress_alert(p_alert_id bigint, p_hours integer default 24)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
declare v_rows int;
begin
  update anomaly_alerts a
  set suppressed_until = now() + (p_hours || ' hours')::interval
  where a.id = p_alert_id
    and exists (
      select 1 from hive_members hm
      where hm.hive_id = a.hive_id and hm.auth_uid = auth.uid() and hm.status = 'active'
    );
  get diagnostics v_rows = row_count;
  if v_rows = 0 then
    return json_build_object('ok', false, 'error', 'not found or not authorized', 'alert_id', p_alert_id);
  end if;
  return json_build_object('ok', true, 'alert_id', p_alert_id, 'suppressed_hours', p_hours);
end;
$function$;

-- Least privilege: these are member actions, not anonymous ones.
revoke execute on function public.acknowledge_alert(bigint) from anon;
revoke execute on function public.suppress_alert(bigint, integer) from anon;
