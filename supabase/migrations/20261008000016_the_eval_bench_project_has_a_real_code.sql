-- ★THE EVAL BENCH'S PROJECT CODE WAS NOT A PROJECT CODE (2026-10-08). ai_eval_bench_ensure (migration
-- 20261007000011) seeded the bench's work-order project as 'PRJ-001', a shape no person can ever get:
-- generate_project_code issues <TYPE>-<YEAR>-<SEQ>, and a 'workorder' is WO-2026-001. The probe
-- project-manager__code_stable (no malformed code in any hive) went red on it, and an eval that asks about a code
-- the product cannot produce measures the model on a fixture, not on the platform. The bench now uses the code a
-- real work order gets; the existing row is renamed in place (its items, logs and links key on project_id).
UPDATE public.projects
   SET project_code = 'WO-2026-001'
 WHERE hive_id = '50f51f72-66ec-4e9d-8dfd-daa5f1eb696c' AND project_code = 'PRJ-001';

CREATE OR REPLACE FUNCTION public.ai_eval_bench_ensure(p_auth_uid uuid, p_force boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  c_hive     CONSTANT uuid     := '50f51f72-66ec-4e9d-8dfd-daa5f1eb696c';
  c_email    CONSTANT text     := 'ai-eval-runner@workhive.test';
  c_version  CONSTANT integer  := 1;
  c_reanchor CONSTANT interval := interval '7 days';
  v_name     text;
  v_now      timestamptz := date_trunc('hour', now());
  v_today    date        := current_date;
  v_assets   jsonb := '{}'::jsonb;
  v_pm       jsonb := '{}'::jsonb;
  v_id       uuid;
  v_pm_id    uuid;
  v_proj     uuid;
  v_meta     jsonb;
  v_rebuild  boolean;
  r          record;
BEGIN
  -- The identity pin: only the eval account, only in the eval hive.
  SELECT hm.worker_name INTO v_name
    FROM public.hive_members hm
    JOIN public.worker_profiles wp ON wp.auth_uid = hm.auth_uid
   WHERE hm.hive_id = c_hive AND hm.auth_uid = p_auth_uid
     AND hm.status = 'active' AND hm.role = 'supervisor'
     AND lower(wp.email) = c_email
   LIMIT 1;
  IF v_name IS NULL THEN
    RAISE EXCEPTION 'ai_eval_bench_ensure: % is not the eval account of the eval hive', p_auth_uid
      USING ERRCODE = '42501';
  END IF;

  -- Two slices must not seed at once (the second would hit the (hive_id, tag) unique key).
  PERFORM pg_advisory_xact_lock(hashtext('ai_eval_bench_ensure'));
  -- An announced system write: the daily row caps count created_at = today, and a rebuild is a batch.
  PERFORM set_config('workhive.row_cap_system_write', 'on', true);

  -- 1a. Assets and their PM records (created once).
  FOR r IN SELECT * FROM (VALUES
      ('PMP-001', 'Cooling Water Pump No. 1',           'Pump',       'high',     'Centrifugal Pump', 'High',
       'Utilities - Cooling Tower Pump House', 'Grundfos',    'NK 80-250', DATE '2019-03-11'),
      ('PMP-002', 'Cooling Water Pump No. 2 (standby)', 'Pump',       'high',     'Centrifugal Pump', 'High',
       'Utilities - Cooling Tower Pump House', 'Grundfos',    'NK 80-250', DATE '2019-03-11'),
      ('CMP-001', 'Instrument Air Compressor',          'Compressor', 'critical', 'Air Compressor',   'Critical',
       'Utilities - Compressor Room',          'Atlas Copco', 'GA 37',     DATE '2020-08-03')
    ) AS s(tag, name, iso_class, crit, category, pm_crit, location, manufacturer, model, installed)
  LOOP
    SELECT id INTO v_pm_id FROM public.pm_assets
     WHERE hive_id = c_hive AND tag_id = r.tag ORDER BY created_at LIMIT 1;
    IF v_pm_id IS NULL THEN
      INSERT INTO public.pm_assets (hive_id, worker_name, auth_uid, asset_name, tag_id, location, category,
                                    criticality, last_anchor_date)
      VALUES (c_hive, v_name, p_auth_uid, r.name, r.tag, r.location, r.category, r.pm_crit, v_today - 26)
      RETURNING id INTO v_pm_id;
    END IF;

    SELECT id INTO v_id FROM public.asset_nodes WHERE hive_id = c_hive AND tag = r.tag;
    IF v_id IS NULL THEN
      INSERT INTO public.asset_nodes (hive_id, auth_uid, worker_name, level, tag, name, iso_class, criticality,
                                      location, manufacturer, model, install_date, pm_asset_id, status,
                                      submitted_by, approved_by, approved_at)
      VALUES (c_hive, p_auth_uid, v_name, 'equipment', r.tag, r.name, r.iso_class, r.crit,
              r.location, r.manufacturer, r.model, r.installed, v_pm_id, 'approved',
              v_name, v_name, now())
      RETURNING id INTO v_id;
    ELSE
      UPDATE public.asset_nodes SET pm_asset_id = v_pm_id WHERE id = v_id AND pm_asset_id IS NULL;
    END IF;

    v_assets := v_assets || jsonb_build_object(r.tag, v_id);
    v_pm     := v_pm     || jsonb_build_object(r.tag, v_pm_id);
  END LOOP;

  -- 1b. PM programmes (created once, per asset + task).
  FOR r IN SELECT * FROM (VALUES
      ('PMP-001', 'Grease pump and motor bearings (DE/NDE) to the OEM quantity',  'Monthly'),
      ('PMP-001', 'Record vibration velocity and bearing temperature at DE/NDE',  'Monthly'),
      ('PMP-001', 'Inspect mechanical seal and seal flush line for leakage',      'Monthly'),
      ('PMP-001', 'Laser-check pump to motor coupling alignment',                 'Quarterly'),
      ('PMP-002', 'Grease pump and motor bearings (DE/NDE) to the OEM quantity',  'Monthly'),
      ('PMP-002', 'Record vibration velocity and bearing temperature at DE/NDE',  'Monthly'),
      ('PMP-002', 'Inspect mechanical seal and seal flush line for leakage',      'Monthly'),
      ('CMP-001', 'Drain air receiver and test the auto-drain valve',             'Monthly'),
      ('CMP-001', 'Clean oil cooler and aftercooler fins',                        'Monthly'),
      ('CMP-001', 'Replace oil filter and air/oil separator element',             'Quarterly')
    ) AS s(tag, item, freq)
  LOOP
    IF NOT EXISTS (SELECT 1 FROM public.pm_scope_items
                    WHERE hive_id = c_hive AND asset_id = (v_pm ->> r.tag)::uuid AND item_text = r.item) THEN
      INSERT INTO public.pm_scope_items (asset_id, hive_id, item_text, frequency, anchor_date)
      VALUES ((v_pm ->> r.tag)::uuid, c_hive, r.item, r.freq, v_today - 90);
    END IF;
  END LOOP;

  -- 1c. The project the project fixtures are asked about (created once), and a change order awaiting a decision.
  SELECT id, meta INTO v_proj, v_meta FROM public.projects
   WHERE hive_id = c_hive AND project_code = 'WO-2026-001' AND deleted_at IS NULL
   ORDER BY created_at LIMIT 1;
  IF v_proj IS NULL THEN
    INSERT INTO public.projects (hive_id, worker_name, auth_uid, project_code, name, project_type, status, priority,
                                 owner_name, description, start_date, end_date, budget_php)
    VALUES (c_hive, v_name, p_auth_uid, 'WO-2026-001', 'PMP-001 Cooling Water Pump Overhaul', 'workorder', 'active',
            'high', v_name,
            'Overhaul of cooling water pump PMP-001 after three mechanical seal failures in 90 days: replace the worn '
            'shaft sleeve and seal, renew both bearings, laser-align, and performance-test before it returns to duty.',
            v_today - 10, v_today + 11, 185000)
    RETURNING id, meta INTO v_proj, v_meta;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.project_change_orders WHERE project_id = v_proj AND co_number = 'CO-001') THEN
    INSERT INTO public.project_change_orders (project_id, hive_id, co_number, title, scope_change, reason,
                                              cost_impact_php, schedule_impact_days, status, requested_by)
    VALUES (v_proj, c_hive, 'CO-001', 'Replace impeller wear rings',
            'Add replacement of both impeller wear rings to the overhaul scope.',
            'Inspection measured wear-ring clearance at 0.9 mm against a 0.4 mm OEM limit; the pump will not meet '
            'its duty point without it.',
            28500, 2, 'pending', v_name);
  END IF;

  -- 2. The time-relative history. Rebuilt when absent, stale, or the seed version moved.
  v_rebuild := p_force
    OR (v_meta ->> 'eval_bench_version') IS DISTINCT FROM c_version::text
    OR COALESCE((v_meta ->> 'eval_bench_anchored_at')::timestamptz, '-infinity'::timestamptz) < now() - c_reanchor
    OR NOT EXISTS (SELECT 1 FROM public.logbook WHERE hive_id = c_hive);

  IF v_rebuild THEN
    DELETE FROM public.logbook               WHERE hive_id = c_hive;
    DELETE FROM public.pm_completions        WHERE hive_id = c_hive;
    DELETE FROM public.project_progress_logs WHERE hive_id = c_hive AND project_id = v_proj;
    DELETE FROM public.project_items         WHERE hive_id = c_hive AND project_id = v_proj;

    -- Corrective history. PMP-001's gaps shrink 32 -> 23 -> 15 -> 9 days: MTBF is worsening, and the
    -- recurring cause (seal) is the reason WO-2026-001 exists. PMP-002 is the peer for "similar failures".
    INSERT INTO public.logbook (worker_name, auth_uid, hive_id, date, created_at, closed_at, machine, category,
                                problem, action, root_cause, maintenance_type, status, downtime_hours,
                                failure_consequence, production_output, readings_json, asset_node_id, sync_meta)
    SELECT v_name, p_auth_uid, c_hive,
           v_now - make_interval(days => s.d, hours => s.h),
           v_now - make_interval(days => s.d, hours => s.h),
           v_now - make_interval(days => s.d, hours => s.h) + make_interval(mins => (s.dt * 60)::int),
           s.tag, 'Mechanical', s.problem, s.action, s.rc, 'Breakdown / Corrective', 'Closed', s.dt, s.fc,
           s.po::jsonb, s.rj::jsonb, (v_assets ->> s.tag)::uuid, jsonb_build_object('eval_bench', c_version)
      FROM (VALUES
        ('PMP-001', 82, 5, 5.5, 'Mechanical seal leaking at the stuffing box, water spraying onto the motor',
         'Seal faces scored - the pump ran dry during a suction valve changeover',
         'Replaced the mechanical seal and flushed the seal chamber', 'Running reduced',
         '{"good_units": 1890, "total_units": 1962}', '{"pressure_bar": 2.6, "temperature_c": 41}'),
        ('PMP-001', 50, 9, 4.0, 'High vibration and DE bearing temperature 92 C',
         'DE bearing grease degraded - a lubrication interval was missed',
         'Replaced DE bearing 6309-2Z, regreased the NDE bearing, checked alignment', 'Running reduced',
         '{"good_units": 1912, "total_units": 1965}', '{"vibration_mms": 7.8, "temperature_c": 92}'),
        ('PMP-001', 27, 14, 6.0, 'Mechanical seal leak recurred within four weeks of replacement',
         'Seal flush line partially blocked by scale, so the seal faces overheated',
         'Descaled the flush line, replaced the seal, added a flush-flow check to the PM', 'Running reduced',
         '{"good_units": 1855, "total_units": 1960}', '{"pressure_bar": 2.4, "temperature_c": 58}'),
        ('PMP-001', 12, 3, 2.5, 'Cavitation noise, discharge pressure fluctuating 2.1-3.4 bar',
         'Suction strainer 60 percent clogged with cooling tower debris',
         'Cleaned the suction strainer and added a weekly strainer check', 'Running reduced',
         '{"good_units": 1931, "total_units": 1968}', '{"pressure_bar": 2.1, "vibration_mms": 6.1}'),
        ('PMP-001', 3, 7, 3.0, 'Mechanical seal leaking again - third seal failure in 90 days',
         'Shaft sleeve worn at the seal seat, runout 0.12 mm',
         'Fitted a temporary seal and moved duty to PMP-002; sleeve replacement planned under WO-2026-001',
         'Running reduced', '{"good_units": 1902, "total_units": 1966}', '{"pressure_bar": 2.5, "temperature_c": 47}'),
        ('PMP-002', 65, 11, 4.5, 'Mechanical seal leaking after a standby changeover',
         'Seal ran dry - the pump was started with its suction valve closed',
         'Replaced the mechanical seal and added a pre-start valve checklist', 'Hidden',
         '{"good_units": 1960, "total_units": 1966}', '{"pressure_bar": 2.7}'),
        ('PMP-002', 20, 6, 2.0, 'Coupling insert worn, knocking at start-up',
         'Elastomer coupling insert aged - not replaced at the last overhaul',
         'Replaced the coupling insert and re-aligned the pump', 'Hidden',
         '{"good_units": 1962, "total_units": 1966}', '{"vibration_mms": 5.2}'),
        ('CMP-001', 74, 2, 3.0, 'Compressor tripped on high element discharge temperature (110 C)',
         'Oil cooler fins fouled with dust', 'Cleaned the oil cooler and aftercooler, topped up the oil',
         'Stopped production', '{"good_units": 1704, "total_units": 1966}', '{"temperature_c": 110, "pressure_bar": 6.9}'),
        ('CMP-001', 38, 8, 2.5, 'Unloader valve stuck - compressor not loading, header pressure 5.2 bar',
         'Unloader valve O-rings hardened', 'Replaced the unloader valve kit', 'Running reduced',
         '{"good_units": 1840, "total_units": 1966}', '{"pressure_bar": 5.2}'),
        ('CMP-001', 9, 4, 3.5, 'High element discharge temperature trip again',
         'Thermostatic valve stuck partly open, so oil bypassed the cooler',
         'Replaced the thermostatic valve element', 'Stopped production',
         '{"good_units": 1688, "total_units": 1966}', '{"temperature_c": 109, "pressure_bar": 7.0}')
      ) AS s(tag, d, h, dt, problem, rc, action, fc, po, rj);

    -- PM history: monthly tasks done ~86/56/26 days ago, quarterly ~70. PMP-001's seal inspection was
    -- SKIPPED 26 days ago - three weeks before the third seal failure.
    INSERT INTO public.pm_completions (asset_id, scope_item_id, hive_id, worker_name, auth_uid, status, notes,
                                       completed_at)
    SELECT si.asset_id, si.id, c_hive, v_name, p_auth_uid,
           CASE WHEN pa.tag_id = 'PMP-001' AND si.item_text LIKE 'Inspect mechanical seal%' AND d.ago = 26
                THEN 'skipped' ELSE 'done' END,
           CASE WHEN pa.tag_id = 'PMP-001' AND si.item_text LIKE 'Inspect mechanical seal%' AND d.ago = 26
                THEN 'Skipped - production could not release PMP-001 for isolation' END,
           v_now - make_interval(days => d.ago, hours => 2)
      FROM public.pm_scope_items si
      JOIN public.pm_assets pa ON pa.id = si.asset_id AND pa.hive_id = c_hive
      JOIN (VALUES ('Monthly', 86), ('Monthly', 56), ('Monthly', 26), ('Quarterly', 70)) AS d(freq, ago)
        ON d.freq = si.frequency
     WHERE si.hive_id = c_hive;

    UPDATE public.pm_assets SET last_anchor_date = v_today - 26 WHERE hive_id = c_hive;

    -- Project scope, progress and its blocker.
    INSERT INTO public.project_items (project_id, hive_id, wbs_code, title, owner_name, status, pct_complete,
                                      planned_start, planned_end, estimated_hours, actual_hours, notes, sort_order)
    SELECT v_proj, c_hive, s.wbs, s.title, v_name, s.status, s.pct, v_today + s.ps, v_today + s.pe, s.est, s.act,
           s.notes, s.ord
      FROM (VALUES
        ('1.1', 'Isolate under LOTO, drain and dismantle PMP-001',             'done',        100, -10, -9, 8,  8,  NULL, 1),
        ('1.2', 'Inspect impeller, wear rings and shaft sleeve',               'done',        100, -8,  -6, 6,  7,  'Sleeve worn 0.12 mm at the seal seat; wear rings out of limit', 2),
        ('1.3', 'Clean suction strainer and descale the seal flush line',      'done',        100, -7,  -6, 3,  3,  NULL, 3),
        ('1.4', 'Machine a replacement shaft sleeve (vendor machine shop)',    'blocked',     20,  -5,  2,  16, 3,  'Blank delivered; vendor lathe backlog', 4),
        ('1.5', 'Replace DE/NDE bearings and the mechanical seal',             'in_progress', 40,  -3,  4,  6,  2,  NULL, 5),
        ('1.6', 'Laser-align the coupling and run a 4-hour performance test',  'pending',     0,   5,   8,  6,  NULL, NULL, 6),
        ('1.7', 'Return to duty and hand over to operations',                  'pending',     0,   9,   11, 2,  NULL, NULL, 7)
      ) AS s(wbs, title, status, pct, ps, pe, est, act, notes, ord);

    INSERT INTO public.project_progress_logs (project_id, hive_id, log_date, reported_by, auth_uid, pct_complete,
                                              hours_worked, notes, blockers)
    SELECT v_proj, c_hive, v_today - s.ago, v_name, p_auth_uid, s.pct, s.hrs, s.notes, s.blockers
      FROM (VALUES
        (9, 15, 8,  'Pump isolated under a LOTO permit, drained and dismantled.', NULL),
        (6, 35, 12, 'Shaft sleeve worn 0.12 mm at the seal seat; wear rings out of limit (CO-001 raised). '
                    'Strainer cleaned and flush line descaled.', NULL),
        (3, 45, 6,  'Bearings received. Sleeve blank sent to the vendor machine shop.',
                    'Shaft sleeve machining delayed - vendor machine shop backlog, earliest slot in 6 days'),
        (1, 50, 4,  'Old bearings pulled; seal kit on hand.',
                    'Shaft sleeve still at the vendor; the performance test cannot be scheduled until it is fitted')
      ) AS s(ago, pct, hrs, notes, blockers);

    UPDATE public.projects
       SET start_date = v_today - 10, end_date = v_today + 11, status = 'active',
           meta = COALESCE(meta, '{}'::jsonb)
                  || jsonb_build_object('eval_bench_version', c_version, 'eval_bench_anchored_at', now())
     WHERE id = v_proj;
  END IF;

  RETURN jsonb_build_object(
    'hive_id',        c_hive,
    'version',        c_version,
    'rebuilt',        v_rebuild,
    'assets',         v_assets,
    'projects',       jsonb_build_object('WO-2026-001', v_proj),
    'breakdowns',     (SELECT count(*) FROM public.logbook
                        WHERE hive_id = c_hive AND maintenance_type = 'Breakdown / Corrective'
                          AND created_at >= now() - interval '90 days'),
    'pm_completions', (SELECT count(*) FROM public.pm_completions WHERE hive_id = c_hive),
    'project_items',  (SELECT count(*) FROM public.project_items WHERE project_id = v_proj),
    'anchored_at',    (SELECT meta ->> 'eval_bench_anchored_at' FROM public.projects WHERE id = v_proj)
  );
END
$function$;

REVOKE EXECUTE ON FUNCTION public.ai_eval_bench_ensure(uuid, boolean) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.ai_eval_bench_ensure(uuid, boolean) FROM anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.ai_eval_bench_ensure(uuid, boolean) TO service_role;
