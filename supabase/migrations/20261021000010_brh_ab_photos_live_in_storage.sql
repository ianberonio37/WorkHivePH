-- ============================================================================================================
-- BRH 9 AB (2026-10-21): a photo lives in Supabase Storage, never inside its row.
--
-- WHAT WAS WRONG. logbook.photo and inventory_items.photo held each picture as base64 text. Production's logbook carried
-- 22 photos (4.35 MB) and inventory_items 5 (0.54 MB) inside their rows, so:
--   * the free plan's 500 MB database grew by every photo, while its 1 GB of file storage sat unused;
--   * every read of a row shipped its photo in free egress, whether the screen showed it or not - the dayplanner read
--     up to a thousand logbook rows with `select *`, the inventory read up to 2,000 parts the same way, and logbook's
--     two feeds named `photo` in their column lists;
--   * both tables are in the realtime publication, so every change to a row with a photo sent the photo to every
--     subscriber.
-- 20260705000009 capped an inline photo at 1.5 MB and deferred the move "until photos start landing". They have.
--
-- WHAT THIS DOES.
--   1. photo_path / photo_thumb_path: the row keeps the names of two objects in the private bucket entry-photos - the
--      picture (<= 800 px, ~50-150 KB) and a 160 px thumbnail (~6 KB) for lists. A CHECK keeps image data out of them.
--   2. entry-photos is PRIVATE. Who may read an object is decided by its row: wh_entry_photo_visible() runs as the
--      reader, so the tables' own RLS answers "can this person see a row that names this object?" - a photo is exactly
--      as private as its entry, and follows the entry's hive membership and trash rules without a second copy of them.
--      The uploader may always read their own upload (the INSERT ... RETURNING the storage API runs needs it).
--   3. Uploads go only into the uploader's own folder (<auth.uid()>/...). An object a row still names cannot be deleted
--      by a client; the uploader deletes their own objects once no row names them (a replaced or removed photo, or an
--      upload whose save failed).
--   4. The server refuses NEW inline photos: check_inline_image_size() now refuses a data: URL that is not already the
--      row's stored value. A legacy row that still holds one can be re-saved unchanged (an old page open across the
--      deploy re-sends it); it cannot gain a new one.
--   5. The one-time move: wh_inline_photos / wh_inline_photo_moved / wh_inline_photo_cleared, callable only by the
--      backend (service_role), used by tools/move_inline_photos_to_storage.py - copy each inline photo to the bucket,
--      record its names, verify the object, then clear the inline text. A move is not an amendment of a closed entry.
--   6. v_logbook_truth / v_inventory_items_truth carry the two names (appended; the views keep security_invoker).
-- ============================================================================================================

BEGIN;

-- 1 -----------------------------------------------------------------------------------------------------------
ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS photo_path text,
  ADD COLUMN IF NOT EXISTS photo_thumb_path text;
ALTER TABLE public.inventory_items
  ADD COLUMN IF NOT EXISTS photo_path text,
  ADD COLUMN IF NOT EXISTS photo_thumb_path text;

-- An object name in entry-photos: <folder>/<uuid>[.t].<ext>. The folder is the uploader's auth uid (or 'legacy' for a
-- photo the move found with no owner). Image data can never be put here under a new column name.
ALTER TABLE public.logbook DROP CONSTRAINT IF EXISTS logbook_photo_names_are_object_names;
ALTER TABLE public.logbook ADD CONSTRAINT logbook_photo_names_are_object_names CHECK (
  (photo_path IS NULL OR photo_path ~ '^[A-Za-z0-9_-]{1,64}/[0-9a-f-]{36}\.(jpg|png|webp)$')
  AND (photo_thumb_path IS NULL OR photo_thumb_path ~ '^[A-Za-z0-9_-]{1,64}/[0-9a-f-]{36}\.t\.jpg$'));
ALTER TABLE public.inventory_items DROP CONSTRAINT IF EXISTS inventory_items_photo_names_are_object_names;
ALTER TABLE public.inventory_items ADD CONSTRAINT inventory_items_photo_names_are_object_names CHECK (
  (photo_path IS NULL OR photo_path ~ '^[A-Za-z0-9_-]{1,64}/[0-9a-f-]{36}\.(jpg|png|webp)$')
  AND (photo_thumb_path IS NULL OR photo_thumb_path ~ '^[A-Za-z0-9_-]{1,64}/[0-9a-f-]{36}\.t\.jpg$'));

-- The storage policy looks an object up by name on every read of it.
CREATE INDEX IF NOT EXISTS logbook_photo_path_idx         ON public.logbook (photo_path)               WHERE photo_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS logbook_photo_thumb_path_idx   ON public.logbook (photo_thumb_path)         WHERE photo_thumb_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS inventory_items_photo_path_idx ON public.inventory_items (photo_path)       WHERE photo_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS inventory_items_photo_thumb_path_idx ON public.inventory_items (photo_thumb_path) WHERE photo_thumb_path IS NOT NULL;

-- 2 -----------------------------------------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('entry-photos', 'entry-photos', false, 1048576, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO UPDATE
  SET public = false, file_size_limit = EXCLUDED.file_size_limit, allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Runs AS THE READER: the two tables' RLS decides, so this can never see more than the reader's own rows.
CREATE OR REPLACE FUNCTION public.wh_entry_photo_visible(p_name text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
  SELECT EXISTS (SELECT 1 FROM public.logbook l WHERE l.photo_path = p_name)
      OR EXISTS (SELECT 1 FROM public.logbook l WHERE l.photo_thumb_path = p_name)
      OR EXISTS (SELECT 1 FROM public.inventory_items i WHERE i.photo_path = p_name)
      OR EXISTS (SELECT 1 FROM public.inventory_items i WHERE i.photo_thumb_path = p_name);
$$;
REVOKE ALL ON FUNCTION public.wh_entry_photo_visible(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.wh_entry_photo_visible(text) TO authenticated, service_role;

-- Is one of MY uploads still named by any row (visible to me or not)? Answers only about the caller's own folder, so it
-- reveals nothing about anyone else's objects; the delete policy uses it so a client cannot pull a photo out from under
-- an entry (one in a hive they have since left, say).
CREATE OR REPLACE FUNCTION public.wh_entry_photo_named(p_name text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT auth.uid() IS NOT NULL
     AND split_part(p_name, '/', 1) = auth.uid()::text
     AND (   EXISTS (SELECT 1 FROM public.logbook l WHERE l.photo_path = p_name)
          OR EXISTS (SELECT 1 FROM public.logbook l WHERE l.photo_thumb_path = p_name)
          OR EXISTS (SELECT 1 FROM public.inventory_items i WHERE i.photo_path = p_name)
          OR EXISTS (SELECT 1 FROM public.inventory_items i WHERE i.photo_thumb_path = p_name));
$$;
REVOKE ALL ON FUNCTION public.wh_entry_photo_named(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.wh_entry_photo_named(text) TO authenticated, service_role;

-- 3 -----------------------------------------------------------------------------------------------------------
DROP POLICY IF EXISTS "entry-photos upload into own folder" ON storage.objects;
CREATE POLICY "entry-photos upload into own folder"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'entry-photos'
    AND (SELECT auth.uid()) IS NOT NULL
    AND (storage.foldername(name))[1] = (SELECT auth.uid())::text
  );

DROP POLICY IF EXISTS "entry-photos read by whoever can read the row" ON storage.objects;
CREATE POLICY "entry-photos read by whoever can read the row"
  ON storage.objects FOR SELECT TO authenticated
  USING (
    bucket_id = 'entry-photos'
    AND (SELECT auth.uid()) IS NOT NULL
    AND (owner_id = (SELECT auth.uid())::text OR public.wh_entry_photo_visible(name))
  );

DROP POLICY IF EXISTS "entry-photos owner deletes what no row names" ON storage.objects;
CREATE POLICY "entry-photos owner deletes what no row names"
  ON storage.objects FOR DELETE TO authenticated
  USING (
    bucket_id = 'entry-photos'
    AND (SELECT auth.uid()) IS NOT NULL
    AND owner_id = (SELECT auth.uid())::text
    AND NOT public.wh_entry_photo_named(name)
  );
-- No UPDATE policy: an object is written once under a fresh name and never overwritten.

-- 4 -----------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.check_inline_image_size()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_cap  integer := 1500000;   -- 1.5 MB base64 (~1.1 MB decoded): the Q5-a backstop, still held
  v_len  integer;
  v_same boolean := false;
BEGIN
  v_len := octet_length(NEW.photo);
  IF v_len IS NOT NULL AND v_len > v_cap THEN
    RAISE EXCEPTION 'Inline image too large (% bytes > % cap) for %', v_len, v_cap, TG_TABLE_NAME
      USING ERRCODE = '54000',
            HINT = 'Please use a smaller photo — images are compressed to about 700 KB before upload.';
  END IF;
  -- ★A NEW PHOTO GOES TO STORAGE (BRH 9 AB, 2026-10-21). Image data that is not already this row's stored value is
  -- refused: the page uploads the picture to entry-photos and writes its name to photo_path. Re-sending a legacy row's
  -- own photo unchanged is allowed - an UPDATE that leaves it as it was, or an upsert (its INSERT half fires first)
  -- of a row that already holds exactly this text - so a page left open across the deploy can still save its edits.
  IF NEW.photo IS NOT NULL AND NEW.photo LIKE 'data:%' THEN
    IF TG_OP = 'UPDATE' THEN
      v_same := NEW.photo IS NOT DISTINCT FROM OLD.photo;
    ELSIF TG_TABLE_NAME = 'logbook' THEN
      v_same := EXISTS (SELECT 1 FROM public.logbook l WHERE l.id = NEW.id AND l.photo = NEW.photo);
    ELSIF TG_TABLE_NAME = 'inventory_items' THEN
      v_same := EXISTS (SELECT 1 FROM public.inventory_items i WHERE i.id = NEW.id AND i.photo = NEW.photo);
    END IF;
    IF NOT v_same THEN
      -- P0001: a deliberate refusal, so a page shows this sentence as written (whWriteError) - an old page open
      -- across the deploy tells its person to reload instead of "try again", which could never work.
      RAISE EXCEPTION 'Photos are now saved separately from the entry. Reload the page and save again - what you typed is still on your screen.'
        USING ERRCODE = 'P0001',
              HINT = 'inline image data in ' || TG_TABLE_NAME || '.photo: upload it to entry-photos and write photo_path';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.check_inline_image_size() IS
  'BRH 9 AB 2026-10-21: refuses NEW inline image data in logbook/inventory_items.photo (photos live in the entry-photos bucket, the row keeps photo_path); a legacy row may re-send its own stored photo unchanged. Keeps the Q5-a 1.5 MB cap.';

-- 5 -----------------------------------------------------------------------------------------------------------
-- The rows still holding image data, for the backend's one-time move. md5 lets the move write only if the photo is
-- still the one it copied.
CREATE OR REPLACE FUNCTION public.wh_inline_photos(p_table text, p_after text DEFAULT '', p_limit integer DEFAULT 50)
RETURNS TABLE (id text, auth_uid uuid, photo text, photo_md5 text, photo_path text, photo_thumb_path text)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF p_table = 'logbook' THEN
    RETURN QUERY SELECT l.id, l.auth_uid, l.photo, md5(l.photo), l.photo_path, l.photo_thumb_path
      FROM public.logbook l WHERE l.photo LIKE 'data:%' AND l.id > coalesce(p_after, '')
      ORDER BY l.id LIMIT greatest(1, least(p_limit, 200));
  ELSIF p_table = 'inventory_items' THEN
    RETURN QUERY SELECT i.id, i.auth_uid, i.photo, md5(i.photo), i.photo_path, i.photo_thumb_path
      FROM public.inventory_items i WHERE i.photo LIKE 'data:%' AND i.id > coalesce(p_after, '')
      ORDER BY i.id LIMIT greatest(1, least(p_limit, 200));
  ELSE
    RAISE EXCEPTION 'wh_inline_photos: unknown table %', p_table USING ERRCODE = '22023';
  END IF;
END;
$$;

-- Copy step: record the names of the copied objects, keeping the inline text (so a page still running the old code
-- shows the photo until the new one is live). Writes only if the photo is still the one copied.
CREATE OR REPLACE FUNCTION public.wh_inline_photo_moved(p_table text, p_id text, p_md5 text, p_path text, p_thumb text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE n integer;
BEGIN
  IF p_table = 'logbook' THEN
    UPDATE public.logbook SET photo_path = p_path, photo_thumb_path = p_thumb
     WHERE id = p_id AND md5(photo) = p_md5 AND photo_path IS NULL;
  ELSIF p_table = 'inventory_items' THEN
    UPDATE public.inventory_items SET photo_path = p_path, photo_thumb_path = p_thumb
     WHERE id = p_id AND md5(photo) = p_md5 AND photo_path IS NULL;
  ELSE
    RAISE EXCEPTION 'wh_inline_photo_moved: unknown table %', p_table USING ERRCODE = '22023';
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
END;
$$;

-- Clear step, after the move tool has read each object back: the inline text goes, the names stay.
CREATE OR REPLACE FUNCTION public.wh_inline_photo_cleared(p_table text, p_id text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE n integer;
BEGIN
  IF p_table = 'logbook' THEN
    UPDATE public.logbook SET photo = NULL
     WHERE id = p_id AND photo LIKE 'data:%' AND photo_path IS NOT NULL AND photo_thumb_path IS NOT NULL;
  ELSIF p_table = 'inventory_items' THEN
    UPDATE public.inventory_items SET photo = NULL
     WHERE id = p_id AND photo LIKE 'data:%' AND photo_path IS NOT NULL AND photo_thumb_path IS NOT NULL;
  ELSE
    RAISE EXCEPTION 'wh_inline_photo_cleared: unknown table %', p_table USING ERRCODE = '22023';
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
END;
$$;

REVOKE ALL ON FUNCTION public.wh_inline_photos(text, text, integer)               FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.wh_inline_photo_moved(text, text, text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.wh_inline_photo_cleared(text, text)                 FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wh_inline_photos(text, text, integer)               TO service_role;
GRANT EXECUTE ON FUNCTION public.wh_inline_photo_moved(text, text, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.wh_inline_photo_cleared(text, text)                 TO service_role;

-- A move changes where the picture is kept, not what the closed entry says.
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

  -- D3 (2026-10-16): deleting or restoring a closed entry is not an amendment - its words and sign-off are
  -- untouched. trg_audit_trash_transition records it as delete / recover.
  IF (to_jsonb(NEW) - 'deleted_at' - 'deleted_by' - 'updated_at') = (to_jsonb(OLD) - 'deleted_at' - 'deleted_by' - 'updated_at') THEN
    RETURN NEW;
  END IF;

  -- BRH 9 AB (2026-10-21): the backend's one-time move of an inline photo to Storage changes only where the picture is
  -- kept. A person who replaces or removes the photo of a closed entry is still recorded (auth.uid() is theirs).
  IF auth.uid() IS NULL
     AND (to_jsonb(NEW) - 'photo' - 'photo_path' - 'photo_thumb_path' - 'updated_at')
       = (to_jsonb(OLD) - 'photo' - 'photo_path' - 'photo_thumb_path' - 'updated_at') THEN
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

-- 6 -----------------------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_logbook_truth WITH (security_invoker = true) AS
 SELECT l.id,
    l.hive_id,
    l.worker_name,
    l.created_at,
    l.closed_at,
    l.date,
    l.status,
    l.maintenance_type,
    l.category,
    l.machine,
    l.problem,
    l.action,
    l.root_cause,
    l.failure_consequence,
    l.downtime_hours,
    l.production_output,
    l.parts_used,
    l.readings_json,
    l.knowledge,
    l.tasklist_acknowledged,
    l.tasklist_note,
    l.photo,
    l.pm_completion_id,
    l.wo_state,
    l.wo_assigned_to,
    l.asset_node_id,
    n.tag AS asset_tag,
    n.name AS asset_node_name,
    n.iso_class AS asset_iso_class,
    n.criticality AS asset_criticality,
    n.location AS asset_location,
    l.maintenance_type ~* '(corrective|breakdown)'::text AS is_corrective,
    l.loto_applied,
    l.permit_reference,
    l.auth_uid,
    l.photo_path,
    l.photo_thumb_path
   FROM public.logbook l
     LEFT JOIN public.asset_nodes n ON n.id = l.asset_node_id AND n.deleted_at IS NULL
  WHERE l.deleted_at IS NULL;

CREATE OR REPLACE VIEW public.v_inventory_items_truth WITH (security_invoker = true) AS
 SELECT id,
    hive_id,
    worker_name,
    part_number,
    part_name,
    category,
    unit,
    qty_on_hand,
    min_qty,
    min_qty AS reorder_point,
    bin_location,
    linked_asset_node_ids,
    notes,
    photo,
    status,
    submitted_by,
    approved_by,
    approved_at,
    created_at,
    updated_at,
    qty_on_hand <= 0::numeric AS is_out_of_stock,
    qty_on_hand <= 0::numeric OR min_qty > 0::numeric AND qty_on_hand <= min_qty AS is_low_stock,
    min_qty > 0::numeric AND qty_on_hand <= (min_qty / 2.0) AS is_critical_low,
    lead_time_days,
    rejection_reason,
    auth_uid,
    photo_path,
    photo_thumb_path
   FROM public.inventory_items i
  WHERE deleted_at IS NULL;

COMMIT;
