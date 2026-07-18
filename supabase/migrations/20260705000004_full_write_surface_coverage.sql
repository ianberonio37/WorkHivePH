-- Q2/Q3 COMPLETION -- comprehensive coverage of EVERY user-writable production table.
-- =====================================================================================
-- A full write-surface audit (grep every .insert/.upsert across all live pages, then
-- classify each table by hive_id/timestamp/text) found the roadmap + Q3-scan had left a
-- whole cluster UNCAPPED: the project-manager tables, engineering_calcs, skill-matrix,
-- dayplanner schedule_items, resume_documents/versions, worker_profiles, and staging
-- tables. This migration closes that gap: per-day caps on the FLOODABLE tables + text
-- caps on their free-text. (System/audit tables — hive_audit_log, cmms_audit_log — and
-- controlled/rare tables — hives, hive_members, api_keys, integration_configs — are
-- intentionally excluded: they're system-generated or admin-gated, not user-floodable.)
--
-- Relies on check_daily_row_cap (Q2), now generic over hive_id (reads it via jsonb) so it
-- also works on the SOLO tables that have no hive_id column (identity-only cap).

BEGIN;

-- ── Per-day caps (check_daily_row_cap: cap, ts_col, identity_col, user_cap) ──────────
-- Project-manager cluster (all hive_id + created_at):
DROP TRIGGER IF EXISTS trg_daily_cap_projects ON public.projects;
CREATE TRIGGER trg_daily_cap_projects BEFORE INSERT ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('100', 'created_at', 'worker_name', '40');

DROP TRIGGER IF EXISTS trg_daily_cap_project_items ON public.project_items;
CREATE TRIGGER trg_daily_cap_project_items BEFORE INSERT ON public.project_items
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('300', 'created_at', 'owner_name', '150');

DROP TRIGGER IF EXISTS trg_daily_cap_project_links ON public.project_links;
CREATE TRIGGER trg_daily_cap_project_links BEFORE INSERT ON public.project_links
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('300', 'created_at', '', '300');

DROP TRIGGER IF EXISTS trg_daily_cap_project_progress ON public.project_progress_logs;
CREATE TRIGGER trg_daily_cap_project_progress BEFORE INSERT ON public.project_progress_logs
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('300', 'created_at', 'reported_by', '150');

DROP TRIGGER IF EXISTS trg_daily_cap_project_co ON public.project_change_orders;
CREATE TRIGGER trg_daily_cap_project_co BEFORE INSERT ON public.project_change_orders
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('100', 'created_at', 'requested_by', '50');

-- Engineering calc saves (hive_id + created_at):
DROP TRIGGER IF EXISTS trg_daily_cap_eng_calcs ON public.engineering_calcs;
CREATE TRIGGER trg_daily_cap_eng_calcs BEFORE INSERT ON public.engineering_calcs
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('200', 'created_at', 'worker_name', '80');

-- Resume documents (hive_id + created_at):
DROP TRIGGER IF EXISTS trg_daily_cap_resume_docs ON public.resume_documents;
CREATE TRIGGER trg_daily_cap_resume_docs BEFORE INSERT ON public.resume_documents
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('50', 'created_at', 'worker_name', '20');

-- Solo tables (NO hive_id → identity-only cap via the generic fn's jsonb hive read):
DROP TRIGGER IF EXISTS trg_daily_cap_schedule_items ON public.schedule_items;
CREATE TRIGGER trg_daily_cap_schedule_items BEFORE INSERT ON public.schedule_items
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('300', 'created_at', 'worker_name', '300');

DROP TRIGGER IF EXISTS trg_daily_cap_skill_exams ON public.skill_exam_attempts;
CREATE TRIGGER trg_daily_cap_skill_exams BEFORE INSERT ON public.skill_exam_attempts
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('50', 'attempted_at', 'worker_name', '50');

DROP TRIGGER IF EXISTS trg_daily_cap_resume_versions ON public.resume_versions;
CREATE TRIGGER trg_daily_cap_resume_versions BEFORE INSERT ON public.resume_versions
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('200', 'created_at', 'auth_uid', '200');

-- Remaining feature-page write tables (pm-scheduler, asset-hub/logbook knowledge, skill-matrix):
DROP TRIGGER IF EXISTS trg_daily_cap_pm_assets ON public.pm_assets;
CREATE TRIGGER trg_daily_cap_pm_assets BEFORE INSERT ON public.pm_assets
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('200', 'created_at', 'worker_name', '80');

DROP TRIGGER IF EXISTS trg_daily_cap_pm_scope ON public.pm_scope_items;
CREATE TRIGGER trg_daily_cap_pm_scope BEFORE INSERT ON public.pm_scope_items
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'created_at', '', '200');

DROP TRIGGER IF EXISTS trg_daily_cap_fault_knowledge ON public.fault_knowledge;
CREATE TRIGGER trg_daily_cap_fault_knowledge BEFORE INSERT ON public.fault_knowledge
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('500', 'created_at', 'worker_name', '200');

DROP TRIGGER IF EXISTS trg_daily_cap_skill_badges ON public.skill_badges;
CREATE TRIGGER trg_daily_cap_skill_badges BEFORE INSERT ON public.skill_badges
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('50', 'earned_at', 'worker_name', '50');

-- ── Text caps (explicit left() per table — the safe Q0 pattern) ──────────────────────
CREATE OR REPLACE FUNCTION public.cap_projects_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.name         IS NOT NULL THEN NEW.name         := left(NEW.name,         200);  END IF;
  IF NEW.description  IS NOT NULL THEN NEW.description  := left(NEW.description,  2000);  END IF;
  IF NEW.project_code IS NOT NULL THEN NEW.project_code := left(NEW.project_code,  100);  END IF;
  IF NEW.owner_name   IS NOT NULL THEN NEW.owner_name   := left(NEW.owner_name,    120);  END IF;
  IF NEW.project_type IS NOT NULL THEN NEW.project_type := left(NEW.project_type,   60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_projects_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_projects ON public.projects;
CREATE TRIGGER trg_text_caps_projects BEFORE INSERT OR UPDATE ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.cap_projects_text();

CREATE OR REPLACE FUNCTION public.cap_project_items_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.title      IS NOT NULL THEN NEW.title      := left(NEW.title,      200);  END IF;
  IF NEW.notes      IS NOT NULL THEN NEW.notes      := left(NEW.notes,     2000);  END IF;
  IF NEW.wbs_code   IS NOT NULL THEN NEW.wbs_code   := left(NEW.wbs_code,   100);  END IF;
  IF NEW.owner_name IS NOT NULL THEN NEW.owner_name := left(NEW.owner_name, 120);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_project_items_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_project_items ON public.project_items;
CREATE TRIGGER trg_text_caps_project_items BEFORE INSERT OR UPDATE ON public.project_items
  FOR EACH ROW EXECUTE FUNCTION public.cap_project_items_text();

CREATE OR REPLACE FUNCTION public.cap_project_change_orders_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.title           IS NOT NULL THEN NEW.title           := left(NEW.title,            200);  END IF;
  IF NEW.scope_change    IS NOT NULL THEN NEW.scope_change    := left(NEW.scope_change,    2000);  END IF;
  IF NEW.reason          IS NOT NULL THEN NEW.reason          := left(NEW.reason,          2000);  END IF;
  IF NEW.rejection_reason IS NOT NULL THEN NEW.rejection_reason := left(NEW.rejection_reason, 1000); END IF;
  IF NEW.co_number       IS NOT NULL THEN NEW.co_number       := left(NEW.co_number,         60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_project_change_orders_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_project_co ON public.project_change_orders;
CREATE TRIGGER trg_text_caps_project_co BEFORE INSERT OR UPDATE ON public.project_change_orders
  FOR EACH ROW EXECUTE FUNCTION public.cap_project_change_orders_text();

CREATE OR REPLACE FUNCTION public.cap_project_progress_logs_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.notes       IS NOT NULL THEN NEW.notes       := left(NEW.notes,      2000);  END IF;
  IF NEW.blockers    IS NOT NULL THEN NEW.blockers    := left(NEW.blockers,   2000);  END IF;
  IF NEW.reported_by IS NOT NULL THEN NEW.reported_by := left(NEW.reported_by, 120);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_project_progress_logs_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_project_progress ON public.project_progress_logs;
CREATE TRIGGER trg_text_caps_project_progress BEFORE INSERT OR UPDATE ON public.project_progress_logs
  FOR EACH ROW EXECUTE FUNCTION public.cap_project_progress_logs_text();

CREATE OR REPLACE FUNCTION public.cap_project_links_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.label     IS NOT NULL THEN NEW.label     := left(NEW.label,     200);  END IF;
  IF NEW.link_type IS NOT NULL THEN NEW.link_type := left(NEW.link_type,  60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_project_links_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_project_links ON public.project_links;
CREATE TRIGGER trg_text_caps_project_links BEFORE INSERT OR UPDATE ON public.project_links
  FOR EACH ROW EXECUTE FUNCTION public.cap_project_links_text();

CREATE OR REPLACE FUNCTION public.cap_project_roles_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.notes IS NOT NULL THEN NEW.notes := left(NEW.notes, 1000);  END IF;
  IF NEW.role  IS NOT NULL THEN NEW.role  := left(NEW.role,   100);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_project_roles_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_project_roles ON public.project_roles;
CREATE TRIGGER trg_text_caps_project_roles BEFORE INSERT OR UPDATE ON public.project_roles
  FOR EACH ROW EXECUTE FUNCTION public.cap_project_roles_text();

CREATE OR REPLACE FUNCTION public.cap_engineering_calcs_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.sow_text     IS NOT NULL THEN NEW.sow_text     := left(NEW.sow_text,    4000);  END IF;
  IF NEW.project_name IS NOT NULL THEN NEW.project_name := left(NEW.project_name, 200);  END IF;
  IF NEW.calc_type    IS NOT NULL THEN NEW.calc_type    := left(NEW.calc_type,    100);  END IF;
  IF NEW.discipline   IS NOT NULL THEN NEW.discipline   := left(NEW.discipline,   100);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_engineering_calcs_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_eng_calcs ON public.engineering_calcs;
CREATE TRIGGER trg_text_caps_eng_calcs BEFORE INSERT OR UPDATE ON public.engineering_calcs
  FOR EACH ROW EXECUTE FUNCTION public.cap_engineering_calcs_text();

CREATE OR REPLACE FUNCTION public.cap_schedule_items_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.title    IS NOT NULL THEN NEW.title    := left(NEW.title,     200);  END IF;
  IF NEW.notes    IS NOT NULL THEN NEW.notes    := left(NEW.notes,    2000);  END IF;
  IF NEW.category IS NOT NULL THEN NEW.category := left(NEW.category,  100);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_schedule_items_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_schedule_items ON public.schedule_items;
CREATE TRIGGER trg_text_caps_schedule_items BEFORE INSERT OR UPDATE ON public.schedule_items
  FOR EACH ROW EXECUTE FUNCTION public.cap_schedule_items_text();

CREATE OR REPLACE FUNCTION public.cap_skill_profiles_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.primary_skill IS NOT NULL THEN NEW.primary_skill := left(NEW.primary_skill, 120);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_skill_profiles_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_skill_profiles ON public.skill_profiles;
CREATE TRIGGER trg_text_caps_skill_profiles BEFORE INSERT OR UPDATE ON public.skill_profiles
  FOR EACH ROW EXECUTE FUNCTION public.cap_skill_profiles_text();

CREATE OR REPLACE FUNCTION public.cap_resume_documents_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.title    IS NOT NULL THEN NEW.title    := left(NEW.title,    200);  END IF;
  IF NEW.template IS NOT NULL THEN NEW.template := left(NEW.template,  60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_resume_documents_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_resume_docs ON public.resume_documents;
CREATE TRIGGER trg_text_caps_resume_docs BEFORE INSERT OR UPDATE ON public.resume_documents
  FOR EACH ROW EXECUTE FUNCTION public.cap_resume_documents_text();

CREATE OR REPLACE FUNCTION public.cap_resume_versions_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.note IS NOT NULL THEN NEW.note := left(NEW.note, 1000);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_resume_versions_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_resume_versions ON public.resume_versions;
CREATE TRIGGER trg_text_caps_resume_versions BEFORE INSERT OR UPDATE ON public.resume_versions
  FOR EACH ROW EXECUTE FUNCTION public.cap_resume_versions_text();

CREATE OR REPLACE FUNCTION public.cap_worker_profiles_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.display_name      IS NOT NULL THEN NEW.display_name      := left(NEW.display_name,      120);  END IF;
  IF NEW.username          IS NOT NULL THEN NEW.username          := left(NEW.username,           60);  END IF;
  IF NEW.email             IS NOT NULL THEN NEW.email             := left(NEW.email,             254);  END IF;
  IF NEW.preferred_persona IS NOT NULL THEN NEW.preferred_persona := left(NEW.preferred_persona,  60);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_worker_profiles_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_worker_profiles ON public.worker_profiles;
CREATE TRIGGER trg_text_caps_worker_profiles BEFORE INSERT OR UPDATE ON public.worker_profiles
  FOR EACH ROW EXECUTE FUNCTION public.cap_worker_profiles_text();

CREATE OR REPLACE FUNCTION public.cap_parts_staged_reservations_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.asset_name  IS NOT NULL THEN NEW.asset_name  := left(NEW.asset_name,  200);  END IF;
  IF NEW.notes       IS NOT NULL THEN NEW.notes       := left(NEW.notes,      1000);  END IF;
  IF NEW.reserved_by IS NOT NULL THEN NEW.reserved_by := left(NEW.reserved_by, 120);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_parts_staged_reservations_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_parts_staged ON public.parts_staged_reservations;
CREATE TRIGGER trg_text_caps_parts_staged BEFORE INSERT OR UPDATE ON public.parts_staged_reservations
  FOR EACH ROW EXECUTE FUNCTION public.cap_parts_staged_reservations_text();

CREATE OR REPLACE FUNCTION public.cap_marketplace_saved_searches_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.search_name IS NOT NULL THEN NEW.search_name := left(NEW.search_name,  80);  END IF;
  IF NEW.query_text  IS NOT NULL THEN NEW.query_text  := left(NEW.query_text,  200);  END IF;
  IF NEW.email       IS NOT NULL THEN NEW.email       := left(NEW.email,       254);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_marketplace_saved_searches_text() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_text_caps_mkt_saved ON public.marketplace_saved_searches;
CREATE TRIGGER trg_text_caps_mkt_saved BEFORE INSERT OR UPDATE ON public.marketplace_saved_searches
  FOR EACH ROW EXECUTE FUNCTION public.cap_marketplace_saved_searches_text();

COMMIT;
