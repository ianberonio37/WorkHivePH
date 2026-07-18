-- P3/attribution finding (bug-hunt roadmap, 2026-07-18, found live via the page-crud gate after
-- adding `projects` to it). bind_projects_submitter pinned ONLY auth_uid, leaving `worker_name`
-- FORGEABLE — a worker could INSERT a project with another person's worker_name (impersonation /
-- attribution forge; the displayed author lies). Same class as migs 010-012 (12 tables); projects
-- was missed. Redefine to the canonical pattern (matches bind_pm_asset_submitter): pin auth_uid,
-- derive worker_name from hive_members for the caller, and make attribution immutable on UPDATE.
CREATE OR REPLACE FUNCTION public.bind_projects_submitter() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;             -- service-role / seeder: trust the batch
  IF TG_OP = 'UPDATE' THEN                                   -- attribution is immutable
    NEW.auth_uid    := OLD.auth_uid;
    NEW.worker_name := OLD.worker_name;
    RETURN NEW;
  END IF;
  NEW.auth_uid := auth.uid();                                -- INSERT: pin to the caller
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.worker_name := v_name; END IF;
  END IF;
  RETURN NEW;
END $$;
