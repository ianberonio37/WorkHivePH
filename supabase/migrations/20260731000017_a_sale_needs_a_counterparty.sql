-- 20260731000017_a_sale_needs_a_counterparty.sql
--
-- P3 (M1/M7). THE TIER LADDER WAS FREE TO MINT, and the credit economy prices against it.
--
-- `recompute_seller_sales_and_tier` counted:
--     SELECT COUNT(*) FROM marketplace_listings WHERE seller_name = X AND status = 'sold'
-- A seller marks their OWN listing sold. No buyer appears anywhere in that path. So gold - the platform's
-- top trust badge, the one a consumer reads before handing over PHP25,000 - was 51 clicks. Silver was 11.
-- The D9 work then added tighten-only FLOORS so a hive could not lower the thresholds, which protected a
-- number that was already forgeable by the seller it was meant to describe.
--
-- TWO CHANGES, and the second is the one that matters:
--
--   1. STRUCTURAL LINK. A listing may only reach `sold` while naming the inquiry it sold through, and that
--      inquiry must belong to THAT listing. A sale now has an artefact with a counterparty on it.
--
--   2. COUNT DISTINCT COUNTERPARTIES, NOT ROWS. This is the anti-farming half. Linking alone would let a
--      seller create 51 inquiries to themselves; counting DISTINCT buyers means 51 sales to one person is
--      worth exactly one. Gold now needs 51 different buyers rather than 51 clicks - the thresholds are
--      deliberately UNCHANGED (the tighten-only CHECK requires gold >= 51 and silver >= 11, and loosening
--      them to compensate would give back exactly what this migration takes away).
--
-- THE RESIDUAL GAP, STATED PLAINLY RATHER THAN PAPERED OVER. `marketplace_inquiries` has no authenticated
-- identity: `buyer_name` and `buyer_contact` are free text, and free-text identity is a CLAIM, not a fact.
-- A determined seller can still farm by inventing distinct names. So:
--   - a nullable `buyer_auth_uid` is added now, populated whenever the inquirer is signed in, and the count
--     prefers it - a real account is worth more than a typed name;
--   - identity falls back to a NORMALISED contact (lowercased, non-digits stripped for phone-shaped
--     values), so "0995 009 2416", "09950092416" and "0995-009-2416" are ONE buyer rather than three;
--   - what remains - anonymous inquiries with invented contacts - is a DETECTION problem, not a refusal
--     one, and belongs to the fraud model (M7) as a farming signal, not to this guard.
-- Naming the residue is the point: a fix that claims to close a hole it only narrows is worse than the
-- hole, because it stops anyone looking.

alter table public.marketplace_inquiries
  add column if not exists buyer_auth_uid uuid references auth.users(id) on delete set null;

comment on column public.marketplace_inquiries.buyer_auth_uid is
  'The inquirer''s account when they were signed in. NULL for anonymous inquiries. Tier counting prefers '
  'this over the free-text buyer_name/buyer_contact, because a name is a claim and an account is not.';

alter table public.marketplace_listings
  add column if not exists sold_to_inquiry_id uuid references public.marketplace_inquiries(id);

comment on column public.marketplace_listings.sold_to_inquiry_id is
  'The inquiry this listing sold through. Required to reach status=sold: a sale must name a counterparty, '
  'or the trust tier built on it is self-minted.';

-- ---------------------------------------------------------------------------------------------------
-- The refusal. A SEPARATE guard: `guard_marketplace_listing_status` is one of the four mutation-scored
-- guards and rebuilding it from a partial read is how a working rule gets silently dropped.
-- ---------------------------------------------------------------------------------------------------
create or replace function public.guard_listing_sale_needs_counterparty()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  v_listing uuid;
BEGIN
  IF new.status <> 'sold' THEN
    RETURN new;
  END IF;
  -- Backend / seeder writes (no JWT) are already vetted, matching the parity rule the sibling listing
  -- guards use. Without this, every seeder and system trigger would have to invent an inquiry.
  IF auth.uid() IS NULL THEN
    RETURN new;
  END IF;

  IF new.sold_to_inquiry_id IS NULL THEN
    RAISE EXCEPTION
      'A sale needs a buyer: link the inquiry this listing sold through before marking it sold'
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT listing_id INTO v_listing
    FROM public.marketplace_inquiries WHERE id = new.sold_to_inquiry_id;

  IF v_listing IS NULL THEN
    RAISE EXCEPTION 'The linked inquiry does not exist' USING ERRCODE = 'check_violation';
  END IF;

  -- Without this an inquiry from ONE listing could be reused to "sell" every other listing the seller
  -- owns - the link would exist and mean nothing, which is the failure this migration is about.
  IF v_listing <> new.id THEN
    RAISE EXCEPTION 'That inquiry belongs to a different listing' USING ERRCODE = 'check_violation';
  END IF;

  RETURN new;
END
$$;

drop trigger if exists trg_guard_listing_sale_needs_counterparty on public.marketplace_listings;
create trigger trg_guard_listing_sale_needs_counterparty
  before insert or update of status on public.marketplace_listings
  for each row execute function public.guard_listing_sale_needs_counterparty();

-- ---------------------------------------------------------------------------------------------------
-- The count. Preserved verbatim from the shipped version except the sold-count query and its comment:
-- the hive resolution, the knob reads, the tier CASE, the system-write announcement and the
-- IS DISTINCT FROM guard on the UPDATE are unchanged.
-- ---------------------------------------------------------------------------------------------------
create or replace function public.recompute_seller_sales_and_tier(p_seller_name text)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  v_sold   integer;
  v_hive   uuid;
  v_silver integer;
  v_gold   integer;
  v_tier   text;
BEGIN
  IF p_seller_name IS NULL OR btrim(p_seller_name) = '' THEN RETURN; END IF;

  -- DISTINCT COUNTERPARTIES, not rows. Identity prefers a real account; falls back to a normalised
  -- contact so the same phone written three ways is one buyer; falls back to the typed name last.
  -- A sold listing with no linked inquiry (a legacy row, or a vetted backend write) still counts once
  -- under its own id rather than being silently dropped - shrinking the numerator would punish sellers
  -- for a schema change they did not make.
  SELECT COUNT(DISTINCT COALESCE(
           i.buyer_auth_uid::text,
           NULLIF(regexp_replace(lower(coalesce(i.buyer_contact, '')), '[^a-z0-9@.]', '', 'g'), ''),
           NULLIF(lower(btrim(coalesce(i.buyer_name, ''))), ''),
           'listing:' || l.id::text
         ))::integer
    INTO v_sold
    FROM public.marketplace_listings l
    LEFT JOIN public.marketplace_inquiries i ON i.id = l.sold_to_inquiry_id
   WHERE l.seller_name = p_seller_name AND l.status = 'sold';

  -- The seller's OWN hive sets the bar. A seller with no hive resolves to the platform ladder, which is
  -- what service_knob() returns for an unknown hive, so the solo path needs no special case.
  SELECT hive_id INTO v_hive FROM public.marketplace_sellers WHERE worker_name = p_seller_name;
  v_silver := public.service_knob(v_hive, 'tier_silver_sales');
  v_gold   := public.service_knob(v_hive, 'tier_gold_sales');

  v_tier := CASE WHEN v_sold >= v_gold   THEN 'gold'
                 WHEN v_sold >= v_silver THEN 'silver'
                 ELSE 'bronze' END;

  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce to the trust guard

  UPDATE public.marketplace_sellers
     SET total_sales = v_sold,
         tier = v_tier,
         updated_at = now()
   WHERE worker_name = p_seller_name
     AND (total_sales IS DISTINCT FROM v_sold OR tier IS DISTINCT FROM v_tier);
END
$$;

comment on function public.recompute_seller_sales_and_tier(text) is
  'Recomputes a seller''s sales and tier from DISTINCT confirmed counterparties. Counting rows made gold '
  '51 self-marked clicks; counting buyers makes 51 sales to one person worth one. Residual: anonymous '
  'inquiries carry free-text identity, so farming by invented contacts is a DETECTION problem (M7).';
