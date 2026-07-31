-- 20260731000011_credit_policy_knobs.sql
--
-- CREDIT-POLICY KNOBS (MARKETPLACE_CREDIT_ECONOMY.md §7.1). Ian proposed a 5% listing fee + 1% consumer
-- cashback; the refinement argues for charging on COMPLETION instead, because a listing fee costs the
-- provider 5% / sell-through and a young marketplace has low sell-through by definition.
--
-- THAT TIMING DECISION IS IAN'S AND IS NOT PRE-EMPTED HERE. This migration ships only what is true under
-- EITHER model, so his version is a config change rather than a rebuild:
--   * commission_pct   — charged on VERIFIED COMPLETION (the roadmap §5 model). Default 5.
--   * listing_fee_pct  — charged at LISTING (Ian's proposal). Default 0 = OFF. Set it to 5 and his model is
--                        live without touching schema or code.
--   * cashback_pct     — consumer cashback on verified completion. Default 1, exactly as proposed.
--   * min_list_balance — credits a provider must HOLD to publish. This is the instrument that gets the float
--                        in early WITHOUT taxing an empty catalogue (roadmap §5's Grab PH precedent).
--
-- Both fee knobs can be live at once, so a hybrid (a small listing fee plus a smaller commission) is
-- expressible too. Nothing here decides the policy; it makes the policy sayable.
--
-- CEILINGS, NOT FLOORS, and the direction is deliberate. The D9 trust knobs are tighten-only because a hive
-- lowering a trust bar forges reputation. These are the mirror case: the risk is a hive (or a mistake)
-- setting a CONFISCATORY rate, so each is capped. 30% is well above any plausible take and far below
-- anything that could quietly eat a provider's earnings.

ALTER TABLE public.hive_service_settings
  ADD COLUMN IF NOT EXISTS commission_pct    numeric(5,2) NOT NULL DEFAULT 5.00
    CHECK (commission_pct   BETWEEN 0 AND 30),
  ADD COLUMN IF NOT EXISTS listing_fee_pct   numeric(5,2) NOT NULL DEFAULT 0.00
    CHECK (listing_fee_pct  BETWEEN 0 AND 30),
  ADD COLUMN IF NOT EXISTS cashback_pct      numeric(5,2) NOT NULL DEFAULT 1.00
    CHECK (cashback_pct     BETWEEN 0 AND 30),
  ADD COLUMN IF NOT EXISTS min_list_balance  integer      NOT NULL DEFAULT 0
    CHECK (min_list_balance BETWEEN 0 AND 100000);

-- THE PLATFORM MUST NOT PAY OUT MORE THAN IT TAKES IN. Cashback is funded from the take, so a policy where
-- cashback exceeds commission + listing fee mints credits the platform never earned - a slow, silent
-- insolvency that would look like generosity on every individual transaction.
ALTER TABLE public.hive_service_settings
  DROP CONSTRAINT IF EXISTS hive_service_settings_cashback_funded;
ALTER TABLE public.hive_service_settings
  ADD CONSTRAINT hive_service_settings_cashback_funded
  CHECK (cashback_pct <= commission_pct + listing_fee_pct);

COMMENT ON COLUMN public.hive_service_settings.commission_pct IS
  'Percent of a completed job taken as credits on VERIFIED completion (roadmap §5 model). Default 5.';
COMMENT ON COLUMN public.hive_service_settings.listing_fee_pct IS
  'Percent of listing price charged in credits AT LISTING (Ian 2026-07-31). Default 0 = OFF. Set to 5 to run '
  'the listing-fee model; see MARKETPLACE_CREDIT_ECONOMY.md §2 for why the effective rate is fee/sell-through.';
COMMENT ON COLUMN public.hive_service_settings.cashback_pct IS
  'Percent returned to the CONSUMER as non-withdrawable credits on verified completion. Default 1.';
COMMENT ON COLUMN public.hive_service_settings.min_list_balance IS
  'Credits a provider must HOLD to publish - the float-without-a-tax instrument (Grab PH precedent). 0 = off.';
