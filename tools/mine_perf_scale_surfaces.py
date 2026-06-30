#!/usr/bin/env python3
"""
L0 — Arc L Performance-&-Scale denominator miner.
=================================================

Mines the *applicable* (surface × performance-lens) cells across the platform
and scores every STATICALLY-MEASURABLE lens NOW (page weight, query
boundedness, edge-fn boot shape, asset render-blocking, SW/cache coverage,
free-tier row-size projection). The LIVE Speed lens (CWV LCP/INP/CLS, edge/calc
p95) is filled by the companion `tools/perf_scale_sweep.mjs`. Together they
write the real baseline matrix that L1–L5 ratchet up.

Spine: PERFORMANCE_SCALE_ROADMAP.md (the 9th arc, S·E·R·B).

The four lenses (PERFORMANCE_SCALE_ROADMAP.md §1):
  S  Speed          — CWV (LCP≤2.5s/INP≤200ms/CLS≤0.1), edge p95≤500ms, calc p95≤1s
  E  Efficiency     — bounded queries, no N+1, page weight ≤ budget, no over-fetch
  R  Resilience     — p95 stable under burst, no pool saturation, degrade-not-error
  B  Budget (free)  — rows/storage/egress/invocations/tokens ≤ free-tier ceiling

Discipline (carried from Arc D, per CLAUDE.md Momentum + the measured-% feedback):
  * The denominator is mined from EVIDENCE (real bytes / real query chains), not
    hardcoded guesses. A surface that genuinely has no target for a lens DROPS
    that lens-cell (anti-false-sense) rather than scoring a free pass or a 0.
  * Every cell carries WHY it is applicable / what was measured, so the
    disposition is auditable.
  * Test / backup / dev-doc pages are dispositioned (kept visible, NOT counted
    in the active CWV denominator) — investing speed work in a *-test page is
    waste, exactly like Arc D's DEPRECATED_PAGES handling.

Run:
  python tools/mine_perf_scale_surfaces.py            # mine + write results + md
  python tools/mine_perf_scale_surfaces.py --check     # mine + print only (no write)
"""
# audit-scope-allow: this is a PERFORMANCE-surface miner (CWV/weight/query-shape of
# ROOT user-facing pages), NOT a column/capture/read consumer-scan. The WorkHive page
# set is flat — every user-facing page is a root *.html — so subdir/_shared HTML are
# not perf surfaces; recursing into them would only add non-user-facing noise to the
# denominator. The feedback_audit_scanner_scope phantom-column rule does not apply.
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "perf_scale_results.json"
RESULTS_MD = ROOT / "perf_scale_results.md"

CHECK_NAMES = ["perf_scale_denominator"]

# ── Budgets (the falsifiable bars; PERFORMANCE_SCALE_ROADMAP.md §1) ─────────────
# Page HTML-doc weight budget. WorkHive pages are single-file (inline JS+CSS), so
# the .html byte size IS the parse/compile weight the browser pays up front. The
# roadmap's own hot-list flags ">250 KB" — we adopt that as the E-weight bar.
PAGE_WEIGHT_BUDGET = 250 * 1024            # 250 KB per HTML doc
EDGE_BOOT_BUDGET = 1                        # ≤1 avoidable top-level sync heavy-op at module load
# Free-tier row-egress projection: an unbounded select('*') that can return the
# whole table is the B (budget) risk — at target scale it streams the full table
# every call. Bounded reads are B-safe.

# ── The user-facing page set (perf matters for REAL users) ──────────────────────
# = Arc D's 37-page denominator (mine_frontend_ufai_surfaces.py PAGES) MINUS
# platform-health.html (retired dev dashboard) = 36 active — the pages a
# worker/supervisor actually loads. Everything else at root (*-test, *.backup,
# architecture/validator-catalog/symbol-gallery dev-docs, platform-health) is mined
# for total weight but DISPOSITIONED out of the active CWV/E denominator.
USER_FACING_PAGES = [
    "index.html", "engineering-design.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "voice-journal.html", "dayplanner.html", "resume.html",
    "asset-hub.html", "alert-hub.html", "analytics.html", "analytics-report.html",
    "shift-brain.html", "predictive.html", "ai-quality.html", "ph-intelligence.html",
    "project-manager.html", "project-report.html", "skillmatrix.html", "achievements.html",
    "audit-log.html", "assistant.html", "hive.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "marketplace-seller-profile.html",
    "marketplace-admin.html", "integrations.html", "plant-connections.html",
    "report-sender.html", "status.html", "founder-console.html",
    "llm-observability.html", "agentic-rag-observability.html",
]
# Dispositioned root pages (kept in the weight total, OUT of the active denominator)
DISPOSITIONED_PAGES = {
    "engineering-design-test.html": "test harness (eng-design QA double) — not a user route",
    "index-native-test.html": "test page", "index-hive-test.html": "test page",
    "index-v3-test.html": "test page", "index.backup.html": "backup snapshot",
    "index.backup2.html": "backup snapshot", "logbook.backup.html": "backup snapshot",
    "architecture.html": "internal dev-doc (not a worker route)",
    "validator-catalog.html": "internal dev-doc", "symbol-gallery.html": "internal dev-doc",
    "platform-health.html": "retired dev dashboard (Arc D DEPRECATED_PAGES)",
}

# ── Query boundedness signals (the E lens on L2) ────────────────────────────────
SELECT_RE = re.compile(r"\.select\s*\(")
FROM_RE = re.compile(r"\.from\s*\(")
# write-RETURN selects (`.insert(x).select('id')`) return only the affected rows —
# bounded by definition, NOT a read; excluded from the read denominator.
WRITE_RE = re.compile(r"\.(?:insert|update|upsert|delete)\s*\(")
# A row-LIMITING clause (caps how many rows return) — the thing that makes a read
# B-safe and pool-safe at scale. PK/unique = `.eq('id'|'uuid'|'slug')` ONLY (a
# non-unique `.eq('user_id'|'hive_id')` is a scope FILTER, not a row cap — verifier
# wxjtoqvu0). `head:true` = count-only (no rows); bare `count:'exact'` (rows returned)
# is NOT a cap (the marketplace-admin whole-table false-pass).
BOUND_RE = re.compile(
    r"\.limit\s*\(|\.single\s*\(|\.maybeSingle\s*\(|\.range\s*\(|"
    r"\.eq\s*\(\s*['\"](?:id|uuid|slug)['\"]|"
    r"head\s*:\s*true"
)
# A scoping FILTER (bounds to a tenant/subset but NOT a hard row cap) — better than
# nothing, but can still return a large set at scale → flagged 'filtered'.
FILTER_RE = re.compile(r"\.eq\s*\(|\.in\s*\(|\.match\s*\(|\.filter\s*\(|\.gte\s*\(|\.lte\s*\(|\.contains\s*\(|\.or\s*\(")
LINE_COMMENT_RE = re.compile(r"^\s*(//|\*|/\*|<!--)")

# ── Render-blocking / heavy client assets (the S+E lens on L5) ──────────────────
# Synchronous (non-defer/async) external <script> in <head> blocks first paint.
SYNC_HEAD_SCRIPT_RE = re.compile(r"<script\b(?![^>]*\b(?:defer|async|type\s*=\s*['\"]module['\"]))[^>]*\bsrc=", re.I)


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _classify_selects(text: str) -> dict:
    """Per-page query-boundedness: classify each SUPABASE READ .select( chain.

    Verifier wxjtoqvu0 hardened this in three ways:
      (1) READ-only: a `.select(` is counted only if a `.from(` precedes it (else it's
          a DOM `element.select()`), AND no write verb sits between the `.from(` and
          the `.select(` (else it's a `.insert(x).select('id')` write-return, bounded
          to written rows — not a read). DOM/write selects are tallied separately.
      (2) OWN-CHAIN window: the forward window is cut at the NEXT `.select(`/`.from(`
          (a sibling in a Promise.all([...]) array) so a sibling's `.limit` can't
          falsely bound this read.
      (3) head:true (count-only) is a cap; bare count:'exact' (rows returned) is NOT.
    """
    bounded = filtered = unbounded = 0
    dom_or_write = 0
    examples = []
    for m in SELECT_RE.finditer(text):
        sp = m.start()
        # (1) backward context — nearest .from( within 400 chars, and no write between
        back = text[max(0, sp - 400): sp]
        froms = list(FROM_RE.finditer(back))
        if not froms:
            dom_or_write += 1          # DOM element.select() — not a supabase read
            continue
        between = back[froms[-1].end():]
        if WRITE_RE.search(between):
            dom_or_write += 1          # .insert/.update/.delete(...).select() write-return
            continue
        # (2) own-chain forward window — cut at next sibling select/from or terminator
        fwd = text[m.end(): m.end() + 600]
        cuts = [len(fwd)]
        for rgx in (SELECT_RE, FROM_RE):
            mm = rgx.search(fwd)
            if mm:
                cuts.append(mm.start())
        mm = re.search(r";|\n\s*(?:await|const|let|var|return|if|for|}\s*\)|\]\s*\))", fwd)
        if mm:
            cuts.append(mm.start())
        chain = text[sp: m.end() + min(cuts)]   # includes .select(...) args + own chain
        if BOUND_RE.search(chain):
            bounded += 1
        elif FILTER_RE.search(chain):
            filtered += 1
            if len(examples) < 3:
                examples.append("FILTERED: " + re.sub(r"\s+", " ", chain[:90]).strip())
        else:
            unbounded += 1
            if len(examples) < 4:
                examples.append("UNBOUNDED: " + re.sub(r"\s+", " ", chain[:90]).strip())
    return {"bounded": bounded, "filtered": filtered, "unbounded": unbounded,
            "dom_or_write": dom_or_write,
            "total": bounded + filtered + unbounded, "examples": examples}


def _scan_assets(text: str) -> dict:
    sync_head = 0
    head = re.search(r"<head\b.*?</head>", text, re.I | re.S)
    if head:
        sync_head = len(SYNC_HEAD_SCRIPT_RE.findall(head.group(0)))
    return {"sync_head_scripts": sync_head,
            "registers_sw": bool(re.search(r"serviceWorker\s*\.\s*register", text))}


def _lens(applicable, status=None, measured=None, why=None, attributed=False):
    c = {"applicable": bool(applicable)}
    if not applicable:
        c["status"] = "n/a"
        if why:
            c["why"] = why
        return c
    c["status"] = status or "pending"
    if measured is not None:
        c["measured"] = measured
    if why:
        c["why"] = why
    if attributed:
        c["attributed"] = True
    return c


def _load_prior():
    """The prior results file, if any. The LIVE probe tools (perf_scale_sweep.mjs,
    perf_l3_calc_latency.py, perf_l3_edge_latency.py) merge their measurements INTO
    this file AFTER the miner runs. A re-mine must read it back so those probes are
    not lost."""
    try:
        return (json.load(open(RESULTS, encoding="utf-8")).get("surfaces") or {})
    except Exception:
        return {}


def _preserve_live(surfaces, prior):
    """Carry forward live-measured cells across a re-mine (handoff NEXT#1).

    The miner emits S (and calc/edge-response E) cells as a `pending` PLACEHOLDER
    that a live probe tool fills in afterward — it cannot measure CWV / p95 / payload
    weight statically. So a re-mine that resets those to `pending` would wipe an
    expensive ~20-min probe sweep. Rule: where the FRESH emission is still `pending`
    AND the prior file holds a real disposition (pass/fix) for the same surface×lens,
    carry the prior cell forward. STATIC cells (emitted directly as pass/fix) are
    never `pending`, so they always refresh from current code — exactly the intent:
    preserve live, refresh static."""
    carried = 0
    for sid, rec in surfaces.items():
        prec = prior.get(sid)
        if not prec:
            continue
        plenses = prec.get("lenses") or {}
        for L, cell in (rec.get("lenses") or {}).items():
            if not cell.get("applicable") or cell.get("status") != "pending":
                continue
            pcell = plenses.get(L)
            if not pcell or not pcell.get("applicable"):
                continue
            if pcell.get("status") in ("pass", "fix"):
                cell["status"] = pcell["status"]
                if "measured" in pcell:
                    cell["measured"] = pcell["measured"]
                if "why" in pcell:
                    cell["why"] = pcell["why"]
                if pcell.get("attributed"):
                    cell["attributed"] = True
                carried += 1
    return carried


def _recount(surfaces):
    """Recompute the per-lens aggregates from the final surfaces (after preservation),
    mirroring add()'s accounting: a 'fix' cell counts toward the denominator but not
    pass/pending."""
    denom = {"S": 0, "E": 0, "R": 0, "B": 0}
    npass = {"S": 0, "E": 0, "R": 0, "B": 0}
    npending = {"S": 0, "E": 0, "R": 0, "B": 0}
    nattrib = {"S": 0, "E": 0, "R": 0, "B": 0}
    for rec in surfaces.values():
        for L in ("S", "E", "R", "B"):
            cell = (rec.get("lenses") or {}).get(L)
            if not cell or not cell.get("applicable"):
                continue
            denom[L] += 1
            st = cell.get("status")
            if st == "pass":
                npass[L] += 1
                if cell.get("attributed"):
                    nattrib[L] += 1
            elif st == "pending":
                npending[L] += 1
    return denom, npass, npending, nattrib


def mine():
    surfaces = {}
    # running per-lens denominators (applicable cells) and pass counts
    denom = {"S": 0, "E": 0, "R": 0, "B": 0}
    npass = {"S": 0, "E": 0, "R": 0, "B": 0}
    npending = {"S": 0, "E": 0, "R": 0, "B": 0}
    nattrib = {"S": 0, "E": 0, "R": 0, "B": 0}

    def add(sid, rec):
        surfaces[sid] = rec
        for L in ("S", "E", "R", "B"):
            cell = rec["lenses"].get(L)
            if not cell or not cell.get("applicable"):
                continue
            denom[L] += 1
            st = cell.get("status")
            if st == "pass":
                npass[L] += 1
                if cell.get("attributed"):
                    nattrib[L] += 1
            elif st == "pending":
                npending[L] += 1

    # ── L1 — frontend pages (S = CWV live · E = HTML weight static) ──────────────
    total_weight = 0
    heavy = []
    for p in sorted(ROOT.glob("*.html")):
        name = p.name
        size = p.stat().st_size
        total_weight += size
        if name not in USER_FACING_PAGES:
            # dispositioned (weight counted in total, out of active denominator)
            surfaces[f"page::{name}"] = {
                "layer": "L1", "type": "page", "bytes": size,
                "dispositioned": DISPOSITIONED_PAGES.get(name, "non-user-facing root page"),
                "lenses": {},
            }
            continue
        if size > PAGE_WEIGHT_BUDGET:
            heavy.append((name, size))
        weight_pass = size <= PAGE_WEIGHT_BUDGET
        assets = _scan_assets(_read(p))
        rec = {
            "layer": "L1", "type": "page", "bytes": size,
            "lenses": {
                # S (CWV) is measured LIVE by perf_scale_sweep.mjs → pending here
                "S": _lens(True, "pending", why="CWV (LCP/INP/CLS) measured live by perf_scale_sweep.mjs"),
                "E": _lens(True, "pass" if weight_pass else "fix",
                           measured=f"{round(size/1024)}KB doc ({'≤' if weight_pass else '>'}{PAGE_WEIGHT_BUDGET//1024}KB budget); sync-head-scripts={assets['sync_head_scripts']}",
                           why="HTML doc weight ≤ budget (single-file app: doc bytes = up-front parse/compile cost)"),
                "R": _lens(False, why="a page is not a concurrency surface (R lives on queries/fns/load)"),
                "B": _lens(False, why="page weight is an E concern; B lives on the data it fetches (L2)"),
            },
        }
        add(f"page::{name}", rec)

    # ── L2 — data queries (E = bounded · R = pool-safe · B = row-egress-safe) ────
    q_tot = {"bounded": 0, "filtered": 0, "unbounded": 0, "dom_or_write": 0, "total": 0}
    for name in USER_FACING_PAGES:
        p = ROOT / name
        if not p.exists():
            continue
        text = _read(p)
        # Page-bundle pairing (Arc L/L1): engineering-design.html's supabase reads moved to
        # the extracted engineering-design.js bundle for a doc-parse-weight win. Pair it for
        # the L2 read-classification (E/R/B lenses) so those reads are still scored — the
        # page is one logical surface. (Page WEIGHT above uses the real 42KB stat, NOT this
        # paired text, so the weight win is preserved; the .js is not an independent L2 surface.)
        if name == "engineering-design.html":
            _bundle = ROOT / "engineering-design.js"
            if _bundle.exists():
                text += "\n" + _read(_bundle)
        # drop full-line comments so commented examples don't inflate the shape
        text = "\n".join(l for l in text.splitlines() if not LINE_COMMENT_RE.match(l))
        q = _classify_selects(text)
        if q["total"] == 0:
            continue
        for k in q_tot:
            if k in q:
                q_tot[k] += q[k]
        # one E/R/B cell per PAGE's query-surface (aggregate). The §1 bar is "every
        # list query BOUNDED (.limit/PK/single)" — a scope FILTER (.eq('worker_name'))
        # is NOT a row cap, so a filtered-only read counts AGAINST E/R/B, not as a pass
        # (verifier wxjtoqvu0: filtered-free-pass leaked against the B95 floor). Pass =
        # fully bounded (no filtered-only AND no unbounded reads). (L2 phase drills per-query.)
        uncapped = q["filtered"] + q["unbounded"]
        bounded_only = uncapped == 0 and q["total"] > 0
        rec = {
            "layer": "L2", "type": "query-surface", "page": name, "queries": q,
            "lenses": {
                "S": _lens(False, why="query latency rolls up into the page's S (CWV) / edge p95"),
                "E": _lens(True, "pass" if bounded_only else "fix",
                           measured=f"{q['bounded']} bounded / {q['filtered']} filtered-only / {q['unbounded']} UNBOUNDED of {q['total']} reads ({q['dom_or_write']} DOM/write-return excluded)",
                           why="every list read row-bounded (.limit/.single/.range/PK or head:true count) — a scope filter is NOT a cap"),
                "R": _lens(True, "pass" if bounded_only else "fix",
                           measured=f"{uncapped} uncapped reads ({q['filtered']} filtered + {q['unbounded']} unbounded) = pool-hold risk under burst",
                           why="bounded reads hold a connection briefly; an uncapped read streams the whole (per-tenant) set → pool risk"),
                "B": _lens(True, "pass" if bounded_only else "fix",
                           measured=f"{uncapped} uncapped-egress reads ({q['unbounded']} whole-table + {q['filtered']} per-tenant-unbounded)",
                           why="an uncapped select = full(-tenant)-table egress every call → free-tier egress burn at scale"),
            },
        }
        add(f"query::{name}", rec)

    # ── L3 — edge functions (E = boot shape static · S/R/B live/attributed) ──────
    fns_dir = ROOT / "supabase" / "functions"
    n_edge = 0
    if fns_dir.exists():
        for fn in sorted(fns_dir.iterdir()):
            if not fn.is_dir() or fn.name.startswith("_"):
                continue
            entry = fn / "index.ts"
            if not entry.exists():
                continue
            n_edge += 1
            src = _read(entry)
            # E: avoidable top-level heavy work at module load (cold-start cost SHAPE,
            # which IS local-provable; the absolute ms is attributed). Heuristic: a
            # top-level (column-0) await or a top-level heavy client/model init.
            top_await = len(re.findall(r"^await\s", src, re.M))
            boot_pass = top_await <= EDGE_BOOT_BUDGET
            rec = {
                "layer": "L3", "type": "edge-fn", "name": fn.name, "bytes": len(src),
                "lenses": {
                    "S": _lens(True, "pending", why="p95 ≤500ms measured live (edge probe) in L3 phase"),
                    "E": _lens(True, "pass" if boot_pass else "fix",
                               measured=f"top-level awaits at module load = {top_await} (≤{EDGE_BOOT_BUDGET})",
                               why="no avoidable sync work at boot (cold-start shape, local-provable)"),
                    "R": _lens(True, "pending", why="429/503 → graceful degrade; attributed to validate_load_resilience in L5"),
                    "B": _lens(True, "pending", why="invocation/egress cost projected vs free-tier in L5"),
                },
            }
            add(f"edge::{fn.name}", rec)

    # ── L4 — python compute calcs (S = p95 live · E = response weight) ──────────
    py_dir = ROOT / "python-api"
    n_calc = 0
    # reliability/ + sensors/ are real wired routes (main.py /reliability/weibull,
    # /reliability/pf-interval, /sensors/zscore) — were silently omitted (verifier
    # wxjtoqvu0). mqtt_subscriber_template.py is a plant-gateway TEMPLATE, not a route.
    NON_ROUTE = {"mqtt_subscriber_template.py"}
    if py_dir.exists():
        for sub in ("calcs", "projects", "analytics", "ml", "diagrams", "reliability", "sensors"):
            d = py_dir / sub
            if not d.exists():
                continue
            for f in sorted(d.glob("*.py")):
                if f.name.startswith("_") or f.name == "__init__.py" or f.name in NON_ROUTE:
                    continue
                n_calc += 1
                rec = {
                    "layer": "L4", "type": "calc", "name": f"{sub}/{f.name}",
                    "lenses": {
                        "S": _lens(True, "pending", why="calc p95 ≤1s measured live (compute-API probe) in L3 phase"),
                        "E": _lens(True, "pending", why="response payload weight measured in L3 phase"),
                        "R": _lens(False, why="stateless calc; concurrency handled at the API/load layer (L7)"),
                        "B": _lens(False, why="compute is CPU not storage/egress; B lives on data layers"),
                    },
                }
                add(f"calc::{sub}/{f.name}", rec)

    # ── L5 — shared client assets (S = render-block/defer · E = weight) ─────────
    # The roadmap scopes L5 (§2/§3: shared JS/CSS + CDN libs) but it was missing from
    # the miner — ~258KB of shared JS + a render-blocking Tailwind CDN went unmeasured
    # (verifier wxjtoqvu0). These load ONCE and cache across pages, so they are a
    # distinct surface from per-page doc weight.
    ASSET_BUDGET = 100 * 1024
    rb_pages = [n for n in USER_FACING_PAGES if (ROOT / n).exists() and _scan_assets(_read(ROOT / n))["sync_head_scripts"] > 0]
    for a in ("utils.js", "companion-launcher.js", "nav-hub.js", "wh-persona.js",
              "qr-scanner.js", "journey_battery.js", "components.css"):
        p = ROOT / a
        if not p.exists():
            continue
        sz = p.stat().st_size
        w_ok = sz <= ASSET_BUDGET
        add(f"asset::{a}", {
            "layer": "L5", "type": "client-asset", "bytes": sz,
            "lenses": {
                "S": _lens(True, "pending", why="defer/async load-position audit (render-block timing) in L4 phase"),
                "E": _lens(True, "pass" if w_ok else "fix",
                           measured=f"{round(sz/1024)}KB ({'<=' if w_ok else '>'}{ASSET_BUDGET//1024}KB shared-asset budget)",
                           why="shared asset weight <= budget (downloaded once, cached across pages)"),
                "R": _lens(False, why="N/A"), "B": _lens(False, why="N/A"),
            },
        })

    # ── L5b — HEAVY page-specific bundles (>250KB) split out of a page doc ────────
    # A page-specific <script src> bundle is the continuation of the L1-hot ">250KB"
    # concern AFTER a doc-weight split: extracting engineering-design.html's 2.14MB
    # inline script to engineering-design.js (defer) drops the DOC to 42KB — a real
    # parse-weight win, credited on the page's E cell — but RELOCATES the bytes; it
    # does NOT eliminate them. Scoring the page pass WITHOUT this cell would re-open
    # verifier wxjtoqvu0 bug #5 (weight vanishing into an unmeasured surface). Only
    # HEAVY bundles (> the 250KB hot bar) get a cell — trivial per-page scripts are
    # not a weight surface and would only dilute the matrix with free passes.
    _shared_emitted = {"utils.js", "companion-launcher.js", "nav-hub.js", "wh-persona.js",
                       "qr-scanner.js", "journey_battery.js", "components.css"}
    _bundle_re = re.compile(r'<script\b[^>]*\bsrc=["\']([^"\']+\.js)["\']', re.I)
    _heavy_bundles = {}
    for name in USER_FACING_PAGES:
        p = ROOT / name
        if not p.exists():
            continue
        for ref in _bundle_re.findall(_read(p)):
            if ref.startswith(("http", "//")):
                continue
            fn = ref.split("/")[-1].split("?")[0]
            if fn in _shared_emitted:
                continue
            bp = ROOT / fn
            if not bp.exists():
                continue
            sz = bp.stat().st_size
            if sz > PAGE_WEIGHT_BUDGET:
                _heavy_bundles.setdefault(fn, (sz, name))
    for fn, (sz, page) in sorted(_heavy_bundles.items()):
        add(f"asset::{fn}", {
            "layer": "L5", "type": "page-bundle", "bytes": sz, "page": page,
            "lenses": {
                "S": _lens(True, "pending", why="defer/render-block load-position audit in L4 (this bundle loads with `defer` → non-render-blocking)"),
                "E": _lens(True, "fix",
                           measured=f"{round(sz/1024)}KB page bundle (>{PAGE_WEIGHT_BUDGET//1024}KB hot bar) — split out of {page} doc; deferred+cacheable but still shipped on first-load",
                           why="a >250KB page bundle is heavy on PH 4G first-load; code-split per-feature / minify / tree-shake (the relocated bytes stay visible, not credited away)"),
                "R": _lens(False, why="N/A"), "B": _lens(False, why="N/A"),
            },
        })

    # the render-blocking Tailwind CDN — ONE shared surface (owns the render-block once,
    # not 16x per page); S=fix while a sync <head> CDN script exists, E=fix (in-browser
    # CDN compiler vs a purged build).
    add("asset::cdn-tailwind", {
        "layer": "L5", "type": "cdn-lib", "detail": "cdn.tailwindcss.com sync <head> script",
        "render_block_pages": len(rb_pages),
        "lenses": {
            "S": _lens(True, "fix" if rb_pages else "pass",
                       measured=f"render-blocking sync <head> script on {len(rb_pages)}/{len(USER_FACING_PAGES)} pages",
                       why="no render-blocking external script in <head> (defer/async, or self-host a purged build)"),
            "E": _lens(True, "fix",
                       measured="full Tailwind runtime compiled in-browser (CDN dev build)",
                       why="ship a purged/built CSS, not the in-browser CDN compiler"),
            "R": _lens(False, why="N/A"), "B": _lens(False, why="N/A"),
        },
    })

    # ── L6 — cache / service-worker coverage (S = cache · R = offline) ──────────
    sw_pages = [n for n in USER_FACING_PAGES if (ROOT / n).exists() and _scan_assets(_read(ROOT / n))["registers_sw"]]
    sw_cell_pass = False  # 1/47 today → coverage gap; L4 phase drives it up
    add("cache::service-worker-coverage", {
        "layer": "L6", "type": "infra", "detail": "SW registration across user-facing pages",
        "measured_pages": sw_pages,
        "lenses": {
            "S": _lens(True, "pass" if sw_cell_pass else "fix",
                       measured=f"SW registered on {len(sw_pages)}/{len(USER_FACING_PAGES)} user-facing pages",
                       why="cache-first SW makes repeat loads instant; target = shared registration"),
            "E": _lens(False, why="caching is an S/R concern, not work-minimization"),
            "R": _lens(True, "pass" if sw_cell_pass else "fix",
                       measured=f"offline resilience on {len(sw_pages)}/{len(USER_FACING_PAGES)} pages",
                       why="SW serves a cached shell when the network drops (degrade-not-blank)"),
            "B": _lens(False, why="N/A"),
        },
    })
    add("cache::immutable-headers", {
        "layer": "L6", "type": "infra", "detail": "immutable cache headers on static assets",
        "lenses": {
            "S": _lens(True, "pending", why="Cache-Control: immutable on hashed assets — measured at L4 (server config)"),
            "E": _lens(False, why="N/A"), "R": _lens(False, why="N/A"), "B": _lens(False, why="N/A"),
        },
    })

    # ── L7 — load / concurrency (R = p95 under burst · B = degrade-not-bill) ─────
    have_load_gate = (ROOT / "validate_load_resilience.py").exists()
    have_pool_gate = (ROOT / "validate_connection_pool_saturation.py").exists()
    add("load::burst-p95", {
        "layer": "L7", "type": "infra", "detail": "p95 stable under k6/curl burst",
        "lenses": {
            "S": _lens(False, why="N/A"), "E": _lens(False, why="N/A"),
            "R": _lens(True, "pending", why=f"k6/curl burst p95 measured in L5 (load_resilience gate {'present' if have_load_gate else 'missing'})"),
            "B": _lens(True, "pending", why="degrade-not-bill verified under burst in L5"),
        },
    })
    add("load::pool-saturation", {
        "layer": "L7", "type": "infra", "detail": "connection-pool saturation guard",
        "lenses": {
            "S": _lens(False, why="N/A"), "E": _lens(False, why="N/A"),
            # the gate EXISTING is not a pass — only a GREEN run is (verifier wxjtoqvu0:
            # presence-based attribution was a latent free-pass). Mark pending; L5 runs
            # the gate under burst and attributes the pass on its exit code.
            "R": _lens(True, "pending",
                       measured=f"validate_connection_pool_saturation.py {'present (not yet run under burst)' if have_pool_gate else 'missing'}",
                       why="pool-saturation pass requires a GREEN gate run under L5 burst, not file presence"),
            "B": _lens(False, why="N/A"),
        },
    })

    # ── L8 — free-tier budget projections (B) ───────────────────────────────────
    for sid, detail in [
        ("budget::db-rows", "Supabase row count vs free-tier ceiling at target scale"),
        ("budget::storage", "Supabase storage (file uploads, embeddings) vs ceiling"),
        ("budget::egress", "DB+storage egress/month vs ceiling (driven by unbounded reads)"),
        ("budget::edge-invocations", "edge-fn invocations/month vs ceiling"),
        ("budget::llm-tokens", "Groq/Gemini RPM/TPM token caps per AI surface"),
    ]:
        add(sid, {
            "layer": "L8", "type": "budget", "detail": detail,
            "lenses": {
                "S": _lens(False, why="N/A"), "E": _lens(False, why="N/A"), "R": _lens(False, why="N/A"),
                "B": _lens(True, "pending", why="projected from local per-request cost × target scale in L5"),
            },
        })

    # ── preserve live probes across re-mines (handoff NEXT#1) ────────────────────
    # The live tools merge CWV / edge-p95 / calc-p95 / payload-weight into the prior
    # results AFTER the miner. Carry those forward so a re-mine (e.g. to refresh a
    # static E cell) does not reset ~20 min of live S/E probes back to `pending`.
    prior = _load_prior()
    carried = _preserve_live(surfaces, prior)
    denom, npass, npending, nattrib = _recount(surfaces)

    # ── aggregate ───────────────────────────────────────────────────────────────
    N = sum(1 for s in surfaces.values() if s.get("lenses") and any(c.get("applicable") for c in s["lenses"].values()))
    lens_pct = {}
    for L in ("S", "E", "R", "B"):
        active = denom[L]  # all applicable cells (pending counts against the target, honestly)
        lens_pct[L] = round(100.0 * npass[L] / active, 1) if active else 0.0

    out = {
        "generated": "L0 — tools/mine_perf_scale_surfaces.py",
        "spine": "PERFORMANCE_SCALE_ROADMAP.md (Arc L · S·E·R·B)",
        "ran": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "budgets": {"page_weight_bytes": PAGE_WEIGHT_BUDGET, "edge_boot_top_awaits": EDGE_BOOT_BUDGET},
        "denominator_surfaces": N,
        "live_cells_preserved": carried,
        "totals": {
            "html_pages_all": sum(1 for s in surfaces.values() if s.get("layer") == "L1"),
            "user_facing_pages": len([n for n in USER_FACING_PAGES if (ROOT / n).exists()]),
            "total_html_weight_bytes": total_weight,
            "total_html_weight_mb": round(total_weight / 1024 / 1024, 2),
            "heavy_pages_over_budget": sorted(heavy, key=lambda x: -x[1]),
            "queries": q_tot,
            "edge_fns": n_edge,
            "python_calcs": n_calc,
            "sw_coverage": f"{len(sw_pages)}/{len(USER_FACING_PAGES)}",
        },
        "lens_denominator": denom,
        "lens_pass": npass,
        "lens_pending": npending,
        "lens_attributed": nattrib,
        "lens_pct": lens_pct,
        "floors": {"S": 90, "E": 85, "R": 85, "B": 95},
        "surfaces": surfaces,
    }
    return out


def write_md(out):
    L = []
    L.append("# Arc L — Performance & Scale coverage tracker (L0 denominator)\n")
    L.append("_Generated by `tools/mine_perf_scale_surfaces.py` · spine `PERFORMANCE_SCALE_ROADMAP.md`._\n")
    t = out["totals"]
    L.append(f"- **Surfaces (denominator)** = **{out['denominator_surfaces']}** applicable (surface × lens) cells.")
    L.append(f"- **HTML weight**: {t['total_html_weight_mb']} MB across {t['html_pages_all']} root pages "
             f"({t['user_facing_pages']} user-facing). **{len(t['heavy_pages_over_budget'])} pages over the "
             f"{out['budgets']['page_weight_bytes']//1024}KB budget.**")
    L.append(f"- **Queries**: {t['queries']['total']} selects → {t['queries']['bounded']} bounded · "
             f"{t['queries']['filtered']} filtered-only · **{t['queries']['unbounded']} UNBOUNDED**.")
    L.append(f"- **Edge fns**: {t['edge_fns']} · **Python calcs**: {t['python_calcs']} · "
             f"**SW coverage**: {t['sw_coverage']}.\n")
    L.append("## Per-lens baseline (measured — `pending` cells count against target, no free pass)\n")
    L.append("| Lens | Applicable | Pass | Pending | Attributed | % now | Floor |")
    L.append("|---|--:|--:|--:|--:|--:|--:|")
    names = {"S": "Speed", "E": "Efficiency", "R": "Resilience", "B": "Budget"}
    for k in ("S", "E", "R", "B"):
        L.append(f"| {k} {names[k]} | {out['lens_denominator'][k]} | {out['lens_pass'][k]} | "
                 f"{out['lens_pending'][k]} | {out['lens_attributed'][k]} | {out['lens_pct'][k]}% | {out['floors'][k]}% |")
    L.append("\n## Heaviest pages over budget\n")
    L.append("| Page | KB |")
    L.append("|---|--:|")
    for name, size in out["totals"]["heavy_pages_over_budget"][:12]:
        L.append(f"| {name} | {round(size/1024)} |")
    RESULTS_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    out = mine()
    t = out["totals"]
    print("=" * 72)
    print("ARC L — L0  Performance-&-Scale denominator (mined from evidence)")
    print("=" * 72)
    print(f"  surfaces (denominator) : {out['denominator_surfaces']}")
    print(f"  live cells preserved   : {out['live_cells_preserved']}  (S/E probes carried forward from prior run)")
    print(f"  HTML weight            : {t['total_html_weight_mb']} MB  ({t['html_pages_all']} root, {t['user_facing_pages']} user-facing)")
    print(f"  pages over {out['budgets']['page_weight_bytes']//1024}KB budget : {len(t['heavy_pages_over_budget'])}")
    for name, size in t["heavy_pages_over_budget"][:6]:
        print(f"      - {name:38s} {round(size/1024):>5d} KB")
    print(f"  queries                : {t['queries']['total']} selects → "
          f"{t['queries']['bounded']} bounded / {t['queries']['filtered']} filtered / {t['queries']['unbounded']} UNBOUNDED")
    print(f"  edge fns / py calcs    : {t['edge_fns']} / {t['python_calcs']}")
    print(f"  SW coverage            : {t['sw_coverage']}")
    print("  per-lens baseline (pass / applicable = %):")
    for k in ("S", "E", "R", "B"):
        print(f"      {k}: {out['lens_pass'][k]:3d}/{out['lens_denominator'][k]:<3d} = {out['lens_pct'][k]:5.1f}%   "
              f"(pending {out['lens_pending'][k]}, floor {out['floors'][k]}%)")

    if "--check" in sys.argv:
        print("\n--check: no files written.")
        return 0
    RESULTS.write_text(json.dumps(out, indent=2), encoding="utf-8")
    write_md(out)
    print(f"\n  -> wrote {RESULTS.name} ({out['denominator_surfaces']} surface cells)")
    print(f"  -> wrote {RESULTS_MD.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
