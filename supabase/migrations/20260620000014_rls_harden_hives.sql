-- Arc G G2 — scope the hives table to members (was open-read; exposed every hive's invite_code).
--
-- hives had always-true read policies (allow_anon_all, hives_read, hives_open_read, anon_select_hives), so
-- any client could enumerate every hive's name + INVITE_CODE (and the secured-against-now join still gates
-- membership, but code enumeration is undesirable). It is also the root of the only truth-view that stayed
-- cross-hive after the security_invoker fix: v_insurance_bridge_truth joins hives, so the open hives read
-- leaked other hives through that view.
--
-- THE FIX: members read their own hives (id IN user_hive_ids()); the join-by-code flow (a NON-member looking
-- up a hive to join) uses a SECURITY DEFINER `find_hive_by_code(text)` that returns only id/name/created_by
-- for an EXACT invite_code (no enumeration). App co-change: hive.html join switches from the view-by-code
-- read to the RPC. Reuses public.user_hive_ids().
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): member reads own hive via v_hives_truth (1) + other hidden (0) +
-- v_insurance_bridge_truth cross-hive now 0 + find_hive_by_code(valid code) returns the hive (join works) +
-- anon sees 0 hives.

create or replace function public.find_hive_by_code(p_code text)
returns table(id uuid, name text, created_by text)
language sql
security definer
set search_path = pg_catalog, public
stable
as $function$
  select h.id, h.name, h.created_by from hives h where h.invite_code = p_code
$function$;

grant execute on function public.find_hive_by_code(text) to anon, authenticated;

drop policy if exists allow_anon_all    on public.hives;
drop policy if exists hives_read         on public.hives;
drop policy if exists hives_open_read    on public.hives;
drop policy if exists anon_select_hives  on public.hives;
drop policy if exists hives_read_member  on public.hives;
create policy hives_read_member on public.hives for select
  using (auth.uid() is not null and id in (select public.user_hive_ids()));
