/**
 * journey-rag-flywheel-walk.spec.ts — RAG Flywheel observational walk.
 *
 * Walks the 5 priority pages, enumerates every [data-rag-tile] tile,
 * captures the displayed value, then POSTs a grounding-probe question to
 * the local agentic-rag-loop. Writes the observations to a per-turn JSONL
 * file at .tmp/rag_observations_turn_<N>.jsonl for tools/rag_flywheel_processor.py
 * to consume.
 *
 * Modes:
 *   WH_FLYWHEEL_DRY=1     structural-only (count tiles, capture values, no LLM)
 *   WH_FLYWHEEL_TURN=N    turn number (default: auto-detect highest existing +1)
 *
 * Auth: uses the local Supabase publishable key (anon-equivalent) and the
 * walk's seeded test hive. Per [[feedback-local-first-never-push-prod]] this
 * spec is local-only — does NOT touch production endpoints.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import * as fs from 'fs';
import * as path from 'path';

const PAGES_THIS_TURN = [
  // First 8 pages (turns 1-22)
  { slug: 'analytics',     path: '/workhive/analytics.html' },
  { slug: 'alert-hub',     path: '/workhive/alert-hub.html' },
  { slug: 'asset-hub',     path: '/workhive/asset-hub.html' },
  { slug: 'pm-scheduler',  path: '/workhive/pm-scheduler.html' },
  { slug: 'predictive',    path: '/workhive/predictive.html' },
  { slug: 'inventory',     path: '/workhive/inventory.html' },
  { slug: 'skillmatrix',   path: '/workhive/skillmatrix.html' },
  { slug: 'hive',          path: '/workhive/hive.html' },
  // Turn 23+ expansion (RAG flywheel): all-pages coverage. +8 pages, +24 tiles → 16 pages / 48 tiles.
  { slug: 'achievements',     path: '/workhive/achievements.html' },
  { slug: 'dayplanner',       path: '/workhive/dayplanner.html' },
  { slug: 'integrations',     path: '/workhive/integrations.html' },
  { slug: 'marketplace',      path: '/workhive/marketplace.html' },
  { slug: 'ph-intelligence',  path: '/workhive/ph-intelligence.html' },
  { slug: 'project-manager',  path: '/workhive/project-manager.html' },
  { slug: 'report-sender',    path: '/workhive/report-sender.html' },
  { slug: 'shift-brain',      path: '/workhive/shift-brain.html' },
];

const LOCAL_FN_URL = 'http://127.0.0.1:54321/functions/v1/agentic-rag-loop';
const LOCAL_KEY    = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';
const TEST_HIVE_ID = process.env.WH_FLYWHEEL_HIVE_ID || '7b785f99-2776-430f-be28-fc21db1d41a6';   // Manila Electronics Assembly (real local hive w/ data)
const TEST_WORKER  = process.env.WH_FLYWHEEL_WORKER  || 'Pablo Aguilar';
const DRY_RUN      = process.env.WH_FLYWHEEL_DRY === '1';

// Resolve turn number: env override OR auto-detect highest existing +1.
function resolveTurn(): number {
  if (process.env.WH_FLYWHEEL_TURN) return parseInt(process.env.WH_FLYWHEEL_TURN, 10);
  const dir = path.join('.tmp');
  if (!fs.existsSync(dir)) return 1;
  const existing = fs.readdirSync(dir)
    .map(f => /^rag_observations_turn_(\d+)\.jsonl$/.exec(f))
    .filter(Boolean)
    .map(m => parseInt(m![1], 10));
  return existing.length ? Math.max(...existing) + 1 : 1;
}

const TURN     = resolveTurn();
// Absolute path keyed off process.cwd() so we don't depend on the test
// worker's CWD assumption. .tmp lives at project root.
const OBS_PATH = path.resolve(process.cwd(), '.tmp', `rag_observations_turn_${TURN}.jsonl`);

function appendObservation(obs: Record<string, unknown>): void {
  try {
    fs.mkdirSync(path.dirname(OBS_PATH), { recursive: true });
    fs.appendFileSync(OBS_PATH, JSON.stringify(obs) + '\n', 'utf-8');
    console.log(`[flywheel] APPEND ok ${obs.page}::${obs.tile_key} mode=${obs.mode}`);
  } catch (err) {
    console.error(`[flywheel] WRITE FAILED to ${OBS_PATH}:`, err);
    throw err;
  }
}

test.describe('rag-flywheel-walk — observational AI-grounding pass', () => {
  test.beforeAll(async () => {
    console.log(`[flywheel] turn=${TURN} mode=${DRY_RUN ? 'DRY' : 'REAL'} hive=${TEST_HIVE_ID.slice(0,8)}... → ${OBS_PATH}`);
    // NOTE: do NOT unlink the OBS_PATH here. Playwright re-runs beforeAll
    // when any test in this describe block RETRIES on failure, which would
    // wipe observations already written by earlier tests in the same turn.
    // To start a clean turn, delete .tmp/rag_observations_turn_<N>.jsonl
    // manually OR bump WH_FLYWHEEL_TURN. The processor dedupes by (turn,page,tile_key).
  });

  for (const pg of PAGES_THIS_TURN) {
    test(`walk ${pg.slug}`, async ({ whPage }) => {
      const errors: string[] = [];
      whPage.on('pageerror', e => errors.push(e.message));

      // Bypass maturity-stair gate (predictive.html hides tagged tiles when
      // the hive is below Stair 3). Turn 22 found the addInitScript
      // monkey-patch was racy — script load order sometimes overwrote it.
      // Turn 23 fix: intercept window.fetch BEFORE any page script runs.
      // When the page queries v_hive_readiness_truth, return a synthetic
      // {current_stair: 5} payload directly. This is deterministic — no race.
      await whPage.addInitScript((hiveId) => {
        try {
          localStorage.setItem(`wh_hive_maturity_stair_${hiveId}`, '5');
          localStorage.setItem('wh_hive_maturity_stair', '5');
        } catch (_) { /* noop */ }

        const origFetch = window.fetch;
        (window as any).fetch = async function(...args: any[]) {
          const url = String(args[0] || '');
          // Short-circuit ALL v_hive_readiness_truth queries to "Stair 5" so
          // any page that gates on maturity sees the test hive as fully unlocked.
          if (url.includes('v_hive_readiness_truth')) {
            return new Response(JSON.stringify([{
              current_stair:    5,
              composite_score:  1.0,
              blocker_summary:  '',
              evidence:         { rag_flywheel_walk: 'gate bypassed at fetch layer' },
            }]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            });
          }
          return origFetch.apply(this, args as any);
        };

        // Belt + suspenders: also stub window.checkMaturityGate in case some
        // codepath calls it without going through the fetch intercept.
        (window as any).checkMaturityGate = async function() {
          return {
            blocked: false, currentStair: 5, currentStairName: 'Industry Leader',
            requiredStair: 3, requiredStairName: 'Predictive Ready',
            blockerSummary: '(rag-flywheel walk: gate bypassed)',
            evidence: {}, compositeScore: 1.0,
          };
        };
      }, TEST_HIVE_ID);

      await whPage.goto(pg.path);
      await waitForPageReady(whPage);
      // Give per-page data loaders ~2.5s to populate KPI tiles.
      await whPage.waitForTimeout(2500);

      // Enumerate every [data-rag-tile] on the page + grab the displayed value.
      // Turn 30: extended selectors to cover section tiles (detail panels, AMC stats,
      // stat-card sections, predictive sub-panels, marketplace grid, etc.)
      const tiles = await whPage.$$eval('[data-rag-tile]', els =>
        els.map(el => {
          const tileKey = el.getAttribute('data-rag-tile') || '';
          const label   = el.getAttribute('data-rag-label') || '';

          // 1. Hero/summary KPI value — check all known value patterns across pages
          const heroEl = el.querySelector(
            '.sc-hero, .sn, .verdict-text, [class*="hero"],' +
            '.amc-stat-num,' +                  // alert-hub AMC sub-stats
            '.stat-value,' +                    // asset-hub stat-cards
            '.text-2xl.font-black,' +           // hive Tailwind stat cards
            '.stat-pill,' +                     // inventory stat pills
            '[data-rag-val]'                    // explicit override on any element
          );

          // 2. For section/panel tiles with no single hero value, count rendered rows
          //    (tables, lists, grids). This gives a "X items loaded" indicator.
          let sectionCount = '';
          if (!heroEl || !(heroEl as HTMLElement).textContent?.trim()) {
            const rows   = el.querySelectorAll('tr:not(:first-child):not(:empty), li, .listing-card, .risk-row, .task-row, .pm-row, [class*="card-item"]');
            const charts = el.querySelectorAll('canvas, .plotly-graph-div');
            if (rows.length > 0)   sectionCount = `${rows.length} rows`;
            else if (charts.length > 0) sectionCount = `${charts.length} charts`;
            else {
              // Last resort: first meaningful text block in the section
              const anyText = el.querySelector('p, span, td, .section-summary');
              sectionCount = (anyText?.textContent || '').trim().slice(0, 60);
            }
          }

          const subEl = el.querySelector('.sc-sub, .amc-stat-label, .stat-label');
          return {
            tileKey,
            label,
            displayed_value: (heroEl?.textContent || sectionCount || '').trim().slice(0, 80),
            sub_text:        (subEl?.textContent  || '').trim().slice(0, 120),
          };
        }),
      );

      console.log(`[flywheel] ${pg.slug}: ${tiles.length} tiles observed`);
      expect(tiles.length, `page ${pg.slug} must expose at least one [data-rag-tile]`).toBeGreaterThan(0);

      for (const t of tiles) {
        const baseObs = {
          turn:            TURN,
          page:            pg.slug,
          tile_key:        t.tileKey,
          tile_label:      t.label,
          displayed_value: t.displayed_value,
          sub_text:        t.sub_text,
          timestamp:       new Date().toISOString(),
          page_errors:     errors.length,
        };

        if (DRY_RUN) {
          appendObservation({ ...baseObs, mode: 'dry', ai: null });
          continue;
        }

        // Real LLM call — grounding probe.
        // Per RAG Flywheel turn 22 finding: 0-value tiles are the hardest
        // because "what does 0 mean?" has no record to cite. Branch THREE ways:
        //   - ZERO/empty ("0", "—", "None", "None today") → BOUNDARY probe
        //     ("under what conditions would this KPI show a non-zero value?")
        //   - Empty-shape ("—", null) → DEFINITION probe (KPI purpose + source view)
        //   - Numeric/textual → VALUE probe (ground the specific number)
        // All three name canonical v_*_truth views so the AI has a concrete
        // anchor to confirm/correct rather than guess.
        const rawVal  = (t.displayed_value || '').trim();
        const isZero  = /^(0|None today|None|null|n\/a)$/i.test(rawVal);
        const isEmpty = !rawVal || /^[\-—\.\s]+$/.test(rawVal);
        const tileHint = `data-rag-tile="${t.tileKey}"`;
        let question: string;
        if (isZero) {
          question = `On the ${pg.slug}.html page the "${t.label}" tile (${tileHint}) is currently showing 0 (zero). Under what conditions would this KPI show a non-zero value? Identify the canonical source view (v_logbook_truth, v_pm_compliance_truth, v_risk_truth, v_asset_truth, v_inventory_items_truth, or a v_kpi_truth_* row from canonical_sources) that this tile reads from, and explain what event / record would increment it. Cite the source name explicitly.`;
        } else if (isEmpty) {
          question = `What does the "${t.label}" KPI on the ${pg.slug}.html page measure? It is a tile marked ${tileHint}. Identify the canonical source view (a v_*_truth view, e.g. v_logbook_truth, v_pm_compliance_truth, v_risk_truth, v_asset_truth, v_kpi_truth) that this tile should read from. Cite the source name explicitly.`;
        } else {
          question = `On the ${pg.slug}.html page, the "${t.label}" tile (${tileHint}) is currently showing ${rawVal}. Using ONLY the maintenance records available, explain what this number reflects and cite at least one specific logbook row or canonical view (v_*_truth) that contributes to it. If you do not have records to ground it, say so plainly.`;
        }
        // Retry-on-empty (RAG flywheel turn 27): the free-tier LLM chain
        // occasionally returns 200 with `answer: ""` when a provider TPM-throttles
        // mid-generation. One 5-second cooldown + retry catches the transient
        // without amplifying load — caps at 1 retry so we don't burn the chain.
        let ai: any;
        for (let attempt = 0; attempt < 2; attempt++) {
          ai = await whPage.evaluate(async ({ url, key, payload }: { url: string; key: string; payload: Record<string, unknown> }) => {
            try {
              const resp = await fetch(url, {
                method:  'POST',
                headers: {
                  'Content-Type':  'application/json',
                  'apikey':        key,
                  'Authorization': `Bearer ${key}`,
                },
                body: JSON.stringify(payload),
              });
              const body = await resp.json().catch(() => ({}));
              return { status: resp.status, body };
            } catch (e: any) {
              return { status: 0, body: {}, error: String(e?.message || e) };
            }
          }, {
            url: LOCAL_FN_URL,
            key: LOCAL_KEY,
            payload: {
              question,
              hive_id:     TEST_HIVE_ID,
              worker_name: TEST_WORKER,
            },
          });
          const emptyAnswer = ai.status === 200 && !String(ai.body?.answer || '').trim();
          if (!emptyAnswer) break;
          if (attempt === 0) {
            console.log(`[flywheel] empty answer for ${t.tileKey}, cooling 5s and retrying`);
            await whPage.waitForTimeout(5000);
          }
        }

        // Inter-tile throttle (turn 30 fix): 83 tiles × rapid-fire LLM calls
        // exhausts Groq free tier (30 req/min) within the first page, leaving
        // all remaining tiles with route=n/a. Space them 5 s apart so the
        // whole turn uses ~7 min of provider capacity (83 × 5s = 415s)
        // staying under Groq's 30-req/min limit with room for retries.
        await whPage.waitForTimeout(5000);

        appendObservation({
          ...baseObs,
          mode:            'real',
          question,
          ai_status:       ai.status,
          ai_route:        ai.body?.route ?? null,
          ai_answer:       String(ai.body?.answer || '').slice(0, 800),
          ai_citations:    Array.isArray(ai.body?.citations) ? ai.body.citations.slice(0, 5) : [],
          ai_citation_count: typeof ai.body?.citation_count === 'number' ? ai.body.citation_count : (Array.isArray(ai.body?.citations) ? ai.body.citations.length : 0),
          ai_grader_passed:  ai.body?.grader_passed ?? null,
          ai_checker_passed: ai.body?.checker_passed ?? null,
          ai_retries:        ai.body?.retries ?? null,
          ai_total_tokens:   ai.body?.total_tokens ?? null,
          ai_latency_ms:     ai.body?.latency_ms ?? null,
          ai_trace_id:       ai.body?.trace_id ?? null,
        });
      }
    });
  }
});
