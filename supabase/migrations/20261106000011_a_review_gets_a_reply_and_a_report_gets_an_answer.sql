-- ★A PARTS DEAL THAT WENT WRONG HAD NOWHERE TO GO AFTER THE FIRST WORD (2026-11-06, GJ M9 J27: "the buyer's complaint, the
-- seller's answer, the platform's decision both parties can read").
--
-- The escrow-dispute loop for parts deals was retired on 2026-08-03 (marketplace_disputes had no client writer and no
-- reader but the admin); a parts deal is settled between the two accounts. So the product's real model of "a deal went
-- wrong" is: the buyer's low review, the seller's answer to it, and the platform acting on the listing the buyer
-- reported. Walking that model found each step ended in silence:
--   1. a review could not be answered - marketplace_reviews has no reply, so a seller's side of a complaint could only
--      live off the platform;
--   2. a report reached the platform and its decision reached no one - "Report listing" files platform_feedback, the
--      founder console triages it (status, an internal note), and the person who reported it can neither read the row (admin-
--      only policies) nor is told anything;
--   3. a listing the platform removes or sends back tells its seller nothing - the reason is on their console (since
--      MK2) only if they happen to open it.
--
-- So:
--   1. marketplace_reviews gains seller_reply / seller_replied_at / seller_replied_by, written ONLY by
--      reply_to_listing_review(review, words) - the caller must own the review's listing - which pushes the reviewer.
--      The three columns are readable wherever the review is (anon included: a public review's public reply).
--   2. platform_feedback gains sender_reply - the answer TO the person who sent it, a field of its own: the founder
--      console's admin_note is labelled "internal, triage notes for yourself", so it is never shown or pushed to the
--      sender. my_feedback_outcomes(): a person reads back their own reports - subject, status, the answer, when - and
--      nothing else of the table; a status or answer change pushes the person who sent it.
--   3. a moderation decision on a listing (removed, or sent back to draft) pushes its seller with the reason.

BEGIN;

-- ── 1. a review's reply ──────────────────────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.marketplace_reviews
  ADD COLUMN IF NOT EXISTS seller_reply text,
  ADD COLUMN IF NOT EXISTS seller_replied_at timestamptz,
  ADD COLUMN IF NOT EXISTS seller_replied_by text;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'marketplace_reviews_seller_reply_len') THEN
    ALTER TABLE public.marketplace_reviews ADD CONSTRAINT marketplace_reviews_seller_reply_len
      CHECK (seller_reply IS NULL OR char_length(seller_reply) BETWEEN 2 AND 600);
  END IF;
END $$;

-- the reply is the seller's, through the function below; no client write (the reviewer's own update included) moves it
CREATE OR REPLACE FUNCTION public.tg_marketplace_reviews_pin_reply()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
BEGIN
  IF coalesce(current_setting('workhive.review_reply', true), '') = 'on' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'INSERT' THEN
    NEW.seller_reply := NULL; NEW.seller_replied_at := NULL; NEW.seller_replied_by := NULL;
  ELSE
    NEW.seller_reply := OLD.seller_reply; NEW.seller_replied_at := OLD.seller_replied_at; NEW.seller_replied_by := OLD.seller_replied_by;
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_marketplace_reviews_pin_reply ON public.marketplace_reviews;
CREATE TRIGGER trg_marketplace_reviews_pin_reply
  BEFORE INSERT OR UPDATE ON public.marketplace_reviews
  FOR EACH ROW EXECUTE FUNCTION public.tg_marketplace_reviews_pin_reply();

REVOKE ALL ON FUNCTION public.tg_marketplace_reviews_pin_reply() FROM PUBLIC, anon, authenticated;

GRANT SELECT (seller_reply, seller_replied_at, seller_replied_by) ON public.marketplace_reviews TO anon, authenticated;

CREATE OR REPLACE FUNCTION public.reply_to_listing_review(p_review_id uuid, p_reply text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_words text := NULLIF(btrim(coalesce(p_reply, '')), '');
  r record;
  v_name text;
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Sign in to answer a review.');
  END IF;
  SELECT mr.id, mr.listing_id, mr.reviewer_auth_uid, mr.reviewer_name, mr.rating, l.title, l.auth_uid AS seller_uid, l.seller_name
    INTO r
    FROM public.marketplace_reviews mr
    JOIN public.marketplace_listings l ON l.id = mr.listing_id
   WHERE mr.id = p_review_id;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'That review is no longer there.');
  END IF;
  -- only the listing's own seller answers its reviews
  IF r.seller_uid IS DISTINCT FROM auth.uid() THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Only the seller of this listing can answer its reviews.');
  END IF;
  IF v_words IS NULL OR char_length(v_words) < 2 THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Write your answer first.');
  END IF;
  v_words := left(v_words, 600);
  SELECT display_name INTO v_name FROM public.worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
  v_name := coalesce(v_name, r.seller_name, 'The seller');

  PERFORM set_config('workhive.review_reply', 'on', true);
  UPDATE public.marketplace_reviews
     SET seller_reply = v_words, seller_replied_at = now(), seller_replied_by = v_name
   WHERE id = p_review_id;
  PERFORM set_config('workhive.review_reply', '', true);

  IF r.reviewer_auth_uid IS NOT NULL AND r.reviewer_auth_uid <> auth.uid() THEN
    PERFORM public.enqueue_user_push(
      ARRAY[r.reviewer_auth_uid],
      'The seller answered your review',
      v_name || ' answered your review of "' || left(coalesce(r.title, 'their listing'), 60) || '": ' || left(v_words, 140),
      '/marketplace.html?listing=' || r.listing_id::text);
  END IF;
  RETURN jsonb_build_object('ok', true, 'by', v_name);
END;
$function$;

REVOKE ALL ON FUNCTION public.reply_to_listing_review(uuid, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.reply_to_listing_review(uuid, text) TO authenticated, service_role;

-- ── 2. a report's answer, read back and pushed ───────────────────────────────────────────────────────────────────────
ALTER TABLE public.platform_feedback ADD COLUMN IF NOT EXISTS sender_reply text;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'platform_feedback_sender_reply_len') THEN
    ALTER TABLE public.platform_feedback ADD CONSTRAINT platform_feedback_sender_reply_len
      CHECK (sender_reply IS NULL OR char_length(sender_reply) <= 1000);
  END IF;
END $$;

DROP FUNCTION IF EXISTS public.my_feedback_outcomes();
CREATE FUNCTION public.my_feedback_outcomes()
 RETURNS TABLE(id uuid, created_at timestamptz, kind text, subject text, status text, sender_reply text,
               triaged_at timestamptz, resolved_at timestamptz, updated_at timestamptz)
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT f.id, f.created_at, f.kind, f.subject, f.status, f.sender_reply, f.triaged_at, f.resolved_at, f.updated_at
    FROM public.platform_feedback f
   WHERE auth.uid() IS NOT NULL AND f.auth_uid = auth.uid()
     AND f.created_at >= now() - interval '90 days'
   ORDER BY coalesce(f.updated_at, f.created_at) DESC, f.id
   LIMIT 20;
$function$;

REVOKE ALL ON FUNCTION public.my_feedback_outcomes() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_feedback_outcomes() TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.tg_platform_feedback_tell_sender()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE v_said text;
BEGIN
  IF NEW.auth_uid IS NULL OR NEW.status = 'new' THEN
    RETURN NEW;
  END IF;
  IF NEW.status IS NOT DISTINCT FROM OLD.status AND NEW.sender_reply IS NOT DISTINCT FROM OLD.sender_reply THEN
    RETURN NEW;
  END IF;
  v_said := CASE NEW.status
              WHEN 'triaged' THEN 'WorkHive has read it'
              WHEN 'in_progress' THEN 'WorkHive is working on it'
              WHEN 'resolved' THEN 'WorkHive resolved it'
              WHEN 'wontfix' THEN 'WorkHive decided not to act on it'
              WHEN 'duplicate' THEN 'WorkHive is handling it with an earlier report'
              ELSE 'WorkHive updated it' END;
  PERFORM public.enqueue_user_push(
    ARRAY[NEW.auth_uid],
    'WorkHive answered your report',
    '"' || left(coalesce(NEW.subject, 'Your report'), 70) || '": ' || v_said || coalesce('. ' || left(NEW.sender_reply, 160), '.'),
    coalesce(NULLIF(NEW.page_url, ''), '/'));
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_platform_feedback_tell_sender ON public.platform_feedback;
CREATE TRIGGER trg_platform_feedback_tell_sender
  AFTER UPDATE OF status, sender_reply ON public.platform_feedback
  FOR EACH ROW EXECUTE FUNCTION public.tg_platform_feedback_tell_sender();

REVOKE ALL ON FUNCTION public.tg_platform_feedback_tell_sender() FROM PUBLIC, anon, authenticated;

-- ── 3. a moderated listing tells its seller ──────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.tg_marketplace_listings_tell_seller()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  IF NEW.auth_uid IS NULL OR NEW.status IS NOT DISTINCT FROM OLD.status OR NEW.status NOT IN ('removed', 'draft')
     OR NEW.moderated_at IS NOT DISTINCT FROM OLD.moderated_at OR NEW.moderated_at IS NULL THEN
    RETURN NEW;                       -- only a platform decision, never the seller's own unpublish
  END IF;
  IF auth.uid() IS NOT NULL AND auth.uid() = NEW.auth_uid THEN
    RETURN NEW;
  END IF;
  PERFORM public.enqueue_user_push(
    ARRAY[NEW.auth_uid],
    CASE WHEN NEW.status = 'removed' THEN 'Your listing was removed' ELSE 'Your listing was sent back' END,
    '"' || left(coalesce(NEW.title, 'Your listing'), 70) || '"' || coalesce(': ' || left(NEW.moderation_reason, 180), '.'),
    '/marketplace-seller.html');
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_marketplace_listings_tell_seller ON public.marketplace_listings;
CREATE TRIGGER trg_marketplace_listings_tell_seller
  AFTER UPDATE OF status ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.tg_marketplace_listings_tell_seller();

REVOKE ALL ON FUNCTION public.tg_marketplace_listings_tell_seller() FROM PUBLIC, anon, authenticated;

COMMIT;
