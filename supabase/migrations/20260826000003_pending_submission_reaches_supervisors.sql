-- T108 (2026-08-26): the LAST silent row — "pending approval (asset/part submitted)".
--
-- WHAT WAS SILENT. The supervisor's only signal was a realtime postgres_changes subscription
-- living on hive.html, so it fired while — and only while — they had the hive board open. A
-- supervisor reading the logbook, walking the plant, or with the app closed learned that work was
-- waiting on them by happening to visit. That is the silent-work class the someone-to-you registry
-- exists to name, and it was its last member.
--
-- WHY A TRIGGER AND NOT A CALL SITE. Its five siblings are client-called guarded RPCs, and that
-- shape is right when ONE page performs the act. A submission is not that: pending rows are
-- written from asset-hub (submit + resubmit), inventory (two paths), logbook, and integrations'
-- BULK CMMS upsert — six-plus paths across five pages. Wiring each is the fix-every-path hazard at
-- its worst, where the miss is invisible: the row lands, no one is told, and nothing errors. A
-- trigger catches every writer by construction, including writers added later.
--
-- ★THE STORM IS THE REASON THE COPY IS GENERIC. integrations.html upserts CMMS batches, and the
-- seeders create pending rows in bulk. A per-row notification would mean 200 pushes from one
-- import — the notification-storm failure this platform already worries about (T110). So the copy
-- names NO row: "Items are waiting for your approval." enqueue_user_push already collapses an
-- identical payload still pending within 2 minutes (mig 20260826000001), so an import of any size
-- produces ONE push, and the board is where the count lives. Fewer words, and the dedupe window
-- becomes the storm guard rather than a separate mechanism.
--
-- ★AND IT CAN NEVER BLOCK A SUBMISSION. The whole body is wrapped so that any failure — a missing
-- helper, a permissions change, a full outbox — is swallowed. A notification is an extra; a
-- submission is the user's work. A guard that breaks the write it was attached to is a lesson this
-- codebase has already paid for once.
--
-- Recipients: ACTIVE supervisors of the row's hive, minus the submitter (a supervisor who submits
-- their own asset does not need telling). No supervisors, or none with an auth_uid: honest no-op.
-- Re-runnable.

CREATE OR REPLACE FUNCTION public.tg_notify_pending_submission()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_uids uuid[]; v_submitter text; v_hive_name text;
BEGIN
  -- fire only on the TRANSITION into pending: an insert that arrives pending, or an update that
  -- moves a row into it (a resubmission). An update that leaves a row pending re-notifies nobody.
  IF NEW.status IS DISTINCT FROM 'pending' THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'pending' THEN RETURN NEW; END IF;

  BEGIN
    v_submitter := COALESCE(NEW.submitted_by, NEW.worker_name);

    SELECT array_agg(DISTINCT hm.auth_uid) INTO v_uids
    FROM public.hive_members hm
    WHERE hm.hive_id = NEW.hive_id
      AND hm.status = 'active'
      AND hm.role = 'supervisor'
      AND hm.auth_uid IS NOT NULL
      AND (v_submitter IS NULL OR lower(hm.worker_name) <> lower(btrim(v_submitter)));
    IF v_uids IS NULL OR array_length(v_uids, 1) IS NULL THEN RETURN NEW; END IF;

    SELECT name INTO v_hive_name FROM public.hives WHERE id = NEW.hive_id;

    PERFORM public.enqueue_user_push(
      v_uids,
      'Items are waiting for your approval',
      'Something new was submitted in ' || COALESCE(v_hive_name, 'your hive')
        || '. Open the Hive board to review what is pending.',
      '/hive.html'
    );
  EXCEPTION WHEN OTHERS THEN
    -- a notification must never cost someone their submission
    NULL;
  END;

  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_notify_pending_asset ON public.asset_nodes;
CREATE TRIGGER trg_notify_pending_asset
  AFTER INSERT OR UPDATE OF status ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.tg_notify_pending_submission();

DROP TRIGGER IF EXISTS trg_notify_pending_part ON public.inventory_items;
CREATE TRIGGER trg_notify_pending_part
  AFTER INSERT OR UPDATE OF status ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.tg_notify_pending_submission();

NOTIFY pgrst, 'reload schema';
