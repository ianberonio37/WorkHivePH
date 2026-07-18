-- Q5-a (2026-07-05): base64-in-row DETECTOR-GUARD (the DEMOTED blob-offload).
--
-- GROUNDED (Step 0): the earlier roadmap called photo blob-offload the #1 scale lever on an
-- ASSUMPTION. Measured reality: photo attach-rate = 0% (0/3,705 logbook rows; inventory photo
-- col = empty string). So a full Storage-offload pipeline is speculative right-now. The
-- right-sized move is a DETECTOR-GUARD:
--   (1) a SERVER-SIDE size cap on the inline base64 photo columns (logbook.photo,
--       inventory_items.photo) — a backstop to the client's <=700 KB compression so a client
--       bypass can't stuff a multi-MB base64 image into a row (1 such photo ~= a user's whole
--       ~50 KB DB budget at 10k). marketplace_listings.image_url is already a URL reference
--       (the CORRECT pattern) — not inline — so it needs no guard.
--   (2) attach-rate TELEMETRY (photo_attach_stats()) — the signal that tells us WHEN photos
--       actually start landing, i.e. when to build the full Storage-offload pipeline. Until
--       that rate climbs, the full pipeline stays deferred (measured, not guessed).
--
-- Cap = 1.5 MB of base64. A legitimate <=700 KB compressed image is ~930 KB as a base64 data
-- URL, so 1.5 MB passes every honest photo and blocks only genuinely oversized/bypass inputs.

CREATE OR REPLACE FUNCTION public.check_inline_image_size()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_cap  integer := 1500000;   -- 1.5 MB base64 (~1.1 MB decoded); honest photos are ~930 KB
  v_len  integer;
BEGIN
  -- Both guarded tables expose the column as `photo` (text, base64 data URL).
  v_len := octet_length(NEW.photo);
  IF v_len IS NOT NULL AND v_len > v_cap THEN
    RAISE EXCEPTION 'Inline image too large (% bytes > % cap) for %', v_len, v_cap, TG_TABLE_NAME
      USING ERRCODE = '54000',
            HINT = 'Please use a smaller photo — images are compressed to about 700 KB before upload.';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_inline_image_size_logbook ON public.logbook;
CREATE TRIGGER trg_inline_image_size_logbook
  BEFORE INSERT OR UPDATE OF photo ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.check_inline_image_size();

DROP TRIGGER IF EXISTS trg_inline_image_size_inventory ON public.inventory_items;
CREATE TRIGGER trg_inline_image_size_inventory
  BEFORE INSERT OR UPDATE OF photo ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.check_inline_image_size();

-- Attach-rate telemetry: the decision signal for building the full Storage-offload pipeline.
-- When with_photo_pct or avg_photo_kb climbs materially, photos are binding the DB budget ->
-- build the offload. Until then it stays deferred (measured, not assumed).
CREATE OR REPLACE FUNCTION public.photo_attach_stats()
RETURNS TABLE(tbl text, total bigint, with_photo bigint, with_photo_pct numeric, avg_photo_kb numeric)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT 'logbook'::text, count(*),
         count(*) FILTER (WHERE coalesce(octet_length(photo),0) > 0),
         round(100.0 * count(*) FILTER (WHERE coalesce(octet_length(photo),0) > 0) / NULLIF(count(*),0), 2),
         round(avg(octet_length(photo)) FILTER (WHERE coalesce(octet_length(photo),0) > 0) / 1024.0, 1)
    FROM public.logbook
  UNION ALL
  SELECT 'inventory_items', count(*),
         count(*) FILTER (WHERE coalesce(octet_length(photo),0) > 0),
         round(100.0 * count(*) FILTER (WHERE coalesce(octet_length(photo),0) > 0) / NULLIF(count(*),0), 2),
         round(avg(octet_length(photo)) FILTER (WHERE coalesce(octet_length(photo),0) > 0) / 1024.0, 1)
    FROM public.inventory_items;
$$;

GRANT EXECUTE ON FUNCTION public.photo_attach_stats() TO authenticated, service_role;

COMMENT ON FUNCTION public.check_inline_image_size() IS
  'Q5-a 2026-07-05: server-side size backstop for inline base64 photo columns (logbook/inventory_items). Blocks >1.5MB base64 — a client-bypass guard, not the honest-photo path. Full Storage-offload stays deferred until photo_attach_stats() shows attach-rate climbing.';
