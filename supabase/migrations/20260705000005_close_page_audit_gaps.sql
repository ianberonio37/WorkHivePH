-- Close the 5 gaps the PER-PAGE audit (tools/quota_page_audit.py) found — feature-page
-- write tables that the table-level audit missed: alert_dismissals (alert-hub),
-- community_reactions (community), early_access_emails (landing/index), marketplace_watchlist
-- (marketplace), report_contacts (report-sender). Per-day caps + text caps, same patterns.
--
-- early_access_emails is ANON-writable (public landing page) — the highest abuse surface;
-- it's capped per-email/day AND relies on its UNIQUE(email) bound. (A global/IP ceiling for
-- fully-anon capture would need infra we don't have locally; per-email + unique is the
-- pragmatic bound here.)

BEGIN;

-- ── Per-day caps ────────────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_daily_cap_alert_dismissals ON public.alert_dismissals;
CREATE TRIGGER trg_daily_cap_alert_dismissals BEFORE INSERT ON public.alert_dismissals
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'created_at', 'actor', '200');

DROP TRIGGER IF EXISTS trg_daily_cap_community_reactions ON public.community_reactions;
CREATE TRIGGER trg_daily_cap_community_reactions BEFORE INSERT ON public.community_reactions
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'created_at', 'worker_name', '300');

DROP TRIGGER IF EXISTS trg_daily_cap_early_access ON public.early_access_emails;
CREATE TRIGGER trg_daily_cap_early_access BEFORE INSERT ON public.early_access_emails
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('20', 'signed_up_at', 'email', '20');

DROP TRIGGER IF EXISTS trg_daily_cap_mkt_watchlist ON public.marketplace_watchlist;
CREATE TRIGGER trg_daily_cap_mkt_watchlist BEFORE INSERT ON public.marketplace_watchlist
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('300', 'created_at', 'worker_name', '300');

DROP TRIGGER IF EXISTS trg_daily_cap_report_contacts ON public.report_contacts;
CREATE TRIGGER trg_daily_cap_report_contacts BEFORE INSERT ON public.report_contacts
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('100', 'created_at', 'email', '50');

-- ── Text caps ───────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.cap_alert_dismissals_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.alert_key IS NOT NULL THEN NEW.alert_key := left(NEW.alert_key, 200);  END IF;
  IF NEW.action    IS NOT NULL THEN NEW.action    := left(NEW.action,     60);  END IF;
  IF NEW.actor     IS NOT NULL THEN NEW.actor     := left(NEW.actor,      120);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_alert_dismissals_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_alert_dismissals ON public.alert_dismissals;
CREATE TRIGGER trg_text_caps_alert_dismissals BEFORE INSERT OR UPDATE ON public.alert_dismissals
  FOR EACH ROW EXECUTE FUNCTION public.cap_alert_dismissals_text();

CREATE OR REPLACE FUNCTION public.cap_community_reactions_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.emoji IS NOT NULL THEN NEW.emoji := left(NEW.emoji, 16);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_community_reactions_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_community_reactions ON public.community_reactions;
CREATE TRIGGER trg_text_caps_community_reactions BEFORE INSERT OR UPDATE ON public.community_reactions
  FOR EACH ROW EXECUTE FUNCTION public.cap_community_reactions_text();

CREATE OR REPLACE FUNCTION public.cap_early_access_emails_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.email  IS NOT NULL THEN NEW.email  := left(NEW.email,  254);  END IF;
  IF NEW.source IS NOT NULL THEN NEW.source := left(NEW.source,  60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_early_access_emails_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_early_access ON public.early_access_emails;
CREATE TRIGGER trg_text_caps_early_access BEFORE INSERT OR UPDATE ON public.early_access_emails
  FOR EACH ROW EXECUTE FUNCTION public.cap_early_access_emails_text();

CREATE OR REPLACE FUNCTION public.cap_report_contacts_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.name  IS NOT NULL THEN NEW.name  := left(NEW.name,  120);  END IF;
  IF NEW.email IS NOT NULL THEN NEW.email := left(NEW.email, 254);  END IF;
  IF NEW.label IS NOT NULL THEN NEW.label := left(NEW.label, 120);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_report_contacts_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_report_contacts ON public.report_contacts;
CREATE TRIGGER trg_text_caps_report_contacts BEFORE INSERT OR UPDATE ON public.report_contacts
  FOR EACH ROW EXECUTE FUNCTION public.cap_report_contacts_text();

COMMIT;
