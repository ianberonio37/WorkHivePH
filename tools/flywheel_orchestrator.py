"""
Flywheel Improvement Loop — one turn of the Unified Mega Gate.
================================================================
The existing flywheels in this codebase ("Cross-Surface KPI Parity",
"Canonical Drift") were manual N-turn sweeps. This script makes the
loop explicit + runnable.

Each turn walks every Mega Gate layer in order, snapshots its state,
diffs against the previous turn, and surfaces three things:

  1. RATCHETS — baselines that tightened since last turn (forward-only
     wins; the platform got measurably better)
  2. REGRESSIONS — baselines that loosened (caught here before they
     ship; should never happen if Mega Gate is green, but defensive)
  3. PROMOTIONS — recurring L-1 miner patterns drafted into L-1.5 / L0 rule
     candidates, and load-bearing L0 validators (ranked by P1 efficacy) drafted
     into L0 → L2 sentinel candidates. Written to `promotion_queue.md` for
     one-pass approval (P2 of SELF_IMPROVING_GATE_ROADMAP.md). The engine
     discovers + drafts; the human judges via `promotion_dispositions.json`.

Layers walked:

  L-1   cluster pattern miners (mine_*.py)             → emergent rules
  L-1.5 skill rules manifest scan                       → documented rules
  L0    static validators with forward-only ratchets   → baseline counts
  L2    Playwright sentinel spec count                  → runtime coverage
  L13   walkthrough staleness                          → coverage freshness

State persists in `flywheel_state.json` (turn number + last-snapshot
counts per layer + per-candidate promotion recurrence). Outputs:
`flywheel_turn_report.md` (latest turn) and `promotion_queue.md` (the ranked
promotion queue; both replaced each run). Human judgments persist in
`promotion_dispositions.json` (read-only to this tool).

Usage:
  python tools/flywheel_orchestrator.py            # run one turn
  python tools/flywheel_orchestrator.py --json     # machine output
  python tools/flywheel_orchestrator.py --reset    # zero the state

Exit code: 0 always (this is a reporting tool, not a gate).
"""
from __future__ import annotations
import argparse
import io
import json
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
STATE_PATH  = ROOT / "flywheel_state.json"
REPORT_PATH = ROOT / "flywheel_turn_report.md"

# P2 promotion engine inputs/outputs (SELF_IMPROVING_GATE_ROADMAP.md §P2)
LEDGER_PATH          = ROOT / "gate_efficacy_ledger.json"      # P1 efficacy (ranking signal)
SUBSTRATE_MANIFEST   = ROOT / "substrate_manifest.json"        # L-1 miner proposals
SENTINEL_COVERAGE    = ROOT / "sentinel_coverage_report.json"  # L0->L2 coverage (best-effort)
SENTINEL_REGISTRY    = ROOT / "SENTINEL_REGISTRY.json"         # L0->L2 coverage (fallback)
PROMOTION_QUEUE_PATH = ROOT / "promotion_queue.md"             # the one-pass approval surface
DISPOSITIONS_PATH    = ROOT / "promotion_dispositions.json"    # human judgments (engine never overwrites)


# ── ANSI for terminal output ───────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── State helpers ───────────────────────────────────────────────────────────

def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {"turn": 0, "history": [], "snapshots": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"turn": 0, "history": [], "snapshots": {}}


def _write_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _read_json(rel: str) -> dict | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Layer snapshotters ──────────────────────────────────────────────────────
# Each returns a dict of measurable scalars for the layer. The flywheel
# diffs successive snapshots — improvements (lower drift, higher coverage)
# are RATCHETS, the opposite are REGRESSIONS.

def _snapshot_L_minus_1() -> dict:
    """L-1 cluster miners. Read the *_pattern_mining_report.md files for
    proposal counts. Each new proposal is a candidate for L-1.5 rule
    promotion."""
    snap = {"proposals_by_cluster": {}}
    for md in ROOT.glob("*_pattern_mining_report.md"):
        cluster = md.name.replace("_pattern_mining_report.md", "")
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Count rule proposals — heuristic: lines starting with "- **" or
        # `## Proposal` sections.
        n_props = len(re.findall(r"^##\s+Proposal", text, re.MULTILINE))
        if n_props == 0:
            n_props = len(re.findall(r"^- \*\*", text, re.MULTILINE))
        snap["proposals_by_cluster"][cluster] = n_props
    snap["total_proposals"] = sum(snap["proposals_by_cluster"].values())
    return snap


def _snapshot_L_minus_1_5() -> dict:
    """L-1.5 skill rules. Counts rules in the manifest + conformance from
    the mining report."""
    snap = {"rules_in_manifest": 0, "conformant_rules": 0, "drift_rules": 0}
    manifest = _read_json("skill_rules_manifest.json")
    if manifest:
        rules = manifest.get("rules", [])
        snap["rules_in_manifest"] = len(rules)
    mining = ROOT / "skill_rules_mining_report.md"
    if mining.exists():
        text = mining.read_text(encoding="utf-8", errors="replace")
        # Look for the "✅ FULL" vs "⚠️" / "❌" counts
        m_full = re.search(r"FULL conformance.*?:\s*\*\*(\d+)\*\*", text)
        m_drift = re.search(r"(?:drift|partial).*?:\s*\*\*(\d+)\*\*", text, re.IGNORECASE)
        if m_full:  snap["conformant_rules"] = int(m_full.group(1))
        if m_drift: snap["drift_rules"]      = int(m_drift.group(1))
    return snap


def _snapshot_L0() -> dict:
    """L0 static validators with forward-only ratchet baselines. Reads
    each *_baseline.json + corresponding *_report.json to surface
    'current' and 'baseline' counts. Tightening = ratchet event."""
    snap: dict[str, Any] = {"baselines": {}, "total_baseline_count": 0,
                            "validators_with_baseline": 0}
    for bf in sorted(ROOT.glob("*_baseline.json")):
        name = bf.name.replace("_baseline.json", "")
        try:
            baseline_doc = json.loads(bf.read_text(encoding="utf-8"))
        except Exception:
            continue
        # The baseline file stores the locked count under various keys
        # depending on the validator. Pull the first numeric value.
        baseline_count = 0
        for v in baseline_doc.values():
            if isinstance(v, (int, float)):
                baseline_count = int(v); break
        snap["baselines"][name] = baseline_count
        snap["total_baseline_count"] += baseline_count
        snap["validators_with_baseline"] += 1
    return snap


def _snapshot_L2() -> dict:
    """L2 Playwright sentinel coverage. Counts test('check_...') and
    `name: 'check_...'` declarations across the canonical-signal-parity
    + cross-surface-kpi-parity specs."""
    snap = {"sentinel_specs": 0, "sentinel_fixme": 0, "voice_sentinels": 0}
    for sf in (ROOT / "tests" / "journey-canonical-signal-parity.spec.ts",
               ROOT / "tests" / "journey-cross-surface-kpi-parity.spec.ts"):
        if sf.exists():
            body = sf.read_text(encoding="utf-8", errors="replace")
            snap["sentinel_specs"] += len(re.findall(r"\btest\s*\(\s*['\"]check_", body))
            snap["sentinel_specs"] += len(re.findall(r"\bname\s*:\s*['\"]check_", body))
            snap["sentinel_fixme"] += len(re.findall(r"\btest\.fixme\s*\(\s*['\"]check_", body))
    vsf = ROOT / "tests" / "journey-voice-phases.spec.ts"
    if vsf.exists():
        body = vsf.read_text(encoding="utf-8", errors="replace")
        snap["voice_sentinels"] = len(re.findall(r"\btest\s*\(\s*['\"]phase_", body))
    return snap


def _snapshot_L13() -> dict:
    """L13 staleness — read the staleness gate report if present."""
    snap = {"walkthroughs_total": 0, "walkthroughs_stale": 0}
    sg = _read_json("staleness_gate_report.json") or _read_json("sentinel_baseline.json")
    if sg:
        s = sg.get("summary", {})
        snap["walkthroughs_total"] = s.get("walkthroughs_total", 0)
        snap["walkthroughs_stale"] = s.get("walkthroughs_stale", 0)
    return snap


# ── Diff + report ──────────────────────────────────────────────────────────

def _diff_L0(prev: dict, curr: dict) -> tuple[list, list]:
    """Compare baselines across turns. Return (ratchets, regressions)."""
    p_base = prev.get("baselines", {})
    c_base = curr.get("baselines", {})
    ratchets, regressions = [], []
    for name, c_val in c_base.items():
        p_val = p_base.get(name, c_val)  # unknown = no change
        if c_val < p_val:
            ratchets.append({"validator": name, "from": p_val, "to": c_val})
        elif c_val > p_val:
            regressions.append({"validator": name, "from": p_val, "to": c_val})
    # New baselines (validator added this turn)
    for name in c_base:
        if name not in p_base:
            pass  # not a ratchet or regression — just a new layer
    return sorted(ratchets, key=lambda x: x["to"] - x["from"]), regressions


def _scalar_diff(prev: dict, curr: dict, key: str) -> dict:
    p = prev.get(key, 0)
    c = curr.get(key, 0)
    return {"from": p, "to": c, "delta": c - p}


# ── P4: Noise quarantine (SELF_IMPROVING_GATE_ROADMAP.md) ───────────────────
# A baseline-count INCREASE between turns is flagged a "regression" by the naive
# diff — but not every increase is rot. Classify each before scoring so weather
# never masquerades as a code regression (and never phantom-blocks a commit via
# the canonical board's "Flywheel turns" gate, which reads L0_regressions):
#
#   real             validator still FAILs at the new count — a violation
#                    ceiling was genuinely loosened. Scored (blocks).
#   adoption-ratchet validator PASSes; the baseline is an adoption FLOOR that
#                    legitimately ROSE (e.g. envelope_return_shape 1->2 when a
#                    new edge fn adopts the envelope). An improvement, not rot.
#   stale-report     re-running the validator shows the count back at `from` —
#                    the snapshot read a stale/half-written report (the recurring
#                    Turn-3 lesson). The re-run also refreshes that report.
#   env-down         re-running errored on a Docker/connection signature
#                    (httpx 10061 / dockerDesktopLinuxEngine) — weather, not code.
#   unknown          no validate_<name>.py to re-run — surfaced conservatively
#                    (scored) so a real regression in an unmapped validator is
#                    never silently dropped.
#
# Mechanism: re-run the regressed validator (the source of truth) and read its
# exit code + refreshed count. Best-effort + isolated — a classifier bug falls
# back to scoring ALL regressions (fail-loud, never hide rot).

ENV_ERROR_SIGNATURES = (
    "WinError 10061", "Connection refused", "ConnectError", "ConnectionError",
    "Max retries exceeded", "dockerDesktopLinuxEngine", "Cannot connect",
    "Failed to establish a new connection", "httpx.ConnectError",
)
# *_baseline.json files that are NOT a single validator's ratchet (gate-wide
# snapshots) — never classified as a code regression.
NON_VALIDATOR_BASELINES = {"platform"}


def _read_single_baseline(name: str) -> int | None:
    """First numeric value in <name>_baseline.json (same convention as
    _snapshot_L0). None if absent/unreadable."""
    try:
        doc = json.loads((ROOT / f"{name}_baseline.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    for v in doc.values():
        if isinstance(v, (int, float)):
            return int(v)
    return None


def _baseline_to_validator(name: str) -> Path | None:
    cand = ROOT / f"validate_{name}.py"
    return cand if cand.exists() else None


def env_probe() -> bool:
    """Best-effort hint: is the local Supabase/Docker stack reachable? Used to
    annotate env-down attribution. The actual env-down verdict comes from the
    re-run's error signature; this is recorded for context."""
    for port in (54321, 54322):   # supabase api / db
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            continue
    return False


def _classify_regression(reg: dict, env_up: bool) -> dict:
    """Bucket one baseline-increase regression. Returns reg + {classification,
    scored, ...}. `scored=True` means it counts as a real L0 regression."""
    name = reg["validator"]
    out = {**reg, "classification": "real", "scored": True, "env_up": env_up}
    if name in NON_VALIDATOR_BASELINES:
        out.update(classification="infra-baseline", scored=False)
        return out
    script = _baseline_to_validator(name)
    if script is None:
        out.update(classification="unknown", scored=True,
                   note="no validate_<name>.py to re-run; surfaced conservatively")
        return out
    try:
        proc = subprocess.run([sys.executable, str(script)], capture_output=True,
                              text=True, timeout=150, cwd=str(ROOT))
        combined = (proc.stdout or "") + (proc.stderr or "")
        if any(sig in combined for sig in ENV_ERROR_SIGNATURES):
            out.update(classification="env-down", scored=False)
            return out
        fresh = _read_single_baseline(name)
        out["fresh_count"] = fresh
        if proc.returncode == 0:
            # Validator passes at the new count → not a loosened ceiling.
            if fresh is not None and fresh <= reg["from"]:
                out.update(classification="stale-report", scored=False)
            else:
                out.update(classification="adoption-ratchet", scored=False)
        else:
            out.update(classification="real", scored=True)
    except subprocess.TimeoutExpired:
        out.update(classification="env-down", scored=False,
                   note="validator timed out — treated as env/weather")
    except Exception as e:
        out.update(classification="unknown", scored=True, error=str(e))
    return out


def _classify_regressions(raw: list, *, cap: int = 20) -> tuple[list, list, bool | None]:
    """Split raw regressions into (real, quarantined, env_up). Isolated: any
    failure falls back to scoring all raw regressions (never hide rot)."""
    if not raw:
        return [], [], None
    try:
        env_up = env_probe()
        real, quarantined = [], []
        for reg in raw[:cap]:
            c = _classify_regression(reg, env_up)
            (real if c.get("scored") else quarantined).append(c)
        for reg in raw[cap:]:
            real.append({**reg, "classification": "unclassified-cap", "scored": True})
        return real, quarantined, env_up
    except Exception:
        return raw, [], None


# ── Promotion engine (P2 of SELF_IMPROVING_GATE_ROADMAP.md) ─────────────────
# Turns the observer into a driver. Two bridges, mechanized:
#   L-1 → L0 : recurring miner patterns (de-facto conventions / anti-patterns)
#              graduate into rule/validator candidates.
#   L0  → L2 : load-bearing static validators with no Playwright sentinel
#              graduate into sentinel-scenario candidates, ranked by P1 efficacy.
# Candidates are DRAFTED into promotion_queue.md for one-pass approval. The
# engine discovers + drafts; the human judges (roadmap §6) — nothing is
# auto-promoted. Recurrence-gated so a one-off blip never queues.

PROMOTION_RECUR_THRESHOLD = 2        # must recur across >= N turns before it queues
PROMOTION_TRACK_PRUNE_AGE = 5        # forget a candidate unseen for this many turns (resolved/aged)
PROMOTION_CONF_BAND       = (0.80, 0.995)  # promotable band: widely-followed but not yet universal
SENTINEL_TOP_K            = 8        # cap sentinel candidates surfaced per turn

# Tokens to drop when fuzzy-matching a miner feature against an existing baseline.
_FEATURE_STOP = {"has", "is", "uses", "calls", "reads", "loads", "in", "the", "a",
                 "of", "with", "first", "handler", "param", "shared", "imports"}

def _load_json_path(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_dispositions() -> dict:
    """Human judgments persist here (approved/rejected/snoozed), keyed by
    candidate key. The orchestrator READS this and never overwrites it — it is
    the human's half of the one-pass-approval contract. Scaffolds an empty
    template on first run so the file is discoverable."""
    doc = _load_json_path(DISPOSITIONS_PATH)
    if doc is None:
        try:
            DISPOSITIONS_PATH.write_text(json.dumps({
                "_README": ("Set a candidate key (e.g. 'rule:edge:imports_cors_shared' or "
                            "'sentinel:rls_open_policy') to {\"status\": \"approved|rejected|snoozed\", "
                            "\"note\": \"...\"} to drop it from promotion_queue.md. "
                            "The orchestrator never overwrites this file."),
            }, indent=2), encoding="utf-8")
        except Exception:
            pass
        return {}
    return doc


def _disposition_status(dispositions: dict, key: str) -> str | None:
    rec = dispositions.get(key)
    if isinstance(rec, dict):
        return rec.get("status")
    if isinstance(rec, str):
        return rec
    return None


def _norm_id(s: str) -> str:
    """Canonical id form — collapses hyphen/underscore/space/case so a ledger id
    ('truth-view-contract') and a baseline key ('truth_view_contract') match."""
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def _feature_tokens(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower())
            if t and t not in _FEATURE_STOP}


def _already_enforced_exact(feature: str, baselines: dict) -> bool:
    """True when an existing L0 baseline already covers this feature (every
    feature token appears in a baseline name) — avoids re-proposing what the
    gate already enforces."""
    ft = _feature_tokens(feature)
    if not ft:
        return False
    return any(ft <= _feature_tokens(name) for name in baselines)


def _enforced_hint(feature: str, baselines: dict) -> str | None:
    """Soft hint: the baseline with the most token overlap, if any (>=2). Shown
    in the queue so the human can spot a likely duplicate without it being
    silently dropped."""
    ft = _feature_tokens(feature)
    best, best_ov = None, 0
    for name in baselines:
        ov = len(ft & _feature_tokens(name))
        if ov > best_ov:
            best, best_ov = name, ov
    return best if best_ov >= 2 else None


def _rule_candidates_from_substrate(baselines: dict) -> list:
    """L-1 → L0: mine substrate_manifest.json for outlier patterns that are
    de-facto conventions (high-but-not-universal conformance) or explicit
    anti-patterns. Each is a candidate rule/validator the gate doesn't yet
    enforce."""
    manifest = _load_json_path(SUBSTRATE_MANIFEST)
    out: list = []
    if not manifest:
        return out
    lo, hi = PROMOTION_CONF_BAND
    for summ in manifest.get("summaries", []) or []:
        cluster = (summ.get("file", "") or "").replace("_pattern_mining_report.json", "")
        cluster = cluster or (summ.get("label", "") or "cluster")
        for prop in summ.get("proposals", []) or []:
            feature = prop.get("feature")
            if not feature:
                continue
            outliers = prop.get("outliers") or []
            n_out = int(prop.get("outlier_count", len(outliers)) or 0)
            conf = float(prop.get("conformance", 0.0) or 0.0)
            anti = bool(prop.get("anti_pattern", False))
            if n_out <= 0:
                continue
            if not anti and not (lo <= conf <= hi):
                continue
            if _already_enforced_exact(feature, baselines):
                continue
            out.append({
                "key": f"rule:{cluster}:{feature}", "kind": "rule",
                "cluster": cluster, "feature": feature, "conformance": conf,
                "anti_pattern": anti, "outlier_count": n_out,
                "outliers": list(outliers)[:12],
                "enforced_hint": _enforced_hint(feature, baselines),
                "predicted_yield": n_out,
            })
    return out


def _strip_validator_id(s: str) -> str:
    """Normalize a coverage-map id ('validate_truth_view_contract.py' / label
    'validate_truth_view_contract') to the gate's short id form
    ('truth_view_contract') so it joins the efficacy ledger ('truth-view-contract')."""
    n = _norm_id(s)
    n = re.sub(r"^validate_", "", n)
    n = re.sub(r"_py$", "", n)
    return n


def _sentinel_candidates_from_gaps(baselines: dict) -> list:
    """L0 → L2: the sentinel coverage map (sentinels/sentinel_coverage_map.py) is
    the authority on which validators lack a Playwright sentinel. Surface only its
    *actionable* gaps — infrastructure / non-actionable gaps (RLS, cron, edge
    config, schema drift) cannot have a runtime sentinel and the map already tags
    them — then rank by P1 efficacy. No coverage map → no confident candidates."""
    doc = _load_json_path(SENTINEL_COVERAGE)
    if not isinstance(doc, dict) or not isinstance(doc.get("gaps"), list):
        return []
    ledger = _load_json_path(LEDGER_PATH) or {}
    led_by_norm = {_strip_validator_id(k): v
                   for k, v in (ledger.get("validators", {}) or {}).items()}
    norm_base = {_norm_id(k): v for k, v in baselines.items()}
    out: list = []
    for g in doc["gaps"]:
        if not isinstance(g, dict):
            continue
        if g.get("is_infrastructure") or g.get("category") == "infrastructure" \
                or g.get("actionable") is False:
            continue
        raw = g.get("file") or g.get("label") or g.get("id") or g.get("validator")
        if not raw:
            continue
        nid = _strip_validator_id(raw)
        rec = led_by_norm.get(nid, {})
        tc = int(rec.get("true_catches", 0) or 0)
        tf = int(rec.get("times_fail", 0) or 0)
        base = int(norm_base.get(nid, 0) or 0)
        score = tc * 100 + tf * 5 + min(base, 20)   # cap baseline pull so true catches dominate
        out.append({
            "key": f"sentinel:{nid}", "kind": "sentinel", "validator": nid,
            "label": rec.get("label", "") or g.get("label", "")
                     or ", ".join((g.get("checks") or [])[:4]),
            "checks": g.get("checks", []),
            "true_catches": tc, "times_fail": tf, "baseline": base,
            "coverage_verified": True, "predicted_yield": score,
        })
    out.sort(key=lambda c: -c["predicted_yield"])
    return out


def _compute_promotions(curr: dict, state: dict, turn: int) -> dict:
    """Discover candidates, update per-candidate recurrence, and emit those past
    the recurrence gate and not already dispositioned. Mutates
    state['promotion_tracking'] (persisted by the caller)."""
    baselines = curr.get("L0", {}).get("baselines", {})
    dispositions = _load_dispositions()
    tracking = state.setdefault("promotion_tracking", {})

    actives = (_rule_candidates_from_substrate(baselines)
               + _sentinel_candidates_from_gaps(baselines))
    active_by_key = {c["key"]: c for c in actives}

    # recurrence accounting
    for key, cand in active_by_key.items():
        t = tracking.get(key)
        if t is None:
            tracking[key] = {"kind": cand["kind"], "first_seen_turn": turn,
                             "last_seen_turn": turn, "seen_turns": 1}
        else:
            t["kind"] = cand["kind"]
            t["last_seen_turn"] = turn
            t["seen_turns"] = int(t.get("seen_turns", 0)) + 1
    # prune candidates that have resolved / aged out
    for key in list(tracking.keys()):
        if int(tracking[key].get("last_seen_turn", 0)) <= turn - PROMOTION_TRACK_PRUNE_AGE:
            del tracking[key]

    rule_q, sent_q = [], []
    n_below, n_disp = 0, 0
    for key, cand in active_by_key.items():
        tr = tracking.get(key, {})
        seen = int(tr.get("seen_turns", 0))
        cand["seen_turns"] = seen
        cand["first_seen_turn"] = tr.get("first_seen_turn", turn)
        if seen < PROMOTION_RECUR_THRESHOLD:
            n_below += 1
            continue
        if _disposition_status(dispositions, key) in ("approved", "rejected", "snoozed"):
            n_disp += 1
            continue
        (rule_q if cand["kind"] == "rule" else sent_q).append(cand)

    rule_q.sort(key=lambda c: (-c["predicted_yield"], -c.get("seen_turns", 0)))
    sent_q.sort(key=lambda c: (-c["predicted_yield"], -c.get("seen_turns", 0)))
    sent_q = sent_q[:SENTINEL_TOP_K]

    return {"rule_candidates": rule_q, "sentinel_candidates": sent_q,
            "tracked_total": len(tracking), "active_total": len(active_by_key),
            "below_threshold": n_below, "dispositioned": n_disp}


def _write_promotion_queue(promo: dict, turn: int, ts: str) -> None:
    rc, sc = promo["rule_candidates"], promo["sentinel_candidates"]
    L: list = []
    L.append(f"# Promotion Queue — Flywheel Turn #{turn}")
    L.append(f"_{ts}_  ·  generated by `tools/flywheel_orchestrator.py` "
             f"(P2, SELF_IMPROVING_GATE_ROADMAP.md)\n")
    L.append("> The engine **discovers and drafts**; you **judge**. Nothing here is auto-promoted.")
    L.append("> To dispose of a candidate, add its `key` to **`promotion_dispositions.json`** as")
    L.append("> `{\"status\": \"approved|rejected|snoozed\", \"note\": \"...\"}` — it then drops off this queue.")
    L.append("> `/harden` consumes the **Rule candidates**; `/sentinel-review` consumes the "
             "**Sentinel candidates**.\n")
    L.append(f"**Summary:** {len(rc)} rule candidate(s) · {len(sc)} sentinel candidate(s) · "
             f"{promo['tracked_total']} tracked · {promo['below_threshold']} still below the "
             f"{PROMOTION_RECUR_THRESHOLD}-turn recurrence gate · {promo['dispositioned']} already "
             f"dispositioned.\n")

    L.append("---\n")
    L.append("## L-1 → L0  ·  Rule candidates (recurring miner patterns)\n")
    if rc:
        L.append("Each has recurred enough turns to be a de-facto convention (or an explicit "
                 "anti-pattern). Promote = author an L-1.5 skill rule and/or an L0 validator that "
                 "locks it, then fix the listed outliers.\n")
        for i, c in enumerate(rc, 1):
            tag = "ANTI-PATTERN" if c["anti_pattern"] else f"convention @ {c['conformance']*100:.1f}%"
            L.append(f"### {i}. `{c['feature']}`  ({c['cluster']})")
            L.append(f"- **key:** `{c['key']}`")
            L.append(f"- **signal:** {tag} · **predicted yield:** {c['predicted_yield']} outlier(s) to "
                     f"fix · recurred {c['seen_turns']} turn(s) (since #{c['first_seen_turn']})")
            if c.get("enforced_hint"):
                L.append(f"- **⚠ possibly already enforced by** `{c['enforced_hint']}` — confirm it isn't "
                         f"a duplicate before promoting")
            if c.get("outliers"):
                L.append("- **outliers:** " + ", ".join("`" + str(o) + "`" for o in c["outliers"]))
            L.append("- [ ] approve → `/harden` (author rule + validator, fix outliers)\n")
    else:
        L.append("_None past the recurrence gate this turn._\n")

    L.append("---\n")
    L.append("## L0 → L2  ·  Sentinel candidates (load-bearing validators lacking a runtime test)\n")
    if sc:
        L.append("Ranked by P1 efficacy (true catches · failure history · open baseline). These static "
                 "validators carry real signal but have no Playwright sentinel asserting the behaviour "
                 "end-to-end. Promote = draft an L2 scenario (paste-ready stub below).\n")
        for i, c in enumerate(sc, 1):
            verif = "" if c.get("coverage_verified") else "  _(coverage unverified — confirm no sentinel exists)_"
            L.append(f"### {i}. `{c['validator']}`{verif}")
            L.append(f"- **key:** `{c['key']}`")
            L.append(f"- **efficacy:** {c['true_catches']} true catch(es) · {c['times_fail']} fail-run(s) · "
                     f"open baseline {c['baseline']} · **score {c['predicted_yield']}**")
            if c.get("label"):
                L.append(f"- **what it checks:** {c['label']}")
            L.append("- **draft sentinel stub:**")
            L.append("  ```ts")
            L.append(f"  test('check_{c['validator']}', async ({{ page }}) => {{")
            L.append(f"    // L0 `{c['validator']}` asserts this statically; confirm it holds at runtime.")
            L.append("    // TODO(sentinel-review): drive the surface this validator guards and assert")
            L.append("    // the user-visible outcome.")
            L.append("  });")
            L.append("  ```")
            L.append("- [ ] approve → `/sentinel-review` (materialize into a tests/*.spec.ts scenario)\n")
    else:
        L.append("_None past the recurrence gate this turn._\n")

    PROMOTION_QUEUE_PATH.write_text("\n".join(L), encoding="utf-8")


# ── Turn runner ────────────────────────────────────────────────────────────

def _run_turn(reset: bool = False) -> dict:
    state = {"turn": 0, "history": [], "snapshots": {}} if reset else _read_state()

    turn = state.get("turn", 0) + 1
    prev_snaps = state.get("snapshots", {})

    curr = {
        "L-1":   _snapshot_L_minus_1(),
        "L-1.5": _snapshot_L_minus_1_5(),
        "L0":    _snapshot_L0(),
        "L2":    _snapshot_L2(),
        "L13":   _snapshot_L13(),
    }

    diff = {
        "L-1_total_proposals":      _scalar_diff(prev_snaps.get("L-1", {}),   curr["L-1"],   "total_proposals"),
        "L-1.5_rules_in_manifest":  _scalar_diff(prev_snaps.get("L-1.5", {}), curr["L-1.5"], "rules_in_manifest"),
        "L0_total_baseline_count":  _scalar_diff(prev_snaps.get("L0", {}),    curr["L0"],    "total_baseline_count"),
        "L0_validators_with_baseline": _scalar_diff(prev_snaps.get("L0", {}), curr["L0"],    "validators_with_baseline"),
        "L2_sentinel_specs":        _scalar_diff(prev_snaps.get("L2", {}),    curr["L2"],    "sentinel_specs"),
        "L13_walkthroughs_stale":   _scalar_diff(prev_snaps.get("L13", {}),   curr["L13"],   "walkthroughs_stale"),
    }
    ratchets, raw_regressions = _diff_L0(prev_snaps.get("L0", {}), curr["L0"])
    # P4 noise quarantine — classify each baseline-increase before scoring; only
    # `real` stays in L0_regressions (what the canonical board's Flywheel-turns
    # gate blocks on). Adoption-floor rises / stale reports / env-down are
    # quarantined with a reason, not scored as rot.
    regressions, regressions_quarantined, env_up = _classify_regressions(raw_regressions)

    # P2 promotion engine — discover + draft + rank, write promotion_queue.md.
    # Best-effort + isolated: a bug here must never break the reporting turn.
    ts = datetime.now().isoformat(timespec="seconds")
    promo_summary = {"rule_candidates": 0, "sentinel_candidates": 0, "tracked_total": 0,
                     "below_threshold": 0, "top_rule": None, "top_sentinel": None}
    try:
        promo = _compute_promotions(curr, state, turn)
        _write_promotion_queue(promo, turn, ts)
        promo_summary = {
            "rule_candidates":    len(promo["rule_candidates"]),
            "sentinel_candidates": len(promo["sentinel_candidates"]),
            "tracked_total":      promo["tracked_total"],
            "below_threshold":    promo["below_threshold"],
            "top_rule":     promo["rule_candidates"][0]["key"] if promo["rule_candidates"] else None,
            "top_sentinel": promo["sentinel_candidates"][0]["key"] if promo["sentinel_candidates"] else None,
        }
    except Exception as e:
        promo_summary["error"] = str(e)

    turn_record = {
        "turn":        turn,
        "ts":          ts,
        "diff":        diff,
        "L0_ratchets": ratchets,
        "L0_regressions": regressions,                       # real only — what gets scored
        "L0_regressions_quarantined": regressions_quarantined,  # noise, classified
        "env_up":      env_up,
        "promotions":  promo_summary,
    }

    state["turn"]     = turn
    state["snapshots"] = curr
    state["history"]  = (state.get("history") or [])[-9:] + [turn_record]
    _write_state(state)
    return turn_record


# ── Reporting ──────────────────────────────────────────────────────────────

def _print_terminal(turn_record: dict) -> None:
    d = turn_record["diff"]
    print()
    print(f"{BOLD}Flywheel Turn #{turn_record['turn']}{RESET}    {turn_record['ts']}")
    print("=" * 64)
    print(f"  {CYAN}L-1{RESET}    cluster proposals:        "
          f"{d['L-1_total_proposals']['from']} → {d['L-1_total_proposals']['to']}  "
          f"({_signed(d['L-1_total_proposals']['delta'])})")
    print(f"  {CYAN}L-1.5{RESET}  skill rules in manifest:  "
          f"{d['L-1.5_rules_in_manifest']['from']} → {d['L-1.5_rules_in_manifest']['to']}  "
          f"({_signed(d['L-1.5_rules_in_manifest']['delta'])})")
    print(f"  {CYAN}L0{RESET}     baselines tracked:         "
          f"{d['L0_validators_with_baseline']['from']} → {d['L0_validators_with_baseline']['to']}  "
          f"({_signed(d['L0_validators_with_baseline']['delta'])})")
    print(f"  {CYAN}L0{RESET}     total locked count:        "
          f"{d['L0_total_baseline_count']['from']} → {d['L0_total_baseline_count']['to']}  "
          f"({_signed(d['L0_total_baseline_count']['delta'], invert=True)})")
    print(f"  {CYAN}L2{RESET}     sentinel parity cases:     "
          f"{d['L2_sentinel_specs']['from']} → {d['L2_sentinel_specs']['to']}  "
          f"({_signed(d['L2_sentinel_specs']['delta'])})")
    print(f"  {CYAN}L13{RESET}    stale walkthroughs:        "
          f"{d['L13_walkthroughs_stale']['from']} → {d['L13_walkthroughs_stale']['to']}  "
          f"({_signed(d['L13_walkthroughs_stale']['delta'], invert=True)})")

    if turn_record["L0_ratchets"]:
        print()
        print(f"{GREEN}{BOLD}  RATCHETS ({len(turn_record['L0_ratchets'])}){RESET} — baselines that tightened this turn:")
        for r in turn_record["L0_ratchets"][:10]:
            print(f"    {GREEN}↓{RESET} {r['validator']:<40s}  {r['from']} → {r['to']}")

    if turn_record["L0_regressions"]:
        print()
        print(f"{RED}{BOLD}  REGRESSIONS ({len(turn_record['L0_regressions'])}){RESET} — real, scored (FIX):")
        for r in turn_record["L0_regressions"][:10]:
            tag = r.get("classification", "real")
            print(f"    {RED}↑{RESET} {r['validator']:<40s}  {r['from']} → {r['to']}  [{tag}]")

    quarantined = turn_record.get("L0_regressions_quarantined") or []
    if quarantined:
        env = turn_record.get("env_up")
        env_note = "" if env is None else f"  (env {'up' if env else 'DOWN'})"
        print()
        print(f"{YELLOW}{BOLD}  QUARANTINED ({len(quarantined)}){RESET} — baseline deltas classified as noise, not scored{env_note}:")
        for r in quarantined[:10]:
            print(f"    {YELLOW}~{RESET} {r['validator']:<34s}  {r['from']} → {r['to']}  [{r.get('classification','?')}]")

    if not turn_record["L0_ratchets"] and not turn_record["L0_regressions"] and not quarantined:
        print()
        print(f"  {YELLOW}No ratchets or regressions this turn — platform is stable.{RESET}")

    promo = turn_record.get("promotions") or {}
    if promo.get("rule_candidates") or promo.get("sentinel_candidates"):
        print()
        print(f"{CYAN}{BOLD}  PROMOTIONS{RESET} — queued for one-pass approval "
              f"({CYAN}promotion_queue.md{RESET}):")
        print(f"    {CYAN}⏫{RESET} {promo.get('rule_candidates', 0)} rule candidate(s) (L-1→L0)  ·  "
              f"{promo.get('sentinel_candidates', 0)} sentinel candidate(s) (L0→L2)   "
              f"[{promo.get('tracked_total', 0)} tracked, {promo.get('below_threshold', 0)} below gate]")
        if promo.get("top_rule"):     print(f"      top rule:     {promo['top_rule']}")
        if promo.get("top_sentinel"): print(f"      top sentinel: {promo['top_sentinel']}")
    elif "promotions" in turn_record:
        print()
        print(f"  {YELLOW}No promotion candidates past the recurrence gate this turn "
              f"({promo.get('below_threshold', 0)} still building recurrence).{RESET}")


def _signed(n: int, invert: bool = False) -> str:
    """Format a delta. invert=True flips arrow direction (for "lower is
    better" stats like baseline_count / stale_walkthroughs)."""
    if n == 0: return "·"
    if invert:
        return f"{GREEN}↓{abs(n)}{RESET}" if n < 0 else f"{RED}↑{n}{RESET}"
    return f"{GREEN}+{n}{RESET}" if n > 0 else f"{RED}{n}{RESET}"


def _write_report_md(turn_record: dict) -> None:
    d = turn_record["diff"]
    lines = []
    lines.append(f"# Flywheel Turn #{turn_record['turn']}\n")
    lines.append(f"_{turn_record['ts']}_\n")
    lines.append("## Layer deltas\n")
    lines.append("| Layer | Metric | Before | After | Delta |")
    lines.append("|---|---|---:|---:|---:|")
    lines.append(f"| L-1   | cluster proposals       | {d['L-1_total_proposals']['from']} | {d['L-1_total_proposals']['to']} | {_md_delta(d['L-1_total_proposals']['delta'])} |")
    lines.append(f"| L-1.5 | rules in manifest       | {d['L-1.5_rules_in_manifest']['from']} | {d['L-1.5_rules_in_manifest']['to']} | {_md_delta(d['L-1.5_rules_in_manifest']['delta'])} |")
    lines.append(f"| L0    | baselines tracked       | {d['L0_validators_with_baseline']['from']} | {d['L0_validators_with_baseline']['to']} | {_md_delta(d['L0_validators_with_baseline']['delta'])} |")
    lines.append(f"| L0    | total locked count      | {d['L0_total_baseline_count']['from']} | {d['L0_total_baseline_count']['to']} | {_md_delta(d['L0_total_baseline_count']['delta'], invert=True)} |")
    lines.append(f"| L2    | sentinel parity cases   | {d['L2_sentinel_specs']['from']} | {d['L2_sentinel_specs']['to']} | {_md_delta(d['L2_sentinel_specs']['delta'])} |")
    lines.append(f"| L13   | stale walkthroughs      | {d['L13_walkthroughs_stale']['from']} | {d['L13_walkthroughs_stale']['to']} | {_md_delta(d['L13_walkthroughs_stale']['delta'], invert=True)} |")
    lines.append("")

    if turn_record["L0_ratchets"]:
        lines.append(f"## ✅ Ratchets ({len(turn_record['L0_ratchets'])}) — baselines tightened\n")
        lines.append("| Validator | Was | Now |")
        lines.append("|---|---:|---:|")
        for r in turn_record["L0_ratchets"]:
            lines.append(f"| `{r['validator']}` | {r['from']} | **{r['to']}** |")
        lines.append("")
    if turn_record["L0_regressions"]:
        lines.append(f"## ❌ Regressions ({len(turn_record['L0_regressions'])}) — real, scored (FIX)\n")
        lines.append("| Validator | Was | Now | Class |")
        lines.append("|---|---:|---:|---|")
        for r in turn_record["L0_regressions"]:
            lines.append(f"| `{r['validator']}` | {r['from']} | **{r['to']}** | {r.get('classification','real')} |")
        lines.append("")
    quarantined = turn_record.get("L0_regressions_quarantined") or []
    if quarantined:
        env = turn_record.get("env_up")
        env_note = "" if env is None else f" (env {'up' if env else 'DOWN'})"
        lines.append(f"## 🟡 Quarantined ({len(quarantined)}) — baseline deltas classified as noise, not scored{env_note}\n")
        lines.append("| Validator | Was | Now | Class | Note |")
        lines.append("|---|---:|---:|---|---|")
        for r in quarantined:
            note = r.get("note") or r.get("error") or ""
            lines.append(f"| `{r['validator']}` | {r['from']} | {r['to']} | **{r.get('classification','?')}** | {note} |")
        lines.append("")
    if not turn_record["L0_ratchets"] and not turn_record["L0_regressions"] and not quarantined:
        lines.append("## No ratchets or regressions this turn — platform stable.\n")

    promo = turn_record.get("promotions")
    if promo is not None:
        lines.append("## ⏫ Promotions — queued for one-pass approval\n")
        lines.append(f"- **{promo.get('rule_candidates', 0)}** rule candidate(s) (L-1→L0) · "
                     f"**{promo.get('sentinel_candidates', 0)}** sentinel candidate(s) (L0→L2)")
        lines.append(f"- {promo.get('tracked_total', 0)} tracked · "
                     f"{promo.get('below_threshold', 0)} still below the recurrence gate")
        if promo.get("top_rule"):     lines.append(f"- top rule: `{promo['top_rule']}`")
        if promo.get("top_sentinel"): lines.append(f"- top sentinel: `{promo['top_sentinel']}`")
        lines.append("- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue "
                     "+ draft stubs.\n")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _md_delta(n: int, invert: bool = False) -> str:
    if n == 0: return "·"
    if invert:
        return f"↓{abs(n)} ✅" if n < 0 else f"↑{n} ❌"
    return f"+{n} ✅" if n > 0 else f"{n} ❌"


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="One turn of the Mega Gate flywheel")
    ap.add_argument("--json",  action="store_true", help="emit JSON instead of pretty")
    ap.add_argument("--reset", action="store_true", help="zero state and start over")
    args = ap.parse_args()

    turn_record = _run_turn(reset=args.reset)
    _write_report_md(turn_record)

    # Retrospection stage (SELF_IMPROVING_GATE_ROADMAP.md P1): fold the latest
    # gate output into the efficacy ledger. Best-effort + fully isolated — this
    # reporting tool stays exit-0, and the gate's verdicts are never touched.
    try:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "tools" / "gate_efficacy_ledger.py"), "update"],
                       timeout=30, capture_output=True)
    except Exception:
        pass

    if args.json:
        print(json.dumps(turn_record, indent=2))
    else:
        _print_terminal(turn_record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
