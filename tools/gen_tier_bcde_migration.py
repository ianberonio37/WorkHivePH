"""Generate the Tier B + C + D + E foundation migration.

Pulls the live standards-citation inventory from the codebase and writes a
single SQL file that creates:
  * canonical_standards (Tier D-s) with all distinct standards seeded
  * canonical_formulas  (Tier D-f) registry + 6 maintenance formulas
  * canonical_agent_contracts (Tier C) registry + 7 brain output schemas
  * v_project_truth     (Tier B)
  * v_knowledge_truth   (Tier B)
  * v_audit_unified     (Tier E)
"""
import re, glob, os
from collections import defaultdict

OUTPUT = "supabase/migrations/20260512000013_tier_bcde_foundation.sql"

# ── Standards collection ─────────────────────────────────────────────────────
files = (glob.glob('*.html') + glob.glob('supabase/functions/**/*.ts', recursive=True)
         + glob.glob('python-api/**/*.py', recursive=True))
files = [f for f in files if not any(t in f.lower() for t in
         ['backup','test','symbol-gallery','__pycache__','.git'])]

refs = defaultdict(set)
for path in files:
    try: content = open(path, encoding='utf-8', errors='ignore').read()
    except: continue
    for m in re.finditer(
        r'\b(ISO|SMRP|SAE\s+JA|NFPA|ASME|ASTM|ANSI|IEC|IESNA|ASHRAE|NEC|OSHA|IEEE)[\s\-:]*(\d{2,5}(?:[\-:][\d\.]+)?)',
        content):
        body = re.sub(r'\s+', '', m.group(1).upper())
        num  = m.group(2).replace(':', '-').rstrip('.')
        refs[(body, num)].add(path)

DISC_BODY = {'ASHRAE':'hvac','NFPA':'fire','NEC':'electrical','IEEE':'electrical',
             'IESNA':'lighting','OSHA':'safety','SMRP':'maintenance','SAEJA':'maintenance'}

def disc(body, num):
    if body in DISC_BODY: return DISC_BODY[body]
    if body == 'ISO':
        if num.startswith(('14224','55','13381','22400')): return 'maintenance'
        if num.startswith('21500'): return 'project_management'
        if num.startswith(('281','1217','10816','20816','21940','8528','3046','898','2372','1940','5348','7919','19451')): return 'mechanical'
        if num.startswith(('4413','1402','6020','10767')): return 'hydraulic'
        if num.startswith('8573'): return 'pneumatic'
        if num.startswith('14520'): return 'fire'
        if num.startswith(('266','3745','11690','9613','1996','3744','3746','3747')): return 'acoustics'
        if num.startswith(('286','4406','11158','15489','16528','4427','12944','4378')): return 'mechanical'
        return 'general'
    if body == 'IEC':
        if num.startswith(('60076','60364','60947','60909','60099','60228','61000','61643','62040','60831','61649','60439','60332','60909-0')): return 'electrical'
        if num.startswith('62305'): return 'lightning_protection'
        if num.startswith(('62548','61215','61727','61730','62446')): return 'solar_pv'
        if num.startswith('60617'): return 'drawing_standards'
        if num.startswith('61672'): return 'acoustics'
        return 'electrical'
    if body == 'ANSI':
        return 'mechanical' if num.startswith(('44','55','61')) else 'general'
    return 'mechanical' if body in ('ASTM','ASME') else 'general'

rows = []
seen = set()
for (body, num), files_set in sorted(refs.items()):
    sid = f'{body}_{num}'.lower().replace('-','_').replace('.','_')
    if sid in seen: continue
    seen.add(sid)
    d = disc(body, num)
    version = ''
    base_num = num
    if '-' in num:
        parts = num.split('-')
        if parts[-1].isdigit() and len(parts[-1]) == 4 and int(parts[-1]) > 1900:
            version = parts[-1]; base_num = '-'.join(parts[:-1])
    rows.append((sid, body, base_num, version, d, f'{body} {num}', len(files_set)))

values_lines = []
for sid, body, base, ver, d, title, refcount in rows:
    values_lines.append(
        f"  ('{sid}', '{body}', '{base}', '{ver}', '{d}', '{title}', "
        f"'{{\"ref_count\":{refcount}}}'::jsonb)"
    )
standards_values = ',\n'.join(values_lines)

# ── Build the full SQL ──────────────────────────────────────────────────────

sql_parts = []

sql_parts.append(f"""-- Tier B + C + D + E foundation registries (2026-05-12).
--
-- Phases 2-7 of the canonical layers initiative shipped as a single
-- coordinated migration:
--
--   Tier D-s: canonical_standards   ({len(rows)} standards seeded)
--   Tier D-f: canonical_formulas    (6 maintenance formulas seeded)
--   Tier C  : canonical_agent_contracts (7 brain output JSON Schemas)
--   Tier B  : v_project_truth + v_knowledge_truth views
--   Tier E  : v_audit_unified view
--
-- Skills consulted: architect (registry FK contract), data-engineer
-- (UNION ALL views), maintenance-expert (ISO/SMRP/SAE taxonomy),
-- security (locked policies), platform-guardian (forward-only ratchet).

BEGIN;

-- =============================================================================
-- PART 1. Tier D-s: canonical_standards registry
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.canonical_standards (
  standard_id   text PRIMARY KEY,
  body          text NOT NULL
                CHECK (body IN ('ISO','IEC','SAE','ASHRAE','NFPA','NEC','IEEE','ANSI','ASTM','IESNA','OSHA','SMRP','SAEJA','ASME')),
  number        text NOT NULL,
  version       text NOT NULL DEFAULT '',
  discipline    text NOT NULL,
  title         text NOT NULL,
  contract      jsonb NOT NULL DEFAULT '{{}}'::jsonb,
  url           text,
  registered_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_standards IS
  'Tier D-s: every standards-body citation used across the platform. canonical_formulas rows reference these by standard_id. AI agents look up standards here for citations + scope.';

CREATE INDEX IF NOT EXISTS idx_canonical_standards_body ON public.canonical_standards (body);
CREATE INDEX IF NOT EXISTS idx_canonical_standards_disc ON public.canonical_standards (discipline);

GRANT SELECT ON public.canonical_standards TO anon, authenticated;
ALTER TABLE public.canonical_standards ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_standards_read ON public.canonical_standards;
CREATE POLICY canonical_standards_read ON public.canonical_standards FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_standards_locked ON public.canonical_standards;
CREATE POLICY canonical_standards_locked ON public.canonical_standards FOR ALL USING (false) WITH CHECK (false);

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
{standards_values}
ON CONFLICT (standard_id) DO UPDATE
  SET body=EXCLUDED.body, number=EXCLUDED.number, version=EXCLUDED.version,
      discipline=EXCLUDED.discipline, title=EXCLUDED.title, contract=EXCLUDED.contract;
""")

sql_parts.append("""

-- =============================================================================
-- PART 2. Tier D-f: canonical_formulas registry + 6 maintenance formulas
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.canonical_formulas (
  formula_id     text PRIMARY KEY,
  name           text NOT NULL,
  domain         text NOT NULL,
  standard_ids   text[] NOT NULL DEFAULT '{}',
  library_source text NOT NULL DEFAULT '',
  inputs         jsonb NOT NULL DEFAULT '[]'::jsonb,
  outputs        jsonb NOT NULL DEFAULT '[]'::jsonb,
  formula_text   text NOT NULL DEFAULT '',
  description    text NOT NULL DEFAULT '',
  registered_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_formulas IS
  'Tier D-f: every derivation attributed to a formula_id + standard_ids + library_source. Python calc_* fns annotated with # formula: <id>.';

CREATE INDEX IF NOT EXISTS idx_canonical_formulas_domain ON public.canonical_formulas (domain);
GRANT SELECT ON public.canonical_formulas TO anon, authenticated;
ALTER TABLE public.canonical_formulas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_formulas_read ON public.canonical_formulas;
CREATE POLICY canonical_formulas_read ON public.canonical_formulas FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_formulas_locked ON public.canonical_formulas;
CREATE POLICY canonical_formulas_locked ON public.canonical_formulas FOR ALL USING (false) WITH CHECK (false);

INSERT INTO public.canonical_formulas (formula_id, name, domain, standard_ids, library_source, inputs, outputs, formula_text, description) VALUES
('mtbf_iso_14224', 'Mean Time Between Failures', 'maintenance',
 ARRAY['iso_14224'], 'sql:get_mtbf_by_machine',
 '[{"name":"hive_id","type":"uuid"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"mtbf_days","unit":"days","type":"numeric"}]'::jsonb,
 'MTBF = sum(uptime) / failure_count',
 'ISO 14224:2016 sec 9.3'),
('mttr_iso_14224', 'Mean Time To Repair', 'maintenance',
 ARRAY['iso_14224'], 'sql:get_mttr_by_machine',
 '[{"name":"hive_id","type":"uuid"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"mttr_hours","unit":"hours","type":"numeric"}]'::jsonb,
 'MTTR = sum(downtime_hours) / repair_count',
 'ISO 14224:2016 sec 9.4'),
('oee_iso_22400', 'Overall Equipment Effectiveness', 'maintenance',
 ARRAY['iso_22400_2'], 'python:python-api/analytics/descriptive.py:calc_oee',
 '[{"name":"logbook_entries","type":"list"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"oee_pct","unit":"percent","type":"numeric"}]'::jsonb,
 'OEE = Availability * Performance * Quality',
 'ISO 22400-2:2014'),
('availability_iso_14224', 'Availability', 'maintenance',
 ARRAY['iso_14224'], 'python:python-api/analytics/descriptive.py:calc_availability',
 '[{"name":"logbook_entries","type":"list"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"availability_pct","unit":"percent","type":"numeric"}]'::jsonb,
 'Availability = MTBF / (MTBF + MTTR)',
 'ISO 14224:2016'),
('pm_compliance_smrp', 'PM Compliance', 'maintenance',
 ARRAY['saeja_1011'], 'sql:v_pm_compliance_truth',
 '[{"name":"hive_id","type":"uuid"}]'::jsonb,
 '[{"name":"compliance_pct","unit":"percent","type":"numeric"}]'::jsonb,
 'Compliance = completed_on_time / scheduled',
 'SMRP 3.5 + SAE JA 1011'),
('rcm_consequence_saeja_1011', 'RCM Failure Consequence Distribution', 'maintenance',
 ARRAY['saeja_1011'], 'python:python-api/analytics/diagnostic.py:calc_rcm_consequence',
 '[{"name":"logbook_entries","type":"list"}]'::jsonb,
 '[{"name":"distribution","type":"object"}]'::jsonb,
 'Categorize each failure into safety/production/environment/cost/quality',
 'SAE JA 1011 RCM consequence taxonomy')
ON CONFLICT (formula_id) DO UPDATE
  SET name=EXCLUDED.name, domain=EXCLUDED.domain, standard_ids=EXCLUDED.standard_ids,
      library_source=EXCLUDED.library_source, inputs=EXCLUDED.inputs, outputs=EXCLUDED.outputs,
      formula_text=EXCLUDED.formula_text, description=EXCLUDED.description;


-- =============================================================================
-- PART 3. Tier C: canonical_agent_contracts + 7 brain output schemas
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.canonical_agent_contracts (
  contract_id   text PRIMARY KEY,
  agent         text NOT NULL,
  version       int  NOT NULL DEFAULT 1,
  json_schema   jsonb NOT NULL,
  consumers     text[] NOT NULL DEFAULT '{}',
  registered_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_agent_contracts IS
  'Tier C: JSON Schema registry for AI/brain outputs. Locks the response shape so multiple consumers can rely on identical fields. Versioned per agent.';

CREATE INDEX IF NOT EXISTS idx_canonical_agent_contracts_agent ON public.canonical_agent_contracts (agent);
GRANT SELECT ON public.canonical_agent_contracts TO anon, authenticated;
ALTER TABLE public.canonical_agent_contracts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_agent_contracts_read ON public.canonical_agent_contracts;
CREATE POLICY canonical_agent_contracts_read ON public.canonical_agent_contracts FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_agent_contracts_locked ON public.canonical_agent_contracts;
CREATE POLICY canonical_agent_contracts_locked ON public.canonical_agent_contracts FOR ALL USING (false) WITH CHECK (false);

INSERT INTO public.canonical_agent_contracts (contract_id, agent, version, json_schema, consumers) VALUES
('analytics_action_plan_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["summary","priorities"],"properties":{"summary":{"type":"string"},"priorities":{"type":"array","items":{"type":"object","required":["asset","action","urgency"],"properties":{"asset":{"type":"string"},"action":{"type":"string"},"why":{"type":"string"},"urgency":{"type":"string","enum":["CRITICAL","HIGH","MEDIUM","LOW"]},"eta":{"type":"string"}}}}}}'::jsonb,
 ARRAY['analytics.html','shift-brain.html','hive.html']),
('next_failure_forecast_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["predictions"],"properties":{"predictions":{"type":"array","items":{"type":"object","required":["machine","predicted_next","risk"],"properties":{"machine":{"type":"string"},"predicted_next":{"type":"string","format":"date"},"risk":{"type":"string","enum":["HIGH","MEDIUM","LOW"]},"basis":{"type":"string"}}}}}}'::jsonb,
 ARRAY['analytics.html','predictive.html','asset-hub.html']),
('parts_stockout_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["reorder"],"properties":{"reorder":{"type":"array","items":{"type":"object","required":["part_name","urgency","suggested_order"],"properties":{"part_name":{"type":"string"},"urgency":{"type":"string","enum":["CRITICAL","HIGH","MEDIUM"]},"suggested_order":{"type":"integer"},"days_until_stockout":{"type":"integer"},"basis":{"type":"string"}}}}}}'::jsonb,
 ARRAY['analytics.html','inventory.html','parts-tracker.html']),
('health_score_v1', 'batch-risk-scoring', 1,
 '{"type":"object","required":["asset","health_score","mtbf_days"],"properties":{"asset":{"type":"string"},"health_score":{"type":"number","minimum":0,"maximum":1},"mtbf_days":{"type":["number","null"]},"risk_level":{"type":"string","enum":["low","medium","high","critical"]},"top_factors":{"type":"array","items":{"type":"object"}}}}'::jsonb,
 ARRAY['predictive.html','asset-hub.html','analytics.html','shift-brain.html']),
('anomaly_baseline_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["assets"],"properties":{"assets":{"type":"array","items":{"type":"object","required":["machine","quality_flag"],"properties":{"machine":{"type":"string"},"quality_flag":{"type":"string","enum":["OK","STALE","ANOMALY"]},"baseline_mean":{"type":"number"},"baseline_std":{"type":"number"},"deviation_sigma":{"type":"number"}}}}}}'::jsonb,
 ARRAY['analytics.html','asset-hub.html']),
('parts_spike_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["spikes"],"properties":{"spikes":{"type":"array","items":{"type":"object","required":["part_name","spike_factor"],"properties":{"part_name":{"type":"string"},"spike_factor":{"type":"number"},"recent_consumption":{"type":"integer"},"baseline_consumption":{"type":"integer"}}}}}}'::jsonb,
 ARRAY['analytics.html','inventory.html']),
('priority_ranking_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["ranking"],"properties":{"ranking":{"type":"array","items":{"type":"object","required":["asset","priority_score"],"properties":{"asset":{"type":"string"},"priority_score":{"type":"number","minimum":0,"maximum":1},"contributing_factors":{"type":"array","items":{"type":"string"}}}}}}}'::jsonb,
 ARRAY['analytics.html','shift-brain.html','asset-hub.html'])
ON CONFLICT (contract_id) DO UPDATE
  SET agent=EXCLUDED.agent, version=EXCLUDED.version, json_schema=EXCLUDED.json_schema, consumers=EXCLUDED.consumers;


-- =============================================================================
-- PART 4. Tier B: v_project_truth + v_knowledge_truth
-- =============================================================================

CREATE OR REPLACE VIEW public.v_project_truth AS
SELECT
  p.id                          AS project_id,
  p.hive_id,
  p.name,
  p.type,
  p.status,
  p.priority,
  p.budget_pesos,
  p.start_date,
  p.target_end_date,
  p.actual_end_date,
  p.created_at,
  p.updated_at,
  (SELECT count(*) FROM public.project_items pi
     WHERE pi.project_id = p.id) AS item_count,
  (SELECT count(*) FROM public.project_items pi
     WHERE pi.project_id = p.id AND pi.status = 'done') AS items_done,
  (SELECT coalesce(sum(pi.estimated_cost_pesos), 0)::numeric FROM public.project_items pi
     WHERE pi.project_id = p.id) AS estimated_total_pesos,
  (SELECT max(ppl.logged_at) FROM public.project_progress_logs ppl
     WHERE ppl.project_id = p.id) AS last_progress_at,
  (SELECT count(*) FROM public.project_change_orders pco
     WHERE pco.project_id = p.id AND pco.status = 'approved') AS approved_change_orders,
  (SELECT count(*) FROM public.project_links pl
     WHERE pl.project_id = p.id) AS link_count
FROM public.projects p
WHERE p.status != 'archived';

COMMENT ON VIEW public.v_project_truth IS
  'Tier B canonical project rollup. Per project: counts + cost + change-order summary. Replaces ad-hoc joins of projects + project_items + project_progress_logs + project_change_orders.';
GRANT SELECT ON public.v_project_truth TO anon, authenticated;


CREATE OR REPLACE VIEW public.v_knowledge_truth AS
  SELECT 'fault'::text AS source, id, hive_id, content, embedding, created_at FROM public.fault_knowledge
  UNION ALL
  SELECT 'skill',   id, hive_id, content, embedding, created_at FROM public.skill_knowledge
  UNION ALL
  SELECT 'pm',      id, hive_id, content, embedding, created_at FROM public.pm_knowledge
  UNION ALL
  SELECT 'bom',     id, hive_id, content, embedding, created_at FROM public.bom_knowledge
  UNION ALL
  SELECT 'calc',    id, hive_id, content, embedding, created_at FROM public.calc_knowledge
  UNION ALL
  SELECT 'project', id, hive_id, content, embedding, created_at FROM public.project_knowledge;

COMMENT ON VIEW public.v_knowledge_truth IS
  'Tier B canonical RAG retrieval view. UNION ALL of all *_knowledge tables for unified pgvector semantic search.';
GRANT SELECT ON public.v_knowledge_truth TO anon, authenticated;


-- =============================================================================
-- PART 5. Tier E: v_audit_unified
-- =============================================================================

CREATE OR REPLACE VIEW public.v_audit_unified AS
  SELECT 'hive'::text AS audit_source, id, hive_id, worker_name, action, target_type, target_id, payload, created_at FROM public.hive_audit_log
  UNION ALL
  SELECT 'cmms',       id, hive_id, worker_name, action, target_type, target_id, payload, created_at FROM public.cmms_audit_log
  UNION ALL
  SELECT 'automation', id, hive_id, NULL::text, event_type, NULL::text, NULL::uuid, payload, created_at FROM public.automation_log
  UNION ALL
  SELECT 'gateway',    id, hive_id, NULL::text, route, 'edge_fn'::text, NULL::uuid, jsonb_build_object('status', status, 'latency_ms', latency_ms), created_at FROM public.gateway_audit_log;

COMMENT ON VIEW public.v_audit_unified IS
  'Tier E canonical audit trail. UNION ALL of hive_audit_log + cmms_audit_log + automation_log + gateway_audit_log.';
GRANT SELECT ON public.v_audit_unified TO anon, authenticated;


-- =============================================================================
-- PART 6. Register the new Tier B + E views in canonical_sources
-- =============================================================================

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description, contract, notes) VALUES
('project_truth', 'view', 'v_project_truth', 'architect', 'realtime',
 'Per project: counts + cost rollup + last-progress + change-order summary.',
 jsonb_build_object('key', jsonb_build_array('project_id'), 'hive_scoped', true,
                    'replaces_direct_reads_of', jsonb_build_array('projects','project_items','project_progress_logs','project_change_orders')),
 'Tier B. Used by project-manager + project-report + analytics-orchestrator project rollup.'),
('knowledge_truth', 'view', 'v_knowledge_truth', 'ai-engineer', 'realtime',
 'UNION ALL of all 6 *_knowledge tables for unified pgvector RAG retrieval.',
 jsonb_build_object('sources', jsonb_build_array('fault','skill','pm','bom','calc','project'), 'dim', 1536, 'hive_scoped', true),
 'Tier B. AMC + semantic-search edge fns read this single view.'),
('audit_unified', 'view', 'v_audit_unified', 'security', 'realtime',
 'UNION ALL of hive_audit_log + cmms_audit_log + automation_log + gateway_audit_log.',
 jsonb_build_object('sources', jsonb_build_array('hive','cmms','automation','gateway'), 'hive_scoped', true, 'append_only', true),
 'Tier E. audit-log.html + compliance reports read this canonical instead of 4 raw tables.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind=EXCLUDED.source_kind, source_name=EXCLUDED.source_name, owner_skill=EXCLUDED.owner_skill,
      freshness=EXCLUDED.freshness, description=EXCLUDED.description, contract=EXCLUDED.contract,
      notes=EXCLUDED.notes, registered_at=now();

COMMIT;
""")

content = ''.join(sql_parts)
with open(OUTPUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print(f'Wrote {OUTPUT} ({len(content)} bytes, {len(rows)} standards seeded)')
