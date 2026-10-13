-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ A PERSON CHOOSES TO BRING THEIR OWN HISTORY INTO A HIVE (decided in UFAI §LM.11, 2026-10-08)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Until 2026-10-07 hive.html moved every hive-less logbook entry of a member - matched by worker NAME - into whichever
-- hive was open, on page load, without asking (LM330; the helper is now a no-op). Personal records stay personal. But a
-- person who joins a hive, or a solo owner who now founds one for their crew, may WANT their history there: their
-- repairs feed the hive's MTBF, its knowledge search and its handover. That is now their explicit choice:
--
--   bring_personal_history_into_hive(p_hive_id)
--     * the caller must be signed in and an ACTIVE member of p_hive_id;
--     * moves only the caller's OWN hive-less logbook entries, matched by ACCOUNT (auth_uid), never by a name;
--     * the hive's audit log records who brought how many entries in, and that it was their choice;
--     * the entries' knowledge rows (fault_knowledge) move WITH them in the same transaction, so the hive's knowledge
--       search sees them at once; the row update also re-queues each entry for embedding (trg_embed_outbox_logbook).
--     * a closed entry it moves is NOT "amended after close": only hive_id changed (see the audit trigger below).
--   my_personal_history_count() - how many such entries the caller holds, for the page to decide whether to ask.
BEGIN;

CREATE OR REPLACE FUNCTION public.my_personal_history_count()
RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT CASE WHEN auth.uid() IS NULL THEN 0 ELSE
    (SELECT count(*)::int FROM public.logbook WHERE auth_uid = auth.uid() AND hive_id IS NULL) END;
$fn$;
REVOKE ALL ON FUNCTION public.my_personal_history_count() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.my_personal_history_count() TO anon, authenticated;   -- 0 for a stranger

CREATE OR REPLACE FUNCTION public.bring_personal_history_into_hive(p_hive_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE
  v_uid  uuid := auth.uid();
  v_name text;
  v_n    int;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Sign in to bring your history into a hive.' USING ERRCODE = '42501';
  END IF;
  SELECT worker_name INTO v_name FROM public.hive_members
   WHERE hive_id = p_hive_id AND auth_uid = v_uid AND status = 'active'
   ORDER BY joined_at LIMIT 1;
  IF v_name IS NULL THEN
    RAISE EXCEPTION 'You can only bring your history into a hive you are an active member of.' USING ERRCODE = '42501';
  END IF;
  WITH moved AS (
    UPDATE public.logbook SET hive_id = p_hive_id WHERE auth_uid = v_uid AND hive_id IS NULL RETURNING id
  ), kn AS (
    -- the knowledge rows move WITH their entries, in this transaction: the outbox re-embed would carry the hive too,
    -- but only when it drains - and until then the hive's knowledge search could not see entries it was just given
    UPDATE public.fault_knowledge f SET hive_id = p_hive_id FROM moved
     WHERE f.logbook_id = moved.id AND f.hive_id IS NULL RETURNING f.logbook_id
  )
  SELECT count(*) INTO v_n FROM moved;
  IF v_n > 0 THEN
    INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
    VALUES (p_hive_id, v_name, 'personal_history_brought_in', 'logbook', NULL, v_name,
            jsonb_build_object('entries', v_n, 'by_choice', true));
  END IF;
  RETURN jsonb_build_object('moved', v_n, 'hive_id', p_hive_id);
END $fn$;
REVOKE ALL ON FUNCTION public.bring_personal_history_into_hive(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.bring_personal_history_into_hive(uuid) TO authenticated;

-- the post-close audit must not call an adoption an amendment (see the function's own note)
CREATE OR REPLACE FUNCTION public.audit_logbook_post_close_amendment()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- SOLO lane (2026-09-02, VM7 walk): hive_audit_log.hive_id is NOT NULL and its audience
  -- is the hive. A hive-less row has neither; without this early return the audit INSERT
  -- ABORTS the user's own edit (proven live per-fn in rolled-back probes).
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- Only rows that were already signed off. Everything else is an ordinary edit.
  IF COALESCE(OLD.status, '') <> 'Closed' THEN
    RETURN NEW;
  END IF;

  -- Ignore no-op updates (a re-save that changed nothing is not an amendment).
  IF NEW IS NOT DISTINCT FROM OLD THEN
    RETURN NEW;
  END IF;

  -- ★ADOPTION IS NOT AN AMENDMENT (2026-10-08, 20261008000064). A closed entry its owner brings from their personal
  -- history into a hive (bring_personal_history_into_hive) changes ONLY hive_id - plus the updated_at the touch trigger
  -- stamps. Its words, sign-off and dates are exactly what they were, so "amended after close" would tell a supervisor
  -- something untrue; the adoption is recorded once, by the function that made it, under the person's own name.
  IF OLD.hive_id IS NULL AND NEW.hive_id IS NOT NULL
     AND (to_jsonb(NEW) - 'hive_id' - 'updated_at') = (to_jsonb(OLD) - 'hive_id' - 'updated_at') THEN
    RETURN NEW;
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, NEW.worker_name, 'unknown'),
    CASE WHEN COALESCE(NEW.status, '') <> 'Closed'
         THEN 'reopen_closed_logbook_entry'
         ELSE 'amend_closed_logbook_entry' END,
    'logbook',
    NEW.id,
    COALESCE(NEW.machine, '(no machine)'),
    jsonb_build_object(
      'prev_status',    OLD.status,
      'new_status',     NEW.status,
      'closed_at_was',  OLD.closed_at,
      'closed_at_now',  NEW.closed_at,
      'source',         'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

COMMIT;
