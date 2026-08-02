-- service_payments had RLS and no GRANT, and anon held DELETE/TRUNCATE on it.
--
-- Two problems, one cause: the table was created with RLS enabled and policies written, and the
-- privileges were left to whatever the environment happened to hand out.
--
-- 1. NO GRANT IN THE MIGRATION. Locally it works because the Supabase stack ships blanket
--    ALTER DEFAULT PRIVILEGES over `public` for anon/authenticated. A project without those defaults —
--    or one that has since tightened them — applies this migration and gets a table `authenticated`
--    cannot touch: 401 on every read and write, with RLS policies that are perfectly correct and never
--    reached. `permission denied for table` is a GRANT problem wearing an RLS costume
--    ([[feedback_permission_denied_table_is_grant_not_rls]]), and it would have surfaced on the FIRST
--    production settle rather than here.
--
-- 2. ANON HAD EVERYTHING. The same blanket default gave anon DELETE and TRUNCATE on the payment record.
--    RLS does hold — every policy requires auth.uid() and anon has none — but a money table should not
--    be reachable by an anonymous role at all. Depending on RLS alone to stop a role that was never
--    meant to have the privilege is one policy edit away from being wrong, and this platform has already
--    paid for that shape twice (ops views over-granted to anon; a GRANT harmless 130 times and
--    catastrophic the 16th).
--
-- What the table actually needs: a client INSERTs their own payment record and both parties SELECT it.
-- Nothing legitimately UPDATEs or DELETEs — the record is immutable by design (one per request, enforced
-- by service_payments_one_per_request), and a mistaken amount is corrected by a dispute adjustment that
-- COMPENSATES rather than by an edit that erases. So the grant is exactly SELECT + INSERT.

revoke all on public.service_payments from anon;
revoke all on public.service_payments from authenticated;

grant select, insert on public.service_payments to authenticated;
-- service_role keeps full access: it is the backend/admin path (test cleanup, founder tooling).
grant all on public.service_payments to service_role;

comment on table public.service_payments is
  'Record-only proof that a client paid a provider DIRECTLY (no custody). Immutable: one row per '
  'request, SELECT+INSERT to authenticated and nothing more — a wrong amount is compensated by a dispute '
  'adjustment, never edited away. anon is explicitly revoked: RLS would refuse it anyway, but a money '
  'table should not be reachable by an anonymous role at all.';
