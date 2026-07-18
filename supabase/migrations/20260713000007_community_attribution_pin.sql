-- 20260713000007_community_attribution_pin.sql
--
-- Community replies + reactions attribution-forgery + over-permissive mutation (MED — forum
-- integrity / trust) — bug-hunt 2026-07-13, community.html P5.
--
-- community_replies_write (ALL) gates hive membership but NOT auth_uid, so within a hive a member
-- can (a) INSERT a reply with a FORGED auth_uid + author_name (attribute their post to another
-- worker or the supervisor), and (b) UPDATE/DELETE ANY member's reply + flip is_accepted (BOLA).
-- LIVE-CONFIRMED (rolled back): Baguio worker (4153311f) INSERTed a reply with
-- auth_uid=<supervisor e324f252> + author_name='FORGED-supervisor' -> stored (INSERT 0 1). A
-- cross-hive write into Lucena is correctly BLOCKED by RLS (hive_id gate holds), so the boundary
-- that leaked is INTRA-hive authorship. Same attribution-pin class as logbook/projects/asset
-- (migs 20260713000003/004/005) — the community_* tables were missed by that sweep.
--
-- community_reactions additionally carries a stray `anon delete community_reactions` DELETE policy
-- with USING(true) — roles={public} — that lets ANY caller (including anon) DELETE ANY reaction on
-- ANY hive's post. Reactions are authed-only to INSERT (community_reactions_write requires
-- auth.uid()), so an anon-delete policy is both nonsensical and a live integrity hole; it is dropped.
-- Reactions also carry only worker_name (no auth_uid), client-supplied and unchecked -> spoofable.
--
-- FIX:
--  1. bind_community_reply_submitter    BEFORE INSERT — pin auth_uid + author_name to the caller.
--  2. bind_community_reaction_submitter BEFORE INSERT — pin worker_name to the caller (no auth_uid
--     column exists on reactions; pin the DISPLAYED attribution so it can't be forged).
--  3. Replace community_replies_write (ALL, hive-only) with author-scoped policies: INSERT requires
--     auth_uid = auth.uid() + hive membership; UPDATE/DELETE require own-reply OR hive-supervisor
--     (moderation, via user_supervisor_hive_ids()). SELECT policy (community_replies_read) unchanged.
--  4. Drop the anon-delete-USING(true) reaction policy; reaction DELETE stays governed by
--     community_reactions_write (authed + public-post-or-hive-member) — no longer anon-nukeable.
--
-- Service-role/seeder inserts (auth.uid() NULL) keep their values + bypass RLS (batch trust).
-- Idempotent: CREATE OR REPLACE + DROP ... IF EXISTS throughout.

BEGIN;

-- 1. reply authorship pin (mirrors bind_logbook_submitter / mig 20260713000004) ----------------
CREATE OR REPLACE FUNCTION public.bind_community_reply_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    NEW.auth_uid := auth.uid();
    IF NEW.hive_id IS NOT NULL THEN
      SELECT worker_name INTO v_name FROM public.hive_members
        WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
      IF v_name IS NOT NULL THEN NEW.author_name := v_name; END IF;
    END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_community_reply ON public.community_replies;
CREATE TRIGGER trg_bind_submitter_community_reply BEFORE INSERT ON public.community_replies
  FOR EACH ROW EXECUTE FUNCTION public.bind_community_reply_submitter();

-- 2. reaction attribution pin (no auth_uid column; pin worker_name) -----------------------------
CREATE OR REPLACE FUNCTION public.bind_community_reaction_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NOT NULL AND NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_community_reaction ON public.community_reactions;
CREATE TRIGGER trg_bind_submitter_community_reaction BEFORE INSERT ON public.community_reactions
  FOR EACH ROW EXECUTE FUNCTION public.bind_community_reaction_submitter();

-- 3. author-scoped replies write policies (replace the hive-only ALL policy) ---------------------
-- DROP IF EXISTS before every CREATE POLICY so the migration is idempotent / re-runnable.
DROP POLICY IF EXISTS community_replies_write ON public.community_replies;
DROP POLICY IF EXISTS community_replies_insert ON public.community_replies;
DROP POLICY IF EXISTS community_replies_modify ON public.community_replies;
DROP POLICY IF EXISTS community_replies_delete ON public.community_replies;

CREATE POLICY community_replies_insert ON public.community_replies FOR INSERT
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
    AND hive_id IN (SELECT hm.hive_id FROM public.hive_members hm
                    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')
  );

CREATE POLICY community_replies_modify ON public.community_replies FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND (auth_uid = auth.uid() OR hive_id IN (SELECT public.user_supervisor_hive_ids()))
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (SELECT hm.hive_id FROM public.hive_members hm
                    WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')
    AND (auth_uid = auth.uid() OR hive_id IN (SELECT public.user_supervisor_hive_ids()))
  );

CREATE POLICY community_replies_delete ON public.community_replies FOR DELETE
  USING (
    auth.uid() IS NOT NULL
    AND (auth_uid = auth.uid() OR hive_id IN (SELECT public.user_supervisor_hive_ids()))
  );

-- 4. drop the over-permissive anon-delete reaction policy ----------------------------------------
DROP POLICY IF EXISTS "anon delete community_reactions" ON public.community_reactions;

COMMIT;
