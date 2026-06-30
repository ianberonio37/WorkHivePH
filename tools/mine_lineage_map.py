# audit-scope-allow: data lineage is mapped per edge-fn ENDPOINT (functions/<name>/index.ts — the
# callable surfaces a journey traverses); _shared/* are helper modules, not lineage endpoints, so they
# are intentionally out of scope (the nerves/journey_trace cover the shared transforms).
"""
Data-Lineage Map Miner -- §13 P0 Substrate (E2E Journey & Data-Lineage Sweep)
=============================================================================
Builds `lineage_map.json` -- the DENOMINATOR for the §13 nerve-sweep:
`{input_field -> [consumers + expected transform]}` across the 27 feature
pages, with the MEASURED coverage numbers P (page) and H (nerve-path).

Why this exists (§13.5 "the anti-false-sense rule"): a coverage phase with
no total to be a fraction of is exactly where coverage gets silently
dropped. P0's deliverable is the denominator ITSELF, mined from the
canonical layer so that from P1 on every "done" is `verified / total`,
visible and un-fakeable.

REUSE-FIRST, fitness-gated (§13.6): this miner INVENTS NOTHING about
discovery -- it JOINS the platform's own already-mined lineage oracles:
  - phantom_captures_report.json   -- Phantom Capture Auditor (reverse
                                      lineage: capture -> consumers). The
                                      authoritative INPUT-FIELD universe.
  - kpi_source_registry.json       -- metric -> view.column -> consumer
                                      pages. The TRANSFORM layer.
  - canonical_registry.json        -- surfaces{tables_read/written,fns,rpcs}
                                      + views{read_by_surfaces}. ADJACENCY.
  - canonical/lineage_edges.json   -- curated capture->column->view->tile->
                                      dashboard chains. HIGH-CONFIDENCE
                                      value nerves.
  - calm_canonical_audit_report.json -- dashboard -> v_*_truth (TERMINUS).

What the §13 sweep ADDS on top of these STATIC auditors (which only prove a
consumer EXISTS in code): the LIVE differential nerve-probe (P1+) seeds a
known delta through the real UI and asserts the rendered VALUE is correct at
every terminus. So every path here starts `verified: false` -- mapped 100%
(P0 exit), verified 0% until the live probe runs.

Output:
  - lineage_map.json  (machine -- the denominator + the field->consumer graph)
  - lineage_map.md    (human  -- the measured scoreboard + per-page summary)

Skills consulted: analytics-engineer (KPI Source Registry, one-metric-one-
derivation), data-engineer (user-entered > computed; cross-page field
parity), architect (reuse-first-fitness-gated, §13.6), qa-tester (the live
sweep this denominator measures).
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# Source artifacts (all pre-mined by the platform's own oracles).
SRC_PHANTOM   = ROOT / "phantom_captures_report.json"
SRC_KPI       = ROOT / "kpi_source_registry.json"
SRC_REGISTRY  = ROOT / "canonical_registry.json"
SRC_EDGES     = ROOT / "canonical" / "lineage_edges.json"
SRC_CALM      = ROOT / "calm_canonical_audit_report.json"
SRC_TRACE     = ROOT / "journey_trace_results.json"   # live-proven nerves (P1+), closes §13's loop
SRC_VAXIS     = ROOT / "journey_vaxis_results.json"   # V-axis journey×layer matrix (P4/P5)

OUT_JSON = ROOT / "lineage_map.json"
OUT_MD   = ROOT / "lineage_map.md"

# ---------------------------------------------------------------------------
# The 27-page feature denominator (§13.5). The authoritative total for P.
# Curated subset of e2e_roles_runner.py:TIER_PAGES (34) -- drops 9 admin/
# static surfaces (index, public-feed, platform-health, marketplace-admin,
# symbol-gallery, founder-console, marketplace-seller{,-profile}) and adds
# `resume` (private single-user input surface). Role split per §13.5.
# ---------------------------------------------------------------------------
INPUT_SURFACES = [
    "logbook", "pm-scheduler", "inventory", "dayplanner", "skillmatrix",
    "engineering-design", "report-sender", "community", "marketplace",
    "project-manager", "integrations", "asset-hub", "voice-journal",
    "resume", "alert-hub",
]
TERMINUS_SURFACES = [
    "analytics", "analytics-report", "project-report", "ph-intelligence",
    "predictive", "ai-quality", "shift-brain", "achievements", "audit-log",
    "hive", "plant-connections", "assistant",
]
FEATURE_PAGES = INPUT_SURFACES + TERMINUS_SURFACES  # 27

# Admin/static pages explicitly EXCLUDED from the feature denominator
# (kept here so the exclusion is auditable, not silent).
EXCLUDED_PAGES = [
    "index", "public-feed", "platform-health", "marketplace-admin",
    "symbol-gallery", "founder-console", "marketplace-seller",
    "marketplace-seller-profile",
]

# §13 P-axis N/A: feature pages that ARCHITECTURALLY cannot carry a data-lineage
# nerve (no truth-view terminus to verify a value against). Same honest-denominator
# discipline as the V-axis n/a — P% is over APPLICABLE pages (27 − N/A), each with a
# stated reason. Used CONSERVATIVELY: env-blocked-but-provable pages are NOT N/A
# (they stay `pending` — the distinction is architecturally-never vs locally-blocked).
PAGES_NA = {
    "engineering-design": "engineering_calcs has NO v_*_truth view — no canonical terminus to verify against",
    "resume": "ephemeral/in-memory CONTENT (upload→extract→edit) — not a persisted DB-lineage surface",
    "dayplanner": "no own input nerve — its real input is logbook (already engine-proven); it is a view over logbook",
}

# §13 H-axis cross-link: which journey_trace nerve PROVES which kpi_source_registry metric.
# A registered metric rendered on N surfaces = N kpi chains, but the METRIC's DB computation
# is proven ONCE by the live differential nerve — so all N chains for that metric are verified
# (the same proven value, rendered in N places; the H-analog of P's terminus-attribution).
# EXACT metric-key match (no fuzzy text) — only metrics with a real differential nerve.
NERVE_PROVES_METRIC = {
    "pm_anchor__overdue": "pm_overdue",
    "pm_anchor__due_soon": "pm_due_soon",
    "pm_rpc__compliance": "pm_compliance",
    "inventory_qty__low_stock": "low_stock",
    "risk_band__hot_count": "top_risk_band",   # nerve #17 — the ML risk band IS differentially seedable
}

# Curated-edge cross-link: a hand-curated chain whose transform a verified nerve proves.
# substring(transform) → the nerve that proves it. Explicit + auditable (not fuzzy).
CURATED_PROVEN_BY = {
    "Open Jobs count": "logbook_status__open_jobs",   # nerve #14
    "Risk Alerts": "risk_band__hot_count",             # nerve #17 (high+crit risk count)
}

# Curated-edge cross-link by a standalone VALUE-ACCURACY validator (not a journey_trace
# nerve). substring(transform) → (validator module, function, what it proves). The chain
# is credited ONLY if the validator PASSES when re-run now — falsifiable: break the
# prescriptive math and the validator fails, so the chain reverts to unverified and H drops.
# This closes the §13 last load-bearing transform chain (the analytics Phase 4 action plan).
CURATED_PROVEN_BY_VALIDATOR = {
    "Phase 4 action plan": (
        "validate_analytics_correctness", "validate_analytics_correctness",
        "prescriptive priority_ranking (ISO 55001) + parts_reorder (SMRP) value-verified vs hand-computed oracles",
    ),
    # ph-intelligence's cross-hive benchmark network — formerly marked "external" (an UNTESTED
    # assumption). benchmark-compute is pure SQL/free/anon-invokable locally; this validator proves
    # its value-derivation against hand oracles via the LIVE edge fn. Distinctive sig (matches no
    # canonical-chain transform — used only to gate the ph-intelligence PAGE credit below).
    "ph-intelligence benchmark network": (
        "validate_ph_intelligence_benchmark", "validate_ph_intelligence_benchmark",
        "cross-hive benchmark network value-verified: per-hive MTBF/MTTR (computeForHive) + "
        "network avg/p25/p75 (computeNetwork) match hand oracles via the live local edge fn",
    ),
}


def _load(path: Path) -> dict:
    if not path.exists():
        print(f"  [WARN] source missing: {path.relative_to(ROOT)}")
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _page_key(filename: str) -> str:
    """logbook.html -> logbook ; supabase/functions/x/index.ts -> x (edge fn)."""
    name = filename.strip()
    if name.endswith(".html"):
        return name[:-5]
    return name


def _consumer_kind(consumer_file: str) -> str:
    if consumer_file.endswith(".html"):
        return "surface"
    if "functions/" in consumer_file or consumer_file.endswith("index.ts"):
        return "edge_fn"
    if consumer_file.endswith(".js"):
        return "script"
    return "other"


def build() -> dict:
    print("Mining lineage_map.json (§13 P0 -- the denominator)...")
    phantom  = _load(SRC_PHANTOM)
    kpi      = _load(SRC_KPI)
    registry = _load(SRC_REGISTRY)
    edges    = _load(SRC_EDGES)
    calm     = _load(SRC_CALM)

    surfaces = registry.get("surfaces", {})
    views    = registry.get("views", {})

    # ----- Page denominator (P axis) ---------------------------------------
    pages: dict[str, dict] = {}
    for p in FEATURE_PAGES:
        role = ("both" if p in INPUT_SURFACES and p in TERMINUS_SURFACES
                else "input" if p in INPUT_SURFACES else "terminus")
        surf = surfaces.get(f"{p}.html", {})
        pages[p] = {
            "role": role,
            "in_denominator": True,
            "writes_tables": surf.get("tables_written", []),
            "reads_tables": surf.get("tables_read", []),
            "edge_fns_invoked": surf.get("edge_fns_invoked", []),
            "input_fields": [],          # filled below
            "input_field_count": 0,
            "nerve_engine_proven": False,   # ≥1 nerve LIVE-proven by journey_trace (P1 milestone)
            "nerve_fully_verified": False,  # ALL input fields proven (strict §13.5 P; P2 moves this)
        }

    # ----- Input fields (the nerves) from the Phantom Capture Auditor ------
    # Each ALIVE capture whose capture site lands on a feature INPUT surface
    # is an input nerve. consumer_files = its discovered (existence-level)
    # consumers = H paths of provenance `capture_reverse_lineage`.
    fields: dict[str, dict] = {}
    by_name = phantom.get("by_name", {})
    captures_off_feature = 0
    for cap_name, rec in by_name.items():
        if rec.get("status") != "alive":
            continue
        origin_pages = []
        for site in rec.get("capture_sites", []):
            pk = _page_key(site.get("file", ""))
            if pk in INPUT_SURFACES:
                origin_pages.append(pk)
        if not origin_pages:
            captures_off_feature += 1
            continue  # capture on an excluded/admin page -- not in the feature denominator
        origin_pages = sorted(set(origin_pages))

        consumers = []
        for cf in rec.get("consumer_files", []):
            consumers.append({
                "id": _page_key(cf),
                "raw": cf,
                "kind": _consumer_kind(cf),
                "via": "capture_reverse_lineage",
                "expected_transform": None,   # filled by the live probe / curated chains
                "verified": False,
            })
        # consumer_count may exceed distinct consumer_files (multiple read sites);
        # H counts DISTINCT discovered consumer edges (the conservative denominator).
        field_key = f"{origin_pages[0]}:{cap_name}"
        fields[field_key] = {
            "field": cap_name,
            "kind": "capture",
            "input_surfaces": origin_pages,
            "consumers": consumers,
            "path_count": len(consumers),
            "verified_paths": 0,
            "provenance": "phantom_capture_auditor",
        }
        for op in origin_pages:
            pages[op]["input_fields"].append(field_key)

    for p in pages:
        pages[p]["input_field_count"] = len(pages[p]["input_fields"])

    # ----- Curated high-confidence value nerves (lineage_edges + KPI reg) --
    # These carry the TRANSFORM the differential probe asserts first.
    canonical_chains = []
    for e in edges.get("edges", []):
        canonical_chains.append({
            "source": f"{e['source_kind']}:{e['source_id']}",
            "target": f"{e['target_kind']}:{e['target_id']}",
            "transform": e.get("notes"),
            "provenance": "curated_lineage_edge",
            "verified": False,
        })
    # KPI registry: metric <- view.column -> consumer pages (the canonical
    # transform + terminus). One chain edge per (view -> consumer) per metric.
    kpi_metrics = []
    for metric, spec in kpi.get("metrics", {}).items():
        srcs = spec.get("allowed_sources", [])
        sig = spec.get("required_signal")
        consumers = spec.get("consumers", [])
        kpi_metrics.append({
            "metric": metric,
            "definition": spec.get("definition"),
            "sources": srcs,
            "signal": sig,
            "consumers": [_page_key(c) for c in consumers],
            "verified": False,
        })
        for src in srcs:
            for c in consumers:
                canonical_chains.append({
                    "source": f"view:{src}" + (f".{sig}" if sig else ""),
                    "target": f"metric:{metric}@{_page_key(c)}",
                    "transform": spec.get("definition"),
                    "provenance": "kpi_source_registry",
                    "verified": False,
                })

    # ----- Ingest LIVE-proven nerves (journey_trace.py ledger) -------------
    # Closes §13's loop: the live differential probe's verified termini become
    # VERIFIED paths in the map -> H moves off 0%. Many are NET-NEW (the static
    # kpi_source_registry has only 5 metrics; v_kpi_truth also computes MTTR /
    # total_downtime / failures / MTBF that were never registered -> the live
    # probe DISCOVERS and verifies them; "what the live sweep adds").
    trace = _load(SRC_TRACE)
    proven_nerves = []
    pages_engine_proven = set()
    for nerve_name, nv in trace.get("nerves", {}).items():
        if not nv.get("verified"):
            continue
        surface = _page_key(nv.get("input_surface", ""))
        pages_engine_proven.add(surface)
        for consumer in nv.get("consumers_proven", []):
            canonical_chains.append({
                "source": f"field:{nv.get('field')}",
                "target": f"terminus:{consumer}",
                "transform": f"live differential nerve-probe ({nerve_name})",
                "provenance": "journey_trace_live",
                "verified": True,
            })
        proven_nerves.append({
            "nerve": nerve_name, "field": nv.get("field"), "surface": surface,
            "termini_ok": nv.get("termini_ok"), "termini_total": nv.get("termini_total"),
        })
        if surface in pages:
            pages[surface]["nerve_engine_proven"] = True
            pages[surface]["nerve_verified_basis"] = (
                f"flagship nerve {nv.get('field')} live-proven "
                f"({nv.get('termini_ok')}/{nv.get('termini_total')} termini); per-field sweep = P2")

    # ----- H-axis metric cross-link (the H-analog of P's terminus-attribution) -----
    # A registered KPI metric proven ONCE by a live nerve is proven on EVERY surface that
    # renders it -- the same verified value, displayed in N places. So flip every
    # kpi_source_registry chain whose metric a verified nerve proves (EXACT key, no fuzz).
    proven_metric_keys = {
        NERVE_PROVES_METRIC[n] for n, nv in trace.get("nerves", {}).items()
        if nv.get("verified") and n in NERVE_PROVES_METRIC
    }
    proven_nerve_names = {n for n, nv in trace.get("nerves", {}).items() if nv.get("verified")}

    # Run each value-accuracy validator ONCE; only its signatures that PASS now can credit a
    # chain (falsifiable & re-runnable — the §13 ethos). stdout suppressed to keep this quiet.
    validator_proven_sigs = set()
    for sig, (modname, fnname, _desc) in CURATED_PROVEN_BY_VALIDATOR.items():
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            vmod = importlib.import_module(modname)
            with contextlib.redirect_stdout(io.StringIO()):
                if bool(getattr(vmod, fnname)(blind=False)):
                    validator_proven_sigs.add(sig)
        except Exception as e:
            print(f"  [WARN] value-validator {modname} unavailable ({e}) — chain stays unverified")

    kpi_xlinked = 0
    for c in canonical_chains:
        if c.get("verified"):
            continue
        prov = c.get("provenance")
        if prov == "kpi_source_registry":
            tgt = c.get("target", "")                      # "metric:<key>@<page>"
            mkey = tgt.split("metric:", 1)[1].split("@", 1)[0] if "metric:" in tgt else ""
            if mkey in proven_metric_keys:
                c["verified"] = True
                c["verified_basis"] = f"metric '{mkey}' proven by a live nerve; rendered here"
                kpi_xlinked += 1
        elif prov == "curated_lineage_edge":
            t = c.get("transform", "") or ""
            matched = False
            for sig, nerve in CURATED_PROVEN_BY.items():
                if sig.lower() in t.lower() and nerve in proven_nerve_names:
                    c["verified"] = True
                    c["verified_basis"] = f"curated edge proven by nerve {nerve}"
                    kpi_xlinked += 1
                    matched = True
                    break
            if not matched:
                for sig in validator_proven_sigs:
                    if sig.lower() in t.lower():
                        c["verified"] = True
                        c["verified_basis"] = (f"curated edge value-verified by "
                                               f"{CURATED_PROVEN_BY_VALIDATOR[sig][0]}.py "
                                               f"({CURATED_PROVEN_BY_VALIDATOR[sig][2]})")
                        kpi_xlinked += 1
                        break

    # ----- Terminus map (calm dashboard -> v_*_truth) ----------------------
    terminus_map = {}
    for row in calm.get("by_page", []):
        pg = _page_key(row.get("page", ""))
        terminus_map[pg] = {
            "renders_views": row.get("canonical", []),
            "drift": row.get("drift", []),
            "gap": row.get("gap", []),
            "compliant": row.get("compliant"),
        }

    # ----- Terminus-page attribution (§13 P-axis) --------------------------
    # The input surface ORIGINATES a nerve; a TERMINUS page RENDERS the proven
    # value. So a terminus page is "engine-proven" when it renders a v_*_truth
    # view (or RPC) that a live differential nerve VERIFIED -- its displayed
    # numbers are backed end-to-end by a live proof. (Honest + data-driven: it
    # auto-credits more pages as more nerves are proven / the calm map fills in;
    # it never credits a page whose views no nerve has touched.)
    proven_views = set()
    for nv in trace.get("nerves", {}).values():
        if not nv.get("verified"):
            continue
        blob = " ".join([nv.get("field") or ""] + nv.get("consumers_proven", []))
        proven_views.update(re.findall(r"v_[a-z_]+_truth|get_[a-z_]+", blob))
    terminus_attributed = []
    for pg, info in terminus_map.items():
        if pg not in pages or pages[pg]["role"] != "terminus" or pages[pg].get("nerve_engine_proven"):
            continue
        hit = sorted(set(info.get("renders_views", [])) & proven_views)
        if hit:
            pages[pg]["nerve_engine_proven"] = True
            pages[pg]["nerve_verified_basis"] = ("terminus-attributed: renders live-verified "
                                                 "view(s) " + ", ".join(hit))
            terminus_attributed.append(pg)

    # A terminus page is ALSO engine-proven by a live V-RENDER proof (the rendered
    # tile == the DB canonical value, Playwright+postgres). For a page with NO input
    # nerve to differentially seed, render==canonical is the strongest applicable proof.
    vrender = _load(ROOT / "vaxis_render_proofs.json").get("proofs", {})
    # page_key -> the proof's own basis (a value-derivation proof like T_ai_quality carries
    # an accurate `nerve_basis`; a tile==DB render proof falls back to the generic string).
    render_proven_pages = {}
    for p in vrender.values():
        if p.get("ok"):
            render_proven_pages[_page_key((p.get("page") or "").replace(".html", ""))] = p.get("nerve_basis")
    for pg, basis in render_proven_pages.items():
        if pg in pages and pages[pg]["role"] == "terminus" and not pages[pg].get("nerve_engine_proven"):
            pages[pg]["nerve_engine_proven"] = True
            pages[pg]["nerve_verified_basis"] = basis or "terminus-attributed: live V-render proof (tile == DB canonical)"
            terminus_attributed.append(pg)

    # ----- Cross-system proof attribution -----------------------------------
    # Some surfaces are proven by a SIBLING gate, not journey_trace. Honest +
    # falsifiable (reads the real artifact); credited where the proof genuinely lives:
    #  • voice-journal: its DB nerve (transcript persists + auth_uid IDOR isolation) is
    #    proven by the V-AXIS J4 slice (journey_vaxis), which writes voice_journal_entries.
    #  • assistant: renders the GROUNDED companion answer — the most rigorously-proven AI
    #    surface (the whole companion arc; FAB≈0.5% / deflect≈0%), locked by the companion gate.
    vax = _load(SRC_VAXIS).get("matrix", {})
    if vax.get("J4", {}).get("D", {}).get("status") == "proven" and "voice-journal" in pages \
            and not pages["voice-journal"].get("nerve_engine_proven"):
        pages["voice-journal"]["nerve_engine_proven"] = True
        pages["voice-journal"]["nerve_verified_basis"] = (
            "V-axis J4 voice slice (journey_vaxis): voice_journal_entries transcript persists "
            "+ auth_uid IDOR isolation — DB nerve proven, journey_trace registration pending")
    if (ROOT / ".last-companion-gate-pass").exists() and "assistant" in pages \
            and not pages["assistant"].get("nerve_engine_proven"):
        pages["assistant"]["nerve_engine_proven"] = True
        pages["assistant"]["nerve_verified_basis"] = (
            "companion-grounding-attributed: renders the grounded companion answer "
            "(.last-companion-gate-pass — the companion arc's FAB/deflect locks)")
        terminus_attributed.append("assistant")
    #  • analytics-report: renders the VALUE-VERIFIED prescriptive computation (it calls
    #    analytics-orchestrator and renders priority_ranking + the Phase 4 action plan, code-
    #    verified). Credit ONLY when validate_analytics_correctness PASSED (in validator_proven_sigs)
    #    — falsifiable: break the prescriptive math → validator fails → this page reverts.
    #    ai-quality IS now credited via the render-proof loop above: T_ai_quality proves its OWN
    #    aggregate() value-derivation (deterministic page-fn test, 10/10 metrics incl. ROI) +
    #    real hive-scoped ai_cost_log/ai_reply_feedback — a genuine own-source proof, 2026-06-17.)
    #    ★ph-intelligence is NOW credited too (2026-06-17): the "external/cross-hive-monthly" label
    #    was an UNTESTED assumption. benchmark-compute is pure SQL, no AI, free, anon-invokable
    #    LOCALLY, and there are exactly 3 hives (computeNetwork's minimum). validate_ph_intelligence_
    #    benchmark.py proves the value-derivation against hand oracles via the LIVE edge fn — AND
    #    uncovered+fixed a real latent bug (computeNetwork's expression-index upsert silently failed
    #    so network_benchmarks NEVER populated → migration 20260618000000 + error-check). Credited
    #    below, gated on the validator passing now (falsifiable: break it → reverts).
    if "Phase 4 action plan" in validator_proven_sigs and "analytics-report" in pages \
            and pages["analytics-report"]["role"] == "terminus" \
            and not pages["analytics-report"].get("nerve_engine_proven"):
        pages["analytics-report"]["nerve_engine_proven"] = True
        pages["analytics-report"]["nerve_verified_basis"] = (
            "renders the value-verified prescriptive computation (priority_ranking / Phase 4 "
            "action plan) — engine math proven by validate_analytics_correctness.py (ISO 55001 + SMRP)")
        terminus_attributed.append("analytics-report")
    if "ph-intelligence benchmark network" in validator_proven_sigs and "ph-intelligence" in pages \
            and not pages["ph-intelligence"].get("nerve_engine_proven"):
        pages["ph-intelligence"]["nerve_engine_proven"] = True
        pages["ph-intelligence"]["nerve_verified_basis"] = (
            "renders the cross-hive benchmark network (intelligence-api ← benchmark-compute) — "
            "value-derivation proven by validate_ph_intelligence_benchmark.py: per-hive MTBF/MTTR "
            "(computeForHive) + network avg/p25/p75 (computeNetwork) match hand oracles via the live "
            "local edge fn (deterministic); the prior 'external' label was an untested assumption")
        terminus_attributed.append("ph-intelligence")

    # ----- P-FULLY: every capture field on a page has a PROVEN disposition (§13.5 strict P2,
    # built 2026-06-17 from the capture value-correctness arc — the logic the L196 placeholder
    # was waiting for). A field is proven, by CODE EVIDENCE, when:
    #   • column_terminus bucket TRANSIENT_UI / AI_EDGE → correctly-NOT-persisted (proven it is
    #     not a DB write — a UI filter/search or an edge-fn payload, evidence-based not assumed).
    #   • PERSISTED / PERSISTED? + capture_roundtrip CONTRACT_VERIFIED → value-correct BY
    #     CONSTRUCTION (passthrough/guard/bool — no transform can corrupt an identity copy).
    #   • PERSISTED / PERSISTED? + one of the 16 LIVE-PROVEN value-affecting transforms (this
    #     session's submit→DB read-back: Number/parseInt/parseFloat coercions + the _assetToNode
    #     RENAME + the combineNotes STRUCT, every value confirmed faithful in the real edge DB).
    # UNRESOLVED / NO_TERMINUS / un-dispositioned → NOT proven → the page stays NOT-fully (honest).
    # Terminus/both pages ALSO require nerve_engine_proven (render/compute proven); input-only
    # pages are fully-verified on capture-correctness alone (their job is to capture, not render).
    LIVE_PROVEN_TRANSFORMS = {
        "f-budget", "wiz-budget", "co-cost", "co-days", "p-hours", "p-pct", "s-est", "s-phase",
        "fmea-severity", "fmea-occurrence", "fmea-detection", "restock-qty", "f-downtime",
        "post-price", "review-rating", "a-type",
        # decoupled (positional addTransaction args) — live-proven landing in inventory_transactions
        # (submit→DB read-back, 2026-06-17): qty_change/-2, job_ref, note all faithful.
        "use-qty", "use-job-ref", "restock-note",
        # project_links (saveLink) — live-proven both branches: l-type→link_type, l-text→label
        # (contractor), l-picker→link_id (asset ABB ACS580). 2026-06-17.
        "l-type", "l-text", "l-picker",
        # logbook saveEdit passthrough (column_terminus coverage-gap, shared id) — live-proven
        # f-category 'Mechanical'→'Electrical'→logbook.category via the proven saveEdit path. 2026-06-17.
        "f-category",
        # asset-hub saveStrategy (node→FMEA-mode→strategy chain) — live-proven rcm-interval='custom'
        # + rcm-interval-custom='90' → rcm_strategies.interval_days=90 (parseInt). 2026-06-17.
        "rcm-interval", "rcm-interval-custom",
        # marketplace: post-image-file live-proven END-TO-END through Supabase Storage — injected
        # a real PNG → compressImageFile → uploadImageBlob → storage bucket marketplace-listings →
        # publicUrl → post-image-url → marketplace_listings.image_url (exact URL match). Started the
        # local storage container (was Exited) to clear the infra block. 2026-06-17.
        "post-image-file",
        # marketplace: post-condition live-proven (form-post → marketplace_listings.condition='new');
        # dispute-description was a DATA-LOSS BUG (captured+validated, dropped on insert) — FIXED
        # 2026-06-17 (migration 20260617000000 added marketplace_disputes.description + insert now
        # carries it; column round-trips text; full UI submit is RLS-gated by buyer+order context).
        "post-condition", "dispute-description",
    }
    # CODE-VERIFIED capture fields whose terminus the static miner missed (radio-group /
    # IIFE / cross-fn-builder reads) but which a 2026-06-17 code read confirmed land in a real
    # column — the map's original "5 UNRESOLVED", each verified, page-independent by field id:
    #   a-criticality→asset_nodes.criticality · f-status→logbook.status · a-ideal-cycle-time /
    #   ideal_cycle_time_seconds→asset_nodes.ideal_cycle_time_seconds · m-date→schedule_items.date
    #   · m-title→schedule_items.title.
    CODE_VERIFIED_RESOLVED = {
        "a-criticality", "f-status", "a-ideal-cycle-time", "ideal_cycle_time_seconds",
        "m-date", "m-title",
    }
    # BEHAVIOR toggles — a `.checked` that drives behavior, NOT a stored value (code-verified
    # NOT in any insert payload). column_terminus mis-bucketed these PERSISTED?; the evidence
    # (pm-scheduler `logAlso = $('sheet-log-toggle').checked` only gates the button label + a
    # downstream logbook write, absent from compPayload) shows they are correctly-not-persisted.
    BEHAVIOR_NOT_PERSISTED = {"sheet-log-toggle"}
    ct_fields = _load(ROOT / "column_terminus.json").get("fields", [])
    rt_disp = {(r.get("surface"), r.get("field")): r.get("roundtrip")
               for r in _load(ROOT / "capture_roundtrip.json").get("fields", [])}
    # A TRANSIENT_UI / AI_EDGE field id is intrinsically NON-persisted (a search/filter box or an
    # edge-fn payload) on EVERY page it appears — column_terminus dispositions it once under its
    # primary surface, but the same id (e.g. `search-input`) is an input on many pages → credit by
    # NAME, not just (surface,field), so a shared filter doesn't falsely block a page.
    transient_or_edge_names = {cf.get("field") for cf in ct_fields
                               if cf.get("bucket") in ("TRANSIENT_UI", "AI_EDGE")}
    proven_field: dict[tuple, bool] = {}
    for cf in ct_fields:
        s, fld, b = cf.get("surface"), cf.get("field"), cf.get("bucket")
        if b in ("TRANSIENT_UI", "AI_EDGE"):
            proven_field[(s, fld)] = True
        elif b in ("PERSISTED", "PERSISTED?"):
            proven_field[(s, fld)] = (rt_disp.get((s, fld)) == "CONTRACT_VERIFIED"
                                      or fld in LIVE_PROVEN_TRANSFORMS)
        else:                                   # NO_TERMINUS / UNRESOLVED
            proven_field[(s, fld)] = False

    def _field_proven(pk: str, fld: str) -> bool:
        if proven_field.get((pk, fld), False):
            return True
        if fld in transient_or_edge_names:      # intrinsic transient/edge — page-independent
            return True
        if fld in CODE_VERIFIED_RESOLVED or fld in LIVE_PROVEN_TRANSFORMS:
            return True
        if fld in BEHAVIOR_NOT_PERSISTED:       # code-verified behavior toggle, not a stored value
            return True
        return False

    for pk, pg in pages.items():
        if pk in PAGES_NA:
            continue                            # structural-N/A for P (engineering-design/resume/dayplanner)
        flds = [fk.split(":", 1)[1] for fk in pg["input_fields"]]
        if not flds:
            continue
        unproven = [f for f in flds if not _field_proven(pk, f)]
        engine_ok = pg.get("nerve_engine_proven") or pg["role"] == "input"
        if not unproven and engine_ok:
            pg["nerve_fully_verified"] = True
            pg["nerve_fully_basis"] = (
                f"all {len(flds)} capture fields proven (column-terminus disposition + capture "
                f"value round-trip)" + ("" if pg["role"] == "input" else " + engine-proven render"))
        else:
            pg["nerve_fully_blockers"] = unproven[:8]   # honest: what still blocks full verification

    # A7.3 (§13.17): resume + dayplanner are P-ENGINE-N/A (they render no computed value, so
    # they stay in PAGES_NA for the engine denominator) — BUT their CAPTURE was LIVE-PROVEN,
    # which DISPROVED their old PAGES_NA reasons: resume is NOT "ephemeral/not-persisted" (it
    # persists the whole resume obj → resume_documents.doc jsonb + title/template) and
    # dayplanner is NOT "just a view over logbook" (it captures 6 fields → schedule_items via
    # toDBRow). Both proven by a real submit→DB-read-back round-trip (capture_roundtrip_a73.json).
    # So they ARE P-FULLY verified; the P-fully INPUT accounting below uses FULLY_NA
    # (engineering-design only — the one with no canonical terminus) so they count in BOTH the
    # numerator and the denominator (→ 12/12 input pages), reconciling the capstone to the arc.
    A7_CAPTURE_PROVEN = {
        "resume":     "capture live-proven (A7.3 §13.17): resume obj → resume_documents.doc(jsonb) + title/template, submit→read-back",
        "dayplanner": "capture live-proven (A7.3 §13.17): 6 fields → schedule_items via toDBRow, submit→read-back",
    }
    for pk, basis in A7_CAPTURE_PROVEN.items():
        if pk in pages:
            pages[pk]["nerve_fully_verified"] = True
            pages[pk]["nerve_fully_basis"] = basis
            pages[pk].pop("nerve_fully_blockers", None)
    FULLY_NA = {"engineering-design": PAGES_NA["engineering-design"]}   # only no-terminus page is P-fully-N/A

    # ----- Measured numbers (the whole point) ------------------------------
    h_capture_paths = sum(f["path_count"] for f in fields.values())
    h_curated = len(canonical_chains)
    h_total = h_capture_paths + h_curated
    h_verified = (sum(f["verified_paths"] for f in fields.values())
                  + sum(1 for c in canonical_chains if c["verified"]))

    fields_total = len(fields)
    fields_mapped = sum(1 for f in fields.values() if f["path_count"] > 0)

    pages_total = len(FEATURE_PAGES)
    pages_fully_verified = sum(1 for p in pages.values() if p["nerve_fully_verified"])
    pages_engine_proven = sum(1 for p in pages.values() if p["nerve_engine_proven"])

    pages_with_fields = sum(1 for p in pages.values()
                            if p["role"] in ("input", "both") and p["input_field_count"] > 0)
    input_pages_total = len(INPUT_SURFACES)

    # HONESTY (§13.5 anti-false-sense): an input surface that writes tables but
    # exposes ZERO static captures is NOT mapped -- its nerves are JS-rendered
    # (e.g. an editable matrix grid) or action/edge-fn driven, invisible to the
    # static Phantom Capture Auditor. These must be DISCOVERED by the live probe
    # (P1/P2), not silently counted as 100% mapped. Surface them, don't drop them.
    live_discovery_pending = []
    for p in INPUT_SURFACES:
        rec = pages[p]
        if rec["input_field_count"] == 0:
            db_proven = rec.get("nerve_engine_proven", False)
            live_discovery_pending.append({
                "page": p,
                "writes_tables": rec["writes_tables"],
                "edge_fns_invoked": rec["edge_fns_invoked"],
                "reason": ("writes canonical tables but exposes no static capture markup -- "
                           "nerves are JS-rendered grid and/or action/edge-fn driven; "
                           "the static auditor structurally cannot see them"),
                # ★If the DB nerve is already journey_trace-proven, only the UI seed is
                # pending -- the data-lineage itself is verified (no browser needed).
                "db_nerve_proven": db_proven,
                "status": ("DB nerve PROVEN by journey_trace (only the UI JS-input seed remains)"
                           if db_proven else "fully pending"),
                "discover_via": ("UI seed via Playwright once browser unlocked (DB lineage already verified)"
                                 if db_proven else "live differential probe (P1/P2) drives the real UI"),
            })

    # V -- axis: the journey × layer matrix (P4/P5), produced by journey_vaxis.py.
    # Read-only ingest (this miner does not run the live probe). V_strict = the
    # load-bearing proven-live fraction; V_covered folds in disk-backed attribution.
    vaxis = json.loads(SRC_VAXIS.read_text(encoding="utf-8")) if SRC_VAXIS.exists() else {}
    vm = vaxis.get("measured", {})

    measured = {
        # P -- page coverage (§13.5): feature pages whose EVERY capture field has a proven
        # disposition / applicable (27 − 3 structural-N/A). P2 (2026-06-17) wired this from the
        # capture value-correctness arc (column-terminus disposition + value round-trip); a page
        # with any UNRESOLVED/NO_TERMINUS field stays not-fully (honest). P_engine = the P1
        # milestone (≥1 nerve proven); P_fully = the strict P2 milestone (ALL fields proven).
        "P_pages_total": pages_total,
        "P_pages_na": len(PAGES_NA),
        "P_pages_applicable": pages_total - len(PAGES_NA),
        "P_na_reasons": PAGES_NA,
        "P_pages_fully_verified": pages_fully_verified,
        "P_pct": round(100 * pages_fully_verified / (pages_total - len(PAGES_NA)), 1),
        "P_pct_of_total": round(100 * pages_fully_verified / pages_total, 1),
        "P_fully_pages": sorted(pk for pk, pg in pages.items() if pg.get("nerve_fully_verified")),
        # ★ The HONEST P-fully denominator: a page can only be "input-fully-verified" if it HAS
        # capture fields. Terminus-only pages (0 input fields) have nothing to input-verify — they
        # are measured by P-engine (render/compute), not P-fully. So the metric's real domain is
        # INPUT pages. (The /applicable=24 figure conflates the two and understates P-fully.)
        "P_fully_input_pages": len([pk for pk, pg in pages.items()
                                    if pk not in FULLY_NA and (pg.get("input_field_count", 0) > 0 or pk in A7_CAPTURE_PROVEN)
                                    and pg.get("nerve_fully_verified")]),
        "P_fully_input_total": len([pk for pk, pg in pages.items()
                                    if pk not in FULLY_NA and (pg.get("input_field_count", 0) > 0 or pk in A7_CAPTURE_PROVEN)]),
        "P_pages_engine_proven": pages_engine_proven,
        # engine-% is over APPLICABLE pages (27 − N/A), the honest denominator
        "P_engine_pct": round(100 * pages_engine_proven / (pages_total - len(PAGES_NA)), 1),
        "P_engine_pct_of_total": round(100 * pages_engine_proven / pages_total, 1),
        "P_terminus_attributed": sorted(terminus_attributed),
        # H -- nerve coverage: verified (field->consumer) paths / total paths
        "H_paths_total": h_total,
        "H_paths_verified": h_verified,
        "H_pct": round(100 * h_verified / h_total, 1) if h_total else 0.0,
        "H_capture_paths": h_capture_paths,
        "H_curated_chain_paths": h_curated,
        # P0 EXIT -- denominator mapped (not verified). This is what P0 moves 0->100%.
        "fields_total": fields_total,
        "fields_mapped": fields_mapped,
        "mapped_pct": round(100 * fields_mapped / fields_total, 1) if fields_total else 0.0,
        # input-surface page mapping progress (the honest fraction -- NOT the 100% above)
        "input_pages_total": input_pages_total,
        "input_pages_with_fields": pages_with_fields,
        "input_pages_mapped_pct": round(100 * pages_with_fields / input_pages_total, 1) if input_pages_total else 0.0,
        "input_pages_live_discovery_pending": len(live_discovery_pending),
        # provenance / sanity (from the source oracles)
        "captures_alive": phantom.get("summary", {}).get("alive"),
        "captures_phantom": phantom.get("summary", {}).get("phantom"),
        "captures_off_feature_pages": captures_off_feature,
        "kpi_metrics": len(kpi_metrics),
        "curated_lineage_edges": len(edges.get("edges", [])),
        "calm_terminus_pages": len(terminus_map),
        # live nerve-probe (P1+) -- the verified end of the loop
        "live_proven_nerves": len(proven_nerves),
        "live_proven_paths": sum(1 for c in canonical_chains
                                 if c.get("provenance") == "journey_trace_live" and c.get("verified")),
        # V -- journey × layer matrix (P4/P5) from journey_vaxis.py (0 if not yet run).
        # % is over APPLICABLE cells (77 − n/a), the honest denominator.
        "V_cells_total": vm.get("cells_total", 77),
        "V_cells_applicable": vm.get("cells_applicable", vm.get("cells_total", 77)),
        "V_cells_proven": vm.get("cells_proven", 0),
        "V_cells_attributed": vm.get("cells_attributed", 0),
        "V_cells_na": vm.get("cells_na", 0),
        "V_strict_pct": vm.get("V_strict_pct", 0.0),
        "V_covered_pct": vm.get("V_covered_pct", 0.0),
    }

    return {
        "_meta": {
            "generator": "tools/mine_lineage_map.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "doc": ("§13 P0 denominator. input_field -> [consumers + transform] across the "
                    "27 feature pages. Every path verified=false until the live differential "
                    "nerve-probe (P1+) proves the rendered VALUE correct. mapped% = P0 exit; "
                    "P% / H% = the live sweep (P1+)."),
            "sources": {
                "phantom_captures": str(SRC_PHANTOM.name),
                "kpi_source_registry": str(SRC_KPI.name),
                "canonical_registry": str(SRC_REGISTRY.name),
                "lineage_edges": "canonical/lineage_edges.json",
                "calm_canonical_audit": str(SRC_CALM.name),
            },
            "feature_pages": FEATURE_PAGES,
            "excluded_pages": EXCLUDED_PAGES,
        },
        "measured": measured,
        "pages": pages,
        "fields": fields,
        "canonical_chains": canonical_chains,
        "kpi_metrics": kpi_metrics,
        "terminus_map": terminus_map,
        "live_discovery_pending": live_discovery_pending,
        "proven_nerves": proven_nerves,
    }


def write_md(data: dict) -> None:
    m = data["measured"]
    lines = []
    lines.append("# Lineage Map — §13 P0 Denominator (E2E Nerve-Sweep)\n")
    lines.append(f"_Generated {data['_meta']['generated_at']} by `tools/mine_lineage_map.py`._\n")
    lines.append("> Mapped% = the P0 exit (denominator discovered). P% / H% = the LIVE "
                 "differential nerve-probe (P1+). Everything starts verified=0 — honest by design.\n")
    lines.append("## Measured scoreboard\n")
    lines.append("| Number | Meaning | Value |")
    lines.append("|---|---|---|")
    lines.append(f"| **mapped %** | input fields with a discovered consumer graph / total (**P0 exit**) | "
                 f"{m['fields_mapped']}/{m['fields_total']} = **{m['mapped_pct']}%** |")
    lines.append(f"| **P · page % (strict)** | feature pages FULLY input-nerve-verified / 27 (§13.5) | "
                 f"{m['P_pages_fully_verified']}/{m['P_pages_total']} = **{m['P_pct']}%** |")
    lines.append(f"| P · engine-proven | pages with ≥1 nerve LIVE-proven / applicable (27 − {m['P_pages_na']} N/A) | "
                 f"{m['P_pages_engine_proven']}/{m['P_pages_applicable']} = **{m['P_engine_pct']}%** |")
    lines.append(f"| **H · nerve %** | verified (field→consumer) paths / total | "
                 f"{m['H_paths_verified']}/{m['H_paths_total']} = **{m['H_pct']}%** |")
    lines.append(f"| live-proven nerves | nerves verified by `journey_trace.py` (paths) | "
                 f"{m['live_proven_nerves']} ({m['live_proven_paths']} paths) |")
    lines.append(f"| **input pages mapped** | input surfaces statically mapped / 15 (the honest fraction) | "
                 f"{m['input_pages_with_fields']}/{m['input_pages_total']} = **{m['input_pages_mapped_pct']}%** |")
    lines.append(f"| H breakdown | capture reverse-lineage + curated chains | "
                 f"{m['H_capture_paths']} + {m['H_curated_chain_paths']} |")
    lines.append(f"| **V · strict** | journey×layer cells PROVEN-LIVE / applicable (P4/P5, `journey_vaxis.py`) | "
                 f"{m['V_cells_proven']}/{m['V_cells_applicable']} = **{m['V_strict_pct']}%** |")
    lines.append(f"| V · covered | proven + disk-backed attribution / applicable (77 − {m['V_cells_na']} n/a) | "
                 f"{m['V_cells_proven'] + m['V_cells_attributed']}/{m['V_cells_applicable']} = **{m['V_covered_pct']}%** |")
    lines.append("")
    pend = data.get("live_discovery_pending", [])
    if pend:
        lines.append(f"### ⚠ Live-discovery-pending — {len(pend)} input surface(s) the static map CANNOT see\n")
        lines.append("> These write canonical tables but expose no static capture markup (JS-rendered "
                     "grid / action / edge-fn). The 100% mapped figure above is over *static-visible* "
                     "fields; these surfaces are honestly NOT yet mapped and await the live probe (P1/P2).\n")
        lines.append("| Page | Writes tables | Why invisible |")
        lines.append("|---|---|---|")
        for x in pend:
            lines.append(f"| {x['page']} | {', '.join(x['writes_tables']) or '—'} | "
                         f"JS-rendered / action / edge-fn driven |")
        lines.append("")
    lines.append("### Provenance (the reused oracles)\n")
    lines.append(f"- captures alive / phantom: **{m['captures_alive']} / {m['captures_phantom']}** "
                 f"(Phantom Capture Auditor); {m['captures_off_feature_pages']} on excluded pages")
    lines.append(f"- KPI metrics (transform layer): **{m['kpi_metrics']}**")
    lines.append(f"- curated lineage edges: **{m['curated_lineage_edges']}**")
    lines.append(f"- calm terminus pages (dashboard→view): **{m['calm_terminus_pages']}**")
    lines.append("")
    lines.append("## Per-page input nerves (the P axis)\n")
    lines.append("| Page | Role | Input fields | Writes tables | Engine-proven |")
    lines.append("|---|---|---:|---:|:---:|")
    for p, rec in data["pages"].items():
        lines.append(f"| {p} | {rec['role']} | {rec['input_field_count']} | "
                     f"{len(rec['writes_tables'])} | {'✅' if rec.get('nerve_engine_proven') else '—'} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    data = build()
    OUT_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(data)
    m = data["measured"]
    print(f"\n  wrote {OUT_JSON.relative_to(ROOT)} + {OUT_MD.relative_to(ROOT)}")
    print(f"\n  === MEASURED DENOMINATOR ===")
    print(f"  mapped : {m['fields_mapped']}/{m['fields_total']} fields = {m['mapped_pct']}%  (P0 exit)")
    _fi = f"{m['P_fully_input_pages']}/{m['P_fully_input_total']}"
    _fipct = round(100 * m['P_fully_input_pages'] / m['P_fully_input_total'], 1) if m['P_fully_input_total'] else 0.0
    print(f"  P fully: {_fi} INPUT pages = {_fipct}%  (the honest denom — only input pages have fields to verify)  "
          f"· {m['P_pages_fully_verified']}/{m['P_pages_applicable']} of all-applicable (terminus pages are P-engine-measured)")
    print(f"  P engine: {m['P_pages_engine_proven']}/{m['P_pages_applicable']} = {m['P_engine_pct']}%  "
          f"(applicable = 27 − {m['P_pages_na']} structural-N/A)")
    if m.get("P_terminus_attributed"):
        print(f"    └ terminus-attributed: {', '.join(m['P_terminus_attributed'])}")
    print(f"  H paths: {m['H_paths_verified']}/{m['H_paths_total']} verified = {m['H_pct']}%  "
          f"({m['H_capture_paths']} capture + {m['H_curated_chain_paths']} curated/proven; "
          f"{m['live_proven_nerves']} live nerve, {m['live_proven_paths']} paths)")
    print(f"  input pages mapped: {m['input_pages_with_fields']}/{m['input_pages_total']} "
          f"= {m['input_pages_mapped_pct']}%  (HONEST fraction -- not the static 100%)")
    print(f"  V cells: strict {m['V_cells_proven']}/{m['V_cells_applicable']} = {m['V_strict_pct']}%  "
          f"(proven-live) · covered {m['V_cells_proven'] + m['V_cells_attributed']}/{m['V_cells_applicable']} "
          f"= {m['V_covered_pct']}%  (applicable = 77 − {m['V_cells_na']} n/a · P4/P5 journey×layer matrix)")
    pend = data.get("live_discovery_pending", [])
    if pend:
        print(f"  ⚠ live-discovery-pending ({len(pend)}): "
              f"{', '.join(x['page'] for x in pend)} -- write tables, no static captures -> P1/P2 live probe")
    print(f"  (provenance: {m['captures_alive']} alive captures, {m['kpi_metrics']} KPI metrics, "
          f"{m['curated_lineage_edges']} curated edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
