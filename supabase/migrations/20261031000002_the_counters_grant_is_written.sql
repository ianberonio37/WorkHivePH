-- THE CODE COUNTERS' GRANT IS WRITTEN, NOT INHERITED (M4's first push, 2026-10-31).
--
-- 20261030000009 created public.code_counters and revoked it from PUBLIC, anon and authenticated - the two SECURITY
-- DEFINER code generators are its only writers. service_role kept every table privilege, but only through the
-- database's default privileges: no migration grants it, so a replay of the schema on a database without those
-- defaults (the 2026-10-30 rule tools/validate_api_grants_explicit.py holds) would leave the seeders' reset and the
-- walk's cleanup unable to clear it. The grant is the one every service-only table carries (20261015800000): every
-- table privilege but MAINTAIN. It changes nothing on a database that already has it.
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.code_counters TO service_role;
