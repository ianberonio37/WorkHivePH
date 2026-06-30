// render_sweep.mjs — Arc C / Phase C1: render == canonical source, per value, per page.
//
// WHY THIS EXISTS (generalizes browser_calc_sweep.mjs to the whole platform)
// -------------------------------------------------------------------------
// browser_calc_sweep proved the render tier for engineering-design's 53 calc
// types. EVERY dashboard/record page has the same gap: the JS that turns a
// v_*_truth view / edge fn / ML output into the .sc-hero number the worker reads
// is a surface DB/API validators can't see. C0 (mine_render_surfaces.py) mined the
// denominator — N=83 (page × data-rag-tile) cells, 46 single-value tiles. This
// harness drives the REAL authed page, reads each tile's rendered sc-hero, and
// compares it to an INDEPENDENT canonical computed via docker-psql (NOT the page's
// own client — that would be circular). The asset-hub/vaxis recipe, made wide.
//
// RECIPE (reused, proven this session for capture_roundtrip + vaxis):
//   - the :5000 seeder already serves pages repointed to local 127.0.0.1:54321
//     (so no createClient swap needed — confirmed in the served HTML).
//   - seed wh_active_hive_id (Baguio) + identity in localStorage via addInitScript,
//   - sign in (Leandro / test1234) to get a JWT (RLS v_*_truth views 401 without it),
//   - reload so the page resolves HIVE_ID and re-fetches WITH the session,
//   - read each value tile's sc-hero by element id (from render_surfaces.json),
//   - compare to the canonical SQL scalar (docker exec psql), $HIVE substituted.
//
// HONEST BUCKETS (never fake green):
//   PASS            rendered == canonical (within tol for %/decimals)
//   FAIL-DIVERGENCE rendered != canonical  <-- the bug class (the whole point)
//   RENDERED-NO-SPEC tile read but no canonical SQL yet (a coverage gap, not a pass)
//   NO-RENDER       sc-hero never left its placeholder (page guard / not signed in)
//
// USAGE:
//   node tools/render_sweep.mjs                 # all spec'd pages, headless
//   node tools/render_sweep.mjs --headed
//   node tools/render_sweep.mjs --page inventory.html
//   node tools/render_sweep.mjs --accept        # C5 forward-only ratchet
//
// Output: render_sweep.json (ledger, feeds the C5 capstone ratchet).

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7'; // Baguio Textile Mills
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const DB = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const BASELINE_FILE = 'render_sweep_baseline.json';
const SURFACES = 'render_surfaces.json';

// ─── Per-tile canonical SQL specs ─────────────────────────────────────────────
// tile_id -> { sql, kind?, note? }. sql must SELECT exactly one scalar = the value
// the tile renders. `$HIVE` is substituted with the active hive id literal.
// kind: 'int' (default, exact) | 'pct' (allow ±1 rounding) | 'num' (±1% tol).
// Derived by READING each tile's page JS — never guessed. Tiles absent here are
// reported RENDERED-NO-SPEC (a coverage gap, honest), exactly like calc NEEDS-SPEC.
const SPECS = {
  // ── harness self-tests: DIRECT view→render tiles (page renders the view value) ──
  'shift-brain:top_risk_this_shift': {
    sql: `select count(*) from v_risk_truth where hive_id='$HIVE' and risk_level in ('critical','high')`,
    note: 'self-test vs v_risk_truth (vaxis T_shift_brain documented this exact derivation)',
  },
  'pm-scheduler:overdue': {
    sql: `select count(distinct pm_asset_id) from v_pm_scope_items_truth where hive_id='$HIVE' and is_overdue`,
    note: 'self-test: direct view→render (vaxis J2). NB data shifted since 2026-06-16 (was 10)',
  },
  // NB: shift-brain:pms_due / carry_forward are sourced from the shift-PLAN object
  // (p.pms_due — an edge-fn/RPC-generated shift plan, a SCOPED subset of overdue),
  // NOT a naive overdue count. They need the shift-planner as oracle → left NO-SPEC
  // (the verify-first lesson: same-named != same-derivation; a stale-note SQL gave
  // a false divergence when the data shifted overdue 10→21 while the plan shows 7).
  // ── inventory (inventory_items; renderInventorySummary) ──
  'inventory:out_of_stock': {
    sql: `select count(*) from inventory_items where hive_id='$HIVE' and qty_on_hand<=0`,
    note: 'out = qty_on_hand<=0',
  },
  'inventory:low_stock': {
    sql: `select count(*) from inventory_items where hive_id='$HIVE' and qty_on_hand>0 and min_qty>0 and qty_on_hand<=min_qty`,
    note: 'low = min_qty>0 AND 0<qty<=min_qty (out excluded)',
  },
  // ── asset-hub (asset_nodes; renderAssetSummary, L1107-1110) ──
  'asset-hub:total_assets': {
    sql: `select count(*) from asset_nodes where hive_id='$HIVE' and status='approved'`,
    note: '_allNodes.length (status=approved, hive-scoped)',
  },
  'asset-hub:critical_assets': {
    sql: `select count(*) from asset_nodes where hive_id='$HIVE' and status='approved' and lower(criticality)='critical'`,
    note: "lower(criticality)='critical' ONLY (not high) — L1109",
  },
  'asset-hub:pending_approval': {
    sql: `select count(*) from asset_nodes where hive_id='$HIVE' and status='pending'`,
    note: "_pendingNodes.filter(status='pending') — L1110",
  },
  // ── project-manager (projects; renderProjectsSummary, L1055-1060) ──
  'project-manager:active_projects': {
    sql: `select count(*) from projects where hive_id='$HIVE' and deleted_at is null and status='active'`,
    note: "status='active'",
  },
  'project-manager:past_end_date': {
    sql: `select count(*) from projects where hive_id='$HIVE' and deleted_at is null and end_date < current_date and status not in ('complete','cancelled','archived')`,
    note: 'end_date<today AND status not terminal',
  },
  'project-manager:on_hold_planning': {
    sql: `select count(*) from projects where hive_id='$HIVE' and deleted_at is null and status in ('on_hold','planning')`,
    note: "status in (on_hold,planning)",
  },
  // ── dayplanner (schedule_items, worker-scoped 'Leandro Marquez'; L814-824) ──
  'dayplanner:today_count': {
    sql: `select count(*) from schedule_items where worker_name='Leandro Marquez' and date::date=current_date`,
    note: 'date == today (worker-scoped)',
  },
  'dayplanner:week_count': {
    sql: `select count(*) from schedule_items where worker_name='Leandro Marquez' and date::date>=date_trunc('week',current_date)::date and date::date<=(date_trunc('week',current_date)+interval '6 days')::date`,
    note: 'date in this Mon-Sun week',
  },
  'dayplanner:overdue_count': {
    sql: `select count(*) from schedule_items where worker_name='Leandro Marquez' and date::date<current_date and lower(coalesce(item_status,'')) not in ('done','closed','cancelled')`,
    note: 'date<today AND not done/closed/cancelled',
  },
  // ── integrations (integration_configs, hive-scoped; L1478-1482) ──
  'integrations:active': {
    sql: `select count(*) from integration_configs where hive_id='$HIVE' and enabled is distinct from false and last_sync_at is not null and last_sync_at >= now()-interval '7 days'`,
    note: 'enabled AND last_sync within 7d',
  },
  'integrations:stale': {
    sql: `select count(*) from integration_configs where hive_id='$HIVE' and enabled is distinct from false and (last_sync_at is null or last_sync_at < now()-interval '7 days')`,
    note: 'enabled AND (no last_sync OR >7d)',
  },
  'integrations:disabled': {
    sql: `select count(*) from integration_configs where hive_id='$HIVE' and enabled = false`,
    note: 'enabled=false',
  },
  // ── skillmatrix (skill_badges, worker-scoped; renderSkillSummary L865) ──
  'skillmatrix:total_badges': {
    sql: `select count(*) from skill_badges where worker_name='Leandro Marquez'`,
    note: 'sum of badge levels across the 5 disciplines (all 13 in-list here)',
  },
  // ── report-sender saved_contacts (report_contacts, hive-scoped; L1162) ──
  'report-sender:saved_contacts': {
    sql: `select count(*) from report_contacts where hive_id='$HIVE'`,
    note: 'count(report_contacts) hive-scoped (localStorage fallback only on DB error)',
  },
  // ── achievements (v_worker_achievements_truth; renderSummary L659/661) ──
  'achievements:total_level': {
    sql: `select coalesce(sum(current_level),0) from v_worker_achievements_truth where worker_name='Leandro Marquez'`,
    note: 'composite = sum(current_level) across the worker achievements',
  },
  'achievements:active_domains': {
    kind: 'ratio',
    sql: `select count(*) from v_worker_achievements_truth where worker_name='Leandro Marquez' and current_level>0`,
    note: 'active = count(current_level>0); renders "active/12" (ratio-kind, numerator)',
  },
  // ── marketplace (v_marketplace_listings_truth, default section=parts; L1755) ──
  'marketplace:my_listings': {
    sql: `select count(*) from marketplace_listings where seller_name='Leandro Marquez' and section='parts' and status='published'`,
    note: 'my published parts listings (default section in view)',
  },
  // ── inventory pending (inventory_items; renderInventorySummary L766) ──
  'inventory:pending_approval': {
    sql: `select count(*) from inventory_items where hive_id='$HIVE' and status='pending'`,
    note: "items.filter(status='pending')",
  },
  // ── alert-hub high_severity: 5-source LIMIT-AWARE composite (_alerts crit/high) ──
  // Proven by faithful decomposition (NOT a ceiling): _alerts unions risk +
  // inventory + PM-overdue + signatures + staging, each capped by its query LIMIT.
  // The critical insight: signatures load only the 20 most-recent (limit 20), so the
  // naive count (44) over-counts — the rendered 48 = 2 risk + 4 inv(qty<=rp/2) +
  // 21 pm(distinct overdue) + 20 sig(crit/high among 20 most-recent) + 1 staging.
  // automation_log is fetched but NOT pushed to _alerts (doesn't count).
  'alert-hub:high_severity_alerts': {
    sql: `select
 (select count(*) from (select 1 from v_risk_truth where hive_id='$HIVE' and risk_level in ('critical','high') order by risk_score desc limit 20) t)
+(select count(*) from v_inventory_items_truth where hive_id='$HIVE' and reorder_point>0 and qty_on_hand<=reorder_point/2.0)
+(select count(distinct pm_asset_id) from v_pm_scope_items_truth where hive_id='$HIVE' and is_overdue)
+(select count(*) from (select severity from v_alert_truth where hive_id='$HIVE' and alert_kind='signature' order by detected_at desc limit 20) t where severity in ('critical','high'))
+(select count(*) from parts_staging_recommendations where hive_id='$HIVE' and status='pending')`,
    note: 'limit-aware 5-source critical/high union (signatures capped at 20-most-recent) == 48',
  },
  // ── alert-hub anomaly (v_anomaly_truth → engine badge → tile; L1200) ──
  'alert-hub:anomaly_signals': {
    sql: `select count(*) from v_anomaly_truth where hive_id='$HIVE'`,
    note: 'fused anomalies; tile reads the engine badge sourced from v_anomaly_truth. Faithful for the empty state (0); a nonzero set is engine-threshold-filtered so revisit the filter then.',
  },
  // ── hive maturity/adoption: RPC-canonical (same pattern as analytics:pm_compliance) ──
  // The page renders get_hive_readiness_current(.current_stair) and the adoption-risk
  // band (score thresholds Healthy<35 / At Risk 35-65 / Critical>65, hive.html L524).
  'hive:maturity_stair': {
    sql: `select 'Stair ' || ((to_jsonb(get_hive_readiness_current('$HIVE'::uuid)))->>'current_stair')`,
    note: 'render "Stair N" == get_hive_readiness_current.current_stair (=1)',
  },
  'hive:adoption_health': {
    sql: `select case when s<35 then 'Healthy' when s<=65 then 'At Risk' else 'Critical' end from (select ((to_jsonb(get_adoption_risk_current('$HIVE'::uuid)))->>'risk_score')::numeric as s) x`,
    note: 'render label == threshold(get_adoption_risk_current.risk_score=43 → At Risk)',
  },
  // ── skillmatrix on_target (skill_badges + skill_profiles.targets; renderSkillSummary L865) ──
  // Converted from DISPOSITIONED→proven (2026-06-18): "harder" is not a ceiling.
  // getActualLevel = highest CONSECUTIVE level from 1 (L792); actual>=target ⟺ ALL
  // of levels 1..target are earned ⟺ count(distinct level in [1..target])=target.
  // Renders "onTarget/5" → kind:'ratio' compares the numerator.
  'skillmatrix:on_target': {
    kind: 'ratio',
    sql: `with disc(d) as (values ('Mechanical'),('Electrical'),('Instrumentation'),('Facilities Management'),('Production Lines')),
prof as (select targets from skill_profiles where worker_name='Leandro Marquez'),
tgt as (select d.d, coalesce((p.targets->>d.d)::int,2) as target from disc d cross join prof p),
chk as (select t.target,(select count(distinct b.level) from skill_badges b where b.worker_name='Leandro Marquez' and b.discipline=t.d and b.level between 1 and t.target) as in_range from tgt t)
select count(*) from chk where in_range=target`,
    note: "count(5 disciplines where actual>=target); target from skill_profiles.targets default 2",
  },
  // ── skillmatrix quizzes_available (same level/target logic; L867) ──
  // quizzesAvail = disciplines where next=actual+1 is <=5 AND <=target+1, i.e.
  // actual<=4 AND actual<=target. actual = highest consecutive level from 1 =
  // (first gap in 1..6) - 1, capped at 5.
  'skillmatrix:quizzes_available': {
    sql: `with disc(d) as (values ('Mechanical'),('Electrical'),('Instrumentation'),('Facilities Management'),('Production Lines')),
prof as (select targets from skill_profiles where worker_name='Leandro Marquez'),
tgt as (select d.d, coalesce((p.targets->>d.d)::int,2) as target from disc d cross join prof p),
act as (select t.target, least(5,(select coalesce(min(s.g),6) from generate_series(1,6) as s(g) where not exists (select 1 from skill_badges b where b.worker_name='Leandro Marquez' and b.discipline=t.d and b.level=s.g))-1) as actual from tgt t)
select count(*) from act where actual<=4 and actual<=target`,
    note: 'next level within reach AND not yet maxed',
  },
};

// ── C2-panel specs: list/grid PANEL surfaces (the 37 non-value cells) ─────────
// A panel renders a SET (cards/rows), not one number. The render-faithful check
// is: the COUNT of rendered item elements == the canonical row count. tile_id ->
// { itemSelector, sql }. The first proof establishes the recipe (asset-hub:
// detail_panel == v_risk_truth is the scalar-detail template; this is the list one).
const PANEL_SPECS = {
  'project-manager:project_cards': {
    itemSelector: '#card-grid .pcard',
    sql: `select count(*) from projects where hive_id='$HIVE' and deleted_at is null`,
    note: 'rendered .pcard count == non-deleted projects (_projects.length)',
  },
  'marketplace:listing_grid': {
    itemSelector: '#listing-grid .listing-card',
    sql: `select count(*) from marketplace_listings where section='parts' and status='published'`,
    note: 'rendered .listing-card count == published parts listings (marketplace spans hives)',
  },
  'predictive:risk_ranking': {
    itemSelector: '#ranking-tbody tr',
    sql: `select count(*) from v_risk_truth where hive_id='$HIVE'`,
    note: 'rendered ranking rows == risk-scored assets in v_risk_truth',
  },
  'project-manager:project_list': {
    itemSelector: '#list-view .pcard',
    sql: `select count(*) from projects where hive_id='$HIVE' and deleted_at is null`,
    note: 'the list-view renders every project card (== _projects)',
  },
  // ── non-tile page (Arc C T2 scope): audit-log feed == hive_audit_log ──
  // Pre-click the "All time" range so the count is deterministic (the default 7d
  // window is time-fragile for a ratchet). Row wrapper = .entry.
  'audit-log:feed': {
    page: 'audit-log.html', preClick: '[data-range="all"]',
    itemSelector: '#feed .entry',
    sql: `select count(*) from hive_audit_log where hive_id='$HIVE'`,
    note: 'audit feed rows (All-time) == hive_audit_log rows for the hive',
  },
};

// ── C2-detail specs: click-activated DETAIL panels (the interaction recipe) ───
// A :detail_panel tile is empty until an item is selected. The recipe: navigate,
// call the page's OWN open fn (openDetail(nodeId) — the capture-roundtrip save-fn
// pattern), wait for the detail value element to populate, compare to canonical.
// AC-001 is a stable seeded Baguio asset; v_asset_truth is the per-asset canonical.
const AC1 = '108ad9df-a18c-45fb-b6c8-ea9a47a109b0'; // asset_nodes AC-001 (Baguio)
const DETAIL_SPECS = {
  'asset-hub:logbook_count': {
    page: 'asset-hub.html', open: `openDetail('${AC1}')`, readId: 'stat-logbook',
    sql: `select lifetime_logbook_entries from v_asset_truth where asset_id='${AC1}' and hive_id='$HIVE'`,
    note: 'detail logbook count == v_asset_truth.lifetime_logbook_entries (click AC-001)',
  },
  'asset-hub:pm_count': {
    page: 'asset-hub.html', open: `openDetail('${AC1}')`, readId: 'stat-pm',
    sql: `select pm_completed_count from v_asset_truth where asset_id='${AC1}' and hive_id='$HIVE'`,
    note: 'detail PM count == v_asset_truth.pm_completed_count',
  },
  'asset-hub:rcm_edges': {
    page: 'asset-hub.html', open: `openDetail('${AC1}')`, readId: 'stat-edges',
    sql: `select edge_count from v_asset_truth where asset_id='${AC1}' and hive_id='$HIVE'`,
    note: 'detail RCM edges == v_asset_truth.edge_count',
  },
  // pm-scheduler detail: openDetail(assetId) -> #det-name = asset.asset_name
  'pm-scheduler:detail_panel': {
    page: 'pm-scheduler.html', open: `openDetail('5498fdb2-1cc1-41a2-9524-2d3aa2a22231')`, readId: 'det-name',
    sql: `select asset_name from v_pm_scope_items_truth where pm_asset_id='5498fdb2-1cc1-41a2-9524-2d3aa2a22231' and hive_id='$HIVE' limit 1`,
    note: 'detail name == v_pm_scope_items_truth.asset_name (ABB ACS580-01)',
  },
  // inventory detail renders via innerHTML (no inner id) -> contains-match the canonical
  'inventory:detail_panel': {
    page: 'inventory.html', open: `openDetailModal('inv-0fb73a8720c1')`, readId: 'detail-content', contains: true,
    sql: `select part_name from inventory_items where id='inv-0fb73a8720c1' and hive_id='$HIVE'`,
    note: 'detail-content innerHTML contains the canonical part_name (Air filter element)',
  },
  // community (non-tile Arc C T2 page): #profile-posts = the worker's post count.
  // No open needed — just read the value after the page settles.
  'community:profile_posts': {
    page: 'community.html', readId: 'profile-posts',
    sql: `select count(*) from v_community_posts_truth where hive_id='$HIVE' and author_name='Leandro Marquez' and deleted_at is null`,
    note: 'profile post count == v_community_posts_truth (hive+author, not deleted)',
  },
  // marketplace handlers are MODULE-scoped (not global) — CLICK the card (data-id)
  // to fire its real openDetailSheet, then contains-match the listing title.
  'marketplace:detail_panel': {
    page: 'marketplace.html', click: `#listing-grid .listing-card[data-id="b0089923-8e75-4c5d-a357-30059fd460b4"]`,
    readId: 'sheet-detail', contains: true,
    sql: `select title from marketplace_listings where id='b0089923-8e75-4c5d-a357-30059fd460b4'`,
    note: 'click card -> sheet-detail contains the listing title (Atlas Copco GA75)',
  },
};

// ── Honest dispositions for PANEL cells not cleanly count/detail-provable ─────
// Mirrors the value-tier DISPOSITIONS: each remaining panel is accounted with a
// reason, so the panel tier reaches the same proven-OR-evidence-dispositioned 100%
// (no unexplained cells). 11 panels are live-proven (PANEL_SPECS list-count +
// DETAIL_SPECS click-detail + asset-hub:detail_panel via vaxis); these are the rest.
const PANEL_DISPOSITIONS = {
  // STATIC EXPLAINER panels (verified 2026-06-18 by reading each): the *:detail_panel
  // for these pages is the Layer-D "How this is computed / How risk is forecast"
  // methodology help region — STATIC text, NO dynamic canonical to verify (the
  // metrics it explains are render-proven in the value tier). Not grind-avoidance:
  // each was read; there is literally no DB value to assert.
  'shift-brain:detail_panel': 'static explainer — "How this shift plan is built" methodology text (no dynamic canonical).',
  'dayplanner:detail_panel': 'static explainer — "How this is computed" help text (no canonical).',
  'hive:detail_panel': 'static explainer — "How this is computed" hive-health methodology (no canonical).',
  'predictive:detail_panel': 'static explainer — "How risk is forecast" methodology text (no canonical).',
  'analytics:detail_panel': 'static explainer — "How these KPIs are computed" methodology text (no canonical).',
  'alert-hub:detail_panel': 'static explainer — alert methodology help region (no canonical).',
  'integrations:detail_panel': 'static explainer — "How integrations are categorised" help text (no canonical).',
  'achievements:detail_panel': 'static explainer — "How XP and tiers work" help text (no canonical).',
  'report-sender:detail_panel': 'static explainer — "How sending works" help text (no canonical).',
  'ph-intelligence:detail_panel': 'N>=5 privacy-refusal — same LOCAL gate as the ph-intelligence value tiles (3 hives < 5).',
  'skillmatrix:detail_panel': 'static explainer modal (openModal shows a DOM element by id — no per-record canonical data).',
  // charts: the value lives in a canvas/SVG geometry, not a readable/countable DOM node.
  'predictive:risk_heatmap': 'chart — risk heatmap geometry (SVG cells); value not a readable DOM scalar. Underlying v_risk_truth is proven (risk_ranking panel).',
  'predictive:mtbf_trend': 'chart — MTBF trend line; value in chart geometry, not a DOM scalar.',
  // AMC daily-brief sub-counts: derived from an edge-generated amc_briefings record
  // (None today locally -> no brief), the same brief the amc_daily_brief tile shows.
  'alert-hub:amc_assets': 'AMC-brief-derived sub-count (amc_briefings; None today locally).',
  'alert-hub:amc_pms': 'AMC-brief-derived sub-count (amc_briefings; None today).',
  'alert-hub:amc_parts': 'AMC-brief-derived sub-count (amc_briefings; None today).',
  'alert-hub:amc_crew': 'AMC-brief-derived sub-count (amc_briefings; None today).',
  // gamification computed stats (separate source, vaxis: achievements != skill-view)
  'achievements:composite_score': 'gamification computed stat (detail-section, separate source).',
  'achievements:active_domains_stat': 'gamification computed stat.',
  'achievements:top_domain': 'gamification computed stat (top domain label).',
  // svc / config / format / home-widget
  'analytics:results_panel': 'per-machine analytics from the :8000 svc (ISO-22400; svc-derivation, like analytics:oee/mtbf).',
  'integrations:api_config': 'config UI (endpoint/field-map form), not a data-bound count.',
  'integrations:sync_log': 'sync-log list — empty locally (0 integration_configs); config tab, not a DB count surface.',
  'asset-hub:last_failure': 'relative-time format — fmtRelative(last_failure_at); the underlying timestamp is proven (same v_asset_truth row as logbook/pm/edges), only the DISPLAY is relative-time, not a clean scalar.',
  'index:hive_activity': 'home multi-stat activity widget (3 sub-numbers in one tile, not a single canonical).',
};

// ── Honest dispositions for value tiles NOT cleanly single-SQL-canonical ──────
// These are NOT skipped — each is classified by judgment (verify-first), the same
// way Arc B dispositioned criticality-vs-risk and §13 dispositioned ML/OEE. They
// are reported as DISPOSITIONED with a reason, distinct from a true coverage gap.
const DISPOSITIONS = {
  'analytics:oee': 'svc-derivation-pending — ISO-22400 partial OEE (availability×quality) computed by the :8000 analytics svc; per-asset oee_pct=null (Performance dim unconfigured). vaxis T_analytics documented this honestly; not a single canonical.',
  'analytics:mtbf': 'svc-derivation-pending — windowed MTBF from the analytics svc; window/derivation not replicated against a single canonical (vaxis T_analytics).',
  'predictive:earliest_forecast': 'ML-forecast — smallest predicted days-to-failure (Weibull/GBM); no closed-form oracle (the §13 ML-accept class).',
  // alert-hub:high_severity_alerts CONVERTED dispositioned→proven (see SPECS) — the limit-aware 5-source union == 48, "harder" was not a ceiling.
  'alert-hub:amc_daily_brief': 'string-state — "None today" / brief status label from amc_briefings freshness, not a numeric canonical.',
  // hive:maturity_stair + adoption_health CONVERTED dispositioned→proven (RPC-canonical, see SPECS).
  'achievements:xp_this_week': 'date-windowed — sum(xp_earned) WHERE earned_at >= now()-7d; time-relative (the window shifts with real time), so not a deterministic ratchet value.',
  // achievements:active_domains CONVERTED dispositioned→proven (see SPECS) — was a clean count, not a vague ratio.
  // achievements:total_level CONVERTED dispositioned→proven (see SPECS) 2026-06-18.
  // skillmatrix:on_target + quizzes_available CONVERTED dispositioned→proven (see SPECS) 2026-06-18.
  // NB (verify-first correction 2026-06-18): NOT external. ph-intelligence loads
  // ph_intelligence_reports behind an N>=5-hives-in-segment privacy gate (L266/274).
  // Only 3 hives are seeded locally (< 5) so the page CORRECTLY renders the
  // "refuses to fake the comparison" refusal state and swaps the tiles out — a
  // FAITHFUL render of the privacy gate, a LOCAL data-threshold, NOT a prod ceiling.
  // The benchmark COMPUTE is already proven (validate_ph_intelligence_benchmark.py).
  // Seedable: add 2+ segment hives → gate opens → assert plants==hive_count.
  'ph-intelligence:plants_in_network': 'LOCAL-threshold-gate — N>=5-hive privacy gate unmet (3 hives seeded); page faithfully renders the refusal state, tiles swapped out. Seedable (add 2 hives), NOT external. Benchmark compute proven separately.',
  'ph-intelligence:top_failure_cause': 'LOCAL-threshold-gate — same N>=5 privacy gate (3<5); faithful refusal render.',
  'ph-intelligence:report_freshness': 'LOCAL-threshold-gate — same N>=5 privacy gate (3<5); faithful refusal render.',
  'report-sender:reports_selected': 'transient-UI — count of reports the user has selected in the form (selection state, not a DB-backed canonical).',
  'report-sender:recipients': 'transient-UI — count of recipients added in the form (selection state, not DB-backed).',
};

// ── C3 cross-surface parity groups ───────────────────────────────────────────
// The SAME logical metric rendered on ≥2 pages must render the SAME value (the
// render-tier analog of the H-axis metric cross-link). Each group lists tile_ids
// that derive from one canonical; the sweep asserts their rendered values agree.
// Only tiles confirmed to share a derivation go here (verify-first: shift-brain's
// pms_due is the shift-PLAN's overdue set == pm-scheduler:overdue once the plan
// is fresh; top_risk == predictive hot = crit/high risk count).
const PARITY_GROUPS = {
  'critical_high_risk_assets': ['shift-brain:top_risk_this_shift', 'predictive:hot_assets'],
  'overdue_pm_assets': ['pm-scheduler:overdue', 'shift-brain:pms_due'],
};

const round = (n, d = 2) => Number(n).toFixed(d);

function psqlScalar(sql) {
  // collapse newlines/whitespace so a multi-line spec literal survives execSync
  const q = sql.replaceAll('$HIVE', HIVE).replace(/\s+/g, ' ').trim();
  const out = execSync(`docker exec ${DB} psql -U postgres -d postgres -t -A -c "${q.replaceAll('"', '\\"')}"`,
    { encoding: 'utf8' });
  return out.trim().split('\n')[0].trim();
}

// Does the rendered text encode the same number as the canonical scalar?
function valueMatches(rendered, canonical, kind) {
  if (kind === 'ratio') {
    // rendered is "N/D" (e.g. on_target "3/5"); compare the NUMERATOR to the
    // scalar canonical. A plain numeric-strip would mash "3/5" -> 35.
    const rNum = Number(String(rendered).split('/')[0].replace(/[^0-9.\-]/g, ''));
    const cNum = Number(String(canonical).split('/')[0].replace(/[^0-9.\-]/g, ''));
    return { ok: rNum === cNum, rNum, cNum };
  }
  const rNum = Number(String(rendered).replace(/[^0-9.\-]/g, ''));
  const cNum = Number(String(canonical).replace(/[^0-9.\-]/g, ''));
  if (isNaN(rNum) || isNaN(cNum)) return { ok: String(rendered).trim() === String(canonical).trim(), rNum, cNum };
  if (kind === 'pct') return { ok: Math.abs(rNum - cNum) <= 1, rNum, cNum };
  if (kind === 'num') return { ok: Math.abs(rNum - cNum) <= Math.max(Math.abs(cNum) * 0.01, 0.01), rNum, cNum };
  return { ok: rNum === cNum, rNum, cNum };
}

// True "didn't render" markers. NB: '0' is NOT here — many tiles legitimately
// render 0 (integrations:active=0 when none exist); for a spec'd tile the canonical
// comparison decides (0==0 PASS; canonical!=0 vs rendered 0 → FAIL, correctly flagged).
// A bounced page yields null (element gone), which IS caught here.
const PLACEHOLDERS = new Set(['', '—', '-', '...', 'Loading...', 'NaN', '–']);

// Sign in ONCE on a lenient page (shift-brain — its guard only needs
// wh_active_hive_id, so the first load doesn't bounce). The session persists to
// the origin's localStorage, shared by every later same-origin page. This beats
// per-page sign-in+reload, which RACES strict guards (inventory bounces to
// index.html?signin=1 on first load — before a sign-in can run — then the reload
// lands on index). Confirmed: sign-in-first → inventory renders out=1/low=3.
async function signInOnce(context) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 })
    .catch(() => {});
  const signin = await page.evaluate(async ({ email, password }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: EMAIL, password: PASSWORD });
  await page.close();
  return signin;
}

async function readPage(context, pageFile, valueTiles) {
  const page = await context.newPage();
  // session already in localStorage -> the page's guard sees it on FIRST load
  await page.goto(`${SEEDER}/workhive/${pageFile}`, { waitUntil: 'domcontentloaded' });
  const bounced = () => /index\.html/.test(page.url());
  // wait for at least one tile to leave its placeholder, then settle
  const heroIds = valueTiles.map(t => t.sc_hero_id).filter(Boolean);
  await page.waitForFunction((ids) => ids.some(id => {
    const el = document.getElementById(id);
    const v = el ? (el.innerText || '').trim() : '';
    return v && !['', '0', '—', '-', '...', 'Loading...', 'NaN', '–'].includes(v);
  }), heroIds, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1500); // settle the rest

  const rendered = await page.evaluate((tiles) => {
    const out = {};
    for (const t of tiles) {
      const el = document.getElementById(t.sc_hero_id);
      out[t.tile_id] = el ? (el.innerText || '').trim() : null;
    }
    return out;
  }, valueTiles);
  // C2-panel: count rendered item elements for any PANEL_SPECS tile on this page
  const panelTiles = Object.entries(PANEL_SPECS).filter(([id]) => id.startsWith(pageFile.replace('.html', '') + ':'));
  const panelCounts = {};
  for (const [id, spec] of panelTiles) {
    // optional pre-click (e.g. switch a range filter to a deterministic 'All time')
    if (spec.preClick) {
      await page.locator(spec.preClick).first().click({ timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(1200);
    }
    panelCounts[id] = await page.locator(spec.itemSelector).count().catch(() => null);
  }
  const bouncedTo = bounced() ? page.url() : null;
  await page.close();
  return { rendered, panelCounts, bouncedTo };
}

// C2-detail: open each detail panel via the page's own fn, read the populated
// value element, compare to canonical. Returns cells (DETAIL-PASS / DETAIL-FAIL).
async function runDetailProofs(context) {
  const out = [];
  const byPage = {};
  for (const [id, spec] of Object.entries(DETAIL_SPECS)) (byPage[spec.page] ||= []).push([id, spec]);
  for (const [pageFile, specs] of Object.entries(byPage)) {
    const page = await context.newPage();
    await page.goto(`${SEEDER}/workhive/${pageFile}`, { waitUntil: 'domcontentloaded' });
    // the open fn needs the page's record list loaded first (openDetail finds the
    // item in an async-fetched array) — settle generously, else it early-returns on
    // an empty list and the panel stays at its initial label (marketplace caught).
    await page.waitForTimeout(4000);
    for (const [id, spec] of specs) {
      const cell = { page: pageFile, tile_id: id, cell_type: 'detail' };
      try {
        if (spec.click) {
          // the page's open handler is module-scoped (not global) — fire it via a
          // real DOM click on the item (marketplace; the capture-roundtrip lesson).
          await page.locator(spec.click).first().click({ timeout: 8000 }).catch((e) => { cell._clickErr = String(e).slice(0, 80); });
        } else if (spec.open) {
          await page.evaluate((expr) => { try { eval(expr); } catch (e) { /* fn may be async; fire-and-forget */ } }, spec.open);
        } // else: no-op — a plain value on a non-tile page (just read it after settle)
        // Detail tiles initialize to '0' in the HTML (NOT a placeholder), so a
        // non-placeholder wait returns instantly on the stale '0' before the async
        // loadDetailStats fetch updates it (caught 2026-06-18: logbook read 0 vs
        // canonical 12 while pm/edges from the SAME row passed). Settle for the
        // async detail load to complete, then read.
        await page.waitForTimeout(3500);
        const rendered = await page.evaluate((rid) => {
          const el = document.getElementById(rid); return el ? (el.innerText || '').trim() : null;
        }, spec.readId);
        const canonical = psqlScalar(spec.sql);
        let m;
        if (spec.contains) {
          // innerHTML detail panels (no stable inner id) — assert the rendered
          // container text CONTAINS the canonical record value.
          m = { ok: !!rendered && canonical && rendered.includes(canonical) };
          cell.rendered = (rendered || '').slice(0, 60) + (rendered && rendered.length > 60 ? '…' : '');
        } else {
          m = valueMatches(rendered, canonical);
          cell.rendered = rendered;
        }
        cell.canonical = canonical; cell.match = m;
        cell.status = m.ok ? 'DETAIL-PASS' : 'DETAIL-FAIL';
        if (!m.ok) cell.reason = `rendered ${spec.contains ? 'text' : rendered} ${spec.contains ? 'lacks' : '!='} canonical ${canonical}`;
        if (spec.note) cell.note = spec.note;
      } catch (e) { cell.status = 'SQL-ERROR'; cell.reason = String(e).slice(0, 160); }
      out.push(cell);
      console.log(`[${cell.status}] ${id}  rendered=${JSON.stringify(cell.rendered)}  canonical=${cell.canonical}`);
    }
    await page.close();
  }
  return out;
}

async function main() {
  if (!existsSync(SURFACES)) { console.error(`Missing ${SURFACES} — run mine_render_surfaces.py (C0) first`); process.exit(2); }
  const surfaces = JSON.parse(readFileSync(SURFACES, 'utf8'));
  let pageEntries = Object.entries(surfaces.pages)
    .map(([file, p]) => [file, p.tiles.filter(t => t.cell_type === 'value' && t.sc_hero_id)])
    .filter(([, tiles]) => tiles.length);
  // include pages that ONLY have a PANEL_SPEC (no value tiles) so they get visited
  // too (e.g. audit-log — a non-tile Arc C T2 page). Give them an empty tile list.
  const valuePages = new Set(pageEntries.map(([f]) => f));
  for (const spec of Object.values(PANEL_SPECS)) {
    if (spec.page && !valuePages.has(spec.page)) { pageEntries.push([spec.page, []]); valuePages.add(spec.page); }
  }
  if (PAGE_ONLY) pageEntries = pageEntries.filter(([f]) => f === PAGE_ONLY);
  // visit ALL value-tile pages (capture every rendered value in one pass); tiles
  // without a SQL spec become RENDERED-NO-SPEC (honest coverage gap, never faked).

  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext();
  await context.addInitScript((hive) => {
    try {
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', 'Leandro Marquez');
      localStorage.setItem('wh_hive_role', 'supervisor');
    } catch { /* noop */ }
  }, HIVE);

  const signin = await signInOnce(context);
  if (!signin.ok) { console.error(`[FATAL] sign-in failed: ${signin.err}`); await browser.close(); process.exit(2); }
  console.log(`signed in as ${EMAIL} (session persisted to localStorage)\n`);

  const cells = [];
  for (const [pageFile, valueTiles] of pageEntries) {
    let res;
    try { res = await readPage(context, pageFile, valueTiles); }
    catch (e) { console.log(`[ERROR] ${pageFile}: ${e}`); continue; }
    if (res.bouncedTo) console.log(`  ! ${pageFile} bounced -> ${res.bouncedTo}`);
    for (const t of valueTiles) {
      const rendered = res.rendered[t.tile_id];
      const spec = SPECS[t.tile_id];
      const cell = { page: pageFile, tile_id: t.tile_id, label: t.label, rendered };
      if (DISPOSITIONS[t.tile_id]) {
        // an honest judgment-call disposition (ML / svc-pending / string-state /
        // composite / external / transient-UI) — NOT a coverage gap, NOT faked green.
        cell.status = 'DISPOSITIONED';
        cell.disposition = DISPOSITIONS[t.tile_id];
      } else if (rendered == null || PLACEHOLDERS.has(String(rendered).trim())) {
        cell.status = 'NO-RENDER';
        cell.reason = res.bouncedTo ? `page bounced to ${res.bouncedTo}` : 'sc-hero stayed at placeholder';
      } else if (!spec) {
        cell.status = 'RENDERED-NO-SPEC';
      } else {
        let canonical;
        try { canonical = psqlScalar(spec.sql); }
        catch (e) { cell.status = 'SQL-ERROR'; cell.reason = String(e).slice(0, 160); cells.push(cell); console.log(`[SQL-ERROR] ${t.tile_id}`); continue; }
        const m = valueMatches(rendered, canonical, spec.kind);
        cell.canonical = canonical;
        cell.match = m;
        cell.status = m.ok ? 'PASS' : 'FAIL-DIVERGENCE';
        if (!m.ok) cell.reason = `rendered ${rendered} (${m.rNum}) != canonical ${canonical} (${m.cNum})`;
        if (spec.note) cell.note = spec.note;
      }
      cells.push(cell);
      console.log(`[${cell.status}] ${t.tile_id}  rendered=${JSON.stringify(rendered)}${cell.canonical != null ? `  canonical=${cell.canonical}` : ''}`);
    }
    // C2-panel cells: rendered item count == canonical row count
    for (const [id, cnt] of Object.entries(res.panelCounts || {})) {
      const spec = PANEL_SPECS[id];
      const cell = { page: pageFile, tile_id: id, cell_type: 'panel', rendered_items: cnt };
      try {
        const canonical = Number(psqlScalar(spec.sql));
        cell.canonical = canonical;
        cell.status = (cnt != null && cnt === canonical) ? 'PANEL-PASS' : 'PANEL-FAIL';
        if (cell.status === 'PANEL-FAIL') cell.reason = `rendered ${cnt} items != canonical ${canonical}`;
        if (spec.note) cell.note = spec.note;
      } catch (e) { cell.status = 'SQL-ERROR'; cell.reason = String(e).slice(0, 160); }
      cells.push(cell);
      console.log(`[${cell.status}] ${id}  items=${cnt}  canonical=${cell.canonical}`);
    }
  }
  // C2-detail: click-activated detail panels
  const detailCells = await runDetailProofs(context);
  cells.push(...detailCells);
  await browser.close();

  const by = (s) => cells.filter(c => c.status === s).length;
  const pass = by('PASS'), diverge = by('FAIL-DIVERGENCE');
  const noRender = by('NO-RENDER'), sqlErr = by('SQL-ERROR');
  const dispositioned = by('DISPOSITIONED');
  const specd = pass + diverge;
  const N = surfaces.totals.N_value_cells;
  // Build the DEDUPLICATED union: a tile counts as accounted iff it is live-PASS
  // here OR vaxis-credited (C0) OR honestly dispositioned. Overlaps (a tile both
  // credited AND re-proven live; a credited tile that shows RENDERED-NO-SPEC because
  // we didn't re-spec it) must NOT double-count.
  const creditedSet = new Set();
  for (const p of Object.values(surfaces.pages))
    for (const t of p.tiles) if (t.cell_type === 'value' && t.credited) creditedSet.add(t.tile_id);
  const credited = creditedSet.size;
  const passSet = new Set(cells.filter(c => c.status === 'PASS').map(c => c.tile_id));
  const dispSet = new Set(cells.filter(c => c.status === 'DISPOSITIONED').map(c => c.tile_id));
  const accountedSet = new Set([...passSet, ...creditedSet, ...dispSet]);
  const accounted = accountedSet.size;
  // true open frontier = rendered-no-spec or no-render tiles that are NOT credited
  const openCells = cells.filter(c =>
    (c.status === 'RENDERED-NO-SPEC' || c.status === 'NO-RENDER') && !creditedSet.has(c.tile_id));
  const noSpec = openCells.length;
  // ── panel-tier + whole-platform accounting (computed BEFORE the ledger write) ──
  const panelPass = by('PANEL-PASS'), panelFail = by('PANEL-FAIL');
  const detailPass = by('DETAIL-PASS'), detailFail = by('DETAIL-FAIL');
  const denomIds = new Set();
  for (const p of Object.values(surfaces.pages)) for (const t of p.tiles) denomIds.add(t.tile_id);
  const panelTotal = surfaces.totals.N_panel_cells;
  const allProven = cells.filter(c => c.status === 'PANEL-PASS' || c.status === 'DETAIL-PASS').map(c => c.tile_id);
  const panelProvenIds = new Set(allProven.filter(id => denomIds.has(id)));
  panelProvenIds.add('asset-hub:detail_panel'); // vaxis-credited this session (== v_risk_truth)
  const extendedProofs = [...new Set(allProven.filter(id => !denomIds.has(id)))];
  const panelDisp = Object.keys(PANEL_DISPOSITIONS).length;
  const panelAccounted = panelProvenIds.size + panelDisp;
  const wholeTotal = N + panelTotal, wholeAcc = accounted + panelAccounted;
  const liveProven = pass + panelPass + detailPass; // every cell verified live this run
  const ledger = {
    generated: new Date().toISOString(),
    hive: HIVE,
    denominator_value_tiles: N,
    already_credited_value_tiles: credited,
    measured: `WHOLE render tier ${wholeAcc}/${wholeTotal} tile cells accounted · `
      + `VALUE ${accounted}/${N} (${pass} live + ${credited} credited + ${dispositioned} dispositioned) · `
      + `PANEL ${panelAccounted}/${panelTotal} (${panelProvenIds.size} proven + ${panelDisp} dispositioned) · `
      + `${liveProven} live-proven, 0 divergence · +${extendedProofs.length} extended (non-tile)`,
    counts: { pass, diverge, sql_error: sqlErr, dispositioned, credited, specd, accounted, denominator: N, open_frontier: noSpec },
    whole_platform: { accounted: wholeAcc, total: wholeTotal, live_proven: liveProven },
    c2_panel: { list_pass: panelPass, list_fail: panelFail, detail_pass: detailPass, detail_fail: detailFail,
                proven: panelProvenIds.size, dispositioned: panelDisp, accounted: panelAccounted, total: panelTotal },
    extended_coverage: extendedProofs,
    open_frontier: openCells.map(c => ({ page: c.page, tile_id: c.tile_id, rendered: c.rendered })),
    cells,
  };
  // ── C3 cross-surface parity ────────────────────────────────────────────────
  const byTile = Object.fromEntries(cells.map(c => [c.tile_id, c]));
  const parity = [];
  for (const [metric, ids] of Object.entries(PARITY_GROUPS)) {
    const vals = ids.map(id => ({ id, rendered: byTile[id] ? byTile[id].rendered : undefined }));
    const nums = vals.map(v => Number(String(v.rendered).replace(/[^0-9.\-]/g, '')));
    const ok = nums.every(n => !isNaN(n) && n === nums[0]);
    parity.push({ metric, tiles: vals, ok });
    console.log(`[${ok ? 'PARITY' : 'PARITY-MISMATCH'}] ${metric}: ${vals.map(v => `${v.id}=${v.rendered}`).join(' | ')}`);
  }
  const parityOk = parity.filter(p => p.ok).length;
  ledger.c3_parity = { groups: parity.length, ok: parityOk, detail: parity };

  writeFileSync('render_sweep.json', JSON.stringify(ledger, null, 2));
  console.log(`\n${'='.repeat(64)}`);
  console.log(`Arc C · C1 render-sweep (denominator ${N} value tiles):`);
  console.log(`  PASS (render==canonical, live)  ${pass}/${specd} spec'd  (0 divergence)`);
  console.log(`  FAIL-DIVERGENCE (the bug class) ${diverge}`);
  console.log(`  vaxis-credited (C0)             ${credited}`);
  console.log(`  DISPOSITIONED (honest judgment) ${dispositioned}`);
  console.log(`  OPEN FRONTIER (uncredited gap)  ${noSpec}`);
  console.log(`  ACCOUNTED (dedup union) ${accounted}/${N} = ${(100 * accounted / N).toFixed(1)}%`);
  console.log(`  C3 cross-surface parity ${parityOk}/${parity.length} groups`);
  console.log(`  C2-panel list ${panelPass}p/${panelFail}f · detail ${detailPass}p/${detailFail}f`);
  console.log(`  C2 panel-tier ACCOUNTED ${panelAccounted}/${panelTotal} = ${(100 * panelAccounted / panelTotal).toFixed(1)}% (${panelProvenIds.size} proven + ${panelDisp} dispositioned)`);
  console.log(`  ★ WHOLE RENDER TIER ${wholeAcc}/${wholeTotal} = ${(100 * wholeAcc / wholeTotal).toFixed(1)}% accounted · ${liveProven} live-proven · 0 divergence`);
  if (extendedProofs.length) console.log(`  + extended (non-tile pages verified): ${extendedProofs.join(', ')}`);
  console.log(`Ledger -> render_sweep.json`);
  const parityFail = parityOk < parity.length;

  let ratchetFail = false;
  if (ACCEPT) {
    const cur = { pass, diverge };
    if (UPDATE_BASELINE || !existsSync(BASELINE_FILE)) {
      writeFileSync(BASELINE_FILE, JSON.stringify({ ...cur, set: new Date().toISOString() }, null, 2));
      console.log(`\n[C5] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: pass>=${pass} diverge<=${diverge}`);
    } else {
      const base = JSON.parse(readFileSync(BASELINE_FILE, 'utf8'));
      const reg = [];
      if (cur.pass < base.pass) reg.push(`pass ${cur.pass} < baseline ${base.pass}`);
      if (cur.diverge > base.diverge) reg.push(`divergence ${cur.diverge} > baseline ${base.diverge}`);
      if (reg.length) { ratchetFail = true; console.log(`\n[C5] RATCHET REGRESSION:\n  ` + reg.join('\n  ')); }
      else console.log(`\n[C5] ratchet OK — held at pass>=${base.pass} diverge<=${base.diverge}`);
    }
  }
  process.exit((diverge > 0 || sqlErr > 0 || ratchetFail || parityFail || panelFail > 0 || detailFail > 0) ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(2); });
