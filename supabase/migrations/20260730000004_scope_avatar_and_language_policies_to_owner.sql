-- 20260730000004_scope_avatar_and_language_policies_to_owner.sql
--
-- FIXING MY OWN REGRESSION, caught by `rls-open-policy` within minutes of shipping it.
--
-- Mig 20260730000002 closed a real hole (1,430 rows destroyable by an unauthenticated caller) but paid
-- for it with three `USING (true)` policies — `avatar_state_authenticated_rw`, `avatar_state_read` and
-- `language_prefs_read`. The open-policy gate flagged all three against a forward-only baseline of 2,
-- and it is right to: I closed a GRANT hole by opening an RLS hole one layer down, which is a trade, not
-- a fix. The previous migration even said so out loud — *"the permissiveness that remains is now WRITTEN
-- DOWN instead of implied"* — and writing a weakness down is not the same as not having it.
--
-- I also wrote that owner-scoping `avatar_state` "is not expressible without a schema change" and
-- treated that as a reason to stop. It is a reason to make the schema change: the table holds THREE rows
-- of ephemeral voice-avatar UI state, and adding the column it always needed is smaller than the
-- permissive policy it replaces ([[feedback_build_structure_to_make_it_liveable]] — if a cell needs
-- structure to be provable, build the structure).
--
-- avatar_state: gains `auth_uid uuid DEFAULT auth.uid()`. The DEFAULT is what makes this invisible to
-- the caller — voice-handler.js:1133 upserts `{session_id, current_state, emotion, updated_at}` and
-- names no owner, so the column fills itself from the JWT on every insert. Existing rows are backfilled
-- from nothing (they have no owner to recover), so they are deleted instead: three rows of "what
-- expression was the avatar making" is cache, not data, and inventing an owner for them would be
-- fabricating attribution ([[feedback_authuid_attribution_on_every_write]]).
--
-- The upsert conflicts on `session_id` (unique index avatar_state_session_id_key), so an UPDATE path
-- exists and needs `USING`: a caller may only overwrite their OWN session row. Without that, one signed-
-- in user could hijack another's session_id — which the permissive policy allowed and nobody would ever
-- have seen, because the write succeeds silently either way.
--
-- language_preferences: only the SELECT policy was open; the ALL policy was already owner-scoped. Now
-- both are. The table has 0 rows and no client reader, so this costs nothing today and is correct
-- tomorrow — a per-worker language choice is not public.
--
-- Net: the two gates that disagreed about these tables now agree. `unprotected-write-grant` wants RLS
-- enabled behind every write grant; `rls-open-policy` wants that RLS to actually decide something.
-- Both hold.

-- ---------------------------------------------------------------------------------------------------
-- avatar_state: give it the owner column it needed, then scope both policies to that owner.
-- ---------------------------------------------------------------------------------------------------
ALTER TABLE public.avatar_state ADD COLUMN IF NOT EXISTS auth_uid uuid DEFAULT auth.uid();

-- Ephemeral rows with no recoverable owner. A row whose auth_uid is NULL would be readable by nobody
-- and writable by nobody under the new policies, so leaving it would be leaving litter that looks like
-- data.
DELETE FROM public.avatar_state WHERE auth_uid IS NULL;

DROP POLICY IF EXISTS avatar_state_authenticated_rw ON public.avatar_state;
DROP POLICY IF EXISTS avatar_state_read             ON public.avatar_state;
-- and the ones THIS migration creates, so a second run replaces them instead of erroring. My first cut
-- dropped only the policies it was superseding and left its own CREATEs bare — re-applying it failed with
-- `policy "avatar_state_owner_rw" already exists`, one command after I had written the comment in mig 002
-- explaining exactly this. Dropping what you are about to create is the whole convention.
DROP POLICY IF EXISTS avatar_state_owner_rw        ON public.avatar_state;
DROP POLICY IF EXISTS avatar_state_owner_read      ON public.avatar_state;

CREATE POLICY avatar_state_owner_rw ON public.avatar_state
  FOR ALL TO authenticated
  USING (auth_uid = auth.uid())
  WITH CHECK (auth_uid = auth.uid());

CREATE POLICY avatar_state_owner_read ON public.avatar_state
  FOR SELECT TO authenticated
  USING (auth_uid = auth.uid());

-- ---------------------------------------------------------------------------------------------------
-- language_preferences: close the open SELECT to the same owner test the write already uses.
-- ---------------------------------------------------------------------------------------------------
DROP POLICY IF EXISTS language_prefs_read       ON public.language_preferences;
DROP POLICY IF EXISTS language_prefs_owner_read ON public.language_preferences;

CREATE POLICY language_prefs_owner_read ON public.language_preferences
  FOR SELECT TO authenticated
  USING (worker_id IN (SELECT id FROM public.worker_profiles WHERE auth_uid = auth.uid()));

-- ---------------------------------------------------------------------------------------------------
-- State the GRANTs explicitly, instead of inheriting them from the Supabase template.
-- ---------------------------------------------------------------------------------------------------
-- `migration_grant_coverage` flagged both tables: RLS is enabled in a migration while no migration
-- states a GRANT, so a database built from migrations alone could end up with correct policies and no
-- privilege behind them — the 401-despite-valid-RLS shape. Live, these tables DO have the privileges
-- (the template's `GRANT ALL ON ALL TABLES IN SCHEMA public` reached them, and the authenticated upsert
-- was probed working: owner_upsert_rows=1). The gate is objecting to the provenance, not the state, and
-- it has a point that is sharper than usual here: **this entire arc exists because that invisible
-- template grant was the only thing standing between anon and 1,430 rows.** A migration that fixes an
-- invisible grant should not itself rely on one.
--
-- So the privileges these two tables need are now written down where they can be read and reviewed. No
-- DELETE for either: avatar_state rows are overwritten by the session-keyed upsert and expire with the
-- session, and a language preference is changed, never removed.
GRANT SELECT, INSERT, UPDATE ON public.avatar_state         TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.language_preferences TO authenticated;

-- anon keeps SELECT only, matching what mig 20260730000002 left in place deliberately: read exposure is
-- a separate question with a separate answer, and revoking it here would risk a pre-login surface to fix
-- a write hole that is already fixed.
GRANT SELECT ON public.avatar_state         TO anon;
GRANT SELECT ON public.language_preferences TO anon;
