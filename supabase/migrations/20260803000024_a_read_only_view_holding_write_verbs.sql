-- v_credit_posture was granted INSERT, UPDATE, DELETE and TRUNCATE. It is a read-only summary.
--
-- Migration ...000012 wrote `grant select on public.v_credit_posture to authenticated, anon, service_role`
-- and the write verbs arrived anyway, from the schema-wide default privileges every new object inherits.
-- The unprotected-write-grant gate caught it: "a view cannot own a write; if it is auto-updatable the
-- write lands on the base table with the VIEW OWNER's privileges."
--
-- This one is not exploitable today. The view selects from pg_proc, pg_trigger and an aggregate over
-- credit_treasury, so it is not auto-updatable and a write against it errors; and it became
-- security_invoker in ...000022 besides. Both of those are properties of what the view happens to select
-- RIGHT NOW. Simplify it one day into a plain SELECT over credit_treasury and it becomes auto-updatable,
-- at which point anon holds INSERT and DELETE on the supply cap and nothing in that change would look
-- like a security decision.
--
-- Same lesson the 2026-07-30 sweep paid for on 16 tables: the dangerous grant is the one nobody chose.
-- It arrives by default, it is invisible in the migration that "only" granted SELECT, and it stays
-- harmless right up until the object beneath it changes shape.

revoke insert, update, delete, truncate, references, trigger
  on public.v_credit_posture from anon, authenticated;

-- and re-state what it IS for, so a future reader sees the intent rather than the leftovers
grant select on public.v_credit_posture to anon, authenticated, service_role;
