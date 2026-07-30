-- =====================================================================
-- C15 (part 1) · SLIs WITH TARGETS — the arc's north-star metrics stop being adjectives
-- =====================================================================
-- The roadmap named allocation rate, time-to-accept and completion rate as this arc's north-star
-- metrics (D9) and then never gave them a NUMBER to be measured against. A hailing platform lives or
-- dies on time-to-accept; without a target nobody can say whether today was acceptable, and "the
-- gates are green" says nothing about whether the marketplace actually works. Google's SRE framing:
-- an SLI is the measurement, the SLO is the numeric target, and the gap is the error budget.
--
-- Every input already exists - service_requests carries a timestamp per state (accepted_at,
-- completed_at, settled_at, cancelled_at) - so this is arithmetic over live data, not new plumbing.
--
-- TARGETS LIVE IN A TABLE, NOT IN THIS FILE, because they are a business call Ian tunes alongside the
-- other D9 knobs (5%/10% commission, 90s TTL, 3->6km radius). Changing a target must never require a
-- migration. The seeded values below are opening defaults, explicitly vetoable.

BEGIN;

CREATE TABLE IF NOT EXISTS public.service_slo_targets (
  sli          text PRIMARY KEY,
  target       numeric     NOT NULL,
  comparator   text        NOT NULL CHECK (comparator IN ('>=', '<=')),
  unit         text        NOT NULL,
  window_days  int         NOT NULL DEFAULT 30,
  note         text,
  updated_at   timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.service_slo_targets (sli, target, comparator, unit, note) VALUES
  ('allocation_rate',  70, '>=', 'percent',
   'Share of broadcast hails that reached an accept. The industry''s own top-line marketplace metric. Ian tunes.'),
  ('time_to_accept_p50', 120, '<=', 'seconds',
   'Median seconds from hail to accept. Paired with the 90s offer TTL - if p50 exceeds the TTL, hails expire before anyone answers. Ian tunes.'),
  ('completion_rate',  90, '>=', 'percent',
   'Share of accepted jobs that reached completed/settled. Catches accept-then-abandon. Ian tunes.')
ON CONFLICT (sli) DO NOTHING;

COMMENT ON TABLE public.service_slo_targets IS
  'C15 SLO targets for the service-hailing SLIs. Editable data, not code: tuning a target is a business decision (Ian), never a migration.';

-- ── the SLIs, measured over each target's own window ──────────────────────────
-- Deliberately NOT materialized: the row counts here are small and a stale reliability number is
-- worse than a slightly slower one (P13 says materialize only what is PROVEN heavy).
CREATE OR REPLACE VIEW public.v_service_slo AS
WITH t AS (SELECT * FROM public.service_slo_targets),
win AS (SELECT COALESCE(max(window_days), 30) AS d FROM t),
r AS (
  SELECT * FROM public.service_requests, win
   WHERE service_requests.created_at >= now() - (win.d || ' days')::interval
),
m AS (
  SELECT
    -- denominator = hails that actually went out. A request still sitting in 'requested' was never
    -- offered to anyone, so counting it as an allocation miss would blame the market for our own queue.
    count(*) FILTER (WHERE status <> 'requested')                                   AS broadcast_n,
    count(*) FILTER (WHERE accepted_at IS NOT NULL)                                 AS accepted_n,
    count(*) FILTER (WHERE completed_at IS NOT NULL OR settled_at IS NOT NULL)      AS completed_n,
    percentile_cont(0.5) WITHIN GROUP (
      ORDER BY EXTRACT(EPOCH FROM (accepted_at - created_at))
    ) FILTER (WHERE accepted_at IS NOT NULL)                                        AS tta_p50
  FROM r
)
SELECT 'allocation_rate' AS sli,
       CASE WHEN m.broadcast_n = 0 THEN NULL
            ELSE round(100.0 * m.accepted_n / m.broadcast_n, 1) END AS value,
       t.target, t.comparator, t.unit, t.window_days,
       m.broadcast_n AS denominator, t.note
  FROM m CROSS JOIN t WHERE t.sli = 'allocation_rate'
UNION ALL
SELECT 'time_to_accept_p50',
       CASE WHEN m.accepted_n = 0 THEN NULL ELSE round(m.tta_p50::numeric, 1) END,
       t.target, t.comparator, t.unit, t.window_days, m.accepted_n, t.note
  FROM m CROSS JOIN t WHERE t.sli = 'time_to_accept_p50'
UNION ALL
SELECT 'completion_rate',
       CASE WHEN m.accepted_n = 0 THEN NULL
            ELSE round(100.0 * m.completed_n / m.accepted_n, 1) END,
       t.target, t.comparator, t.unit, t.window_days, m.accepted_n, t.note
  FROM m CROSS JOIN t WHERE t.sli = 'completion_rate';

COMMENT ON VIEW public.v_service_slo IS
  'C15 SLIs vs their SLOs over the target window. value IS NULL means NOT MEASURABLE YET (empty denominator) - deliberately distinct from 0, which would be a real breach. Read-only aggregate over service_requests.';

-- Aggregate marketplace health is not tenant data - every hail contributes to one platform number,
-- and no row is attributable to a hive through it. Readable, like the seller directory.
GRANT SELECT ON public.v_service_slo TO authenticated;
GRANT SELECT ON public.service_slo_targets TO authenticated;

COMMIT;
