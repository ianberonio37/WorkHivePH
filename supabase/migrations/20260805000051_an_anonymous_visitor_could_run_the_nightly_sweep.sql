-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- AN ANONYMOUS VISITOR COULD RUN THE NIGHTLY SWEEP
--
-- Postgres grants EXECUTE to PUBLIC on every new function. A SECURITY DEFINER helper is therefore
-- callable by anyone unless someone remembered the REVOKE — and this is the second time that habit
-- has cost us: a previous session found `sweep_service_broadcasts()` the same way.
--
-- Measured this session, not reasoned about. Two functions that the cron scheduler invokes are
-- DEFINER and were EXECUTE-able by anon and authenticated. Called from a rolled-back transaction:
--
--     as authenticated (a stranger, no relationship to any row):  amc_expire_stale() -> 3
--     as anon          (no account at all):                       amc_expire_stale() -> 3
--     as authenticated:                                           snapshot_db_size() -> ran
--
-- The `3` is three real records expired on demand, by someone with no claim to them. This is the
-- class RLS cannot help with: the function's whole job is to act ACROSS tenants, so there is no
-- caller-owned row to write a predicate against. The only correct control is that a person cannot
-- call it at all. The cron scheduler is unaffected — it runs as the table owner, not as anon.
--
-- THE SECOND HALF: 95 DEFINER TRIGGER FUNCTIONS WERE ALSO USER-CALLABLE. Directly invoking a
-- trigger function is refused by Postgres ("can only be called as a trigger"), so this is surface
-- rather than an open door — but it is surface with owner rights on it, and the fix is one line.
--
-- REVOKING A TRIGGER FUNCTION DOES NOT DISABLE ITS TRIGGER, and I proved that before shipping rather
-- than assuming it. Inside one transaction: revoke all 95, then re-run the same insert twice.
--
--     before revoke:  ERROR "The lowest price WorkHive lists is PHP500. This one is PHP5..."
--                     CONTEXT: guard_listing_meets_minimum() line 16
--     after  revoke:  ERROR "The lowest price WorkHive lists is PHP500. This one is PHP5..."
--                     CONTEXT: guard_listing_meets_minimum() line 16      <- byte-identical
--     after  revoke:  a VALID draft inserted successfully, id f3313684...
--
-- Identical refusal, and writes still land. Trigger execution goes through the trigger machinery
-- under the table owner and never consults the calling role's EXECUTE privilege.
--
-- NOT TOUCHED HERE: the 86 non-trigger DEFINER functions that are still user-callable. Many of them
-- are legitimate RPCs the client is supposed to call, and telling those apart from the next
-- amc_expire_stale needs a function-by-function reading, not a blanket revoke. That reading is what
-- tools/verify_layer_invariants.py (layer_cron/grant_matches_policy) now does on every run, so a
-- newly-added cron helper trips a check instead of waiting for someone to notice.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

-- ── 1. the two proven-callable cron helpers ─────────────────────────────────────────────────────
revoke all on function public.amc_expire_stale() from public, anon, authenticated;
revoke all on function public.snapshot_db_size() from public, anon, authenticated;

-- ── 2. every SECURITY DEFINER trigger function ──────────────────────────────────────────────────
-- Written as a loop because naming 95 signatures by hand is how one gets missed, and because the
-- set is defined by a property ("DEFINER and returns trigger") rather than by a list.
do $$
declare
  r record;
  n int := 0;
begin
  for r in
    select p.oid::regprocedure as sig
      from pg_proc p
      join pg_namespace nsp on nsp.oid = p.pronamespace
     where nsp.nspname = 'public'
       and p.prosecdef
       and p.prorettype = 'trigger'::regtype
  loop
    execute format('revoke all on function %s from public, anon, authenticated', r.sig);
    n := n + 1;
  end loop;
  raise notice 'revoked EXECUTE on % SECURITY DEFINER trigger functions', n;
end $$;
