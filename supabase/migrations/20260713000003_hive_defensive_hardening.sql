-- 20260713000003_hive_defensive_hardening.sql
--
-- Three LOW-severity defense-in-depth siblings the 2026-07-12 write-hardening sweep skipped
-- (bug-hunt 2026-07-13, hive.html P4/P5). Each mirrors an existing platform pattern.
--
-- P4-02  No server-side text-length cap on hives.name / hive_members.worker_name (both text,
--        character_maximum_length NULL, no CHECK). ~30 other name siblings got cap_*_text triggers
--        (worker_profiles.display_name 120, report_contacts.name 120, asset_nodes, inventory_items,
--        pm_completions, …); these two were missed. A raw PostgREST write bypasses the UI maxlength.
-- P4-03  hive_audit_log actor-spoof: wh_bind_audit_actor() rebinds NEW.actor ONLY when a
--        worker_profiles row exists (nothing auto-creates one on signup), so a profile-less active
--        member could INSERT an audit row with a forged `actor`. Bind it UNCONDITIONALLY.
-- P5-04  asset_nodes INSERT WITH CHECK does not pin auth_uid (the FOR ALL policy's auth_uid=auth.uid()
--        lives only in USING, which governs UPDATE/DELETE), so a member could attribute a pending
--        submission to another member's identity. Bind auth_uid + worker_name/submitted_by server-side
--        on INSERT (matches feedback_authuid_attribution_on_every_write; pm_completions already pins it).

BEGIN;

-- ── P4-02: text caps on hives.name (60) + hive_members.worker_name (120) ──
CREATE OR REPLACE FUNCTION public.cap_hives_text() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  IF NEW.name IS NOT NULL THEN NEW.name := left(NEW.name, 60); END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_text_caps_hives ON public.hives;
CREATE TRIGGER trg_text_caps_hives BEFORE INSERT OR UPDATE ON public.hives
  FOR EACH ROW EXECUTE FUNCTION public.cap_hives_text();

CREATE OR REPLACE FUNCTION public.cap_hive_members_text() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  IF NEW.worker_name IS NOT NULL THEN NEW.worker_name := left(NEW.worker_name, 120); END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_text_caps_hive_members ON public.hive_members;
CREATE TRIGGER trg_text_caps_hive_members BEFORE INSERT OR UPDATE ON public.hive_members
  FOR EACH ROW EXECUTE FUNCTION public.cap_hive_members_text();

-- ── P4-03: bind hive_audit_log.actor UNCONDITIONALLY (server-authoritative, never client-trusted) ──
CREATE OR REPLACE FUNCTION public.wh_bind_audit_actor() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE real_actor text;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    SELECT display_name INTO real_actor FROM worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
    IF real_actor IS NULL THEN
      -- no worker_profiles row (nothing auto-creates one) -> fall back to the caller's server-bound
      -- hive_members name (NOT NULL, bound to auth_uid) so a profile-less member cannot forge actor.
      SELECT worker_name INTO real_actor FROM public.hive_members
        WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    END IF;
    NEW.actor := COALESCE(real_actor, '(unknown)');  -- always overwrite the client-supplied value
  END IF;
  RETURN NEW;
END; $fn$;

-- ── P5-04: pin asset_nodes submitter attribution server-side on INSERT ──
CREATE OR REPLACE FUNCTION public.bind_asset_nodes_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  -- Only on member (authed) INSERTs; a service-role batch (auth.uid() NULL) keeps its supplied values.
  IF auth.uid() IS NOT NULL THEN
    NEW.auth_uid := auth.uid();
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN
      NEW.worker_name  := v_name;
      NEW.submitted_by := v_name;
    END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_asset_nodes ON public.asset_nodes;
CREATE TRIGGER trg_bind_submitter_asset_nodes BEFORE INSERT ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.bind_asset_nodes_submitter();

COMMIT;
