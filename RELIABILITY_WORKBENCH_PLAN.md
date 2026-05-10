# Reliability Engineering Workbench: Plan

Date: 2026-05-09. Author: Reliability Workbench planning session, building on
the Asset Brain + Canonical Sources foundation shipped earlier this conversation.

The platform's Asset Brain knows *what* every asset is. The Predictive layer
(rules-v2 with structured top_factors) knows *how risky* it is. The Workbench
adds *why it fails, what to do about it, and when to inspect for it*. Four
sub-tools, sequenced so each builds on the previous.

## What this is and why now

Reliability engineers currently leave WorkHive to do RCM, FMEA, Weibull, and
P-F interval analysis in Excel. Bringing those tools in turns the platform
from operations tool into engineering platform: different audience (manager
+ reliability engineer), different price tier, different competitive
landscape.

Three things changed in the last week that make this the right move now:

1. **`asset_nodes`** (Asset Brain Phase 0) gives every asset a uuid and a
   hierarchy (ISO 14224 levels: enterprise / site / plant / unit / equipment /
   component). RCM and FMEA both work per-equipment with reference back to
   parent / child / sister context. We have that for free.
2. **`v_asset_truth`** + **`v_risk_truth`** (Phase A.2 + A.3) give every reader
   a single shape for asset history and risk score with structured
   `top_factors`. FMEA needs failure-mode + occurrence frequency; risk_truth
   already produces that with explanations.
3. **Multi-provider AI chain** (`_shared/ai-chain.ts`) lets us delegate the
   "auto-populate FMEA failure modes from logbook history" step to an LLM
   without per-tool integration work. The 2026 reliability-software industry
   has converged on LLM-assisted FMEA as the standard pattern (per recent
   research from Cambridge Design Science, Springer Nature, Energent.ai); the
   platform is positioned to do the same.

## The four sub-tools, in build order

Each tool has its own data shape, audience, and standards reference. Build
them in this order because each later tool consumes outputs from earlier ones.

### 1. FMEA Matrix (Failure Mode and Effects Analysis)

Per asset: list every plausible failure mode, its effect, severity (1-10),
occurrence (1-10), detection (1-10), Risk Priority Number = S × O × D, and
the recommended action.

**Standards**: SAE J1739, MIL-STD-1629A (the original 1980 spec, still the
canonical FMECA reference), AIAG-VDA FMEA Handbook (2019, automotive),
ISO 14224 (reliability data exchange).

**Auto-population**: pull the asset's logbook history (via
`v_asset_truth.legacy_asset_id` + `logbook` table) for the last 365 days. Group
by `root_cause`. For each cluster of >= 2 occurrences, pre-populate one
failure mode with:
- Effect = synthesised from the `action` field of past entries (LLM call)
- Occurrence = clamp(count / 10, 1, 10) where count is failures in window
- Detection = derived from whether prior entries had `failure_consequence` set
  to "Hidden" (high D) or "Stopped production" (low D)
- Severity = manual entry, or LLM suggestion based on `failure_consequence`

**Output**: structured FMEA rows that drive the next tool (RCM).

### 2. RCM Decision Logic (Reliability-Centered Maintenance)

For each FMEA failure mode, walk the SAE JA1011 decision tree:

```
Is the failure mode evident to the operator under normal use?
├── YES → Apply scheduled tasks if cost-effective
│         ├── Scheduled on-condition (P-F interval based)
│         ├── Scheduled restoration (age-based)
│         └── Scheduled discard (life-based)
└── NO  → Failure-finding task; if not, redesign required
```

Output per failure mode: one of
- `run_to_failure` — the cheapest option, only when consequence is acceptable
- `scheduled_on_condition` — needs Tool 4 (P-F) to set the interval
- `scheduled_restoration` — needs Tool 3 (Weibull) to set the interval
- `scheduled_discard` — same, needs Weibull
- `failure_finding` — for hidden failures
- `redesign_required` — flag for engineering review

**Output**: a PM strategy per asset that writes back to `pm_assets` +
`pm_scope_items`. The PM Scheduler picks up the new tasks automatically.

### 3. Weibull Analysis

Inputs: time-to-failure data from `logbook` (corrective entries on the asset),
filtered to the failure mode under analysis. Censored data (still-running
hours since last failure) included.

**Computation**: Maximum Likelihood Estimation of shape (β) and characteristic
life (η). The Python Analytics API (`Z:\python-api`) already runs scipy +
numpy + pandas. We add the `lifelines` library (one line in
`requirements.txt`; the canonical Python reliability library) and use
`lifelines.WeibullFitter`, which handles censored data natively and is the
2026 industry-standard implementation. No DIY Newton-Raphson solver needed.
A new endpoint `/reliability/weibull` wraps the call; a TS edge function
proxies hive-scoped requests to it.

**Output**: shape parameter β, characteristic life η, failure-pattern
classification:
- β < 1 → infant mortality (early failures, often after install or repair)
- β = 1 → random failures (constant hazard rate)
- β > 1 → wear-out (failures concentrate near end of life)

This classification feeds Tool 4 (P-F) and informs the RCM decision: wear-out
suggests scheduled-restoration; random suggests run-to-failure or condition
monitoring.

### 4. P-F Interval Calculator

The interval between when a potential failure (P) becomes detectable and when
it progresses to functional failure (F). Inspection interval should be
P-F / 2 by the standard rule (some sources use P-F / 3 for safety-critical).

**Inputs**: asset's condition-monitoring readings (`equipment_reading_templates`
already exists; readings live in `logbook.notes` JSONB and could move to a
dedicated table later) plus failure dates from logbook.

**Method**: regression on degradation curve (vibration, temperature, current
draw, oil debris), find the inflection where rate-of-change increases sharply
(the P point), measure days to failure (the F point).

**Output**: recommended inspection interval, written back to the matching
`pm_scope_items.frequency` field. Adjusts the PM Scheduler automatically.

## Where it lives

Two architectural options. I recommend Path A.

### Path A: Per-asset Reliability tab on Asset Hub (recommended)

Asset Hub already centralises every per-asset surface (timeline, neighbors,
risk, parts, external IDs). FMEA + RCM + Weibull + P-F are all per-asset.
Adding a "Reliability" tab keeps the platform's cross-cutting philosophy:
no new top-level page, every asset gets the engineering view inline.

**Pros**: zero new page registration, no nav-hub entry, every asset
auto-discovers the Reliability tab. AI Asset Brain Q&A picks up the new
data. Print-ready Reliability Report can be generated per asset on demand.

**Cons**: requires Asset Hub to grow another tab/section. Asset Hub is already
the largest page (~750 lines after Phase 2b). Discipline needed to keep it
scannable on mobile.

### Path B: Standalone `reliability.html` page

Pros: clean separation, dedicated audience landing, no Asset Hub bloat.
Cons: yet another nav entry, duplicate hive gate, splits per-asset truth
across two surfaces, harder to keep in sync with Asset Hub's risk card.

The audit's repeated lesson is "single source of truth, single read path".
Path A is consistent with that. Standalone landing makes sense only if
reliability engineers want a hive-wide RCM dashboard (see Phase 6 below).

## Data model

Three new tables, all keyed by canonical asset_id and registered in
`canonical_sources`.

```sql
-- 1. FMEA matrix rows (one per failure mode per asset)
CREATE TABLE rcm_fmea_modes (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  asset_id        uuid NOT NULL REFERENCES asset_nodes(id) ON DELETE CASCADE,
  function_text   text NOT NULL,                    -- "Maintain 2.5 bar discharge pressure"
  failure_mode    text NOT NULL,                    -- "V-belt slipping under load"
  effect_text     text,
  cause_text      text,
  severity        smallint CHECK (severity BETWEEN 1 AND 10),
  occurrence      smallint CHECK (occurrence BETWEEN 1 AND 10),
  detection       smallint CHECK (detection BETWEEN 1 AND 10),
  rpn             smallint GENERATED ALWAYS AS (severity * occurrence * detection) STORED,
  consequence_class text,                            -- 'safety'|'production'|'environment'|'cost'
  source          text NOT NULL DEFAULT 'manual',    -- 'manual'|'ai_logbook'|'ai_template'|'imported'
  ai_confidence   numeric,                           -- 0..1 when source ~ 'ai_*'
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  created_by      text,
  approved_by     text,
  approved_at     timestamptz
);
CREATE INDEX idx_fmea_modes_hive_asset ON rcm_fmea_modes (hive_id, asset_id);
CREATE INDEX idx_fmea_modes_rpn        ON rcm_fmea_modes (hive_id, rpn DESC);

-- 2. RCM strategy per failure mode
CREATE TABLE rcm_strategies (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  fmea_mode_id  uuid NOT NULL REFERENCES rcm_fmea_modes(id) ON DELETE CASCADE,
  decision      text NOT NULL CHECK (decision IN (
    'run_to_failure','scheduled_on_condition','scheduled_restoration',
    'scheduled_discard','failure_finding','redesign_required'
  )),
  task_text     text,
  interval_days integer,
  rationale     text,
  weibull_fit_id uuid,                                -- optional FK to weibull_fits
  pf_interval_id uuid,                                -- optional FK to pf_intervals
  written_to_pm_scope_item_id uuid REFERENCES pm_scope_items(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now(),
  updated_at    timestamptz DEFAULT now()
);
CREATE INDEX idx_rcm_strategies_hive ON rcm_strategies (hive_id, decision);

-- 3. Weibull fits (per asset per failure mode)
CREATE TABLE weibull_fits (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id        uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  asset_id       uuid NOT NULL REFERENCES asset_nodes(id) ON DELETE CASCADE,
  fmea_mode_id   uuid REFERENCES rcm_fmea_modes(id) ON DELETE SET NULL,
  beta           numeric,                              -- shape parameter
  eta_days       numeric,                              -- characteristic life in days
  failure_pattern text CHECK (failure_pattern IN ('infant','random','wearout','insufficient_data')),
  n_failures     integer,
  n_censored     integer,
  fit_method     text DEFAULT 'mle',                   -- 'mle'|'lsq'|'mrr'
  fit_quality    numeric,                              -- log-likelihood or R^2
  generated_at   timestamptz DEFAULT now(),
  source_window_days integer DEFAULT 365
);

-- 4. P-F intervals (per asset per condition-monitoring channel)
CREATE TABLE pf_intervals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid NOT NULL REFERENCES hives(id) ON DELETE CASCADE,
  asset_id      uuid NOT NULL REFERENCES asset_nodes(id) ON DELETE CASCADE,
  fmea_mode_id  uuid REFERENCES rcm_fmea_modes(id) ON DELETE SET NULL,
  parameter     text NOT NULL,                       -- 'vibration_mm_s'|'bearing_temp_c'|...
  p_threshold   numeric NOT NULL,                    -- value at potential-failure point
  f_threshold   numeric NOT NULL,                    -- value at functional failure
  pf_days       numeric NOT NULL,                    -- median days from P to F
  recommended_interval_days integer NOT NULL,        -- typically pf_days / 2
  basis         text,                                -- standard rule cited (e.g. 'P-F/2')
  generated_at  timestamptz DEFAULT now()
);
```

All four tables RLS-gated by hive membership join (Phase 0 Asset Brain
pattern), GRANT to anon + authenticated, REPLICA IDENTITY FULL where
DELETE filters on hive_id are needed.

## Canonical sources registration

Three new domains in `canonical_sources` after the schema lands:

| Domain | source_kind | source_name | Owner skill | Freshness |
|---|---|---|---|---|
| fmea_truth     | view | v_fmea_truth     | maintenance-expert | realtime |
| rcm_truth      | view | v_rcm_truth      | maintenance-expert | realtime |
| weibull_truth  | view | v_weibull_truth  | predictive-analytics | weekly_recompute |

`v_fmea_truth` joins `rcm_fmea_modes` to `asset_nodes.tag/name` and to the
linked logbook entries (so an AI agent reading "what's the top-RPN failure
mode for Pump P-5" gets the structured row plus the raw evidence).

## AI assistance pattern

Per the 2026 reliability literature, LLM-assisted FMEA is the dominant
pattern. The integration on this platform looks like:

**FMEA auto-populator** — a new edge function `fmea-populator` that runs on
demand (worker clicks "Suggest from history") OR weekly via pg_cron:

1. Fetch the asset's last 365 days of logbook entries (corrective only)
2. Group by `root_cause`; clusters of >= 2 are candidate failure modes
3. For each cluster, build a context payload (top-N entries with action +
   problem fields)
4. Call `callAI` with a structured FMEA prompt that returns one row of
   `{function, failure_mode, effect, cause, suggested_severity,
   suggested_occurrence, suggested_detection, confidence}`
5. Insert into `rcm_fmea_modes` with `source = 'ai_logbook'` and
   `ai_confidence` set
6. Engineer reviews each row, tunes S/O/D, marks `approved_at`. RPN is
   automatically computed.

Per ai-engineer skill rules: rate-limit gate first, transcript/payload cap,
JSON-only output, hive-scoped, Promise.allSettled on parallel cluster calls.

**RCM decision assistant** — for each FMEA mode, the page can offer "Suggest
strategy" which calls `callAI` with the failure-mode row + the JA1011
decision tree as system prompt. Returns one of the six decisions with a
rationale citing the SAE clause.

**Weibull explainer** — once a fit is computed (deterministic Newton-Raphson),
`callAI` writes a one-paragraph plain-language interpretation: "β = 1.8
indicates wear-out; characteristic life is 87 days, meaning 63% of belts in
this service profile fail by day 87. Schedule replacement at day 60 for a
safety margin."

## Standards taxonomy

Used throughout, surfaced inline in the UI as authoritative anchors:

| Standard | Purpose | Where it shows up |
|---|---|---|
| **SAE JA1011** | RCM minimum criteria (the 7 questions) | RCM decision tree headers |
| **SAE JA1012** | RCM guideline (interpretation) | "Why this decision" tooltips |
| **MIL-STD-1629A** | Original FMECA spec (1980, still canonical) | FMEA matrix legend |
| **AIAG-VDA FMEA Handbook (2019)** | Current automotive FMEA reference | S/O/D scoring rubric |
| **ISO 14224** | Reliability data exchange | Asset hierarchy, failure mode taxonomy |
| **IEC 60812** | FMEA technique (international counterpart to MIL-STD-1629A) | Cited where ISO clients are involved |

The standards-validator skill (per project memory) requires every formula
cross-referenced via WebSearch against the live standard text on first
introduction. The Weibull MLE solver triggers that check; RCM decision logic
also does.

## UI design (Path A: Reliability tab on Asset Hub)

A new section card on `asset-hub.html` detail view, between Risk and
Marketplace:

```
+ Reliability                                          rules-v2 / SAE JA1011
+----------------------------------------------------------------------+
| [FMEA] [RCM Strategy] [Weibull] [P-F]      [Suggest from history]   |
+----------------------------------------------------------------------+
| FMEA Matrix (3 modes registered, RPN >= 50)                          |
|                                                                      |
|  Function: Maintain 2.5 bar discharge pressure                       |
|  ┌──────────────────────────────────────────────┐                   |
|  │ Failure mode: V-belt slipping under load     │ S O D RPN          |
|  │ Effect:       Loss of pressure, no flow      │ 7 6 5 210          |
|  │ Cause:        Worn V-belt / misalignment     │                    |
|  │ AI suggested  • 4 recurrences in last 90 days│ approved by Ian    |
|  └──────────────────────────────────────────────┘                   |
|                                                                      |
|  ... (more rows)                                                     |
|                                                                      |
| [+ Add failure mode]    [Print Reliability Report]                   |
+----------------------------------------------------------------------+
```

Tabs (FMEA / RCM / Weibull / P-F) within the section card swap the body.
On mobile, tabs collapse to a vertical accordion. Print-ready Reliability
Report compiles all four into one PDF (mirrors `analytics-report.html` and
`project-report.html`).

## Phased build plan

Sized for one session each, each phase Guardian-clean before moving on.

### Phase R.1: Schema + canonical registration (~0.5 session)
- Migration `20260510000000_reliability_workbench_foundation.sql`:
  4 tables + RLS + GRANT + supabase_realtime publication
- 3 canonical views (`v_fmea_truth`, `v_rcm_truth`, `v_weibull_truth`)
  registered in `canonical_sources`
- `validate_reliability_workbench.py` Layer 1 (schema completeness)
- Existing tester reset.py extended

### Phase R.2: FMEA tab on Asset Hub + manual entry (~1 session)
- Asset Hub gets the Reliability section card with FMEA tab visible
- "Add failure mode" form with S/O/D inputs (clamped 1-10), RPN auto-computed
  by the schema's GENERATED ALWAYS AS column
- List of existing modes sorted by RPN descending
- Edit / approve workflow (supervisor approval gate, mirrors community moderation)
- Tester flow `reliability_workbench_flow.py` Layer 1 (page renders, manual
  insert round-trips)

### Phase R.3: AI auto-populate FMEA from logbook (~1 session)
- Edge function `fmea-populator/index.ts` with rate-limit gate + 4-place sync
- "Suggest from history" button on FMEA tab
- Confidence pill on each AI-generated row; engineer-approval still required
  before RPN counts in dashboards
- Validator extension: every AI-generated row carries `ai_confidence` and
  `source = 'ai_logbook'`
- Tester flow Layer 2 (mock LLM response, assert insert shape)

### Phase R.4: RCM decision tree + write-back to PM Scheduler (~1 session)
- RCM tab on Asset Hub: per failure mode, walk the JA1011 questions,
  produce a decision + interval recommendation
- "Apply to PM Scheduler" button writes the recommended interval back to
  `pm_scope_items.frequency` and links via
  `rcm_strategies.written_to_pm_scope_item_id`
- AI assistance: "Suggest strategy" button (cites JA1011 clause in rationale)

### Phase R.5: Weibull fitter (~0.5 session, was 1.5)
- Add `lifelines` to `python-api/requirements.txt`
- New Python endpoint `/reliability/weibull` wrapping
  `lifelines.WeibullFitter` for censored TTF data; returns
  `{ beta, eta_days, n_failures, n_censored, fit_method, log_likelihood }`
- New TS edge function `reliability-weibull/index.ts` that hive-scopes the
  TTF query, proxies to Python, writes the fit into `weibull_fits`
- Weibull tab on Asset Hub: triggers the edge fn, displays β + η + failure
  pattern with a plain-language explanation from `callAI`
- `validate_reliability_workbench.py` Layer 3: MLE returns expected β / η on
  a known reference dataset (within 5%)
- Standards-validator runs the cross-reference on the lifelines algorithm
  reference

### Phase R.6: P-F interval calculator (~0.7 session, was 1)
- Reuse the same Python endpoint pattern: new `/reliability/pf_interval`
  uses `scipy.optimize.curve_fit` to fit a degradation curve and detect
  the P-point inflection
- P-F tab on Asset Hub: select condition-monitoring channel
  (vibration / temperature / current / oil-debris), pull readings, call the
  edge fn, return `pf_days / 2` as the recommended interval
- Write back to `pf_intervals` table; offer "Apply to PM Scheduler" button
  same shape as R.4

### Phase R.7: Print-ready Reliability Report (~0.5 session)
- New `reliability-report.html` (mirrors `analytics-report.html`,
  `project-report.html` patterns)
- Sections: Executive summary / Asset hierarchy / FMEA matrix top-N by RPN /
  RCM strategy table / Weibull fits / P-F intervals / Sign-off block
- Print CSS validated by the existing `print popup pattern`
  (margin:0 + body padding + color override per maintenance-expert skill)

**Total: ~4.9 sessions (was 6.5) once existing libraries are reused.**

## Cross-skill writeback table

Per the Self-Improvement Loop in `CLAUDE.md`. Every phase generates lessons
that should land in the relevant skill files in one pass. Pre-identified:

| Lesson | Maintenance Expert | Predictive Analytics | Architect | AI Engineer | Knowledge Manager | Frontend |
|---|---|---|---|---|---|---|
| RCM JA1011 / JA1012 decision tree as canonical taxonomy | X | | X | | X | |
| FMEA S/O/D rubric per AIAG-VDA 2019 | X | | | | X | |
| Weibull MLE Newton-Raphson with censored data | | X | | | | |
| P-F / 2 default interval rule, P-F / 3 for safety-critical | X | X | | | | |
| LLM-assisted FMEA pattern: cluster by root_cause >= 2 occurrences first | | | | X | | |
| AI confidence + engineer approval gate before RPN counts in dashboards | | | X | X | | |
| Print-ready Reliability Report follows analytics-report pattern | | | | | | X |
| ISO 14224 hierarchy reused as FMEA function-decomposition tree | X | | X | | X | |

## Open questions before any code lands

1. **Path A vs Path B for the UI.** Recommended Path A (Asset Hub tab) but
   confirm the user wants per-asset depth over a hive-wide reliability
   dashboard. Path A doesn't exclude a hive-wide rollup later as a
   `reliability-overview.html` page that reads from `v_fmea_truth`.

2. **Approval gate granularity.** Worker can submit FMEA / RCM rows but
   only supervisor approval makes them count? Or reliability engineer is a
   new role beyond worker / supervisor / engineer (per nav-hub roles)?
   Cleaner: keep the existing roles, add a `requires_approval` flag on
   rcm_fmea_modes, mirror the marketplace listing approval pattern.

3. **AI cost.** FMEA auto-populator runs callAI per failure-mode cluster.
   For a hive with 20 assets and an average of 5 clusters each, one weekly
   pg_cron run is 100 LLM calls. At Groq free tier that is fine; track in
   ai_rate_limits per the existing pattern.

4. **Weibull fit refresh frequency.** Per the predictive-analytics skill,
   start with rules and move to ML once data is sufficient (500+ records).
   Weibull needs less data (10+ failures gives a meaningful fit). Recompute
   nightly with batch-risk-scoring, or weekly to keep cost low? Default to
   weekly; rerun on demand from the page.

5. **Standards version pinning.** AIAG-VDA 2019 is the current automotive
   handbook; SAE JA1011 was last reaffirmed in 2009. Pin the citation to
   the current version with a comment so a future standards update triggers
   a content review, not a silent drift.

6. **Mobile UX for FMEA tables.** Mobile-maestro skill rules apply. FMEA is
   inherently tabular; on mobile the table becomes a stack of cards (one
   per failure mode), tapping expands. Same pattern as the Phase 5b
   structured-factor render (each factor a card on mobile).

## Build readiness

- Skills consulted: maintenance-expert (RCM, FMEA, MTBF, PM strategy domain),
  predictive-analytics (Weibull, MTBF math, time decay), architect (canonical
  sources + view + RLS pattern), ai-engineer (LLM-assisted analysis with
  rate-limit gate), knowledge-manager (structured records over free text)
- Web research validated: 2026 industry pattern is integrated platforms
  (ReliaSoft / Relyence / Isograph) combining all four; LLM-assisted FMEA is
  the dominant new pattern with 90+% accuracy on unstructured input
- No new technology required: every data source already canonical, every AI
  call goes through the existing chain, every page registration follows the
  Asset Hub pattern shipped this session

## Recommended starting move

Phase R.1 (schema + canonical registration) is the smallest meaningful first
move. It costs half a session and proves the pattern before any user-facing
work. Once the migrations land and the validator is green, Phase R.2 (FMEA
manual entry tab on Asset Hub) is the first surface the engineer sees.

End of plan.
