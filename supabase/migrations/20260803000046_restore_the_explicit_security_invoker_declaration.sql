-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- CREATE OR REPLACE VIEW SILENTLY REVERTED A SECURITY HARDENING
--
-- Both truth-view security gates went red on v_service_request_truth:
--   "reads RLS table(s) [...] but is NOT security_invoker -> BYPASSES RLS (cross-tenant read)"
--
-- Mine. mig 34 added `objection_deadline` to that view with CREATE OR REPLACE VIEW, and
-- CREATE OR REPLACE VIEW DOES NOT PRESERVE reloptions unless they are re-specified. The option it
-- dropped was not incidental — it was a deliberate hardening.
--
-- I NEARLY FIXED THIS THE WRONG WAY, and the wrong way looked well-argued. mig 20260728000040
-- created this view `with (security_invoker = false)` under an explicit house comment ("views are
-- WITH (security_invoker = false) — owner's rights"), so restoring FALSE looked like restoring the
-- original intent. I wrote that migration, and an exemption entry to match.
--
-- Then I checked whether anything had CHANGED that decision since — and something had.
-- `20260729000010_harden_service_views_security_invoker.sql` had already tested this exact view and
-- moved it the other way:
--
--     v_service_request_truth       CAN  (8 own requests still visible)
--
-- It hardened four of the six service truth views to invoker rights, and documented the two that
-- genuinely CANNOT (they read a column-revoked table, so an invoker read hits permission denial
-- before any row filter runs). This view was in the CAN group. Restoring `false` would have
-- silently un-done a reviewed hardening for the second time in two migrations, and my exemption
-- would have taught the gate to stop reporting it.
--
-- The lesson is the banked one about premises: the ORIGINAL declaration is not automatically the
-- CURRENT decision. mig 40 was superseded by mig 20260729000010 nine days later, and I read only
-- the first.
--
-- THE FIX is what the hardening migration already concluded: security_invoker = on.
--
-- Re-verified live before and after, rather than trusting either migration's prose:
--   party (David Velasco)      8 of 12 requests      unchanged
--   party (Christine Dizon)    9 of 12               unchanged
--   a stranger                 0                     unchanged
--   anon                       permission denied for table service_requests
--
-- The anon result is the POINT, not a regression: with owner rights anon silently read 0 rows
-- because the view's own WHERE clause filtered them; with invoker rights the database refuses at the
-- table. Same answer, enforced one layer deeper — which is exactly what "RLS *and* the predicate,
-- defence in depth" meant. Nothing signed-out queries this view: the buyer's services pane is gated
-- on an authenticated uid.
--
-- ALTER VIEW, not CREATE OR REPLACE: it sets the option without restating the SELECT, so this
-- migration cannot alter the projection or the boundary. Restating is the mistake being fixed.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

alter view public.v_service_request_truth set (security_invoker = on);

comment on view public.v_service_request_truth is
  'A party''s own service requests: client_auth_uid = auth.uid() OR active membership of the '
  'request''s hive. security_invoker = ON (mig 20260729000010''s hardening, RESTORED by mig 46 after '
  'mig 34''s CREATE OR REPLACE dropped the option) — base-table RLS applies UNDER the view''s own '
  'predicate. Verified live: party 8 of 12, second party 9, stranger 0, anon refused at the table.';

-- Assert the hardening actually took. An ALTER that silently no-ops would leave both gates red while
-- this migration reported success — the "green while broken" shape migs 42/45 also guard against.
do $$
begin
  if not exists (
    select 1 from pg_class c
     where c.relname = 'v_service_request_truth'
       and c.reloptions::text like '%security_invoker=on%')
  then
    raise exception 'mig 46 FAILED: v_service_request_truth is not security_invoker=on, so it still bypasses base-table RLS';
  end if;
end $$;
