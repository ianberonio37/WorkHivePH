#!/usr/bin/env python3
"""validate_operator_console_covers_surfaces.py - the one operator console holds every panel it claims (OPC, 2026-10-22).

Ian, 2026-10-14: the founder / admin / developer surfaces were scattered across a retired console, Platform Actions,
two observability pages, the audit log, AI quality, a status page, six Grafana dashboards, GlitchTip and the gate
board. DECIDED: founder-console.html un-retired as the ONE console, Grafana as live numbers in it plus a link per
dashboard. Each OPC row is one panel (tools/operator_console_inventory.py), marked in the console as
data-opc="<surface>::<slug of its title>" (tools/build_console_reads.py opc_marker). This gate holds the console to it:

  K1  every OPC row at locking or locked has a home: its mark is in founder-console.html (a data-opc attribute, or a
      mark string the console stamps at runtime) or is a Grafana panel the generated manifest has the console draw
      (operator-console-panels.js, not folded into another cell). Rows not built yet are counted, not failed.
  K2  the console is un-retired: founder-console.html carries no #wh-retired-overlay element.
  K3  the dashboards' reads are generated and current: tools/build_console_reads.py --check passes against the migration.
  K4  the console reads totals, never rows: none of the retired page's client scans of analytics_events, ai_cost_log,
      v_hive_readiness_truth, v_marketplace_listings_truth or the credit ledger is back, and the rollups are called.
  K5  a read that answers a platform-wide question runs as the platform, for an admin only: every founder_* and
      console_read_* function the console's migrations define is SECURITY DEFINER and asks is_platform_admin() first.
  K6  the old homes send a founder to the console: the retired observability pages link founder-console.html#developer,
      retired Platform Actions and Marketplace Admin link #operations, AI quality and the audit log point an admin to
      the console, and the component gallery's axes point to the console instead of measuring a second copy.
  K7  every delegated queue listener holds its queue: the element operator-actions.js listens on contains the element
      the queue's buttons are drawn into. On Platform Actions the sellers' Verify ID / Verify certs buttons were drawn
      outside the one listener that answers them - pressed, nothing happened, with 13 sellers waiting on KYB.
  K8  the queues run in one copy: operator-actions.js is the current cut of platform-actions.html's script
      (tools/build_operator_actions.py), so a fix made where the queues are written reaches the console.

    python tools/validate_operator_console_covers_surfaces.py              the gate
    python tools/validate_operator_console_covers_surfaces.py --self-test  the console as it was before OPC (BEFORE_BUILD)
                                                                           fails K1/K2/K4/K6; mutants are caught
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_console_reads import opc_marker  # noqa: E402

TRAJ = ROOT / "trajectory_registry.json"
CONSOLE = "founder-console.html"
MANIFEST = "operator-console-panels.js"
READS_MIGRATION = "supabase/migrations/20261022000003_opc_console_reads.sql"
ROLLUP_MIGRATIONS = ("supabase/migrations/20261022000002_opc_console_reads_bounded.sql",
                     "supabase/migrations/20261022000004_opc_developer_reads.sql")
BEFORE_BUILD = "76fe4884"   # the ENH-C commit: the console still retired, its reads still row scans
BANKED = ("locking", "locked")
# the retired console's row scans (W3-AR measured ~77,000 rows a visit behind the overlay)
SCANS = [
    (r"from\('analytics_events'\)[^;]*?\.limit\(50000\)", "the 30-day hive Pareto scanned up to 50,000 page views"),
    (r"from\('ai_cost_log'\)[^;]*?\.limit\(20000\)", "AI cost by provider scanned up to 20,000 cost rows"),
    (r"from\('ai_cost_log'\)[^;]*?\.limit\(5000\)", "AI cost today scanned up to 5,000 cost rows"),
    (r"from\('v_hive_readiness_truth'\)", "the readiness stairs read rows through the admin's own RLS slice"),
    (r"from\('v_marketplace_listings_truth'\)\s*\.select\('id, status, price, seller_name'\)", "the marketplace pulse read every listing"),
    (r"from\('v_service_credit_ledger_truth'\)\s*\.select\('entry_type, amount", "the credit totals read the whole ledger with no limit"),
]
ROLLUPS = ("founder_hive_pareto", "founder_ai_cost", "founder_maturity", "founder_marketplace_pulse", "founder_audit_feed")
ACTIONS = "operator-actions.js"
# the element operator-actions.js delegates clicks on -> the elements its queues draw their buttons into
DELEGATED = {"sec-mkt-mod": ("mkt-listings-content", "mkt-sellers-content"), "sec-svc-topups": ("svc-topups-content",)}
# the pages that send a founder to the console, and where
POINTERS = (("llm-observability.html", "founder-console.html#developer"),
            ("agentic-rag-observability.html", "founder-console.html#developer"),
            ("platform-actions.html", "founder-console.html#operations"),
            ("marketplace-admin.html", "founder-console.html#operations"),
            ("ai-quality.html", "founder-console.html#developer"),
            ("audit-log.html", "founder-console.html#operations"))
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def _ancestor_ids(html: str) -> dict[str, list[str]]:
    """{element id: the ids of the elements around it, outermost first} - the markup's own nesting"""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.out = [], {}

        def handle_starttag(self, tag, attrs):
            i = dict(attrs).get("id")
            if i and i not in self.out:
                self.out[i] = [x for _, x in self.stack if x]
            if tag not in VOID:
                self.stack.append((tag, i))

        def handle_startendtag(self, tag, attrs):
            i = dict(attrs).get("id")
            if i and i not in self.out:
                self.out[i] = [x for _, x in self.stack if x]

        def handle_endtag(self, tag):
            for k in range(len(self.stack) - 1, -1, -1):
                if self.stack[k][0] == tag:
                    del self.stack[k:]
                    break

    p = P()
    p.feed(re.sub(r"<script\b[\s\S]*?</script>", "", html, flags=re.I))   # script bodies hold markup strings
    return p.out


def _read(rel: str, files: dict | None) -> str:
    if files is not None and rel in files:
        return files[rel]
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _rows(traj: list | None = None) -> list[dict]:
    if traj is None:
        traj = json.loads(TRAJ.read_text(encoding="utf-8"))["trajectories"]
    out = []
    for t in traj:
        if not str(t.get("id", "")).startswith("OPC") or t.get("status") == "descoped":
            continue
        o = t.get("opc")
        o = o if isinstance(o, dict) else ast.literal_eval(o)
        out.append({"id": t["id"], "status": t.get("status"), "mark": opc_marker(o["surface"], o["panel"])})
    return out


def _homes(files: dict | None) -> set[str]:
    """every mark the console carries: data-opc attributes and the mark strings its script stamps, plus the Grafana
    panels the manifest has it draw"""
    src = _read(CONSOLE, files)
    marks = set()
    for v in re.findall(r'data-opc="([^"]+)"', src):
        marks.update(x.strip() for x in v.split("|"))
    marks.update(re.findall(r"'((?:[a-z0-9.-]+\.html|grafana:[a-z0-9-]+|glitchtip|board)::[a-z0-9-]+)'", src))
    man = _read(MANIFEST, files)
    if man:
        try:
            dashes = json.loads(man[man.index("=") + 1:].strip().rstrip(";"))
        except ValueError:
            dashes = []
        for d in dashes:
            for p in d.get("panels", []):
                if not p.get("home"):
                    marks.add(p.get("opc", ""))
    return marks


def check(files: dict | None = None, traj: list | None = None, run_k3: bool = True) -> tuple[list[str], dict]:
    issues, stats = [], {}
    rows = _rows(traj)
    homes = _homes(files)
    missing = [r for r in rows if r["mark"] not in homes]
    stats["rows"], stats["homed"] = len(rows), len(rows) - len(missing)
    for r in missing:
        if r["status"] in BANKED:
            issues.append(f"K1 {r['id']} is {r['status']} but the console has no home for it ({r['mark']})")
    src = _read(CONSOLE, files)
    if re.search(r'<div[^>]*\bid="wh-retired-overlay"', src):
        issues.append("K2 founder-console.html is still retired: its #wh-retired-overlay element is back")
    if run_k3:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_console_reads.py"), "--check", READS_MIGRATION],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            issues.append("K3 the console's dashboard reads no longer match the dashboards - regenerate "
                          f"{READS_MIGRATION} (tools/build_console_reads.py --out)")
    for rx, why in SCANS:
        if re.search(rx, src, re.S):
            issues.append(f"K4 {why} - the console reads totals, never rows")
    for fn in ROLLUPS:
        if f"rpc('{fn}'" not in src:
            issues.append(f"K4 the console no longer calls {fn}: its total is worked out somewhere else again")
    for mig in ROLLUP_MIGRATIONS + (READS_MIGRATION,):
        sql = _read(mig, files)
        for m in re.finditer(r"create or replace function public\.((?:founder|console_read)_\w+)\((.*?)\$(?:\$|fn\$)\n(.*?)end \$", sql, re.S):
            head, body = m.group(2), m.group(3)
            if "security definer" not in head:
                issues.append(f"K5 {m.group(1)} ({mig}) is not SECURITY DEFINER: as the admin's own RLS it reads one hive's slice")
            if "is_platform_admin()" not in body:
                issues.append(f"K5 {m.group(1)} ({mig}) does not ask is_platform_admin() first: a platform figure for anyone")
    for page, href in POINTERS:
        if f'href="{href}"' not in _read(page, files):
            issues.append(f"K6 {page} does not send a founder to the console ({href})")
    ds = _read("design-system.html", files)
    if "Centralization axes: measured live" in ds or "founder-console.html#developer" not in ds:
        issues.append("K6 design-system.html measures its own copy of the centralization axes instead of pointing to the console")
    acts = _read(ACTIONS, files)
    nest = _ancestor_ids(src)
    for outer, inners in DELEGATED.items():
        if not re.search(r"getElementById\('" + re.escape(outer) + r"'\)\.addEventListener\('click'", acts):
            issues.append(f"K7 {ACTIONS} no longer delegates on #{outer} - update DELEGATED to the element it listens on")
        for inner in inners:
            if inner not in nest:
                issues.append(f"K7 the console has no #{inner}, where the #{outer} queue draws its buttons")
            elif outer not in nest[inner]:
                issues.append(f"K7 #{inner} is outside #{outer}: its buttons are drawn where the one listener that "
                              f"answers them cannot hear them")
    try:
        from build_operator_actions import build as _cut
        if acts != _cut():
            issues.append(f"K8 {ACTIONS} is not the current cut of platform-actions.html's queues - two copies drift "
                          f"(tools/build_operator_actions.py --out)")
    except SystemExit as e:
        issues.append(f"K8 the cut cannot be made: {e}")
    return issues, stats


def _git(path: str) -> str:
    r = subprocess.run(["git", "show", f"{BEFORE_BUILD}:{path}"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def _sellers_outside(src: str) -> str:
    """the console with the sellers card moved out of the moderation section - the layout that left Platform Actions'
    Verify ID buttons dead"""
    a = src.index('<section class="panel" id="mkt-sellers-card"')
    b = src.index("</section>", a) + len("</section>")
    rest = src[:a] + src[b:]
    at = rest.index('<div class="section" id="sec-mkt-mod"')
    return rest[:at] + src[a:b] + "\n" + rest[at:]


def self_test() -> list[str]:
    fails = []
    clean, _ = check()
    if clean:
        fails.append(f"the clean run is not green: {clean[:2]}")
    before = {p: _git(p) for p in (CONSOLE, "llm-observability.html", "agentic-rag-observability.html", "design-system.html")}
    before[MANIFEST] = ""
    banked = [dict(t, status="locking") for t in json.loads(TRAJ.read_text(encoding="utf-8"))["trajectories"]
              if str(t.get("id", "")).startswith("OPC") and t.get("status") != "descoped"]
    got, _ = check(before, banked, run_k3=False)
    for k in ("K1", "K2", "K4", "K6"):
        if not any(i.startswith(k) for i in got):
            fails.append(f"the console as it was before OPC ({BEFORE_BUILD}) did not fail {k}")
    src = _read(CONSOLE, None)
    mutants = [
        ("a panel's mark removed", {CONSOLE: src.replace('data-opc="founder-console.html::tech-health', 'data-x="founder-console.html::tech-health', 1)},
         "K1", [dict(t, status="locking") for t in json.loads(TRAJ.read_text(encoding="utf-8"))["trajectories"]
                if t.get("id") == "OPC2"]),
        ("the retired overlay back", {CONSOLE: src.replace("<main>", '<div id="wh-retired-overlay" hidden></div>\n<main>', 1)}, "K2", None),
        ("the Pareto row scan back", {CONSOLE: src.replace("db.rpc('founder_hive_pareto', { p_days: 30 })",
            "db.from('analytics_events').select('hive_id').limit(50000)", 1)}, "K4", None),
        ("a rollup as the admin's own RLS", {ROLLUP_MIGRATIONS[0]: _read(ROLLUP_MIGRATIONS[0], None).replace(
            "returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$\ndeclare r jsonb;\nbegin\n  if not public.is_platform_admin()",
            "returns jsonb language plpgsql stable set search_path = public, pg_temp as $$\ndeclare r jsonb;\nbegin\n  if not public.is_platform_admin()", 1)},
         "K5", None),
        ("the Developer link gone", {"llm-observability.html": _read("llm-observability.html", None).replace(
            'href="founder-console.html#developer"', 'href="platform-actions.html"')}, "K6", None),
        ("Platform Actions sending founders back to itself", {"platform-actions.html": _read("platform-actions.html", None).replace(
            'href="founder-console.html#operations"', 'href="platform-actions.html"')}, "K6", None),
        # Platform Actions' own layout: the sellers card after the moderation section closes
        ("the sellers queue drawn outside its listener", {CONSOLE: _sellers_outside(src)}, "K7", None),
        ("a fix made in the console's copy only", {ACTIONS: _read(ACTIONS, None).replace(
            "'You are offline, so nothing was sent.", "'Offline.", 1)}, "K8", None),
    ]
    for name, files, k, traj in mutants:
        got, _ = check(files, traj, run_k3=False)
        if not any(i.startswith(k) for i in got):
            fails.append(f"mutant '{name}' was not caught by {k}")
    print(f"  the console as it was before OPC fails K1/K2/K4/K6; {len(mutants)} mutants")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (the pre-OPC console fails; every mutant is caught; the clean run is green)" if not fails
              else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues, stats = check()
    print(f"Operator console (OPC): {stats['homed']} of {stats['rows']} rows have a home in the console")
    if issues:
        print("FAIL\n  " + "\n  ".join(issues))
        return 1
    print("  PASS - every banked panel has a home, the console is un-retired, its reads are generated, bounded and "
          "admin-only, and the old homes point to it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
