-- Q3 (server half) -- Free-Tier Quota Roadmap: server-side text-field caps sweep.
-- =============================================================================
-- FREE_TIER_QUOTA_ROADMAP Phase Q3 delivers "no unbounded user text". Q0 capped the
-- logbook fields with cap_logbook_text_fields(); this extends the SAME proven pattern
-- (explicit `NEW.col := left(NEW.col, n)`, truncate-not-reject) to the other high-write
-- tables. The client `maxlength` half (UI) is applied per-surface separately.
--
-- WHY explicit per-table fns (not one generic jsonb capper): these are BEFORE INSERT OR
-- UPDATE triggers on CORE tables (inventory / PM / assets) -- a bug would break every
-- write to them. The explicit left() form is the zero-surprise, already-proven Q0 pattern
-- (no jsonb_populate_record round-trip whose type edge-cases can't be live-verified while
-- local Docker is down). Truncate keeps the useful head of an over-long paste.
--
-- SCOPE NOTE: community_posts / community_replies `content` already carry length CHECK
-- constraints from the baseline, so they are intentionally NOT re-capped here. logbook
-- keeps its bespoke Q0 cap_logbook_text_fields(). Marketplace / asset-hub text caps are
-- added in the same phase once their columns are confirmed.

BEGIN;

-- inventory_items: part_name/part_number/category/bin_location/notes
CREATE OR REPLACE FUNCTION public.cap_inventory_items_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.part_name    IS NOT NULL THEN NEW.part_name    := left(NEW.part_name,    200);  END IF;
  IF NEW.part_number  IS NOT NULL THEN NEW.part_number  := left(NEW.part_number,  100);  END IF;
  IF NEW.category     IS NOT NULL THEN NEW.category     := left(NEW.category,     100);  END IF;
  IF NEW.bin_location IS NOT NULL THEN NEW.bin_location := left(NEW.bin_location, 200);  END IF;
  IF NEW.notes        IS NOT NULL THEN NEW.notes        := left(NEW.notes,       2000);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_inventory_items_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_inv_items ON public.inventory_items;
CREATE TRIGGER trg_text_caps_inv_items BEFORE INSERT OR UPDATE ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.cap_inventory_items_text();

-- inventory_transactions: note/job_ref
CREATE OR REPLACE FUNCTION public.cap_inventory_transactions_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.note    IS NOT NULL THEN NEW.note    := left(NEW.note,    2000); END IF;
  IF NEW.job_ref IS NOT NULL THEN NEW.job_ref := left(NEW.job_ref,  200); END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_inventory_transactions_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_inv_tx ON public.inventory_transactions;
CREATE TRIGGER trg_text_caps_inv_tx BEFORE INSERT OR UPDATE ON public.inventory_transactions
  FOR EACH ROW EXECUTE FUNCTION public.cap_inventory_transactions_text();

-- pm_completions: notes
CREATE OR REPLACE FUNCTION public.cap_pm_completions_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.notes IS NOT NULL THEN NEW.notes := left(NEW.notes, 2000); END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_pm_completions_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_pm_comp ON public.pm_completions;
CREATE TRIGGER trg_text_caps_pm_comp BEFORE INSERT OR UPDATE ON public.pm_completions
  FOR EACH ROW EXECUTE FUNCTION public.cap_pm_completions_text();

-- asset_nodes (the real asset table; baseline `assets` was DROPPED in 20260512000009):
-- name/tag/location/criticality/iso_class/manufacturer/model/serial_no
CREATE OR REPLACE FUNCTION public.cap_asset_nodes_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.name         IS NOT NULL THEN NEW.name         := left(NEW.name,         200); END IF;
  IF NEW.tag          IS NOT NULL THEN NEW.tag          := left(NEW.tag,           50); END IF;
  IF NEW.location     IS NOT NULL THEN NEW.location     := left(NEW.location,     200); END IF;
  IF NEW.criticality  IS NOT NULL THEN NEW.criticality  := left(NEW.criticality,  100); END IF;
  IF NEW.iso_class    IS NOT NULL THEN NEW.iso_class    := left(NEW.iso_class,     50); END IF;
  IF NEW.manufacturer IS NOT NULL THEN NEW.manufacturer := left(NEW.manufacturer, 120); END IF;
  IF NEW.model        IS NOT NULL THEN NEW.model        := left(NEW.model,        120); END IF;
  IF NEW.serial_no    IS NOT NULL THEN NEW.serial_no    := left(NEW.serial_no,    120); END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_asset_nodes_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_asset_nodes ON public.asset_nodes;
CREATE TRIGGER trg_text_caps_asset_nodes BEFORE INSERT OR UPDATE ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.cap_asset_nodes_text();

-- marketplace_listings: title/description/location/seller_contact/seller_name/condition/category/section
-- (already daily-capped by the baseline check_listing_rate 20/day trigger; this is the text half)
CREATE OR REPLACE FUNCTION public.cap_marketplace_listings_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.title          IS NOT NULL THEN NEW.title          := left(NEW.title,          120);  END IF;
  IF NEW.description    IS NOT NULL THEN NEW.description    := left(NEW.description,    2000);  END IF;
  IF NEW.location       IS NOT NULL THEN NEW.location       := left(NEW.location,       100);  END IF;
  IF NEW.seller_contact IS NOT NULL THEN NEW.seller_contact := left(NEW.seller_contact, 100);  END IF;
  IF NEW.seller_name    IS NOT NULL THEN NEW.seller_name    := left(NEW.seller_name,    120);  END IF;
  IF NEW.condition      IS NOT NULL THEN NEW.condition      := left(NEW.condition,       40);  END IF;
  IF NEW.category       IS NOT NULL THEN NEW.category       := left(NEW.category,        60);  END IF;
  IF NEW.section        IS NOT NULL THEN NEW.section        := left(NEW.section,         60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_marketplace_listings_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_mkt_listings ON public.marketplace_listings;
CREATE TRIGGER trg_text_caps_mkt_listings BEFORE INSERT OR UPDATE ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.cap_marketplace_listings_text();

-- marketplace_inquiries: buyer_name/buyer_contact/message/seller_name/reply_text
CREATE OR REPLACE FUNCTION public.cap_marketplace_inquiries_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.buyer_name    IS NOT NULL THEN NEW.buyer_name    := left(NEW.buyer_name,    120);  END IF;
  IF NEW.buyer_contact IS NOT NULL THEN NEW.buyer_contact := left(NEW.buyer_contact, 100);  END IF;
  IF NEW.message       IS NOT NULL THEN NEW.message       := left(NEW.message,      1000);  END IF;
  IF NEW.seller_name   IS NOT NULL THEN NEW.seller_name   := left(NEW.seller_name,   120);  END IF;
  IF NEW.reply_text    IS NOT NULL THEN NEW.reply_text    := left(NEW.reply_text,   1000);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_marketplace_inquiries_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_mkt_inquiries ON public.marketplace_inquiries;
CREATE TRIGGER trg_text_caps_mkt_inquiries BEFORE INSERT OR UPDATE ON public.marketplace_inquiries
  FOR EACH ROW EXECUTE FUNCTION public.cap_marketplace_inquiries_text();

-- marketplace_sellers: messenger_username/certifications (worker_name is the identity key)
CREATE OR REPLACE FUNCTION public.cap_marketplace_sellers_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.messenger_username IS NOT NULL THEN NEW.messenger_username := left(NEW.messenger_username,  50);  END IF;
  IF NEW.certifications     IS NOT NULL THEN NEW.certifications     := left(NEW.certifications,    1000);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_marketplace_sellers_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_mkt_sellers ON public.marketplace_sellers;
CREATE TRIGGER trg_text_caps_mkt_sellers BEFORE INSERT OR UPDATE ON public.marketplace_sellers
  FOR EACH ROW EXECUTE FUNCTION public.cap_marketplace_sellers_text();

-- pm_assets: asset_name/tag_id/location/category/criticality
CREATE OR REPLACE FUNCTION public.cap_pm_assets_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.asset_name  IS NOT NULL THEN NEW.asset_name  := left(NEW.asset_name,  120); END IF;
  IF NEW.tag_id      IS NOT NULL THEN NEW.tag_id      := left(NEW.tag_id,       50); END IF;
  IF NEW.location    IS NOT NULL THEN NEW.location    := left(NEW.location,    150); END IF;
  IF NEW.category    IS NOT NULL THEN NEW.category    := left(NEW.category,     60); END IF;
  IF NEW.criticality IS NOT NULL THEN NEW.criticality := left(NEW.criticality,  40); END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_pm_assets_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_pm_assets ON public.pm_assets;
CREATE TRIGGER trg_text_caps_pm_assets BEFORE INSERT OR UPDATE ON public.pm_assets
  FOR EACH ROW EXECUTE FUNCTION public.cap_pm_assets_text();

-- pm_scope_items: item_text (frequency is controlled but capped defensively)
CREATE OR REPLACE FUNCTION public.cap_pm_scope_items_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.item_text IS NOT NULL THEN NEW.item_text := left(NEW.item_text, 250); END IF;
  IF NEW.frequency IS NOT NULL THEN NEW.frequency := left(NEW.frequency,  40); END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_pm_scope_items_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_pm_scope ON public.pm_scope_items;
CREATE TRIGGER trg_text_caps_pm_scope BEFORE INSERT OR UPDATE ON public.pm_scope_items
  FOR EACH ROW EXECUTE FUNCTION public.cap_pm_scope_items_text();

-- asset-hub RCM/FMEA (the roadmap's "asset-hub Q&A" target): free-text analysis fields.
CREATE OR REPLACE FUNCTION public.cap_rcm_fmea_modes_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.function_text      IS NOT NULL THEN NEW.function_text      := left(NEW.function_text,      500);  END IF;
  IF NEW.failure_mode       IS NOT NULL THEN NEW.failure_mode       := left(NEW.failure_mode,       500);  END IF;
  IF NEW.effect_text        IS NOT NULL THEN NEW.effect_text        := left(NEW.effect_text,        500);  END IF;
  IF NEW.cause_text         IS NOT NULL THEN NEW.cause_text         := left(NEW.cause_text,         500);  END IF;
  IF NEW.consequence_class  IS NOT NULL THEN NEW.consequence_class  := left(NEW.consequence_class,   40);  END IF;
  IF NEW.notes              IS NOT NULL THEN NEW.notes              := left(NEW.notes,             2000);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_rcm_fmea_modes_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_rcm_fmea ON public.rcm_fmea_modes;
CREATE TRIGGER trg_text_caps_rcm_fmea BEFORE INSERT OR UPDATE ON public.rcm_fmea_modes
  FOR EACH ROW EXECUTE FUNCTION public.cap_rcm_fmea_modes_text();

CREATE OR REPLACE FUNCTION public.cap_rcm_strategies_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.decision  IS NOT NULL THEN NEW.decision  := left(NEW.decision,   100);  END IF;
  IF NEW.task_text IS NOT NULL THEN NEW.task_text := left(NEW.task_text,  500);  END IF;
  IF NEW.rationale IS NOT NULL THEN NEW.rationale := left(NEW.rationale, 1000);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_rcm_strategies_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_rcm_strat ON public.rcm_strategies;
CREATE TRIGGER trg_text_caps_rcm_strat BEFORE INSERT OR UPDATE ON public.rcm_strategies
  FOR EACH ROW EXECUTE FUNCTION public.cap_rcm_strategies_text();

COMMIT;
