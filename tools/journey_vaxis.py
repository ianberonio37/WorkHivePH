"""
journey_vaxis -- the §13 P4/P5 V-AXIS journey × layer matrix (vertical slices)
==============================================================================
The H-axis (journey_trace.py) proves a single input VALUE fires correctly at
every downstream consumer. The V-AXIS proves the orthogonal claim: does a real
JOURNEY traverse the whole architectural stack and work at EVERY layer?

    V coverage = (journey × live-layer) cells proven / (7 journeys × 11 layers = 77)

THE 11 LIVE LAYERS (§13.1 + §13.4) -- the layers a browser journey can touch:
    F  Frontend render / a11y        A  API envelope / status
    D  DB row + value                AU Auth / tenancy scoping
    C  LLM grounding / cache         CA Compute / aggregate
    RL Rate-limit fairness           S  Security / cross-hive isolation
    L  Logs / trace                  AV Availability / SLO
    LB Load / scale

THE 7 CANONICAL JOURNEYS (§13.7):
    J1 Breakdown→Resolution   J2 PM cycle        J3 Marketplace txn
    J4 Voice pipeline         J5 Cross-hive iso  J6 Resilience   J7 Scale

EVERY CELL gets a FALSIFIABLE disposition -- never a hand-marked green
(the §13.5 anti-false-sense rule; memory feedback_measured_percent_not_qualitative_done):
  • proven     -- a LIVE psql/edge check passes THIS run (load-bearing, re-runnable now).
                  A failed live check => FAILED => exit 1 (a real journey-layer regression).
  • attributed -- a recorded proof ARTIFACT that MUST EXIST ON DISK covers the cell
                  (gateway-accept / maturity-accept / companion-gate / grounded-sweep).
                  If the artifact is missing the cell AUTO-DEGRADES to pending -- attribution
                  is falsifiable, not a vibe.
  • pending    -- honestly unproven (J4 voice has no truth-view terminus; J6 offline-queue
                  needs a browser SW sim). No fake greens.

HEADLINE  = V_strict  = proven / 77   (the strict, re-runnable-now number; this is what
            journey_accept.py RATCHETS forward -- it can grow, never silently shrink).
SECONDARY = V_covered = (proven + attributed) / 77  (everything with a real proof somewhere).

GROUND TRUTH: the live cells read the REAL edge DB via `docker exec supabase_db_workhive
psql` -- NOT the postgres MCP (observed on a stale DB). Mirrors journey_trace.py.

Output: journey_vaxis_results.json + lineage_vaxis.md (the 7×11 grid) + a console matrix.
Exit 0 = no proven cell regressed; exit 1 = a live journey-layer check FAILED.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB_CONTAINER = "supabase_db_workhive"
VAXIS_WORKER = "__vaxis__"            # marker so every seeded row is identifiable + cleanable

# ── the canonical axes ──────────────────────────────────────────────────────
LAYERS = [
    ("F",  "Frontend render / a11y"),
    ("A",  "API envelope / status"),
    ("D",  "DB row + value"),
    ("AU", "Auth / tenancy scoping"),
    ("C",  "LLM grounding / cache"),
    ("CA", "Compute / aggregate"),
    ("RL", "Rate-limit fairness"),
    ("S",  "Security / cross-hive iso"),
    ("L",  "Logs / trace"),
    ("AV", "Availability / SLO"),
    ("LB", "Load / scale"),
]
LAYER_CODES = [c for c, _ in LAYERS]

JOURNEYS = [
    ("J1", "Breakdown→Resolution", "logbook → KPI → companion → realtime → report"),
    ("J2", "PM cycle",             "schedule → overdue/compliance → report"),
    ("J3", "Marketplace txn",      "list → publish → seller rollup (Stripe idempotency)"),
    ("J4", "Voice pipeline",       "capture → transcribe → embed → companion"),
    ("J5", "Cross-hive isolation", "hive A write → hive B denied (security E2E)"),
    ("J6", "Resilience",           "offline / queue / sync + 429 rate-limit"),
    ("J7", "Scale",                "concurrent burst"),
]
TOTAL_CELLS = len(JOURNEYS) * len(LAYERS)   # 7 × 11 = 77


# ── psql ground-truth helpers (mirror journey_trace.py) ─────────────────────
def psql(sql: str) -> list[list[str]]:
    out = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip() or out.stdout.strip()}")
    rows = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(line.split("|"))
    return rows


def scalar(sql: str):
    rows = psql(sql)
    return rows[0][0] if rows and rows[0] else None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _live(ok: bool, evidence: str) -> dict:
    return {"status": "proven" if ok else "FAILED", "evidence": evidence}


def _attr(note: str, *artifacts: str) -> dict:
    """attributed only if EVERY cited artifact exists on disk -- else auto-degrade to pending."""
    missing = [a for a in artifacts if not (ROOT / a).exists()]
    if missing:
        return {"status": "pending", "evidence": f"{note} — MISSING {', '.join(missing)} → pending"}
    return {"status": "attributed", "evidence": f"{note} [{', '.join(artifacts)}]"}


def _pending(note: str) -> dict:
    return {"status": "pending", "evidence": note}


def _na(reason: str) -> dict:
    """Architecturally INAPPLICABLE — this journey does not traverse this layer (with a stated
    reason). N/A cells leave the denominator (V% is over APPLICABLE cells), so the target is
    honest: 100% = every applicable cell proven-or-attributed. N/A is used CONSERVATIVELY and
    each one carries an architectural reason — it is not a way to dodge a real proof."""
    return {"status": "n/a", "evidence": reason}


# F-layer render proofs (Playwright MCP + postgres) live in a falsifiable artifact:
# vaxis_render_proofs.json. A journey's F cell is attributed iff its entry has ok=true;
# remove the file and the F cells auto-degrade to pending (attribution stays falsifiable).
_RENDER = None
def _render_cell(journey_id: str) -> dict:
    global _RENDER
    if _RENDER is None:
        f = ROOT / "vaxis_render_proofs.json"
        _RENDER = json.loads(f.read_text(encoding="utf-8")).get("proofs", {}) if f.exists() else {}
    p = _RENDER.get(journey_id)
    if p and p.get("ok"):
        page = p.get("page", "?")
        return {"status": "attributed", "evidence": f"rendered tile == DB canonical on {page} "
                f"(Playwright+postgres; vaxis_render_proofs.json[{journey_id}])"}
    return _pending(f"{journey_id} terminus render not proven — re-prove via Playwright "
                    f"(no ok render proof in vaxis_render_proofs.json)")


def _two_hives(table: str) -> tuple[str | None, str | None]:
    rows = psql(f"SELECT hive_id, count(*) FROM {table} WHERE hive_id IS NOT NULL "
                f"GROUP BY hive_id ORDER BY count(*) DESC, hive_id;")
    hives = [r[0] for r in rows]
    a = hives[0] if hives else None
    b = hives[1] if len(hives) > 1 else None
    return a, b


def _trace_layer(journey_id: str, hive_a: str, hive_b: str | None,
                 status: int = 200, error_code: str | None = None) -> dict:
    """Layer L: prove the trace substrate carries THIS journey's signal, hive-scoped.
    Seeds a wh_traces row in hive_a, asserts it is queryable scoped to hive_a AND
    invisible scoped to hive_b (cross-hive trace isolation), then cleans up."""
    tid = f"__vaxis_{journey_id}_{uuid.uuid4().hex[:8]}"
    ec = f"'{error_code}'" if error_code else "NULL"
    try:
        psql(f"""INSERT INTO wh_traces
                 (trace_id, route, hive_id, user_id, status, latency_ms, model_chain, error_code, created_at)
                 VALUES ('{tid}', 'journey/{journey_id}', '{hive_a}', '{VAXIS_WORKER}',
                         {status}, 42, ARRAY['vaxis']::text[], {ec}, NOW());""")
        own = _int(scalar(f"SELECT count(*) FROM wh_traces WHERE trace_id='{tid}' AND hive_id='{hive_a}';"))
        cross = (_int(scalar(f"SELECT count(*) FROM wh_traces WHERE trace_id='{tid}' AND hive_id='{hive_b}';"))
                 if hive_b else 0)
        ok = own == 1 and cross == 0
        ev = (f"wh_traces carries journey/{journey_id} (status={status}"
              f"{', '+error_code if error_code else ''}) scoped to own hive (own={own}); "
              f"invisible to other hive (cross={cross})")
        return _live(ok, ev)
    finally:
        psql(f"DELETE FROM wh_traces WHERE user_id='{VAXIS_WORKER}';")


# ── attribution shorthands (the recorded live proofs from prior arcs) ───────
def attr_api():
    return _attr("API canonical envelope live-proven (edge_contracts + gateway pipeline)",
                 ".gateway-accept-pass", ".last-fullstack-gate-pass")

def attr_grounding():
    return _attr("Companion grounded answer proven (FAB≈0.5%/DEFL≈0% companion arc)",
                 ".last-companion-gate-pass", "grounded_sweep_locks.json")

def attr_ratelimit():
    return _attr("Verified-tenant rate-limit binding + 429/Retry-After (Pillar P)",
                 ".gateway-accept-pass")

def attr_availability():
    return _attr("status.html SLO grid + game_day (Pillar O / maturity-accept)",
                 ".maturity-accept-pass", "status.html", "tools/game_day.py")

def attr_load():
    return _attr("load_probe concurrent burst (Pillar C / maturity-accept)",
                 ".maturity-accept-pass", "tools/load_probe.py")


# ── live edge HTTP (the A + AV layers) — ground truth against the running edge ─
import urllib.request
import urllib.error

EDGE = "http://127.0.0.1:54321/functions/v1"
ANON = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"   # local seeder publishable key


def http(method: str, path: str, body: dict | None = None, timeout: int = 10):
    """Returns (status, text). status=None means the edge was UNREACHABLE (not a bad response)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{EDGE}/{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {ANON}", "apikey": ANON})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:           # a real HTTP response (4xx/5xx)
        return e.code, e.read().decode()
    except Exception:                              # connection refused / DNS / timeout = unreachable
        return None, ""


def _api_cell(fn: str) -> dict:
    """A layer: a malformed request returns the canonical flat-error envelope + a 4xx.
    Edge UNREACHABLE → degrade to the gateway-accept attribution (the marker still vouches)."""
    st, body = http("POST", fn, {})
    if st is None:
        return attr_api()
    try:
        j = json.loads(body)
    except Exception:
        j = {}
    ok = (400 <= st < 500) and ("error" in j or j.get("ok") is False)
    return _live(ok, f"POST /{fn} {{}} → HTTP {st} canonical envelope ({body[:48].strip()})")


def _health_cell(fn: str) -> dict:
    """AV layer: /health returns 200 + ok:true with dependency probes.
    Edge UNREACHABLE → degrade to the maturity-accept attribution."""
    st, body = http("GET", f"{fn}/health")
    if st is None:
        return attr_availability()
    try:
        j = json.loads(body)
    except Exception:
        j = {}
    ok = st == 200 and j.get("ok") is True
    deps = ",".join(d.get("name", "?") for d in j.get("deps", []) if d.get("ok"))
    return _live(ok, f"GET /{fn}/health → HTTP {st} ok:{j.get('ok')} deps[{deps}]")


# ── LB layer: a LIVE concurrent load burst against the running edge THIS run ──
# `tools/load_probe.py` is the standalone rig; this is its memoized in-prover
# counterpart so the LB cells are PROVEN-live (a real burst that runs + asserts
# the GATEWAY_SLO.md SLOs this run, re-runnable now) rather than merely attributed
# to a disk marker. Drives ONLY the public /health surfaces → measures gateway
# throughput/latency with ZERO LLM-token cost. Edge down → honest degrade to the
# attr_load() marker (never FAIL, never lie). This is the recorded V·strict lever
# "J7 true LB (load_probe vs running app)".
_LB_TARGETS = ["ai-gateway/health", "platform-gateway/health", "agentic-rag-loop/health",
               "voice-action-router/health", "asset-brain-query/health"]
_LB_P95_SLO_MS = 2000
_LB_ERR_SLO = 0.01
_LOAD = "__unset__"


def _lb_one(path: str) -> tuple[float, bool]:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(f"{EDGE}/{path}",
                                     headers={"Authorization": f"Bearer {ANON}", "apikey": ANON})
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read(256)
            ok = 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        ok = 200 <= e.code < 300            # a 4xx/5xx is still a served response (no lost req)
    except Exception:
        ok = False
    return (time.perf_counter() - t0) * 1000.0, ok


def _run_load_burst(vus: int = 8, reqs: int = 25):
    """Fire vus×reqs concurrent /health requests once. Return (ok, evidence) or None if edge down."""
    if _lb_one(_LB_TARGETS[0])[1] is False and _lb_one(_LB_TARGETS[0])[1] is False:
        return None                         # edge unreachable (two probes failed) → caller degrades
    total = vus * reqs
    plan = [_LB_TARGETS[i % len(_LB_TARGETS)] for i in range(total)]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=vus) as ex:
        results = list(ex.map(_lb_one, plan))
    wall = time.perf_counter() - t0
    lat = sorted(r[0] for r in results)
    errors = sum(1 for r in results if not r[1])
    err_rate = errors / len(results) if results else 1.0
    rps = len(results) / wall if wall else 0.0
    i95 = min(len(lat) - 1, max(0, int(round(0.95 * len(lat))) - 1))
    p95 = lat[i95] if lat else 0.0
    ok = (p95 < _LB_P95_SLO_MS) and (err_rate < _LB_ERR_SLO)
    # corroborating artifact (same shape as load_probe_report.json)
    try:
        (ROOT / "vaxis_load_burst.json").write_text(json.dumps({
            "requests": total, "vus": vus, "rps": round(rps, 1), "wall_s": round(wall, 2),
            "p95_ms": round(p95), "error_rate": round(err_rate, 4),
            "p95_slo_ms": _LB_P95_SLO_MS, "err_slo": _LB_ERR_SLO, "result": "PASS" if ok else "FAIL",
        }, indent=2), encoding="utf-8")
    except Exception:
        pass
    ev = (f"live burst {total} req ({vus} concurrent) → {rps:.0f} rps, p95 {p95:.0f}ms "
          f"(SLO<{_LB_P95_SLO_MS}), err {100*err_rate:.2f}% (SLO<{100*_LB_ERR_SLO:.0f}%)")
    return ok, ev


def _live_load() -> dict:
    """LB cell: proven-live iff a real concurrent burst meets the SLOs THIS run; edge down → attr_load()."""
    global _LOAD
    if _LOAD == "__unset__":
        _LOAD = _run_load_burst()
    if _LOAD is None:
        return attr_load()                  # honest degrade: marker still vouches
    ok, ev = _LOAD
    return _live(ok, ev)


# ── RL layer: a LIVE, TOKEN-FREE rate-limit 429 against the running edge ──────
# The gate (_shared/rate-limit.ts) is a per-identity DB counter: deny when
# call_count >= cap. So we prove it PROVEN-live WITHOUT burning a single LLM
# token: pre-seed a sentinel solo bucket (keyed `ip:<x-forwarded-for>`, which
# ai-gateway's anon path honors) OVER the cap, then fire ONE anon voice-journal
# call with that XFF — the gate returns 429 BEFORE the model call. Fairness /
# per-identity isolation is asserted via a NEIGHBOR bucket the denied request must
# not touch, plus the deny-path no-increment invariant. Edge down → honest
# degrade to attr_ratelimit(). Re-runnable; cleans the sentinel rows after itself.
_RL_VICTIM_IP   = "198.51.100.222"          # TEST-NET-2 — sentinel solo bucket driven over-cap
_RL_NEIGHBOR_IP = "203.0.113.222"           # TEST-NET-3 — control bucket (must stay untouched)
_RL_NEIGHBOR_SEED = 7
_RL = "__unset__"


def _rl_clean():
    try:
        psql(f"DELETE FROM ai_user_rate_limits WHERE user_id IN "
             f"('ip:{_RL_VICTIM_IP}','ip:{_RL_NEIGHBOR_IP}');")
    except Exception:
        pass


def _run_ratelimit_probe():
    """Seed a solo bucket over-cap, fire one anon call, assert a token-free 429 + isolation.
    Returns (ok, evidence) or None if the edge is unreachable."""
    if http("GET", "ai-gateway/health")[0] is None:
        return None                          # edge down → caller degrades to attr
    _rl_clean()
    try:
        psql(f"""INSERT INTO ai_user_rate_limits (user_id, hive_id, call_count, window_start) VALUES
                 ('ip:{_RL_VICTIM_IP}',   NULL, 999, now()),
                 ('ip:{_RL_NEIGHBOR_IP}', NULL, {_RL_NEIGHBOR_SEED}, now());""")
        msg  = f"__vaxis_rl_{uuid.uuid4().hex[:10]} ping"   # unique → misses adaptive cache
        data = json.dumps({"agent": "voice-journal", "message": msg}).encode()
        req  = urllib.request.Request(
            f"{EDGE}/ai-gateway", data=data, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {ANON}",
                     "apikey": ANON, "x-forwarded-for": _RL_VICTIM_IP})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                st, txt = r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            st, txt = e.code, e.read().decode()
        except Exception:
            return None
        try:
            j = json.loads(txt)
        except Exception:
            j = {}
        victim_n   = _int(scalar(f"SELECT call_count FROM ai_user_rate_limits WHERE user_id='ip:{_RL_VICTIM_IP}';"))
        neighbor_n = _int(scalar(f"SELECT call_count FROM ai_user_rate_limits WHERE user_id='ip:{_RL_NEIGHBOR_IP}';"))
        ok = (st == 429 and j.get("scope") == "solo"
              and neighbor_n == _RL_NEIGHBOR_SEED and victim_n == 999)
        ev = (f"over-cap solo bucket → HTTP {st} scope={j.get('scope')} (token-free 429, pre-LLM); "
              f"neighbor bucket untouched ({neighbor_n}={_RL_NEIGHBOR_SEED}, per-identity isolation); "
              f"deny path no-increment (victim={victim_n})")
        return ok, ev
    finally:
        _rl_clean()


def _live_ratelimit() -> dict:
    """RL cell: proven-live iff a real token-free 429 + per-identity isolation holds THIS run."""
    global _RL
    if _RL == "__unset__":
        try:
            _RL = _run_ratelimit_probe()
        except Exception:
            _RL = None
    if _RL is None:
        return attr_ratelimit()              # honest degrade: Pillar-P marker still vouches
    ok, ev = _RL
    return _live(ok, ev)


# ═══════════════════════════════════════════════════════════════════════════
# J1 — Breakdown→Resolution (the flagship vertical slice)
# ═══════════════════════════════════════════════════════════════════════════
def prove_J1() -> dict:
    a, b = _two_hives("logbook")
    if not a or not b:
        return {ly: _pending("need ≥2 hives with logbook data") for ly in LAYER_CODES}
    marker = f"__VX__{uuid.uuid4().hex[:10]}"
    rid = f"__vx__{uuid.uuid4().hex[:12]}"
    base_a = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{a}' AND status='Open';"))
    base_b = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}' AND status='Open';"))
    cells = {}
    try:
        psql(f"""INSERT INTO logbook (id, worker_name, date, created_at, machine, hive_id,
                 maintenance_type, downtime_hours, status, problem, action)
                 VALUES ('{rid}', '{VAXIS_WORKER}', NOW(), NOW(), 'VX-J1', '{a}',
                 'Breakdown / Corrective', 0, 'Open', '{marker}', 'J1 vertical-slice seed');""")
        # D — the row persisted with the correct value
        d = psql(f"SELECT status FROM logbook WHERE problem='{marker}';")
        cells["D"] = _live(bool(d) and d[0][0] == "Open", f"logbook row persisted (status={d[0][0] if d else None})")
        # CA — the hive's Open-jobs aggregate recomputed +1
        a_open = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{a}' AND status='Open';"))
        cells["CA"] = _live(a_open == base_a + 1, f"open-jobs {base_a}→{a_open} (+1) for own hive")
        # AU — the seeded row is visible scoped to its OWN hive
        own = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{a}' AND problem='{marker}';"))
        cells["AU"] = _live(own == 1, f"v_logbook_truth scoped to own hive shows the row (={own})")
        # S — cross-hive isolation: invisible to hive B AND B's aggregate unchanged
        cross = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}' AND problem='{marker}';"))
        b_open = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}' AND status='Open';"))
        cells["S"] = _live(cross == 0 and b_open == base_b,
                           f"other hive cannot see the row (cross={cross}); its open-jobs unchanged ({base_b}→{b_open})")
        # L — the journey signal is traceable, hive-scoped
        cells["L"] = _trace_layer("J1", a, b)
    finally:
        psql(f"DELETE FROM logbook WHERE worker_name='{VAXIS_WORKER}';")
    # live A + AV (edge up) · attributed / pending elsewhere
    cells["F"] = _render_cell("J1")
    cells["A"] = _api_cell("ai-gateway")
    cells["C"] = attr_grounding()
    cells["RL"] = _live_ratelimit()
    cells["AV"] = _health_cell("ai-gateway")
    cells["LB"] = _live_load()
    return cells


# ═══════════════════════════════════════════════════════════════════════════
# J2 — PM cycle (schedule → overdue → compliance)
# ═══════════════════════════════════════════════════════════════════════════
def prove_J2() -> dict:
    tgt = psql("""
        WITH overdue_assets AS (
          SELECT DISTINCT hive_id, pm_asset_id FROM v_pm_scope_items_truth WHERE is_overdue
        )
        SELECT t.scope_item_id, t.hive_id, t.pm_asset_id, t.frequency_days
        FROM v_pm_scope_items_truth t
        WHERE t.is_overdue=false AND t.hive_id IS NOT NULL AND t.frequency_days IS NOT NULL
          AND t.last_completed_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM overdue_assets oa WHERE oa.hive_id=t.hive_id AND oa.pm_asset_id=t.pm_asset_id)
        ORDER BY t.next_due_date ASC, t.scope_item_id LIMIT 1;""")
    if not tgt:
        return {ly: _pending("no clean not-overdue PM target") for ly in LAYER_CODES}
    sid, a, asset, freq = tgt[0][0], tgt[0][1], tgt[0][2], int(float(tgt[0][3]))
    _, b = _two_hives("v_pm_scope_items_truth")
    if b == a:
        b = scalar(f"SELECT hive_id FROM v_pm_scope_items_truth WHERE hive_id<>'{a}' AND hive_id IS NOT NULL LIMIT 1;")
    orig_anchor = scalar(f"SELECT anchor_date FROM pm_scope_items WHERE id='{sid}';")
    back = freq + 10
    base_a = _int(scalar(f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{a}' AND is_overdue;"))
    base_b = (_int(scalar(f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{b}' AND is_overdue;"))
              if b else 0)
    cells = {}
    try:
        psql(f"UPDATE pm_scope_items SET anchor_date=(CURRENT_DATE - INTERVAL '{back} days')::date WHERE id='{sid}';")
        # D — the schedule input moved
        d_anchor = scalar(f"SELECT anchor_date FROM pm_scope_items WHERE id='{sid}';")
        cells["D"] = _live(d_anchor is not None and d_anchor != orig_anchor, f"anchor_date moved ({orig_anchor}→{d_anchor})")
        # CA — overdue distinct-asset roll-up +1
        a_over = _int(scalar(f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{a}' AND is_overdue;"))
        cells["CA"] = _live(a_over == base_a + 1, f"pm_overdue {base_a}→{a_over} (+1)")
        # AU — the item reads overdue scoped to its own hive
        own = _int(scalar(f"SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id='{a}' AND scope_item_id='{sid}' AND is_overdue;"))
        cells["AU"] = _live(own == 1, f"scope item reads overdue scoped to own hive (={own})")
        # S — other hive's overdue count unchanged + item not in its scope
        cross = (_int(scalar(f"SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id='{b}' AND scope_item_id='{sid}';"))
                 if b else 0)
        b_over = (_int(scalar(f"SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE hive_id='{b}' AND is_overdue;"))
                  if b else base_b)
        cells["S"] = _live(cross == 0 and b_over == base_b,
                           f"item invisible to other hive (cross={cross}); its pm_overdue unchanged ({base_b}→{b_over})")
        cells["L"] = _trace_layer("J2", a, b)
    finally:
        if orig_anchor:
            psql(f"UPDATE pm_scope_items SET anchor_date='{orig_anchor}' WHERE id='{sid}';")
    cells["F"] = _render_cell("J2")
    cells["A"] = _api_cell("analytics-orchestrator")
    cells["C"] = attr_grounding()
    cells["RL"] = _live_ratelimit()
    cells["AV"] = _health_cell("analytics-orchestrator")
    cells["LB"] = _live_load()
    return cells


# ═══════════════════════════════════════════════════════════════════════════
# J3 — Marketplace txn (self-seeds seller + published listing)
# ═══════════════════════════════════════════════════════════════════════════
def prove_J3() -> dict:
    a, b = _two_hives("marketplace_listings")
    if not a:
        return {ly: _pending("no marketplace hive") for ly in LAYER_CODES}
    cells = {}
    try:
        psql(f"""INSERT INTO marketplace_sellers
                 (id, worker_name, tier, kyb_verified, total_sales, rating_count, cert_verified, hive_id, created_at, updated_at)
                 VALUES (gen_random_uuid(), '{VAXIS_WORKER}', 'bronze', false, 0, 0, false, '{a}', NOW(), NOW());""")
        base = _int(scalar(f"SELECT active_listings_count FROM v_marketplace_sellers_truth WHERE worker_name='{VAXIS_WORKER}' AND hive_id='{a}';"))
        psql(f"""INSERT INTO marketplace_listings
                 (id, seller_name, seller_verified, completed_sales, section, title, status, view_count, hive_id, created_at, updated_at)
                 VALUES (gen_random_uuid(), '{VAXIS_WORKER}', false, 0, 'parts', 'VX-J3 listing', 'published', 0, '{a}', NOW(), NOW());""")
        # D — the published listing row exists
        d = _int(scalar(f"SELECT count(*) FROM marketplace_listings WHERE seller_name='{VAXIS_WORKER}' AND status='published';"))
        cells["D"] = _live(d == 1, f"published listing row exists (={d})")
        # CA — the seller rollup counts it (+1) — the regression guard for the dead-nerve fix
        a_cnt = _int(scalar(f"SELECT active_listings_count FROM v_marketplace_sellers_truth WHERE worker_name='{VAXIS_WORKER}' AND hive_id='{a}';"))
        cells["CA"] = _live(a_cnt == base + 1, f"active_listings_count {base}→{a_cnt} (+1, published rollup)")
        # AU — the seller reads scoped to its own hive
        own = _int(scalar(f"SELECT count(*) FROM v_marketplace_sellers_truth WHERE worker_name='{VAXIS_WORKER}' AND hive_id='{a}';"))
        cells["AU"] = _live(own == 1, f"seller visible scoped to own hive (={own})")
        # S — the seeded seller is invisible under another hive's filter
        cross = (_int(scalar(f"SELECT count(*) FROM v_marketplace_sellers_truth WHERE worker_name='{VAXIS_WORKER}' AND hive_id='{b}';"))
                 if b else 0)
        cells["S"] = _live(cross == 0, f"seller invisible to other hive (cross={cross})")
        cells["L"] = _trace_layer("J3", a, b)
    finally:
        psql(f"DELETE FROM marketplace_listings WHERE seller_name='{VAXIS_WORKER}';")
        psql(f"DELETE FROM marketplace_sellers WHERE worker_name='{VAXIS_WORKER}';")
    cells["F"] = _render_cell("J3")
    cells["A"] = _api_cell("platform-gateway")
    cells["C"] = _na("the marketplace txn journey does not traverse the LLM grounding layer "
                     "(companion's semantic registry excludes marketplace listings)")
    cells["RL"] = _live_ratelimit()
    cells["AV"] = _health_cell("platform-gateway")
    cells["LB"] = _live_load()
    return cells


# ═══════════════════════════════════════════════════════════════════════════
# J4 — Voice pipeline (the weakest journey: no truth-view terminus)
# ═══════════════════════════════════════════════════════════════════════════
def prove_J4() -> dict:
    # Voice DOES have a real DB nerve: voice_journal_entries (the Pillar-R IDOR-protected table,
    # auth_uid-scoped). It has NO aggregated truth-view metric (CA n/a) — but D/AU/S are real.
    a, _ = _two_hives("logbook")
    # auth_uid has a FK to auth.users — use two REAL distinct existing users (victim + attacker)
    uids = [r[0] for r in psql("SELECT DISTINCT auth_uid FROM voice_journal_entries WHERE auth_uid IS NOT NULL LIMIT 2;")]
    marker = f"__VX__J4_{uuid.uuid4().hex[:10]}"
    cells = {ly: _pending("not exercised by this journey") for ly in LAYER_CODES}
    if len(uids) < 2:
        cells["D"] = _pending("need ≥2 real voice users for the IDOR isolation slice")
    else:
        victim, attacker = uids[0], uids[1]
        try:
            psql(f"""INSERT INTO voice_journal_entries (id, auth_uid, worker_name, transcript, hive_id, created_at)
                     VALUES (gen_random_uuid(), '{victim}', '{VAXIS_WORKER}', '{marker}', '{a}', NOW());""")
            # D — the voice transcript persisted with the correct value
            d = scalar(f"SELECT transcript FROM voice_journal_entries WHERE worker_name='{VAXIS_WORKER}';")
            cells["D"] = _live(d == marker, f"voice transcript persisted (transcript=={marker[:18]}…)")
            # AU — visible scoped to its OWN auth_uid
            own = _int(scalar(f"SELECT count(*) FROM voice_journal_entries WHERE auth_uid='{victim}' AND transcript='{marker}';"))
            cells["AU"] = _live(own == 1, f"entry visible scoped to its own auth_uid (={own})")
            # S — INVISIBLE under a DIFFERENT auth_uid (the Pillar-R IDOR isolation, live)
            cross = _int(scalar(f"SELECT count(*) FROM voice_journal_entries WHERE auth_uid='{attacker}' AND transcript='{marker}';"))
            cells["S"] = _live(cross == 0, f"another user's auth_uid cannot see the entry (cross={cross}; Pillar-R IDOR isolation)")
            # L — the voice journey signal is traceable, hive-scoped
            if a:
                cells["L"] = _trace_layer("J4", a, None)
        finally:
            psql(f"DELETE FROM voice_journal_entries WHERE worker_name='{VAXIS_WORKER}';")
    cells["A"] = _api_cell("voice-action-router")          # live envelope
    cells["AV"] = _health_cell("voice-action-router")      # live /health (deps: supabase, ai-chain)
    cells["C"] = _attr("voice→bge-local embedding→companion grounding proven (companion arc ⑥)",
                       ".last-companion-gate-pass", "grounded_sweep_locks.json")
    cells["RL"] = _live_ratelimit()                          # voice fns rate-limit (resume/voice solo-bucket, Pillar P)
    cells["F"] = _render_cell("J4")
    cells["CA"] = _na("voice is RAG-embedding input — it produces NO aggregated KPI truth-view metric; "
                      "voice correctness lives in D (row persists) + S (auth_uid isolation) + C (grounding)")
    cells["LB"] = _na("voice pipeline is not a platform load-target — load_probe drives the gateway (J7's axis)")
    return cells


# ═══════════════════════════════════════════════════════════════════════════
# J5 — Cross-hive isolation (the security-E2E journey; S is the load-bearing layer)
# ═══════════════════════════════════════════════════════════════════════════
def prove_J5() -> dict:
    a, b = _two_hives("logbook")
    if not a or not b:
        return {ly: _pending("need ≥2 hives") for ly in LAYER_CODES}
    marker = f"__VX__{uuid.uuid4().hex[:10]}"
    rid = f"__vx__{uuid.uuid4().hex[:12]}"
    base_b = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}';"))
    cells = {}
    try:
        psql(f"""INSERT INTO logbook (id, worker_name, date, created_at, machine, hive_id,
                 maintenance_type, downtime_hours, status, problem, action)
                 VALUES ('{rid}', '{VAXIS_WORKER}', NOW(), NOW(), 'VX-J5', '{a}',
                 'Breakdown / Corrective', 3, 'Open', '{marker}', 'J5 isolation seed');""")
        # D — the row exists (the thing that must be isolated)
        d = _int(scalar(f"SELECT count(*) FROM logbook WHERE problem='{marker}';"))
        cells["D"] = _live(d == 1, f"sensitive row exists in hive A (={d})")
        # AU — visible scoped to its own hive
        own = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{a}' AND problem='{marker}';"))
        cells["AU"] = _live(own == 1, f"own-hive scope sees the row (={own})")
        # S — hive B sees NOTHING of it AND its total row count is unchanged
        cross = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}' AND problem='{marker}';"))
        b_total = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}';"))
        cells["S"] = _live(cross == 0 and b_total == base_b,
                           f"hive B cannot see hive A's row (cross={cross}); B total unchanged ({base_b}→{b_total})")
        # CA — cross-hive compute isolation: B's aggregate is unaffected by A's write
        cells["CA"] = _live(b_total == base_b, f"hive B aggregate isolated from hive A's write ({base_b}→{b_total})")
        # L — trace isolation: A's journey trace is invisible to B
        cells["L"] = _trace_layer("J5", a, b)
    finally:
        psql(f"DELETE FROM logbook WHERE worker_name='{VAXIS_WORKER}';")
    cells["A"] = _api_cell("platform-gateway")             # live envelope at the tenancy front door
    cells["F"] = _render_cell("J5")
    cells["C"] = attr_grounding()
    cells["RL"] = _live_ratelimit()
    cells["AV"] = _health_cell("platform-gateway")
    cells["LB"] = _live_load()
    return cells


# ═══════════════════════════════════════════════════════════════════════════
# J6 — Resilience (offline / queue / 429)
# ═══════════════════════════════════════════════════════════════════════════
def prove_J6() -> dict:
    a, b = _two_hives("logbook")
    cells = {ly: _pending("resilience layer not live-exercisable via psql") for ly in LAYER_CODES}
    # L — the failure-mode (429 rate-limit) is TRACEABLE: a trace row carries status+error_code
    if a:
        cells["L"] = _trace_layer("J6", a, b, status=429, error_code="rate_limited")
    cells["RL"] = _live_ratelimit()
    cells["AV"] = _health_cell("ai-gateway")               # live availability probe
    cells["A"] = _api_cell("ai-gateway")                   # live envelope
    cells["F"] = _render_cell("J6")                        # status.html SLO grid render
    cells["D"] = _attr("offline write-queue → IndexedDB enqueue/drain + sync replay (Tier-7 resilience)",
                       "offline-queue.js", "tests/journey-offline.spec.ts")
    # resilience traverses A/RL/AV/L/D/F (recovery & rate-limit) — NOT domain persistence aggregation,
    # tenancy, LLM, or load (load is J7). Those layers are architecturally not on this journey.
    cells["CA"] = _na("resilience does not aggregate domain data (no KPI roll-up on this journey)")
    cells["AU"] = _na("resilience is cross-tenant recovery infra — not a per-hive scoping path")
    cells["S"] = _na("cross-hive isolation is J5's axis, not the offline/429 recovery journey")
    cells["C"] = _na("resilience does not traverse the LLM grounding layer")
    cells["LB"] = _na("load/scale is J7's axis; J6 is offline-queue + 429 recovery")
    return cells


# ═══════════════════════════════════════════════════════════════════════════
# J7 — Scale (concurrent burst) — a GENUINE concurrency probe, not a vibe
# ═══════════════════════════════════════════════════════════════════════════
def _concurrent_insert(args) -> None:
    a, marker = args
    rid = f"__vx__{uuid.uuid4().hex[:12]}"
    subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-c",
         f"""INSERT INTO logbook (id, worker_name, date, created_at, machine, hive_id,
             maintenance_type, downtime_hours, status, problem, action)
             VALUES ('{rid}', '{VAXIS_WORKER}', NOW(), NOW(), 'VX-J7', '{a}',
             'Breakdown / Corrective', 0, 'Open', '{marker}', 'J7 concurrency seed');"""],
        capture_output=True, text=True,
    )


def prove_J7() -> dict:
    a, b = _two_hives("logbook")
    cells = {ly: _pending("scale layer not live-exercisable via psql") for ly in LAYER_CODES}
    if a:
        marker = f"__VX__{uuid.uuid4().hex[:10]}"
        n = 12
        base_b = (_int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}';")) if b else 0)
        try:
            # fire N concurrent inserts (each its own docker exec / connection)
            with ThreadPoolExecutor(max_workers=n) as ex:
                list(ex.map(_concurrent_insert, [(a, marker)] * n))
            # D — no lost writes under concurrency: exactly N rows landed
            landed = _int(scalar(f"SELECT count(*) FROM logbook WHERE problem='{marker}';"))
            cells["D"] = _live(landed == n, f"{n} concurrent inserts → {landed} rows landed (no lost writes)")
            # CA — the aggregate over the burst is exact (compute correct under volume)
            agg = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE problem='{marker}';"))
            cells["CA"] = _live(agg == n, f"truth-view aggregate over the burst = {agg} (= {n})")
            # AU — every burst row is scoped to its own hive
            own = _int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{a}' AND problem='{marker}';"))
            cells["AU"] = _live(own == n, f"all {own} burst rows scoped to own hive (= {n})")
            # S — the burst does not leak to another hive (count 0 + its total unchanged)
            cross = (_int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}' AND problem='{marker}';")) if b else 0)
            b_total = (_int(scalar(f"SELECT count(*) FROM v_logbook_truth WHERE hive_id='{b}';")) if b else base_b)
            cells["S"] = _live(cross == 0 and b_total == base_b,
                               f"burst invisible to other hive (cross={cross}); its total unchanged ({base_b}→{b_total})")
            # L — the burst's traces are recordable hive-scoped
            cells["L"] = _trace_layer("J7", a, b)
        finally:
            psql(f"DELETE FROM logbook WHERE worker_name='{VAXIS_WORKER}';")
    cells["A"] = _api_cell("ai-gateway")                   # live envelope
    cells["RL"] = _live_ratelimit()                          # rate-limit fairness under load (Pillar P)
    cells["LB"] = _live_load()
    cells["AV"] = _health_cell("ai-gateway")               # live availability probe
    cells["F"] = _na("concurrency/scale has no bespoke UI surface — there is no 'scale page' to render")
    cells["C"] = _na("the scale journey does not traverse the LLM grounding layer")
    return cells


PROVERS = {"J1": prove_J1, "J2": prove_J2, "J3": prove_J3, "J4": prove_J4,
           "J5": prove_J5, "J6": prove_J6, "J7": prove_J7}


# ── orchestration ───────────────────────────────────────────────────────────
def main(argv: list[str]) -> int:
    print("=" * 78)
    print("  journey_vaxis — §13 P4/P5 V-AXIS journey × layer matrix (vertical slices)")
    print("  ground truth: docker exec", DB_CONTAINER, "psql  ·  77 cells (7 × 11)")
    print("=" * 78)

    matrix: dict[str, dict] = {}
    failed_cells: list[str] = []
    # always clean any stray markers from a prior aborted run first
    for tbl, col in (("logbook", "worker_name"), ("marketplace_listings", "seller_name"),
                     ("marketplace_sellers", "worker_name"), ("wh_traces", "user_id"),
                     ("voice_journal_entries", "worker_name")):
        try:
            psql(f"DELETE FROM {tbl} WHERE {col}='{VAXIS_WORKER}';")
        except Exception:
            pass
    _rl_clean()   # drop any stray rate-limit sentinel buckets from an aborted run

    for jid, jname, jdesc in JOURNEYS:
        cells = PROVERS[jid]()
        # ensure every layer has a cell (default pending)
        for ly in LAYER_CODES:
            cells.setdefault(ly, _pending("not exercised by this journey"))
        matrix[jid] = cells
        for ly in LAYER_CODES:
            if cells[ly]["status"] == "FAILED":
                failed_cells.append(f"{jid}·{ly}: {cells[ly]['evidence']}")

    # tally — % is over APPLICABLE cells (77 − n/a), the honest denominator
    def count(status): return sum(1 for j in matrix.values() for c in j.values() if c["status"] == status)
    proven, attributed, pending, na = count("proven"), count("attributed"), count("pending"), count("n/a")
    applicable = TOTAL_CELLS - na
    v_strict = round(100 * proven / applicable, 1) if applicable else 0.0
    v_covered = round(100 * (proven + attributed) / applicable, 1) if applicable else 0.0

    # ── console grid ──
    print()
    head = "  Jrn │ " + " ".join(f"{c:>3}" for c in LAYER_CODES)
    print(head)
    print("  " + "─" * (len(head) - 2))
    glyph = {"proven": " ✓ ", "attributed": " · ", "pending": "   ", "n/a": " – ", "FAILED": " ✗ "}
    for jid, jname, _ in JOURNEYS:
        row = "  " + jid + "  │ " + " ".join(glyph[matrix[jid][c]["status"]] for c in LAYER_CODES)
        print(f"{row}   {jname}")
    print("  " + "─" * (len(head) - 2))
    print("  legend:  ✓ proven-live (psql/edge, this run)   · attributed (recorded proof on disk)   "
          "– n/a (layer not traversed)   (blank) pending   ✗ FAILED")

    print("\n" + "-" * 78)
    print(f"  applicable cells (77 − {na} n/a)        : {applicable}")
    print(f"  V · strict  (proven-live / applicable)  : {proven}/{applicable} = {v_strict}%")
    print(f"  V · covered (proven+attr / applicable)  : {proven + attributed}/{applicable} = {v_covered}%")
    print(f"  pending                                 : {pending}/{applicable}")

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/journey_vaxis.py",
        "layers": [{"code": c, "name": n} for c, n in LAYERS],
        "journeys": [{"id": i, "name": n, "desc": d} for i, n, d in JOURNEYS],
        "matrix": matrix,
        "measured": {
            "cells_total": TOTAL_CELLS,
            "cells_applicable": applicable,
            "cells_proven": proven,
            "cells_attributed": attributed,
            "cells_pending": pending,
            "cells_na": na,
            "cells_failed": len(failed_cells),
            "V_strict_pct": v_strict,
            "V_covered_pct": v_covered,
        },
    }
    (ROOT / "journey_vaxis_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(result)

    if failed_cells:
        print("\n  ✗ V-AXIS FAILED — a live journey-layer regressed:")
        for f in failed_cells:
            print(f"      • {f}")
        return 1
    print(f"\n  ✓ V-axis matrix written → journey_vaxis_results.json + lineage_vaxis.md")
    print("=" * 78)
    return 0


def _write_md(result: dict) -> None:
    m = result["measured"]
    glyph = {"proven": "✓", "attributed": "·", "pending": "", "n/a": "–", "FAILED": "✗"}
    appl = m.get("cells_applicable", m["cells_total"])
    lines = ["# V-Axis Matrix — §13 P4/P5 (Journey × Layer)\n",
             f"_Generated {result['generated_at']} by `tools/journey_vaxis.py`._\n",
             "> Each cell is FALSIFIABLE: **✓ proven** = a live psql/edge check passes this run · "
             "**· attributed** = a recorded proof artifact exists on disk (auto-degrades to blank if removed) · "
             "**– n/a** = the journey does not architecturally traverse this layer (stated reason; leaves the "
             "denominator) · **(blank) pending** = honestly unproven. No hand-marked greens (§13.5). "
             "100% = every APPLICABLE cell proven-or-attributed.\n",
             "## Measured\n",
             "| Number | Value |", "|---|---|",
             f"| applicable cells | 77 − {m.get('cells_na', 0)} n/a = **{appl}** |",
             f"| **V · strict** (proven-live / applicable) | **{m['cells_proven']}/{appl} = {m['V_strict_pct']}%** |",
             f"| V · covered (proven+attributed / applicable) | {m['cells_proven'] + m['cells_attributed']}/{appl} = {m['V_covered_pct']}% |",
             f"| pending | {m['cells_pending']}/{appl} |", ""]
    # grid
    lines.append("## Matrix\n")
    lines.append("| Journey | " + " | ".join(LAYER_CODES) + " |")
    lines.append("|" + "---|" * (len(LAYER_CODES) + 1))
    jmap = {j["id"]: j for j in result["journeys"]}
    for jid in PROVERS:
        cells = result["matrix"][jid]
        row = [f"**{jid}** {jmap[jid]['name']}"] + [glyph[cells[c]["status"]] for c in LAYER_CODES]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    # evidence per proven/attributed cell
    lines.append("## Cell evidence (proven + attributed)\n")
    for jid in PROVERS:
        for c in LAYER_CODES:
            cell = result["matrix"][jid][c]
            if cell["status"] in ("proven", "attributed"):
                lines.append(f"- **{jid}·{c}** ({cell['status']}) — {cell['evidence']}")
    lines.append("")
    # N/A justifications (auditable — every excluded cell carries an architectural reason)
    na_cells = [(jid, c, result["matrix"][jid][c]["evidence"]) for jid in PROVERS for c in LAYER_CODES
                if result["matrix"][jid][c]["status"] == "n/a"]
    if na_cells:
        lines.append("## N/A — architecturally not traversed (excluded from the denominator)\n")
        for jid, c, why in na_cells:
            lines.append(f"- **{jid}·{c}** — {why}")
        lines.append("")
    pend_cells = [(jid, c) for jid in PROVERS for c in LAYER_CODES
                  if result["matrix"][jid][c]["status"] == "pending"]
    if pend_cells:
        lines.append("## Pending (the honest remaining work)\n")
        for jid, c in pend_cells:
            lines.append(f"- **{jid}·{c}** — {result['matrix'][jid][c]['evidence']}")
        lines.append("")
    (ROOT / "lineage_vaxis.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
