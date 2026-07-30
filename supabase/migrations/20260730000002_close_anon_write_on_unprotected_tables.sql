-- 20260730000002_close_anon_write_on_unprotected_tables.sql
--
-- THE FINDING, measured not argued (2026-07-30, marketplace test bank / anon partition). The bank
-- enumerated 18 `anon` obligations and had never run one, because the SQL runner needed a uid to mint
-- and `anon` is the ABSENCE of an identity, not a different one. Teaching the runner `set local role
-- anon` (no JWT at all) made the largest-blast-radius partition executable for the first time — an
-- unauthenticated stranger on the public internet.
--
-- On the marketplace surface itself the answer was reassuring: RLS refused every anon write. Anon reads
-- 21 listings and 17 reviews (the intended public browse) and moves ZERO rows on insert, update and
-- delete; `service_requests`/`service_providers`/`service_credit_topups` grant anon nothing at all, so
-- they refuse at the strongest layer (42501, before RLS is even consulted).
--
-- Then the sweep asked the question one level up — *where is RLS not there to catch it?* — and found
-- **16 public tables with `relrowsecurity = false` that grant `anon` INSERT, UPDATE, DELETE and
-- TRUNCATE.** The GRANT is the Supabase template default (`GRANT ALL ON ALL TABLES IN SCHEMA public TO
-- anon, authenticated`), which is harmless on the ~130 tables where RLS is the real control, and is the
-- ONLY gate on these 16. Nothing stands behind it.
--
-- MEASURED BLAST RADIUS — a rolled-back `delete ... where true` as the `anon` role:
--
--     persona_knowledge             434 rows      the AI's persona corpus
--     embedding_cache               766 rows      the RAG embedding cache
--     multilingual_terms            207 rows      the i18n dictionary
--     equipment_reading_templates    15 rows
--     service_slo_targets             3 rows      the thresholds the gate panel grades against
--     avatar_state                    3 rows
--     ai_global_budget                1 row       *** the platform's AI spend cap ***
--     ph_intelligence_reports         1 row
--                                 -------
--                                  1,430 rows destroyable with only the anon key
--
-- `ai_global_budget` is the worst in kind rather than in count: delete that single row and either the
-- AI chain stops for everyone, or — if any reader treats a missing row as "no cap configured" — the
-- spend ceiling silently disappears on a founder who has said plainly he is a startup watching every
-- peso. `service_slo_targets` is the same shape one layer down: rewrite the targets and the gate panel
-- grades against numbers an attacker chose ([[feedback_gate_panel_honesty]]'s premise, inverted).
--
-- WHY THIS IS A REVOKE AND NOT A POLICY. RLS is the right control for tenant data. These 16 are not
-- tenant data — they are system/service_role tables (caches, budgets, dictionaries, seeded corpora).
-- For them the honest statement is *no end-user role writes this at all*, and a REVOKE says exactly
-- that, cheaply and unambiguously. It also restores defence in depth: this class exists precisely
-- because a single missing `ENABLE ROW LEVEL SECURITY` left one layer holding everything.
--
-- Two of the 16 ARE client-written and are handled differently rather than lumped in:
--   * `avatar_state`        voice-handler.js:1133 upserts it from a SIGNED-IN session. Keyed by a
--                           client-generated `session_id`, and it had NO auth column at all.
--   * `language_preferences` has `worker_id uuid`, so ownership was already expressible.
--                           Both get RLS ON here and their owner-scoped policies in mig
--                           20260730000004, which also gives avatar_state the `auth_uid` column it
--                           always needed. I first wrote a permissive `USING (true)` policy for
--                           avatar_state and called the column "a schema change I should not smuggle
--                           into a security fix" - the column IS the fix, and the permissive policy was
--                           the smuggling.
--
-- TRUNCATE deserves its own line, because it is the one verb RLS would never have caught: **row-level
-- security does not apply to TRUNCATE.** Today an anon TRUNCATE on `marketplace_listings` fails with
-- 0A000 — "cannot truncate a table referenced in a foreign key constraint" — which is not a security
-- control, it is a coincidence of the schema that would evaporate the day that FK is dropped. It is
-- also not reachable through PostgREST, which never issues TRUNCATE; that bounds the exposure without
-- excusing the grant. Revoked here on the whole class.
--
-- Idempotent: REVOKE of an absent privilege is a no-op, and every ENABLE/POLICY is guarded.

-- ---------------------------------------------------------------------------------------------------
-- 1. The 14 system tables: no end-user role writes these. service_role and the table owner still do.
-- ---------------------------------------------------------------------------------------------------
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON
    public.ai_global_budget,
    public.avatar_animations,
    public.best_practices,
    public.cross_hive_alerts,
    public.embedding_cache,
    public.equipment_reading_templates,
    public.multilingual_terms,
    public.network_benchmarks,
    public.persona_knowledge,
    public.ph_intelligence_reports,
    public.service_slo_targets,
    public.terminology_gaps,
    public.tts_cache,
    public.voice_response_queue
  FROM anon, authenticated;

-- SELECT is deliberately left alone. Read exposure on these is a separate question with a separate
-- answer (a landing page may legitimately read the i18n dictionary before anyone signs in), and
-- bundling it here would risk breaking a pre-login surface to fix a write hole. Scoped fix, scoped
-- claim.

-- ---------------------------------------------------------------------------------------------------
-- 2. The two client-written tables: close anon, and make the remaining permission EXPLICIT.
-- ---------------------------------------------------------------------------------------------------
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON public.avatar_state, public.language_preferences FROM anon;
REVOKE TRUNCATE, REFERENCES, TRIGGER
  ON public.avatar_state, public.language_preferences FROM authenticated;

ALTER TABLE public.avatar_state         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.language_preferences ENABLE ROW LEVEL SECURITY;

-- RLS ON with NO POLICY YET is deliberate here, and it fails CLOSED: until the next migration defines
-- the policies, both tables deny every end-user read and write. That is the correct intermediate state
-- for a security migration — the alternative I first wrote was worse in a way two gates caught.
--
-- WHAT I FIRST WROTE, AND WHY IT IS GONE. This file used to CREATE three permissive policies here
-- (`avatar_state_authenticated_rw`, `avatar_state_read`, `language_prefs_read`, all `USING (true)`),
-- because owner-scoping `avatar_state` needed a column the table did not have and I treated that as a
-- reason to settle. `rls-open-policy` flagged all three against a forward-only baseline; the honest fix
-- was to ADD the column (mig 20260730000004), not to ship the permissive policy. Once 004 existed, this
-- file was creating three policies for the very next migration to immediately drop — churn from my own
-- iteration, left in the tree as if it were history.
--
-- It also produced a genuinely confusing disagreement: `rls-open-policy` understands DROP-supersede and
-- read the pair as clean, while `mine_rls_policies` scans migration TEXT and counted the three CREATEs
-- forever, reporting `USING(true) 21 vs baseline 18` on a database that had none of them. Both gates
-- were right about what they measured. Deleting dead DDL beats teaching a second scanner to forgive it.
--
-- So the division of labour is now clean: this migration REVOKES and turns RLS on; mig 004 adds the
-- `auth_uid` column, defines the owner-scoped policies, and states the GRANTs explicitly.

-- ---------------------------------------------------------------------------------------------------
-- 3. The v_* views: write privileges nothing has ever used, on objects that cannot honestly own a write.
-- ---------------------------------------------------------------------------------------------------
-- Thirteen `v_*` views are AUTO-UPDATABLE (a plain SELECT from one table, so Postgres will happily
-- rewrite a write through them) and grant anon INSERT/UPDATE/DELETE, and eleven of those are NOT
-- `security_invoker`. On paper that is the textbook RLS bypass: a write through a non-invoker view
-- executes with the VIEW OWNER's privileges, the owner here is `postgres`, and `forced=false` means a
-- table owner is exempt from RLS.
--
-- Probed as `anon`, it did NOT bypass: `update v_hives_truth` moved 0 rows, `delete v_asset_truth`
-- moved 0 rows, and a plain `select` through the view returned 0 rows as well. The base table's RLS was
-- still being applied. **Recorded as measured rather than as reasoned** — the mechanism I predicted did
-- not fire, and the honest note is that the empirical result governs, not my model of it
-- ([[feedback_check_the_premise_before_building_the_pattern]]).
--
-- The grants go anyway, because they are privileges with no purpose: a repo-wide grep finds ZERO writes
-- through any `v_*` view (`.from('v_…').insert|update|upsert|delete` — no matches), the views exist to
-- be read, and a privilege nobody uses is only ever a future foothold. This one costs nothing to close
-- and removes the entire question.
DO $$
DECLARE v record;
BEGIN
  FOR v IN
    SELECT c.relname
      FROM pg_class c
     WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'v'
       AND c.relname LIKE 'v\_%'
       AND EXISTS (SELECT 1 FROM information_schema.role_table_grants g
                    WHERE g.table_schema='public' AND g.table_name=c.relname
                      AND g.grantee IN ('anon','authenticated')
                      AND g.privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE'))
  LOOP
    EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.%I '
                   'FROM anon, authenticated', v.relname);
  END LOOP;
END $$;
