"""
Gate Efficacy Ledger — P1 of SELF_IMPROVING_GATE_ROADMAP.md.
============================================================
The gate's missing sense: *which of its own validators actually matter.*

PURE OBSERVATION. This tool reads the gate's own output (`platform_health.json`,
already written by run_platform_checks.py) and maintains an append-only ledger
of per-validator efficacy. It NEVER runs the gate, NEVER changes a verdict, and
NEVER affects an exit code. It only watches.

What it tracks per validator, across gate runs:
  - times_run / times_pass / times_fail / times_warn / times_skip
  - true_catches  : PASS-or-WARN -> FAIL transitions (it caught a NEW regression,
                    vs. a chronically-red baseline that fires every run)
  - last_fired_run: the run index of the most recent true catch
  - elapsed_recent: last runtime (feeds the P5 retirement payoff / runtime budget)
  - origin        : bug | miner | manual | wiring | unknown (override file optional)
  - domain/dim    : C1 verdict contract — {general|saas|ai} x {usability|functionality|
                    adaptability|internal_control|safety|cost}. Deterministic heuristic +
                    `gate_domain_dimension_map.json` override. Powers the 4-axis scorecard
                    (roadmap §1.5) and is the SAME taxonomy tools/gate_eval_splits.py uses.

Why "true catch" = a transition, not just "is FAIL": a validator that is red on
every run is a known-issue baseline, not a catch. A validator that goes green->red
caught something new — that is the load-bearing signal. A validator with 0 true
catches over many runs AND no origin is a P5 retirement candidate (Rule D).

Usage:
  python tools/gate_efficacy_ledger.py            # update from latest platform_health.json
  python tools/gate_efficacy_ledger.py update      # (same)
  python tools/gate_efficacy_ledger.py report      # human-readable efficacy report
  python tools/gate_efficacy_ledger.py update --force   # re-ingest same run (dedup off)

State: `gate_efficacy_ledger.json` (append-only history per validator). Optional
origin overrides: `gate_efficacy_origins.json` ({ "<validator-id>": "bug|miner|manual" }).
Exit code: 0 always (observation tool, never a gate).
"""
from __future__ import annotations
import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT        = Path(__file__).resolve().parent.parent
HEALTH_PATH = ROOT / "platform_health.json"
LEDGER_PATH = ROOT / "gate_efficacy_ledger.json"
ORIGINS_PATH = ROOT / "gate_efficacy_origins.json"
DOMAIN_DIM_PATH = ROOT / "gate_domain_dimension_map.json"
FLYWHEEL_STATE = ROOT / "flywheel_state.json"

MIN_RUNS_FOR_RETIREMENT = 10   # don't call anything a retirement candidate until history is deep enough
FIRED_RUNS_CAP          = 25   # cap the per-validator catch-history list

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _empty_ledger() -> dict:
    return {"version": 1, "runs_observed": 0, "last_ingested_ts": None,
            "last_run": {}, "validators": {}}


def _infer_origin(vid: str, overrides: dict) -> str:
    if vid in overrides:
        return str(overrides[vid])
    # Light auto-inference; everything else is "unknown" until enriched.
    if vid.endswith("-wiring") or "wiring" in vid:
        return "wiring"
    return "unknown"


# ── C1 / Track C — domain × dimension verdict contract ────────────────────────
# Every validator carries a {domain, dimension} tag so the ledger reports per-domain
# and the roadmap's 4-axis scorecard (§1.5) is computable. Deterministic heuristic on
# the validator's id/label/group; the human override file `gate_domain_dimension_map.json`
# wins ({ "<id>": {"domain": "...", "dimension": "..."} } | "<id>": "domain/dimension").
# tools/gate_eval_splits.py (P6) imports this same vocabulary so the validator corpus and
# the spec/probe corpus stay on ONE taxonomy.
DOMAINS    = ("general", "saas", "ai")
DIMENSIONS = ("usability", "functionality", "adaptability", "internal_control", "safety", "cost")

# ── Phase 8 / Companion eval axis — a SEPARATE taxonomy from DIMENSIONS above ──────
# DIMENSIONS classifies the GATE's own validators (the verdict contract). Phase 8 grades
# the COMPANION's *behaviour* along its own four product dimensions + safety + cost. It is
# kept on a distinct axis on purpose: adding companion dims must never reshuffle a single
# validator tag, and (critically) must never move the eval-split `test_seal`, which keys on
# unit id only. gate_eval_splits.py / ai_eval_gate.py / companion_eval_scorecard.json all
# import THIS one vocabulary so the corpus, the scorer and the registry never drift apart.
#   agent   — tool/route selection correctness (BFCL/τ-bench style; expected_route + params)
#   rag     — grounding + citations (Ragas: faithfulness, relevancy, context precision/recall)
#   memory  — cross-session recall + temporal reasoning + abstention (LongMemEval 5 abilities)
#   persona — specialist voice markers / narration fidelity
#   safety  — adversarial robustness (injection/jailbreak/PII/harmful) — the hard backstop
#   cost    — latency / tokens (lower = better; measured per-result, not classified)
COMPANION_DIMENSIONS = ("agent", "rag", "memory", "persona", "safety", "cost")

# Companion-axis category hints (a probe-bank `category` is the primary signal). Checked
# safety -> rag -> memory -> persona, default `agent` (route/tool selection is the most
# common companion task and the one `expected_route` already exercises). Substring match
# against `category + id + agent` lowercased.
# NOTE: the "safety" dimension here means ADVERSARIAL ROBUSTNESS (the probe bank's `adversarial`
# section: injection/jailbreak/harmful/PII/gibberish/...). It is deliberately NOT a bare
# "safety" substring — DOMAIN safety queries (`safety_intent`, `held_out_safety`: "what PPE /
# permit do I need for hot work") are route-selection tasks that go to the AGENT dimension, not
# adversarial-safety. This keeps eval_dimension=safety EQUAL to the frozen baseline's safety set.
_CD_SAFETY  = ("robustness", "injection", "jailbreak", "harmful", "pii", "gibberish",
               "offtopic", "off_topic", "contradiction", "underspecified", "adversarial")
_CD_RAG     = ("rag", "grounded", "grounding", "citation", "cited", "retrieval",
               "knowledge_base", "knowledge-base", "faithful")
_CD_MEMORY  = ("recall", "memory", "multi_session", "multi-session", "session", "remember",
               "follow_up", "followup", "abstention", "temporal")
_CD_PERSONA = ("persona", "voice_marker", "voice-marker", "narration", "tone", "briefing")


def classify_companion_dimension(entry: dict | None = None, *, category: str = "",
                                 unit_id: str = "", agent: str = "") -> str:
    """Map ONE companion eval unit (a probe-bank entry or canonical fixture) to a single
    companion dimension in {agent, rag, memory, persona, safety}. `cost` is measured per
    result, never classified here. Deterministic, category-first, side-effect-free.

    Pass either a probe dict via `entry` (uses its `category`/`id`/`agent`) or the fields
    directly. Default is `agent` — route/tool selection is the dominant companion task and
    the dimension `expected_route` already grades, so an untagged unit lands there honestly.
    """
    if entry:
        category = category or str(entry.get("category", ""))
        unit_id  = unit_id  or str(entry.get("id", ""))
        agent    = agent    or str(entry.get("agent", ""))
    txt = f"{category} {unit_id} {agent}".lower()
    if any(h in txt for h in _CD_SAFETY):  return "safety"
    if any(h in txt for h in _CD_RAG):     return "rag"
    if any(h in txt for h in _CD_MEMORY):  return "memory"
    if any(h in txt for h in _CD_PERSONA): return "persona"
    return "agent"

# domain hints (checked AI -> SaaS -> general; first hit wins)
_AI_HINTS   = ("ai-", "ai_", "prompt", "rag", "companion", "model-router", "model_router",
               "embedding", "voice", "agent", "episodic", "semantic", "procedural",
               "prospective", "hierarchical", "memory", "gateway", "llm", "brain", "provider")
_SAAS_HINTS = ("rls", "hive", "tenant", "permission", "audit", "compliance", "marketplace",
               "billing", "entitlement", "migration", "schema-coverage", "fk-on-delete",
               "fk_on_delete", "security-definer", "pg-cron", "pg_cron", "trigger",
               "add-column", "reset-coverage", "table-collision", "role-string", "rpc-argument")

# dimension hints (checked safety -> cost -> usability -> internal_control -> adaptability
# -> functionality default)
_SAFETY_HINTS    = ("injection", "jailbreak", "hallucination", "grounding", "adversarial", "safety")
_COST_HINTS      = ("cost", "latency", "token-budget", "provider-health")
_USABILITY_HINTS = ("aria", "tap-target", "heading", "viewport", "img-alt", "icon-button",
                    "tabindex", "button-type", "password-input", "select-placeholder",
                    "meta-description", "mobile", "home-stack", "label-coverage", "alt-cover")
_CONTROL_HINTS   = ("rls", "security-definer", "audit", "eschtml", "innerhtml", "xss",
                    "like-escape", "env-variable", "unpinned", "body-size", "json-parse",
                    "fetch-error", "empty-catch", "document-write", "settimeout", "javascript-href",
                    "external-link", "console-log", "duplicate", "compliance", "permission")
_ADAPT_HINTS     = ("migration", "schema", "fk-", "add-column", "view-select-star",
                    "auto-discovery", "edge-config", "table-collision", "reset-coverage",
                    "freshness", "decay", "silo", "drift", "tier-contract")


def _load_dd_overrides() -> dict:
    """Load the {domain,dimension} override map. Tolerates a flat `{ "<id>": ... }`
    map OR an `{ "overrides": { "<id>": ... } }` wrapper (docs/examples live as
    sibling underscore keys, which never match a real id)."""
    raw = _load_json(DOMAIN_DIM_PATH) or {}
    inner = raw.get("overrides")
    return inner if isinstance(inner, dict) else raw


def _parse_dd_override(val) -> tuple[str | None, str | None]:
    """Override entry: {'domain':..,'dimension':..} | 'domain/dimension' | 'domain'."""
    if isinstance(val, dict):
        return val.get("domain"), val.get("dimension")
    if isinstance(val, str):
        if "/" in val:
            d, _, dim = val.partition("/")
            return (d.strip() or None), (dim.strip() or None)
        return (val.strip() or None), None
    return None, None


def _hit(hint: str, text: str, tokens: set) -> bool:
    """Multi-part hints (containing - _ or space) match as a substring; single-word
    hints must match a WHOLE token, so 'rag' does not fire inside 'localstorage'."""
    if "-" in hint or "_" in hint or " " in hint:
        return hint in text
    return hint in tokens


def classify_domain_dimension(vid: str, label: str = "", group: str = "",
                              overrides: dict | None = None) -> tuple[str, str]:
    """Deterministic {domain, dimension} tag for one validator. Human override wins;
    otherwise a token/substring heuristic over id+label+group. Pure + side-effect-free."""
    overrides = overrides or {}
    o_dom, o_dim = _parse_dd_override(overrides.get(vid))
    text = f"{vid} {label} {group}".lower()
    tokens = set(re.split(r"[^a-z0-9]+", text))

    if o_dom in DOMAINS:
        domain = o_dom
    elif any(_hit(h, text, tokens) for h in _AI_HINTS):
        domain = "ai"
    elif any(_hit(h, text, tokens) for h in _SAAS_HINTS):
        domain = "saas"
    else:
        domain = "general"

    if o_dim in DIMENSIONS:
        dimension = o_dim
    elif any(_hit(h, text, tokens) for h in _SAFETY_HINTS):
        dimension = "safety"
    elif any(_hit(h, text, tokens) for h in _COST_HINTS):
        dimension = "cost"
    elif any(_hit(h, text, tokens) for h in _USABILITY_HINTS):
        dimension = "usability"
    elif any(_hit(h, text, tokens) for h in _CONTROL_HINTS):
        dimension = "internal_control"
    elif any(_hit(h, text, tokens) for h in _ADAPT_HINTS):
        dimension = "adaptability"
    else:
        dimension = "functionality"
    return domain, dimension


def update(force: bool = False) -> dict:
    """Ingest the latest platform_health.json into the ledger. Idempotent per
    run (dedup by timestamp) unless --force."""
    health = _load_json(HEALTH_PATH)
    if not health or not isinstance(health.get("validators"), list):
        print(f"{YEL}No usable platform_health.json — run the gate first (run_platform_checks.py).{RESET}")
        return _load_json(LEDGER_PATH) or _empty_ledger()

    ledger   = _load_json(LEDGER_PATH) or _empty_ledger()
    overrides = _load_json(ORIGINS_PATH) or {}
    dd_overrides = _load_dd_overrides()
    ts = health.get("timestamp")

    if ts and ledger.get("last_ingested_ts") == ts and not force:
        print(f"{YEL}platform_health.json (ts={ts}) already ingested — nothing new. Use --force to re-ingest.{RESET}")
        return ledger

    run = ledger.get("runs_observed", 0) + 1
    fly = _load_json(FLYWHEEL_STATE) or {}
    vals = ledger.setdefault("validators", {})

    n_catch = 0
    for row in health["validators"]:
        vid = row.get("id")
        if not vid:
            continue
        status = (row.get("status") or "").upper()
        rec = vals.get(vid)
        if rec is None:
            rec = {
                "label": row.get("label", ""), "group": row.get("group", ""),
                "origin": _infer_origin(vid, overrides),
                "domain": "", "dimension": "",   # set by the refresh block below (C1)
                "first_seen_run": run, "last_run": run,
                "times_run": 0, "times_pass": 0, "times_fail": 0, "times_warn": 0, "times_skip": 0,
                "last_status": None, "true_catches": 0, "last_fired_run": None,
                "fired_runs": [], "elapsed_recent": row.get("elapsed", 0),
            }
            vals[vid] = rec
        # refresh metadata that can change as the gate evolves
        rec["label"] = row.get("label", rec.get("label", ""))
        rec["group"] = row.get("group", rec.get("group", ""))
        if vid in overrides:
            rec["origin"] = str(overrides[vid])
        rec["elapsed_recent"] = row.get("elapsed", rec.get("elapsed_recent", 0))
        rec["domain"], rec["dimension"] = classify_domain_dimension(
            vid, rec["label"], rec["group"], dd_overrides)

        prev = rec.get("last_status")
        rec["times_run"] += 1
        rec["last_run"]   = run
        if   status == "PASS": rec["times_pass"] += 1
        elif status == "FAIL": rec["times_fail"] += 1
        elif status == "WARN": rec["times_warn"] += 1
        elif status == "SKIP": rec["times_skip"] += 1

        # True catch: was not-failing (PASS/WARN), now FAIL. A new validator that
        # is born FAIL (prev is None) is NOT a catch — it had nothing to transition from.
        if status == "FAIL" and prev in ("PASS", "WARN"):
            rec["true_catches"] += 1
            rec["last_fired_run"] = run
            rec["fired_runs"] = (rec.get("fired_runs", []) + [run])[-FIRED_RUNS_CAP:]
            n_catch += 1

        rec["last_status"] = status

    # Backfill {domain,dimension} on validators not seen this run (retired/skipped).
    for _vid, _rec in vals.items():
        if not _rec.get("domain") or not _rec.get("dimension"):
            _rec["domain"], _rec["dimension"] = classify_domain_dimension(
                _vid, _rec.get("label", ""), _rec.get("group", ""), dd_overrides)

    ledger["taxonomy"] = {"domains": list(DOMAINS), "dimensions": list(DIMENSIONS),
                          "companion_dimensions": list(COMPANION_DIMENSIONS)}
    ledger["runs_observed"]   = run
    ledger["last_ingested_ts"] = ts
    ledger["last_run"] = {
        "ts": ts, "mode": health.get("mode"),
        "flywheel_turn": fly.get("turn"),
        "ingested_at": datetime.now().isoformat(timespec="seconds"),
        "overall": health.get("overall"),
        "validators_seen": len(health["validators"]),
        "new_catches_this_run": n_catch,
    }
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"{GREEN}Efficacy ledger updated.{RESET} run #{run} · {len(health['validators'])} validators · "
          f"{n_catch} new true-catch(es) this run · history depth {run} run(s).")
    return ledger


def report(ledger: dict | None = None) -> None:
    ledger = ledger or _load_json(LEDGER_PATH)
    if not ledger or not ledger.get("validators"):
        print(f"{YEL}No ledger yet — run `python tools/gate_efficacy_ledger.py update` after a gate run.{RESET}")
        return
    runs = ledger.get("runs_observed", 0)
    vals = ledger["validators"]
    total = len(vals)

    catchers   = sorted([v for v in vals.values() if v["true_catches"] > 0],
                        key=lambda v: -v["true_catches"])
    never      = [k for k, v in vals.items() if v["true_catches"] == 0]
    never_noorigin = [k for k in never if vals[k].get("origin", "unknown") == "unknown"]
    chronic    = [k for k, v in vals.items()
                 if v["times_run"] >= 3 and v["times_fail"] / max(1, v["times_run"]) >= 0.8]
    slowest    = sorted(vals.items(), key=lambda kv: -(kv[1].get("elapsed_recent") or 0))[:8]
    runtime    = sum((v.get("elapsed_recent") or 0) for v in vals.values())

    print(f"\n{BOLD}Gate Efficacy Report{RESET}  ·  history depth: {runs} run(s)  ·  {total} validators tracked")
    print("=" * 68)
    print(f"  total recent gate runtime (sum of last elapsed): {runtime:.0f}s")
    print(f"  load-bearing (>=1 true catch): {len(catchers)}   "
          f"never-fired: {len(never)}   chronically-red: {len(chronic)}")

    # ── 4-axis scorecard coverage (C1): where the gate's own validators sit ──
    by_dom: dict = {}
    by_dim: dict = {}
    for v in vals.values():
        dom = v.get("domain") or "?"; dim = v.get("dimension") or "?"
        d = by_dom.setdefault(dom, {"n": 0, "catch": 0}); d["n"] += 1
        d["catch"] += 1 if v["true_catches"] > 0 else 0
        m = by_dim.setdefault(dim, {"n": 0, "catch": 0}); m["n"] += 1
        m["catch"] += 1 if v["true_catches"] > 0 else 0
    print(f"\n{CYAN}{BOLD}  Coverage by domain{RESET}  (validators · load-bearing)")
    for dom in list(DOMAINS) + [k for k in sorted(by_dom) if k not in DOMAINS]:
        if dom in by_dom:
            c = by_dom[dom]
            print(f"    {dom:<10}{c['n']:>5} validators   {c['catch']:>3} load-bearing")
    print(f"\n{CYAN}{BOLD}  Coverage by dimension{RESET}  (4-axis scorecard + AI safety/cost)")
    for dim in list(DIMENSIONS) + [k for k in sorted(by_dim) if k not in DIMENSIONS]:
        if dim in by_dim:
            c = by_dim[dim]
            print(f"    {dim:<18}{c['n']:>5} validators   {c['catch']:>3} load-bearing")

    if runs < MIN_RUNS_FOR_RETIREMENT:
        print(f"\n  {YEL}History is shallow (need >= {MIN_RUNS_FOR_RETIREMENT} runs for retirement signal). "
              f"Counts below are seeded but not yet actionable.{RESET}")

    print(f"\n{CYAN}{BOLD}  Top catchers (load-bearing validators){RESET}")
    if catchers:
        for v in catchers[:12]:
            print(f"    {GREEN}{v['true_catches']:>3}x{RESET}  {_short(v['label']) or '?'}  "
                  f"[{v.get('origin','unknown')}]  last fired run #{v.get('last_fired_run')}")
    else:
        print(f"    (none yet — true catches accrue as validators go green->red across runs)")

    print(f"\n{CYAN}{BOLD}  Chronically-red ({len(chronic)}){RESET} — known-issue baselines or miscalibrated (not catches):")
    for k in chronic[:10]:
        v = vals[k]; print(f"    {RED}{v['times_fail']}/{v['times_run']} fail{RESET}  {k}")
    if not chronic: print("    (none)")

    print(f"\n{CYAN}{BOLD}  Retirement candidates (Rule D){RESET} — never fired AND no origin: {len(never_noorigin)}")
    if runs >= MIN_RUNS_FOR_RETIREMENT:
        for k in never_noorigin[:15]:
            print(f"    {YEL}-{RESET} {k}  (runs={vals[k]['times_run']}, never a true catch, origin=unknown)")
        if len(never_noorigin) > 15:
            print(f"    ... +{len(never_noorigin) - 15} more")
    else:
        print(f"    {YEL}deferred until history depth >= {MIN_RUNS_FOR_RETIREMENT} ({len(never_noorigin)} would qualify today){RESET}")

    print(f"\n{CYAN}{BOLD}  Slowest validators (runtime budget){RESET}")
    for k, v in slowest:
        print(f"    {(v.get('elapsed_recent') or 0):>6.1f}s  {k}")
    print()


def _short(s: str, n: int = 52) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def reclassify() -> dict:
    """Re-tag every validator's {domain,dimension} from the current heuristic +
    `gate_domain_dimension_map.json` override, WITHOUT re-ingesting a run (no count
    mutation). Run after editing the override map. Idempotent. Exit 0."""
    ledger = _load_json(LEDGER_PATH)
    if not ledger or not ledger.get("validators"):
        print(f"{YEL}No ledger yet — run `update` after a gate run first.{RESET}")
        return ledger or _empty_ledger()
    dd_overrides = _load_dd_overrides()
    changed = 0
    for vid, rec in ledger["validators"].items():
        dom, dim = classify_domain_dimension(vid, rec.get("label", ""),
                                             rec.get("group", ""), dd_overrides)
        if rec.get("domain") != dom or rec.get("dimension") != dim:
            changed += 1
        rec["domain"], rec["dimension"] = dom, dim
    ledger["taxonomy"] = {"domains": list(DOMAINS), "dimensions": list(DIMENSIONS),
                          "companion_dimensions": list(COMPANION_DIMENSIONS)}
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"{GREEN}Reclassified{RESET} {len(ledger['validators'])} validators "
          f"({changed} changed) using {len(dd_overrides)} override(s).")
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate efficacy ledger (pure observation)")
    ap.add_argument("cmd", nargs="?", default="update", choices=["update", "report", "reclassify"])
    ap.add_argument("--force", action="store_true", help="re-ingest the current platform_health.json")
    args = ap.parse_args()
    if args.cmd == "report":
        report()
    elif args.cmd == "reclassify":
        report(reclassify())
    else:
        led = update(force=args.force)
        report(led)
    return 0


if __name__ == "__main__":
    sys.exit(main())
