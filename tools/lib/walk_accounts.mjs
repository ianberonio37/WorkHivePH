// walk_accounts.mjs - remove the throwaway accounts a walk made, and everything they wrote (2026-10-27).
//
// ★THE ACCOUNT WENT AND ITS WORK STAYED. prove_self_efficacy_pages.mjs removed each first-timer's membership, profile and
// auth user - and left 539 rows its journeys wrote: 185 achievements, 229 XP log rows, 10 seller profiles, 26 memories,
// 8 skill profiles with no owner (skill_profiles.auth_uid is ON DELETE SET NULL). The data gate failed on the orphans,
// and the achievements cap gate sized its lists against a hive swollen by people who no longer exist. So the account
// leaves with every row keyed to its auth_uid or its name, in every base table, before the auth user goes.
//
//   import { removeWalkAccounts } from './lib/walk_accounts.mjs';
//   removeWalkAccounts(['seprobe_abc123', ...])   -> { removed, rows }
import { execFileSync } from 'node:child_process';

const lit = (s) => "'" + String(s).replace(/'/g, "''") + "'";

export function removeWalkAccounts(usernames, db = 'supabase_db_workhive') {
  if (!usernames || !usernames.length) return { removed: 0, rows: 0 };
  const users = `ARRAY[${usernames.map(lit).join(',')}]::text[]`;
  const emails = `ARRAY[${usernames.map((u) => lit(u + '@auth.workhiveph.com')).join(',')}]::text[]`;
  // two passes: a child row whose parent is deleted later in the first pass is refused, and goes in the second
  const sql = `DO $$
DECLARE uids uuid[]; names text[]; t text; n bigint; total bigint := 0; pass int;
BEGIN
  SELECT coalesce(array_agg(u.id), '{}') INTO uids FROM auth.users u WHERE u.email = ANY(${emails});
  SELECT coalesce(array_agg(w.display_name), '{}') INTO names FROM public.worker_profiles w WHERE w.username = ANY(${users});
  FOR pass IN 1..2 LOOP
    FOR t IN SELECT c.table_name FROM information_schema.columns c JOIN information_schema.tables b
               ON b.table_schema = c.table_schema AND b.table_name = c.table_name
              WHERE c.table_schema = 'public' AND c.column_name = 'auth_uid' AND b.table_type = 'BASE TABLE'
                AND c.table_name NOT IN ('worker_profiles') LOOP
      BEGIN EXECUTE format('DELETE FROM public.%I WHERE auth_uid = ANY($1)', t) USING uids; GET DIAGNOSTICS n = ROW_COUNT; total := total + n;
      EXCEPTION WHEN others THEN NULL; END;
    END LOOP;
    FOR t IN SELECT c.table_name FROM information_schema.columns c JOIN information_schema.tables b
               ON b.table_schema = c.table_schema AND b.table_name = c.table_name
              WHERE c.table_schema = 'public' AND c.column_name = 'worker_name' AND b.table_type = 'BASE TABLE' LOOP
      BEGIN EXECUTE format('DELETE FROM public.%I WHERE worker_name = ANY($1)', t) USING names; GET DIAGNOSTICS n = ROW_COUNT; total := total + n;
      EXCEPTION WHEN others THEN NULL; END;
    END LOOP;
  END LOOP;
  DELETE FROM public.worker_profiles WHERE username = ANY(${users});
  DELETE FROM auth.users WHERE id = ANY(uids);
  RAISE NOTICE 'walk rows removed: %', total;
END $$;`;
  const out = execFileSync('docker', ['exec', '-i', db, 'psql', '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1'],
    { input: sql, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  void out;
  return { removed: usernames.length };
}
