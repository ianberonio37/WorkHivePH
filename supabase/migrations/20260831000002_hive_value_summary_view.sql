-- T188 (the renewal moment: "is this worth it?") — the whole-platform value summary, computed
-- ENTIRELY from existing tables per the approved default: no new table, no new collection, just a
-- saved query over what the hive already did. Three honest counts a renewing owner can check by hand:
--   • pms_kept        — preventive maintenance actually completed (status 'done'; a 'skipped' PM is
--                        NOT kept, which is why the count excludes it — verified 2026-08-31 against
--                        real data after a draft that read 'completed' returned 0 for every hive).
--   • faults_resolved — logbook faults closed (status 'Closed').
--   • knowledge_written — fault_knowledge rows the hive captured from those faults.
--
-- security_invoker so the row a caller sees is scoped by the SAME RLS as the base tables (the
-- platform's v_*_truth view discipline); a renewing owner sees only their own hive's value.
create or replace view public.v_hive_value_summary
with (security_invoker = true) as
select
  h.id   as hive_id,
  h.name as hive_name,
  (select count(*) from public.pm_completions pc
     where pc.hive_id = h.id and pc.status = 'done')          as pms_kept,
  (select count(*) from public.logbook lb
     where lb.hive_id = h.id and lb.status = 'Closed')        as faults_resolved,
  (select count(*) from public.fault_knowledge fk
     where fk.hive_id = h.id)                                 as knowledge_written
from public.hives h;

comment on view public.v_hive_value_summary is
  'T188 value summary — pms_kept / faults_resolved / knowledge_written per hive, from existing '
  'tables only. security_invoker: RLS-scoped to the caller. Verified against live data 2026-08-31.';

-- Anchor the Engine view in the canonical registry (canonical-anchor gate: every v_* view a migration
-- adds must be registered in canonical_sources or it is a silo). Idempotent on the (domain) PK.
insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('v_hive_value_summary', 'view', 'v_hive_value_summary', 'analytics-engineer', 'on_demand',
   '{"derived_from": ["pm_completions", "logbook", "fault_knowledge", "hives"], "security_invoker": true}'::jsonb,
   'T188 renewal-moment value summary — pms_kept (pm_completions done) / faults_resolved (logbook Closed) '
   '/ knowledge_written (fault_knowledge) per hive, computed from existing tables only, RLS-scoped via '
   'security_invoker so a renewing owner sees only their own hive.')
on conflict (domain) do update set
  source_kind = excluded.source_kind,
  source_name = excluded.source_name,
  owner_skill = excluded.owner_skill,
  freshness   = excluded.freshness,
  contract    = excluded.contract,
  description = excluded.description;
