-- 20260730000003_admin_bypass_only_for_non_parties.sql
--
-- SECURITY · the self-deal class, found in FOUR MORE GUARDS after being fixed in a fifth.
--
-- On 2026-07-29, mig 20260729000003 fixed `guard_service_review`: `is_marketplace_admin()` early-
-- returned BEFORE any party check, so an identity that was both admin AND the matched provider could
-- author the CLIENT's 5-star review of its OWN completed job — a self-minted rating and, at 25 jobs +
-- 4.5 stars, a self-minted GOLD tier with broadcast priority. The fix was one sentence: **the admin
-- bypass applies only when the admin is NOT a party to the row.**
--
-- That fix was applied to the ONE guard the live probe happened to walk. The identical unqualified
-- bypass was left standing in all four STATUS-MACHINE guards, and each one defeats an invariant its own
-- comments state out loud. Found 2026-07-30 by the marketplace test bank: teaching the SQL runner the
-- `anon` partition made `admin` the next unexecuted partition, and reading the guard to mint an admin
-- identity is what surfaced the bypass ([[feedback_cross_page_sibling_sweep_and_registration]] — grep a
-- fix's pattern platform-wide; this is the cost of not doing that in July).
--
-- PROVEN, not reasoned. A rolled-back probe minted an identity that is both a platform admin (via
-- `marketplace_platform_admins.worker_name IN auth_worker_names()`) and the matched provider on a
-- completed job, then fired `completed -> settled`:
--
--     RESULT is_admin=t
--     RESULT provider_admin_settles_own_job_rows=1        <-- the client's own "I paid" confirmation
--
-- `completed -> settled` is reserved for `v_is_client` and fires `trg_mint_settlement_commission`
-- (mig 47). So a provider-admin confirmed their own payment and minted their own commission.
--
-- THE FOUR HOLES, each against the guard's own words:
--
--   guard_service_request_status   "(v_is_client and old.status='completed' and new.status='settled')
--                                   -- P6: the client confirms they paid"
--                                  -> a provider-admin settles their OWN job and mints the commission.
--
--   guard_service_topup_status     the admin branch MINTS the ledger credit inline on
--                                  pending_verification -> verified.
--                                  -> an admin who is the PAYER verifies their OWN GCash top-up:
--                                     credits created from a `gcash_ref` nobody checked. Ian's rule
--                                     that credits are non-withdrawable limits the damage to service
--                                     access rather than cash-out; it does not make self-minting money
--                                     acceptable, and the founder is the person paying for the AI those
--                                     credits buy.
--
--   guard_marketplace_order_status "'released' fires the total_sales / tier bump; 'refunded' reverses a
--                                   payment — neither may be self-assigned by a buyer or seller"
--                                  -> a seller-admin self-releases (self-minted sales count and tier,
--                                     the exact trust-counter forgery [[feedback_marketplace_trust_
--                                     forge_verified_only]] exists to prevent) or self-refunds.
--
--   guard_marketplace_listing_status "a listing goes live only after WorkHive review, not by
--                                     self-publishing"
--                                  -> a seller-admin publishes their own listing unreviewed.
--
-- THE FIX, identical in all four and identical to mig 53: the bypass is gated on `NOT <is a party>`.
-- An admin who is NOT a party keeps every moderation power — dispute resolution, manual release and
-- refund, publishing someone else's listing, verifying someone else's top-up. An admin who IS a party
-- simply falls through to the ordinary party rules, which is the correct answer: acting on your own job
-- makes you a provider, not a moderator. Backend/service-role writes (`auth.uid() IS NULL`) and the
-- announced GUC system-write paths are untouched — they were never the hole.
--
-- WHY NOT "just trust the admins". There are two platform admins today and one of them is the founder,
-- who also sells services — so the exploit identity is not hypothetical, it is the normal shape of a
-- small marketplace. The same reasoning applied in July: *any founder/moderator who also sells services
-- would be in production.* A guard that is correct only while the admin behaves is not a guard.
--
-- Every function keeps its SECURITY DEFINER / search_path exactly as found; only the bypass predicate
-- changes. Idempotent: CREATE OR REPLACE.

-- ---------------------------------------------------------------------------------------------------
-- 1. service_requests — the settlement commission path
-- ---------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guard_service_request_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, extensions
AS $fn$
declare
  v_is_client boolean;
  v_is_matched_provider boolean;
  v_is_party boolean;
  v_legal boolean := false;
begin
  -- THE ONLY LOGIC CHANGE IN THIS FUNCTION: party-ness is computed BEFORE the bypass, and the admin
  -- bypass is gated on NOT being a party. Everything from the bypass down is byte-identical to the
  -- version this replaces — deliberately. My first draft of this migration was reconstructed from a
  -- PARTIAL read of the original and silently lost three real rules: the hive-provider branch of
  -- v_is_matched_provider, the "a new request cannot be born matched" refusal, and BOTH the
  -- matched_provider_id and client_auth_uid reassignment refusals. A security fix that quietly deletes
  -- three other security rules is a net loss. Read the whole function, then change one line
  -- ([[feedback_redesign_scope_whole_page_not_component]], applied to a function instead of a page).
  --
  -- On INSERT there is no OLD row, so party-ness reads NEW. The provider test mirrors the UPDATE-path
  -- one below EXACTLY, hive branch included: a hive provider profile is acted for by any active member
  -- of that hive, so an admin who is such a member is a party even though sp.auth_uid is not theirs.
  v_is_party := (coalesce(old.client_auth_uid, new.client_auth_uid) = auth.uid())
             or exists (
                  select 1 from public.service_providers sp
                  where sp.id = coalesce(old.matched_provider_id, new.matched_provider_id)
                    and (sp.auth_uid = auth.uid()
                         or (sp.provider_type = 'hive' and sp.hive_id in (
                               select hm.hive_id from public.hive_members hm
                               where hm.auth_uid = auth.uid() and hm.status = 'active'))));

  -- backend writes (no JWT: seeders, system sweeps) are vetted — allow.
  -- (journaling lives in the AFTER trigger journal_service_request — an AFTER-INSERT
  --  journal from a BEFORE trigger FK-fails because the request row doesn't exist yet;
  --  caught live by the P1 adversarial suite.)
  -- The admin bypass applies ONLY to a NON-party: moderating someone else's job is moderation,
  -- advancing your own is self-dealing (mig 20260729000003, same fix, sibling guard).
  if auth.uid() is null
     or (public.is_marketplace_admin() and not v_is_party)
     or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  -- ---- raw authenticated client from here ----
  if TG_OP = 'INSERT' then
    if new.status not in ('requested','broadcasting') then
      raise exception 'Not allowed: a new service request must start as requested/broadcasting (status % is system-set)', new.status
        using errcode = 'check_violation';
    end if;
    if new.client_auth_uid is distinct from auth.uid() then
      raise exception 'Not allowed: client_auth_uid must be the caller (attribution)' using errcode = 'check_violation';
    end if;
    if new.matched_provider_id is not null then
      raise exception 'Not allowed: a new request cannot be born matched' using errcode = 'check_violation';
    end if;
    return new;
  end if;

  -- UPDATE: who is the caller relative to this request?
  v_is_client := (old.client_auth_uid = auth.uid());
  v_is_matched_provider := exists (
    select 1 from public.service_providers sp
    where sp.id = old.matched_provider_id
      and (sp.auth_uid = auth.uid()
           or (sp.provider_type = 'hive' and sp.hive_id in (
                 select hm.hive_id from public.hive_members hm
                 where hm.auth_uid = auth.uid() and hm.status = 'active')))
  );

  if new.status is distinct from old.status then
    -- the accept transition (broadcasting→accepted) is RPC-only (atomic, GUC-announced) — never a raw client write.
    v_legal :=
         (v_is_client and old.status = 'requested'    and new.status = 'broadcasting')
      or (v_is_client and old.status = 'completed'    and new.status = 'settled')  -- P6: the client confirms they paid (mig 47 mints the commission)
      or (v_is_client and old.status in ('requested','broadcasting','accepted','en_route','on_site')
                      and new.status = 'cancelled_by_client')
      or (v_is_matched_provider and old.status = 'accepted'    and new.status = 'en_route')
      or (v_is_matched_provider and old.status = 'en_route'    and new.status = 'on_site')
      or (v_is_matched_provider and old.status = 'on_site'     and new.status = 'in_progress')
      or (v_is_matched_provider and old.status = 'in_progress' and new.status = 'completed')
      or (v_is_matched_provider and old.status in ('accepted','en_route','on_site')
                      and new.status = 'cancelled_by_provider')
      or ((v_is_client or v_is_matched_provider) and old.status in ('in_progress','completed')
                      and new.status = 'disputed');
    if not v_legal then
      raise exception 'Not allowed: illegal service request transition % -> % for this caller', old.status, new.status
        using errcode = 'check_violation';
    end if;
  elsif not (v_is_client or v_is_matched_provider) then
    raise exception 'Not allowed: only the request''s client or matched provider may edit it' using errcode = 'check_violation';
  end if;

  -- clients/providers may not reassign matching or identity fields directly
  if new.matched_provider_id is distinct from old.matched_provider_id then
    raise exception 'Not allowed: matching is set by the accept/select RPC, not a direct write' using errcode = 'check_violation';
  end if;
  if new.client_auth_uid is distinct from old.client_auth_uid then
    raise exception 'Not allowed: request ownership cannot be reassigned' using errcode = 'check_violation';
  end if;

  return new;
end
$fn$;

-- ---------------------------------------------------------------------------------------------------
-- 2. service_credit_topups — the credit-minting path
-- ---------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guard_service_topup_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
declare
  v_is_party boolean;
begin
  -- A party to a top-up is the person who says they paid, OR the account the credit lands in. Both
  -- matter: verifying a top-up you filed is self-minting, and so is verifying someone else's top-up
  -- into your own provider account.
  v_is_party := (coalesce(old.payer_auth_uid, new.payer_auth_uid) = auth.uid())
             or (coalesce(old.account_type, new.account_type) = 'provider'
                 and coalesce(old.account_id, new.account_id)
                     in (select id from public.service_providers where auth_uid = auth.uid()))
             or (coalesce(old.account_type, new.account_type) = 'consumer'
                 and coalesce(old.account_id, new.account_id) = auth.uid());

  if auth.uid() is null
     or (public.is_marketplace_admin() and not v_is_party)
     or current_setting('workhive.service_system_write', true) = 'on' then
    -- a verification mints the ledger entry exactly once
    if TG_OP = 'UPDATE' and new.status = 'verified' and old.status = 'pending_verification' then
      new.verified_by := coalesce(new.verified_by, auth.uid());
      new.verified_at := coalesce(new.verified_at, now());
      insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
      values (new.account_type, new.account_id, 'topup', new.amount, 'topup', new.id, 'GCash ref ' || new.gcash_ref);
    end if;
    return new;
  end if;
  -- raw client: may only file a PENDING intake row for themself
  if TG_OP = 'INSERT' then
    if new.status <> 'pending_verification' then
      raise exception 'Not allowed: a top-up starts pending_verification (the founder verifies it)' using errcode = 'check_violation';
    end if;
    if new.payer_auth_uid is distinct from auth.uid() then
      raise exception 'Not allowed: payer_auth_uid must be the caller' using errcode = 'check_violation';
    end if;
    return new;
  end if;
  raise exception 'Not allowed: top-up verification is founder/admin-only, and never on a top-up you are a party to' using errcode = 'check_violation';
end
$fn$;

-- ---------------------------------------------------------------------------------------------------
-- 3. marketplace_orders — the total_sales / tier bump and the refund path
-- ---------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guard_marketplace_order_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  v_is_party boolean;
BEGIN
  -- Buyer and seller are free-text worker names on this table, so party-ness is resolved the way the
  -- app resolves identity everywhere else: auth_worker_names() maps auth.uid() through
  -- hive_members / marketplace_sellers ([[feedback_free_text_identity_is_a_claim]] — the NAME is a
  -- claim, the mapping is the proof).
  v_is_party := (coalesce(OLD.buyer_name,  NEW.buyer_name)  IN (SELECT public.auth_worker_names()))
             OR (coalesce(OLD.seller_name, NEW.seller_name) IN (SELECT public.auth_worker_names()));

  -- service-role / backend writes (no JWT: seeders, escrow edge fns) are already vetted — allow.
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- marketplace admins may drive any transition (dispute resolution, manual release/refund) — on an
  -- order they are NOT a party to. On their own order they are a buyer or a seller like anyone else,
  -- because 'released' fires the total_sales / tier bump and 'refunded' reverses a payment.
  IF public.is_marketplace_admin() AND NOT v_is_party THEN RETURN NEW; END IF;
  -- a future release/refund RPC or edge fn announces itself for the duration of its transaction.
  IF current_setting('workhive.order_system_write', true) = 'on' THEN RETURN NEW; END IF;

  -- ---- from here: a raw authenticated (buyer/seller) client ----
  -- A client may NOT create an order already in a privileged/terminal state.
  IF TG_OP = 'INSERT' AND NEW.status <> 'pending_payment' THEN
    RAISE EXCEPTION 'Not allowed: a new order must start as pending_payment (status % is set by the escrow system)', NEW.status
      USING ERRCODE = 'check_violation';
  END IF;

  -- The trust-bearing terminal states are backend-only. 'released' fires the total_sales / tier bump;
  -- 'refunded' reverses a payment — neither may be self-assigned by a buyer or seller.
  IF TG_OP = 'UPDATE' AND NEW.status IN ('released', 'refunded') AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'Not allowed: order status % is set by the WorkHive escrow system, not by a buyer or seller', NEW.status
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END;
$fn$;

-- ---------------------------------------------------------------------------------------------------
-- 4. marketplace_listings — the review-gated publish
-- ---------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guard_marketplace_listing_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  v_is_party boolean;
BEGIN
  v_is_party := coalesce(OLD.seller_name, NEW.seller_name) IN (SELECT public.auth_worker_names());

  -- service-role / backend writes (no JWT: seeders, edge fns, any system trigger) are
  -- already vetted -- allow. (Parity with guard_marketplace_seller_trust_columns.)
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- platform admins publish / moderate -- OTHER PEOPLE's listings. Reviewing your own is not review,
  -- and 'a listing goes live only after WorkHive review' is exactly the sentence the old bypass broke.
  IF public.is_marketplace_admin() AND NOT v_is_party THEN RETURN NEW; END IF;
  -- a system write announced itself this transaction (future auto-approve path) -- allow.
  IF current_setting('workhive.listing_system_write', true) = 'on' THEN RETURN NEW; END IF;

  -- Block a NON-ADMIN from transitioning a listing INTO 'published' (self-approval).
  -- A seller MAY keep editing (status stays 'draft'), withdraw ('removed'), or mark
  -- 'sold' on their OWN listing (RLS already scopes to owner) -- but going LIVE is an
  -- admin/review-gated transition, never self-served. On INSERT there is no OLD row,
  -- so any non-admin insert that arrives already-published is blocked outright.
  IF NEW.status = 'published'
     AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'published') THEN
    RAISE EXCEPTION 'Not allowed: a listing goes live only after WorkHive review, not by self-publishing'
      USING ERRCODE = '42501';
  END IF;

  RETURN NEW;
END;
$fn$;
