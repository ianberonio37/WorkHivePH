-- Shift Brain Phase 4: foundation schema for the autonomous shift planner.
--
-- One row per hive per shift window. The orchestrator edge function writes a
-- DRAFT row at shift change; supervisors review, edit, and publish. Published
-- rows are read by shift-brain.html for the crew briefing.
--
-- Skills consulted: architect (shared catalog status pattern, GRANT + RLS),
-- multitenant-engineer (hive-membership-join policy), data-engineer (composite
-- indexes at creation), realtime-engineer (publication opt-in, REPLICA FULL),
-- devops (pg_cron commented out by default), security (supervisor-only publish).

BEGIN;

CREATE TABLE IF NOT EXISTS public.shift_plans (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  shift_window    text NOT NULL
                  CHECK (shift_window IN ('06-14','14-22','22-06')),
  shift_date      date NOT NULL DEFAULT (now() AT TIME ZONE 'Asia/Manila')::date,
  status          text NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','published','archived')),
  generated_at    timestamptz NOT NULL DEFAULT now(),
  generated_by    text NOT NULL DEFAULT 'shift-planner-orchestrator',
  published_at    timestamptz,
  published_by    text,
  briefing        text,                                 -- AI-written morning paragraph
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,   -- structured plan: risk_top, pms_due, carry_forward, parts_prestage, assignments, projects_today
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT shift_plans_unique_per_window UNIQUE (hive_id, shift_date, shift_window)
);

COMMENT ON TABLE public.shift_plans IS
  'Shift Brain output: one draft per hive per shift window (06-14 / 14-22 / 22-06). Supervisor reviews, edits, then publishes to crew via report-sender.';

CREATE INDEX IF NOT EXISTS idx_shift_plans_hive_date
  ON public.shift_plans (hive_id, shift_date DESC, shift_window);
CREATE INDEX IF NOT EXISTS idx_shift_plans_status
  ON public.shift_plans (hive_id, status, generated_at DESC);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.tg_shift_plans_touch_updated()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS shift_plans_touch_updated ON public.shift_plans;
CREATE TRIGGER shift_plans_touch_updated
  BEFORE UPDATE ON public.shift_plans
  FOR EACH ROW EXECUTE FUNCTION public.tg_shift_plans_touch_updated();

-- Grants (required for migration-created tables per multitenant skill)
GRANT SELECT, INSERT, UPDATE, DELETE ON public.shift_plans TO anon, authenticated;

-- RLS
ALTER TABLE public.shift_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS shift_plans_read ON public.shift_plans;
CREATE POLICY shift_plans_read ON public.shift_plans FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Workers can read; only supervisors can edit and publish.
DROP POLICY IF EXISTS shift_plans_supervisor_write ON public.shift_plans;
CREATE POLICY shift_plans_supervisor_write ON public.shift_plans FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = shift_plans.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.role = 'supervisor' AND hm.status = 'active'
    )
  );

-- Service role (used by the orchestrator edge function) bypasses RLS automatically
-- via the service_role key.

-- Realtime publication for live supervisor updates as the orchestrator writes
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'shift_plans'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.shift_plans';
  END IF;
END
$$;

ALTER TABLE public.shift_plans REPLICA IDENTITY FULL;

COMMIT;

-- pg_cron schedules (run AFTER enabling pg_cron extension in Supabase Dashboard)
-- Three jobs at the Filipino industrial 3-shift boundaries (UTC offsets from PHT).
-- PHT = UTC+8, so:
--   06:00 PHT = 22:00 UTC (prior day)
--   14:00 PHT = 06:00 UTC
--   22:00 PHT = 14:00 UTC
--
-- /*
-- SELECT cron.schedule(
--   'shift-brain-morning',
--   '0 22 * * *',
--   $$ SELECT net.http_post(
--     url     := 'https://YOUR_PROJECT.supabase.co/functions/v1/shift-planner-orchestrator',
--     headers := '{"Authorization": "Bearer YOUR_SERVICE_ROLE_KEY", "Content-Type": "application/json"}'::jsonb,
--     body    := '{"shift_window":"06-14"}'::jsonb
--   ) $$
-- );
-- SELECT cron.schedule(
--   'shift-brain-afternoon',
--   '0 6 * * *',
--   $$ SELECT net.http_post(
--     url     := 'https://YOUR_PROJECT.supabase.co/functions/v1/shift-planner-orchestrator',
--     headers := '{"Authorization": "Bearer YOUR_SERVICE_ROLE_KEY", "Content-Type": "application/json"}'::jsonb,
--     body    := '{"shift_window":"14-22"}'::jsonb
--   ) $$
-- );
-- SELECT cron.schedule(
--   'shift-brain-night',
--   '0 14 * * *',
--   $$ SELECT net.http_post(
--     url     := 'https://YOUR_PROJECT.supabase.co/functions/v1/shift-planner-orchestrator',
--     headers := '{"Authorization": "Bearer YOUR_SERVICE_ROLE_KEY", "Content-Type": "application/json"}'::jsonb,
--     body    := '{"shift_window":"22-06"}'::jsonb
--   ) $$
-- );
-- */
