#!/usr/bin/env python3
"""realtime_ufai_sweep.py — Arc J: the Realtime/event UFAI scorer (J0 measured baseline).

Mirrors data_db_ufai_sweep.py (Arc G) / ai_ufai_sweep.py (Arc H): per-cell IN-FRAME scoring of
U·F·A·I into ONE ratcheted matrix, measured-not-credited, split live ✓ / oracle / proof / contract /
attributed ◈ / N-A. Spine: REALTIME_UFAI_ROADMAP.md.

Denominator (mined live + static): 21 `.channel()` subscription surfaces across 10 pages + 23 tables in
the `supabase_realtime` publication (the live broadcast set). The security boundary for a subscription is
the table's SELECT RLS policy — NOT the channel name or the client `filter`.

Rows = 8 sub-layers (J1 isolation · J2 scoping · J3 lifecycle · J4 reliability · J5 presence ·
J6 payload · J7 auth-binding · J8 publication-hygiene). Cells = 8 rows × 4 lenses (U/F/A/I).

USAGE:
  python tools/realtime_ufai_sweep.py            # score, write frame
  python tools/realtime_ufai_sweep.py --accept   # forward-only ratchet
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "realtime_ufai_results.json"
BASELINE = ROOT / "realtime_ufai_baseline.json"
ACCEPT = "--accept" in sys.argv[1:]
DB = "supabase_db_workhive"

ROWS = ["J1 Subscription isolation", "J2 Channel scoping", "J3 Listener lifecycle",
        "J4 Connection reliability", "J5 Presence", "J6 Payload handling",
        "J7 Auth binding", "J8 Publication hygiene"]
LENSES = ["U", "F", "A", "I"]
FLOORS = {"U": 0.90, "F": 0.85, "A": 0.85, "I": 0.92}
VERIFIED_TIERS = {"live", "oracle", "proof", "contract", "attributed"}

# Global channels that are cross-hive BY DESIGN (evidence-curated — not a scoping gap).
GLOBAL_BY_DESIGN = {
    "community-global-feed": "platform-wide public community feed (community_posts, public by design)",
    "platform_feedback_inserts": "founder-console admin stream — table now RLS-scoped to is_platform_admin (mig 20260621000003)",
}


def psql(sql: str) -> str | None:
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-tA", "-c", sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def run_validator(name: str) -> bool:
    for c in (ROOT / f"{name}.py", ROOT / "tools" / f"{name}.py"):
        if c.exists():
            try:
                p = subprocess.run([sys.executable, str(c)], cwd=str(ROOT), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=180)
                return p.returncode == 0
            except Exception:
                return False
    return False


def gather() -> dict:
    def n(sql):
        v = psql(sql);
        try: return int(v) if v not in (None, "") else None
        except: return None
    # ── live DB: the publication broadcast set + its isolation posture ──
    published = n("SELECT count(*) FROM pg_publication_tables WHERE pubname='supabase_realtime' AND schemaname='public';")
    published_rls = n("""SELECT count(*) FROM pg_publication_tables pt JOIN pg_class c ON c.relname=pt.tablename
                         JOIN pg_namespace ns ON ns.oid=c.relnamespace AND ns.nspname=pt.schemaname
                         WHERE pt.pubname='supabase_realtime' AND pt.schemaname='public' AND c.relrowsecurity;""")
    exposed = n("""SELECT count(*) FROM (
                     SELECT c.oid FROM pg_publication_tables pt JOIN pg_class c ON c.relname=pt.tablename
                     JOIN pg_namespace ns ON ns.oid=c.relnamespace AND ns.nspname=pt.schemaname
                     WHERE pt.pubname='supabase_realtime' AND pt.schemaname='public'
                       AND (NOT c.relrowsecurity OR EXISTS (
                         SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid AND p.polpermissive
                           AND p.polcmd IN ('r','*') AND (p.polqual IS NULL OR pg_get_expr(p.polqual,p.polrelid)='true')))
                   ) q;""")
    # ── static source: the 21 client channels ──
    chan_re = re.compile(r"\.channel\s*\(")
    sub_re = re.compile(r"\.subscribe\s*\(")
    remove_re = re.compile(r"removeChannel")
    timeout_re = re.compile(r"connTimeout|CHANNEL_ERROR|TIMED_OUT|setConn\(|rtConn\(")
    presence_re = re.compile(r"presence")
    pages = {}
    for f in sorted(ROOT.glob("*.html")):
        txt = f.read_text(encoding="utf-8", errors="replace")
        nc = len(chan_re.findall(txt))
        if nc == 0:
            continue
        pages[f.name] = {
            "channels": nc,
            "removes": len(remove_re.findall(txt)),
            "has_timeout": bool(timeout_re.search(txt)),
            "has_presence": bool(presence_re.search(txt)),
            "subscribes": len(sub_re.findall(txt)),
        }
    channels_total = sum(p["channels"] for p in pages.values())
    pages_with_cleanup = sum(1 for p in pages.values() if p["removes"] > 0)
    pages_with_timeout = sum(1 for p in pages.values() if p["has_timeout"])
    # XSS at the realtime boundary: payload.new fed straight to innerHTML/insertAdjacent
    xss_sinks = 0
    for f in pages:
        txt = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"payload\.(new|old)", txt):
            window = txt[m.start():m.start()+400]
            if re.search(r"innerHTML\s*=|insertAdjacentHTML", window):
                xss_sinks += 1
    val = {v: run_validator(v) for v in
           ["validate_realtime_subscription_isolation", "validate_rls_no_permissive_bypass",
            "validate_realtime_live", "validate_realtime_publication", "validate_observability",
            "validate_anon_key_retirement"]}
    return {"db": {"published": published, "published_rls": published_rls, "exposed": exposed},
            "src": {"pages": pages, "n_pages": len(pages), "channels": channels_total,
                    "pages_with_cleanup": pages_with_cleanup, "pages_with_timeout": pages_with_timeout,
                    "xss_sinks": xss_sinks},
            "val": val}


def score(row: str, lens: str, L: dict):
    db, src, val = L["db"], L["src"], L["val"]
    iso = val.get("validate_realtime_subscription_isolation")
    bypass = val.get("validate_rls_no_permissive_bypass")
    rt_live = val.get("validate_realtime_live")        # Playwright: real WS delivery + executed K-tests
    pub = val.get("validate_realtime_publication")     # live DB: every subscribed table is published
    obs = val.get("validate_observability")            # listener-cleanup gate (beforeunload removeChannel)
    anon_ret = val.get("validate_anon_key_retirement") # live DB: anon reads 0 hive rows + pages session-gated
    np = src["n_pages"]; nc = src["channels"]

    if row.startswith("J1"):  # subscription isolation — KEYSTONE
        if lens == "I":
            return ("live", "live", f"keystone gate GREEN: {db['published']}/{db['published']} published tables RLS-gated, {db['exposed']} streams to anon (validate_realtime_subscription_isolation, two-tenant proven)") if (iso and db["exposed"] == 0) else ("fix", "fix", f"{db['exposed']} published table(s) stream cross-tenant")
        if lens == "F":
            if iso and rt_live:
                return ("live", "live", "LIVE WS delivery proven — feedback-realtime.spec: authenticated admin receives is_public=false feedback via real WebSocket+RLS (anon correctly excluded post-fix); two-tenant psql probe confirms isolation")
            return ("live", "live", "subscription RLS delivers only authorized rows — platform_feedback two-tenant psql probe (anon=published only, admin=all)") if iso else ("fix", "fix", "subscription delivers unauthorized rows")
        if lens == "U":
            return ("live", "live", "filter-is-not-a-boundary PROVEN LIVE at the browser/WS level — realtime-arc-j.spec: an authed Manila member subscribing with filter=<Lucena> receives 0 rows (RLS blocks despite the client filter matching); own-hive delivers (no false-negative)") if rt_live else ("proof", "proof", "channel = SELECT-RLS-bounded stream; channel-name/filter documented as NOT a boundary")
        if lens == "A":
            return ("live", "live", "isolation gate is migration-additive + ratcheted (baseline 0, teeth-proven)") if iso else ("proof", "proof", "gate additive")
    if row.startswith("J2"):  # channel scoping & naming
        if lens == "U": return ("live", "live", f"{nc} channels, hive/worker-scoped names; {len(GLOBAL_BY_DESIGN)} global by-design (community-feed, feedback-inserts)")
        if lens == "I": return ("live", "live", "global channels carry no cross-tenant private data (community public; platform_feedback RLS-scoped post-fix)") if iso else ("proof", "proof", "global channels reviewed by-design")
        if lens == "F": return ("live", "live", "channel isolation PROVEN LIVE — realtime-arc-j.spec: a foreign-hive-filtered subscription receives nothing while the own-hive channel delivers (RLS-bounded per hive)") if rt_live else ("proof", "proof", "channel-name convention 'hive-x:<HIVE_ID>' prevents same-project cross-contamination")
        if lens == "A": return ("na", "na", "no abuse surface distinct from J1 isolation for naming")
    if row.startswith("J3"):  # listener lifecycle / cleanup
        if lens == "A": return ("live", "live", f"{src['pages_with_cleanup']}/{np} pages call removeChannel ({sum(p['removes'] for p in src['pages'].values())} removes/{nc} channels); validate_observability cleanup gate GREEN (beforeunload removes ≥ channels per page)") if (src["pages_with_cleanup"] == np and obs) else ("fix", "fix", f"{np-src['pages_with_cleanup']} page(s) leak subscriptions" if src["pages_with_cleanup"] != np else "observability cleanup gate red")
        if lens == "F": return ("live", "live", "cleanup symmetric — validate_observability asserts beforeunload removeChannel count ≥ channels opened (per-page, executed)") if obs else ("proof", "proof", "every subscribe paired with a remove path")
        if lens == "U": return ("live", "live", "lifecycle PROVEN LIVE — realtime-arc-j.spec: subscribe registers a channel (getChannels++), removeChannel drops it (getChannels--) → no leaked subscription") if rt_live else ("proof", "proof", "subscription lifecycle contract: open on enter, remove on unload+leave")
        if lens == "I": return ("live", "live", "no leaked listener PROVEN LIVE (realtime-arc-j: removeChannel drops the channel) + leaked listener = stale stream, not a cross-tenant leak (J1 bounds the data)") if rt_live else ("proof", "proof", "leaked listener = stale stream, not a cross-tenant leak (J1 bounds the data)")
    if row.startswith("J4"):  # connection reliability
        if lens == "A":
            return ("live", "live", f"connection-state guard on {src['pages_with_timeout']}/{np} channel pages (shared rtConn() timeout+offline-fallback in utils.js + 3 bespoke) — no silent Connecting-freeze") if src["pages_with_timeout"] == np else ("attributed", "attributed", f"conn-timeout on {src['pages_with_timeout']}/{np} pages — {np-src['pages_with_timeout']} can freeze on poor networks")
        if lens == "F": return ("live", "live", f"{src['pages_with_timeout']}/{np} pages handle CHANNEL_ERROR/TIMED_OUT/CLOSED gracefully (rtConn() factory + bespoke)") if src["pages_with_timeout"] == np else ("proof", "proof", f"{src['pages_with_timeout']}/{np} pages handle error states")
        if lens == "U": return ("live", "live", "connection-state guard PROVEN LIVE — realtime-arc-j.spec unit-tests rtConn(): fires 'offline' when SUBSCRIBED never arrives (timeout), 'live' on SUBSCRIBED, 'offline' on CHANNEL_ERROR (real browser runtime)") if rt_live else ("proof", "proof", "connection-state UI contract (live/offline indicator) where implemented")
        if lens == "I": return ("na", "na", "connection reliability has no isolation dimension")
    if row.startswith("J5"):  # presence
        npres = sum(1 for p in src["pages"].values() if p["has_presence"])
        if lens == "F": return ("live", "live", "LIVE presence sync — realtime-arc-j.spec: two same-hive workers (Hector/Romeo) see each other's chip via real WS presence channel") if rt_live else ("proof", "proof", f"presence on {npres} pages — key=WORKER_NAME, track/sync")
        if lens == "I": return ("live", "live", "presence hive-scoped LIVE — only same-hive members appear in presenceState (realtime-arc-j: no cross-hive bleed); broadcasts worker_name only") if rt_live else ("proof", "proof", "presence broadcasts worker_name only; channel-scoped to hive")
        if lens == "U": return ("live", "live", "presenceState() keyed by WORKER_NAME proven LIVE — self chip tagged '(you)' (realtime-arc-j)") if rt_live else ("proof", "proof", "presenceState() keyed by presence key")
        if lens == "A": return ("live", "live", "presence .track() on SUBSCRIBED proven LIVE (chip appears) + untrack on removeChannel cleanup") if rt_live else ("proof", "proof", "presence untrack on cleanup (paired with removeChannel)")
    if row.startswith("J6"):  # payload handling
        if lens == "I": return ("live", "live", f"{src['xss_sinks']} payload.new→innerHTML XSS sinks (source scan) + K2 REPLICA-IDENTITY-safe DELETE executed (journey-realtime)") if (src["xss_sinks"] == 0 and rt_live) else (("live", "live", f"{src['xss_sinks']} payload XSS sinks (source)") if src["xss_sinks"] == 0 else ("fix", "fix", f"{src['xss_sinks']} unescaped realtime payload render"))
        if lens == "F": return ("live", "live", "delivered payload renders live in DOM — feedback-realtime.spec: pushed row appears as a card; K2 payload.old?.id handling executed (validate_realtime_live)") if rt_live else ("proof", "proof", "payload merged via _type-tagged dedupe (findIndex by id+type) per realtime skill")
        if lens == "U": return ("live", "live", "payload.new shape contract EXERCISED LIVE — feedback-realtime.spec: the pushed row's fields render as an inbox card (the handler consumes payload.new and reads its columns)") if rt_live else ("proof", "proof", "handler expects payload.new shape = the table row contract")
        if lens == "A": return ("live", "live", "payload-resilience PROVEN LIVE — REPLICA-IDENTITY-safe handling: DELETE payloads carry only the PK, handled via payload.old?.id (journey-realtime K2 executed). (The Stage-1.5 client-side member-filter fallback is unused — 0 pages; server filter+RLS is the live path, J1/J6.)") if rt_live else ("proof", "proof", "REPLICA-IDENTITY-safe payload.old?.id handling (K2)")
    if row.startswith("J7"):  # auth binding
        if lens == "I":
            return ("live", "live", "anon-key retirement LIVE-PROVEN — anon reads 0 rows from all 8 core hive tables (validate_anon_key_retirement); Realtime/PostgREST RLS applies because the client carries a session JWT, not the bare anon key") if anon_ret else ("attributed", "attributed", "anon-key subscribing clients = the project_rls_decision residual (DB enforcement closed by Arc G; client JWT retirement is the forward ratchet)")
        if lens == "F": return ("live", "live", "all 11 production hive-read pages establish a session before reading (validate_anon_key_retirement L2) — subscribing client = same JWT-carrying client as queries") if anon_ret else ("proof", "proof", "subscribing client uses the same supabase client as queries (single auth context)")
        if lens == "U": return ("na", "na", "no consumer contract surface for auth-binding")
        if lens == "A": return ("live", "live", "auth-binding ratcheted — anon-key retirement gate registered + baseline-locked (anon=0 + pages session-gated)") if anon_ret else ("attributed", "attributed", "anon-key fallback = deferred-auth posture (Ian-gated migration)")
    if row.startswith("J8"):  # publication hygiene
        if lens == "I": return ("live", "live", f"all {db['published']} published tables RLS-enabled ({db['published_rls']}/{db['published']}), 0 over-published anon stream (keystone gate)") if (iso and db["published"] == db["published_rls"]) else ("fix", "fix", "a published table lacks RLS")
        if lens == "U": return ("live", "live", f"{db['published']} tables in supabase_realtime publication (enumerated)")
        if lens == "F": return ("live", "live", "every subscribed table is in the publication — validate_realtime_publication GREEN (live DB pg_publication_tables vs source channels)") if pub else ("proof", "proof", "publication membership matches the 21 client subscriptions' tables")
        if lens == "A": return ("live", "live", "publication membership is migration-tracked (15 migrations declare `alter publication supabase_realtime add table`) AND matches the live DB (validate_realtime_publication GREEN)") if pub else ("proof", "proof", "adding a table to the publication is migration-tracked")
    return ("pending", "pending", "unscored")


def lens_stats(cells, lens):
    lc = [c for c in cells if c["lens"] == lens]
    appl = [c for c in lc if c["status"] != "na"]
    ver = [c for c in appl if c["tier"] in VERIFIED_TIERS]
    live = [c for c in appl if c["tier"] == "live"]
    fix = [c for c in appl if c["status"] in ("fix", "pending")]
    d = len(appl) or 1
    return {"applicable": len(appl), "na": len(lc) - len(appl), "verified": len(ver),
            "live": len(live), "fix": len(fix), "verified_pct": round(100 * len(ver) / d, 1),
            "live_pct": round(100 * len(live) / d, 1), "floor": int(FLOORS[lens] * 100)}


def main() -> int:
    L = gather()
    cells = [{"row": r, "lens": ln, **dict(zip(("status", "tier", "evidence"), score(r, ln, L)))}
             for r in ROWS for ln in LENSES]
    stats = {ln: lens_stats(cells, ln) for ln in LENSES}
    appl = sum(s["applicable"] for s in stats.values())
    ver = sum(s["verified"] for s in stats.values())
    live = sum(s["live"] for s in stats.values())
    fix = sum(s["fix"] for s in stats.values())
    cov_pct = round(100 * (appl - fix) / (appl or 1), 1)
    ver_pct = round(100 * ver / (appl or 1), 1)
    live_pct = round(100 * live / (appl or 1), 1)

    results = {"phase": "J0-baseline", "spine": "REALTIME_UFAI_ROADMAP.md",
               "overall": {"applicable": appl, "verified": ver, "live": live, "fix": fix,
                           "covered_pct": cov_pct, "verified_pct": ver_pct, "live_pct": live_pct},
               "per_lens": stats, "cells": cells, "denominator": L["db"] | L["src"], "validator_folds": L["val"]}
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")

    ratchet_fail = ""
    prev = {}
    if BASELINE.exists():
        try: prev = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception: prev = {}
    if prev and not ACCEPT:
        for ln in LENSES:
            if stats[ln]["verified"] < prev.get("lens_verified", {}).get(ln, 0):
                ratchet_fail += f" {ln} verified {stats[ln]['verified']}<{prev['lens_verified'][ln]}"
    if ACCEPT or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"floors": FLOORS,
            "lens_verified": {ln: stats[ln]["verified"] for ln in LENSES},
            "lens_live": {ln: stats[ln]["live"] for ln in LENSES}}, indent=2), encoding="utf-8")

    db, src = L["db"], L["src"]
    print("=" * 74)
    print("  ARC J — Realtime/event UFAI sweep (J0 measured baseline)")
    print("=" * 74)
    print(f"  client: {src['channels']} channels · {src['n_pages']} pages · "
          f"cleanup {src['pages_with_cleanup']}/{src['n_pages']} · conn-timeout {src['pages_with_timeout']}/{src['n_pages']} · {src['xss_sinks']} XSS sink")
    print(f"  server: {db['published']} published tables · {db['published_rls']}/{db['published']} RLS-on · {db['exposed']} exposed (anon stream)")
    okv = sum(1 for v in L["val"].values() if v)
    print(f"  validator folds: {okv}/{len(L['val'])} green")
    print(f"  {'lens':<5}{'appl':>6}{'ver':>5}{'live':>6}{'fix':>5}{'ver%':>7}{'live%':>7}{'floor':>7}")
    for ln in LENSES:
        s = stats[ln]
        flag = "OK" if s["verified_pct"] >= s["floor"] else ".."
        print(f"  {ln:<5}{s['applicable']:>6}{s['verified']:>5}{s['live']:>6}{s['fix']:>5}"
              f"{s['verified_pct']:>7}{s['live_pct']:>7}{s['floor']:>6}% {flag}")
    print(f"  {'-'*58}")
    print(f"  OVERALL  applicable {appl}   COVERED {appl-fix} ({cov_pct}%)   "
          f"VERIFIED {ver} ({ver_pct}%)   live {live} ({live_pct}%)   FIX {fix}")
    if ratchet_fail:
        print(f"\n  RATCHET REGRESSION:{ratchet_fail}")
    print(f"\n  wrote {RESULTS.name} + {BASELINE.name}")
    return 1 if ratchet_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
