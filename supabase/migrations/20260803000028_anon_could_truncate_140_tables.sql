-- An anonymous visitor could TRUNCATE 140 tables. RLS cannot stop TRUNCATE.
--
-- PROVEN, not reasoned. As the `anon` role, inside a rolled-back transaction:
--
--     truncate table public.marketplace_sellers cascade;   -- SUCCEEDED
--     select count(*) from public.marketplace_sellers;     -- 0
--
-- Every seller on the platform, gone, by someone who never signed in. Measured blast radius:
-- **140 tables anon-truncatable, 142 for authenticated, ~104,000 rows.**
--
-- WHY EVERY EXISTING GATE MISSED IT, and this is the part worth keeping. The July sweep
-- (20260730000002) closed exactly this class for 16 tables and locked it with
-- `validate_unprotected_write_grant`, whose invariant is:
--
--     a base table may grant an end-user WRITE VERB only if row-level security is enabled on it.
--
-- That invariant is correct for INSERT/UPDATE/DELETE and USELESS for TRUNCATE, because **RLS does not
-- apply to TRUNCATE at all**. marketplace_sellers has RLS enabled and a proper policy set, so it passes
-- that gate cleanly - and an anon TRUNCATE still empties it. The gate was not wrong; its premise simply
-- does not extend to the one verb that ignores the mechanism it depends on.
--
-- The July migration's own notes even flagged this: "anon TRUNCATE on marketplace_listings fails today
-- only with 0A000 'referenced in a foreign key constraint', a coincidence of the schema that evaporates
-- the day that FK is dropped." That coincidence was the only thing standing between an anonymous visitor
-- and the catalogue. marketplace_sellers had no such FK, so nothing stood there at all.
--
-- Found by the live-MCP flywheel, three steps removed from where it started: walking G-trust for
-- anonymous visitors -> the badges were all wrong -> the read policy was signed-in-only -> widening the
-- READ meant auditing the writes -> the write privileges included TRUNCATE.
--
-- NO CLIENT PATH NEEDS IT. Grepped every page, module and edge function: zero TRUNCATE usage outside
-- backup copies. Truncation is a maintenance act for a migration or a seeder, both of which run as
-- postgres or service_role and are unaffected by this.

revoke truncate on all tables in schema public from anon, authenticated;

-- And for every table created from here on, so the next `create table` does not silently re-open it.
-- The template default is what put it there in the first place, and a fix that only covers today's
-- tables is a fix with an expiry date.
alter default privileges in schema public revoke truncate on tables from anon, authenticated;

-- ── and the vendor-managed schemas, which the schema-wide REVOKE above does not reach ────────────────
-- `revoke ... on all tables in schema public` covers public only. Five grants survived it, all in
-- Supabase's own schemas, and one of them is not theoretical:
--
--     set role anon; truncate table storage.objects cascade;   -- SUCCEEDED (6 file records)
--
-- Every uploaded file's record, removed by an anonymous visitor. These are Supabase's template defaults
-- rather than anything this project wrote, but they are live in this stack and would be live in prod.
-- No browser client truncates storage: uploads and deletes go through the storage API under its own
-- role, so revoking costs nothing. If a Supabase upgrade re-grants them, the gate below catches it.
-- THE STORAGE GRANTS CANNOT BE REVOKED FROM HERE, and that is a finding rather than an omission.
-- storage.objects/buckets are owned by supabase_storage_admin, and only the owner or a superuser may
-- revoke what it granted. In this stack `postgres` is NOT superuser and cannot `set role` to it:
--
--     ERROR: permission denied to set role "supabase_storage_admin"
--
-- Migrations run as postgres both locally and in the hosted dashboard, so no migration this project can
-- write will close it. It stays live and it stays exploitable (proven: anon truncated storage.objects,
-- 6 file records). Attempted here anyway and swallowed, so a future stack where postgres IS superuser
-- closes it automatically rather than needing someone to remember.
--
-- Made VISIBLE instead of silent by tools/validate_no_client_truncate.py, which reports the public
-- schema as an enforced invariant and the storage residual as a named, tracked exception. Closing it for
-- real needs a Supabase-side action under a superuser - Ian's call, and outside a migration's reach.
do $$
begin
  set local role supabase_storage_admin;
  revoke truncate on storage.objects, storage.buckets from anon, authenticated;
  reset role;
exception when insufficient_privilege or undefined_object then
  raise notice 'storage TRUNCATE grants left in place: postgres cannot assume supabase_storage_admin. '
               'Tracked by validate_no_client_truncate.py.';
end $$;
