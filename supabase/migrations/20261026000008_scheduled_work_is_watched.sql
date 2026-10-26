-- 20261026000008_scheduled_work_is_watched.sql
--
-- A SCHEDULED JOB'S FAILURE REACHED NO PERSON (OWN scheduled-work lens, 2026-10-26). Two ways:
--   1. cron records a run that ERRORS in cron.job_run_details, and nothing a person opens reads that table. Production's
--      16 HTTP jobs failed every run for weeks ("unrecognized configuration parameter app.supabase_functions_url") and
--      nobody saw it; locally validate_cron_health.py even excluded that exact message as "environment".
--   2. an HTTP job that REACHES its function is "succeeded" to cron whatever the function answers: the SELECT returned a
--      request id. When the functions refused the scheduler's bearer (401), cron still said succeeded. The answer lives
--      in net._http_response for pg_net's TTL (6 hours) and then disappears, unconnected to the job that asked.
--
-- Now:
--   - every HTTP job's net.http_post(...) is wrapped in place by private.note_scheduled_call(job, fn, <the call>), which
--     records the request id against the job and passes it through. The call expression is untouched (the ai-eval jobs
--     derive their run_id from the date - their own double-fire guard - so the command is wrapped, never rebuilt).
--   - private.settle_scheduled_calls() (every 5 minutes) copies each answer's status onto its call before the TTL drops
--     it, marks a call with no answer after 15 minutes as unanswered, and keeps 30 days.
--   - public.founder_scheduled_work() gives the console, for a platform admin only, every job's last run, what it did
--     (its last message - "DELETE 12", "1 row"), its last call's answer, and its failures over 7 days, cron's and the
--     function's alike.

CREATE TABLE IF NOT EXISTS private.scheduled_calls (
  id          bigserial PRIMARY KEY,
  jobname     text        NOT NULL,
  fn          text        NOT NULL,
  request_id  bigint,
  called_at   timestamptz NOT NULL DEFAULT now(),
  status_code integer,
  error       text,
  settled_at  timestamptz
);
CREATE INDEX IF NOT EXISTS scheduled_calls_job_recent ON private.scheduled_calls (jobname, called_at DESC);
CREATE INDEX IF NOT EXISTS scheduled_calls_unsettled ON private.scheduled_calls (request_id) WHERE settled_at IS NULL;
REVOKE ALL ON private.scheduled_calls FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.note_scheduled_call(p_job text, p_fn text, p_request_id bigint)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = private, pg_temp
AS $$
BEGIN
  INSERT INTO private.scheduled_calls (jobname, fn, request_id) VALUES (p_job, p_fn, p_request_id);
  RETURN p_request_id;
END
$$;
REVOKE ALL ON FUNCTION private.note_scheduled_call(text, text, bigint) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.settle_scheduled_calls()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = private, public, pg_temp
AS $$
DECLARE v_n integer;
BEGIN
  UPDATE private.scheduled_calls c
     SET status_code = h.status_code,
         error = CASE WHEN h.timed_out THEN 'timed out'
                      WHEN h.status_code BETWEEN 200 AND 299 THEN NULL
                      ELSE left(coalesce(h.error_msg, h.content, ''), 300) END,
         settled_at = now()
    FROM net._http_response h
   WHERE c.settled_at IS NULL AND h.id = c.request_id;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  UPDATE private.scheduled_calls
     SET error = 'no answer within 15 minutes', settled_at = now()
   WHERE settled_at IS NULL AND called_at < now() - interval '15 minutes';
  DELETE FROM private.scheduled_calls WHERE called_at < now() - interval '30 days';
  RETURN v_n;
END
$$;
REVOKE ALL ON FUNCTION private.settle_scheduled_calls() FROM PUBLIC, anon, authenticated;

-- wrap every scheduler HTTP job in place (the relay settles its own calls and is left alone)
DO $$
DECLARE
  j     record;
  v_fn  text;
  v_cmd text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    RETURN;
  END IF;
  FOR j IN SELECT jobid, jobname, command FROM cron.job
            WHERE command ~* 'select\s+net\.http_post\(' AND command NOT ILIKE '%note_scheduled_call%'
  LOOP
    v_fn := (regexp_match(j.command, '''/([a-z0-9_-]+)'''))[1];
    IF v_fn IS NULL THEN
      RAISE NOTICE 'scheduled job % left unwrapped: no function name in its command', j.jobname;
      CONTINUE;
    END IF;
    v_cmd := regexp_replace(rtrim(j.command, E' \t\r\n;'), 'select\s+net\.http_post\(',
                            format('SELECT private.note_scheduled_call(%L, %L, net.http_post(', j.jobname, v_fn), 'i')
             || ');';
    PERFORM cron.alter_job(j.jobid, command := v_cmd);
  END LOOP;
  PERFORM cron.unschedule(jobid) FROM cron.job WHERE jobname = 'scheduled-calls-settle';
  PERFORM cron.schedule('scheduled-calls-settle', '*/5 * * * *', 'SELECT private.settle_scheduled_calls();');
END
$$;

CREATE OR REPLACE FUNCTION public.founder_scheduled_work()
RETURNS TABLE (
  jobname          text,
  schedule         text,
  active           boolean,
  fn               text,
  last_run_at      timestamptz,
  last_status      text,
  last_message     text,
  runs_7d          integer,
  failed_7d        integer,
  last_call_at     timestamptz,
  last_call_status integer,
  last_call_error  text,
  calls_failed_7d  integer
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, private, pg_temp
AS $$
BEGIN
  IF NOT public.is_platform_admin() THEN
    RAISE EXCEPTION 'Only a platform admin can read scheduled work' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  SELECT j.jobname::text, j.schedule::text, j.active,
         (regexp_match(j.command, 'note_scheduled_call\(''[^'']*'',\s*''([^'']+)'''))[1],
         r.start_time, r.status::text, left(r.return_message, 200),
         coalesce(w.runs, 0)::integer, coalesce(w.failed, 0)::integer,
         c.called_at, c.status_code, c.error,
         coalesce(cf.failed, 0)::integer
    FROM cron.job j
    -- by runid, never start_time: a run killed by a restart has no start_time, and DESC sorts NULLs FIRST - a dead run
    -- from days ago read as the latest (caught on the console's first walk)
    LEFT JOIN LATERAL (SELECT d.start_time, d.status, d.return_message FROM cron.job_run_details d
                        WHERE d.jobid = j.jobid ORDER BY d.runid DESC LIMIT 1) r ON true
    LEFT JOIN LATERAL (SELECT count(*) AS runs, count(*) FILTER (WHERE d.status = 'failed') AS failed
                         FROM cron.job_run_details d
                        WHERE d.jobid = j.jobid AND d.start_time > now() - interval '7 days') w ON true
    LEFT JOIN LATERAL (SELECT s.called_at, s.status_code, s.error FROM private.scheduled_calls s
                        WHERE s.jobname = j.jobname ORDER BY s.called_at DESC LIMIT 1) c ON true
    LEFT JOIN LATERAL (SELECT count(*) AS failed FROM private.scheduled_calls s
                        WHERE s.jobname = j.jobname AND s.called_at > now() - interval '7 days'
                          AND s.settled_at IS NOT NULL AND s.error IS NOT NULL) cf ON true
   ORDER BY j.jobname;
END
$$;
REVOKE ALL ON FUNCTION public.founder_scheduled_work() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.founder_scheduled_work() TO authenticated;
