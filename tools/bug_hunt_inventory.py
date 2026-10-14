#!/usr/bin/env python3
"""bug_hunt_inventory.py - the MEASURED population for the BUG-HUNT wave (BRH), 2026-10-14.

Ian, 2026-10-14, after the release that fixed his missing logbook assets and the MCP journey that found WHY the fix
had not reached his phone: *"we have to expand and extend the numbers of our trajectories roadmap to hunt and sort
out bugs, painpoints, gaps, defects or whatever the terminologies, anything that affects my platform ... we use the
same trajectories roadmap, the same flow that we use MCP walk, with open and closed. I will let you decide the
numbers of trajectories first."*

The number is DERIVED, never typed (the BRP rule). Every class below is a defect class met on 2026-10-13/14 in a
real person's hands, generalised to every production page by measuring the real source and the committed
evidence artifacts. A class that cannot be measured seeds no rows. Each site is one CONCRETE place + a mechanism
+ a reproduction that can be made to fail on demand + a fix target + the gate that reddens on revert.

CLASSES (each measurable, each with its own repro recipe):
  D  version skew silenced by a guard       a page calls utils.js functions behind `typeof whX === 'function'`;
                                            with yesterday's utils.js still cached the guard turns a missing fix
                                            into silence (Ian's logbook: no restore, "No assets registered yet")
  E  scope-silent empty state               a page with a hive mode and a personal mode renders "No X yet." without
                                            saying WHICH list is empty, nor offering the other one
  F  stored role trusted without re-check   a page gates supervisor controls on localStorage wh_hive_role and never
                                            re-validates the role against the membership row
  G  stored hive name never reconciled      a page shows localStorage wh_hive_name and never calls whReconcileHiveName,
                                            so a rename on another device never reaches this one
  H  hive restored by reload, not start-up  a page that scopes by the stored hive relies on utils.js whHiveRecovery
                                            (render solo, then reload once) instead of re-seating the hive in its own
                                            start-up before the first read - a visible flash and a double load
  J  a live journey that is not live        live_page_journeys_results.json: a non-external journey with a failing lens
  K  design slop the ratchet still holds    design_detector_baseline.json: a (file :: antipattern) pair with a count
                                            above zero - the committed, print-exempt population, not a raw detector run

THREE MORE, from what Ian pointed out on 2026-10-14 (the same wave, the same rule - measured, never typed):
  L  a control offered to a person the      Ian: "founder/admin pages button should also be visible to only
     page behind it refuses                 founder/admin. not that kind of they are visible to all users then it says
                                            only admin has access to this, because that would be a slop." Every link,
                                            nav entry or search result on a production page or in the shared chrome
                                            that leads to a page whose own start-up refuses some people (isPlatformAdmin;
                                            a "Supervisors only" wall) - shown to people it will refuse unless the
                                            control itself is role-gated
  M  copy that says two contradictory       Ian: "a certain user like 'working as (name of a user).. not signed in..'
     things about who the person is         what is that slop? you are working, but not signed in?" Every production
                                            page and shared component that reads the device-remembered display name -
                                            the only way a page can call someone by name while the session says nobody
                                            is signed in (or tell a signed-in person to sign in)
  N  a file every deployment stores that    Ian: "I am not using these pages ... remove this project completely, this
     the site never serves                  is just add to the Vercel storage allowed" (Deployment Storage 75% of
                                            10 GB). What the LAST PUSHED commit's deployment uploaded (its tree minus
                                            its own .vercelignore, via tools/deploy_payload.py) that no page, script,
                                            stylesheet, manifest or the service worker asks for - one row per kind of
                                            artifact, so each kind is probed on the live origin for its 404

Only PRODUCTION pages seed rows (LX_NON_PRODUCTION, per Ian 2026-09-30). Deterministic: source regexes and committed
JSON only, so the registry validator can replay it on every run.

    python tools/bug_hunt_inventory.py            # the human report
    python tools/bug_hunt_inventory.py --json     # the machine population (what the seeder reads)
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OWNS_SEATING = {"index.html", "hive.html"}          # these pages seat the hive themselves (join/create/switch, the home)
JOURNEYS = ROOT / "live_page_journeys_results.json"
DESIGN_BASELINE = ROOT / "design_detector_baseline.json"

GUARD = re.compile(r"typeof\s+(wh[A-Za-z0-9_]+)\s*(?:===|==)\s*'function'")
DEFINED = re.compile(r"^(?:async\s+)?function\s+(wh[A-Za-z0-9_]+)\s*\(|^\s*window\.(wh[A-Za-z0-9_]+)\s*=", re.M)
DUAL_MODE = re.compile(r"is\('hive_id',\s*null\)|hive_id\.is\.null|!HIVE_ID\b")
EMPTY_STATE = re.compile(r"[>`'\"]\s*(No [a-z][^<`'\"]{3,60}?yet\.?)")
ROLE_READ = re.compile(r"localStorage\.getItem\(\s*'wh_hive_role'\s*\)")
ROLE_REVALIDATES = re.compile(r"from\(\s*'hive_members'\s*\)[^;]{0,300}select\([^)]*role|from\(\s*'v_worker_truth'|"
                              r"get_hive_board_dashboard|validateHiveMembership|validateMembership", re.S)
NAME_READ = re.compile(r"localStorage\.getItem\(\s*'wh_hive_name'\s*\)")
HIVE_READ = re.compile(r"\bwhHiveId\(\)")
OWN_RESTORE = re.compile(r"\bwhEnsureHiveContext\(")

# L - the destination's OWN refusal decides who it shuts out: the platform-admin check, or a supervisors-only wall
ADMIN_GATE = re.compile(r"isPlatformAdmin\(\s*db|verifyPlatformAdmin\(")
SUPERVISOR_GATE = re.compile(r"""data-wh-gate[\"'\s,=]+[\"']?supervisor-only|>\s*Supervisors only\s*<""")
# the shared chrome a person meets on every page: a control in one of these is offered everywhere it loads
CHROME = ("nav-hub.js", "wayfinding.js", "search-overlay.js", "voice-handler.js", "utils.js", "wh-help.js",
          "learn-link.js", "onboarding.js", "companion-launcher.js", "wh-feedback-fab.js", "worker-drawer.js",
          "session-timeout.js", "wh-persona.js", "impact-preview.js", "maturity-gate.js", "wh-patterns.js")
# who a destination refuses, in the cast order the seeder tries (the first whose route the journey-paths gate accepts)
REFUSED_BY = {"supervisor": ["worker", "worker (engineer mode)"], "admin": ["worker", "buyer", "supervisor"],
              "supervisor-or-admin": ["worker", "worker (engineer mode)"]}
REFUSES = {"admin": "everyone but a platform admin", "supervisor": "everyone but the hive supervisor",
           "supervisor-or-admin": "everyone but the hive supervisor or a platform admin"}


def page_gate(text: str) -> str | None:
    """The page's OWN refusal, measured - the one reading the inventory, validate_gated_offers and the catalog renderer
    share. A page that walls everyone but its supervisor AND admits a platform admin (ai-quality, 2026-10-14) is
    'supervisor-or-admin'; isPlatformAdmin alone is 'admin'; a supervisors-only wall alone is 'supervisor'."""
    admin, sup = bool(ADMIN_GATE.search(text)), bool(SUPERVISOR_GATE.search(text))
    if admin and sup:
        return "supervisor-or-admin"
    return "admin" if admin else ("supervisor" if sup else None)
# M - the device-remembered display name, read directly or through the page's cached global
NAME_REMEMBERED = re.compile(r"""localStorage\.getItem\(\s*['"]wh_last_worker['"]\s*\)|\bwhWorker\(\)|\bWORKER_NAME\b""")
NAME_PAINT = re.compile(r"""\.(?:textContent|innerText|innerHTML|value|placeholder)\s*\+?=[^;\n]*\b(?:WORKER_NAME|whWorker\(\)|workerName|_meName|myName|_myName|_name)\b|\$\{[^}]*\b(?:WORKER_NAME|whWorker\(\)|workerName|_meName)\b[^}]*\}""")
# N - one row per KIND of artifact a person would name; an unmapped place becomes its own kind, so a new place shows up
N_KINDS = (
    ("the three founder pages Ian does not use (architecture, validator-catalog, symbol-gallery)", ("(root) *.html",)),
    ("the live-walk evidence banks", ("banks/",)),
    ("registries, baselines and reports at the root", ("(root) *.json",)),
    ("test-run logs", ("test-runs/",)),
    ("screenshots", ("(root) *.png", "(root) *.jpeg", "(root) *.jpg", "hive-baseline/", "test-images/")),
    ("the development toolbox: scripts no page loads", ("tools/", "(root) *.py", "(root) *.js", "(root) *.mjs",
                                                        "(root) *.sh", "(root) *.ps1", "(root) *.bat", "scripts/",
                                                        "sentinels/", "__pycache__/")),
    ("design sources and unused brand images", ("promo_posters/", "brand_assets/")),
    ("documents and notes", ("(root) *.md", "workflows/", "seo_assets/", "persona_corpus/", ".impeccable/")),
    ("database, function and server source", ("supabase/", "(root) *.sql", "python-api/", "docker/", "infra/")),
    ("logs and captured output", ("(root) *.log", "(root) *.jsonl", "(root) *.txt", "(root) *.yml")),
    ("the knowledge substrate and contracts", ("substrate/", "canonical/", "page_bank_anatomy/", "evals/")),
    ("test suites", ("tests/", "(root) *.ts")),
)
N_CONFIG = "configuration, environment templates and run-state files"   # every remaining dotfile / config kind


def _blank_comments(src: str) -> str:
    """Comments out, line numbers kept: a link named in a comment is not a control - and neither is the rule's own map
    (utils.js WH_PAGE_GATES names every refusing page in order to WITHHOLD it)."""
    keep = lambda m: re.sub(r"[^\n]", " ", m.group(0))   # noqa: E731
    src = re.sub(r"var WH_PAGE_GATES = \{.*?\};", keep, src, flags=re.S)
    src = re.sub(r"<!--.*?-->", keep, src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", keep, src, flags=re.S)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", keep, src)


def _kind_of_place(place: str) -> str:
    for label, places in N_KINDS:
        if place in places:
            return label
    if place.startswith("(root) *.") or place in (".github/", ".vscode/"):
        return N_CONFIG
    return place


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _non_production() -> set:
    try:
        from seed_expansion_wave4 import LX_NON_PRODUCTION
        return set(LX_NON_PRODUCTION)
    except Exception:
        return set()


def production_pages() -> list[str]:
    skip = _non_production()
    return sorted(os.path.basename(p) for p in glob.glob(str(ROOT / "*.html"))
                  if not os.path.basename(p).startswith("_") and os.path.basename(p) not in skip)


def _line_of(src: str, pos: int) -> int:
    return src[:pos].count("\n") + 1


def collect(sources: dict | None = None) -> list[dict]:
    """Every measured site, sorted (cls, page, line, key). `sources` lets the self-test pass page text in."""
    pages = production_pages() if sources is None else sorted(sources)
    read = (lambda p: sources[p]) if sources is not None else (lambda p: (ROOT / p).read_text(encoding="utf-8", errors="replace"))
    utils_src = (sources.get("utils.js", "") if sources is not None
                 else (ROOT / "utils.js").read_text(encoding="utf-8", errors="replace"))
    defined = {a or b for a, b in DEFINED.findall(utils_src)}
    sites: list[dict] = []
    # L's destinations: EVERY root page whose own start-up refuses some people (founder pages included - a refusal
    # there is still a door the product offered), measured from the page itself
    every = (sorted(sources) if sources is not None
             else sorted(os.path.basename(p) for p in glob.glob(str(ROOT / "*.html"))))
    gated: dict[str, str] = {}
    for p in every:
        if not p.endswith(".html"):
            continue
        t = read(p) if sources is not None else (ROOT / p).read_text(encoding="utf-8", errors="replace")
        g = page_gate(t)
        if g:
            gated[p] = g
    dest_rx = (re.compile(r"""["'`/](%s)(?:[?#][^"'`]*)?["'`]""" % "|".join(re.escape(d) for d in sorted(gated)))
               if gated else None)

    def offered(src: str, own: str | None) -> list[tuple[int, str]]:
        """(line, destination) for every control in `src` that leads to a gated page - skipping a page's links to
        itself, and links inside a gated page to a page its own audience is admitted to."""
        if not dest_rx:
            return []
        code = _blank_comments(src)
        out = []
        for m in dest_rx.finditer(code):
            d = m.group(1)
            if d == own:
                continue
            if own in gated and (gated[own] == "admin" or gated[own] == gated[d]):
                continue
            out.append((_line_of(code, m.start()), d))
        return out

    for page in pages:
        if not page.endswith(".html"):
            continue
        src = read(page)
        # L - a control offered to a person the page behind it refuses (one row per control)
        for line, d in offered(src, page):
            sites.append({"cls": "L", "page": page, "line": line, "key": f"-> {d}", "personas": REFUSED_BY[gated[d]],
                          "detail": f"a control on {page}:{line} leads to {d}, whose own start-up refuses "
                                    f"{REFUSES[gated[d]]}"})
        # M - the remembered display name, read on this page (one row per page: every identity sentence is checked)
        code = _blank_comments(src)
        nm_read = NAME_REMEMBERED.search(code)
        if nm_read:
            paints = [_line_of(code, m.start()) for m in NAME_PAINT.finditer(code)]
            # the walker must be admitted to the page to read it: an admin on a founder page, a supervisor behind a
            # supervisors-only wall, otherwise the first persona whose route the gate accepts
            sites.append({"cls": "M", "page": page, "line": _line_of(code, nm_read.start()), "key": "remembered name",
                          "personas": ({"admin": ["oversight"], "supervisor": ["supervisor"], "supervisor-or-admin": ["supervisor"]}.get(gated.get(page))
                                       or ["worker", "supervisor", "oversight"]),
                          "detail": f"reads the device-remembered display name (first at :{_line_of(code, nm_read.start())})"
                                    + (f" and paints it at {len(paints)} place(s) in code ({', '.join(map(str, paints[:5]))}"
                                       f"{' ...' if len(paints) > 5 else ''})" if paints else "")
                                    + " - with the session expired, signed out or signed in, no sentence on the page "
                                      "may say the opposite of the session"})
        # D - version skew silenced by typeof guards (one row per page: the heal is per page)
        guards = [(m.group(1), _line_of(src, m.start())) for m in GUARD.finditer(src) if m.group(1) in defined]
        if guards:
            names = sorted({g for g, _ in guards})
            sites.append({"cls": "D", "page": page, "line": guards[0][1], "key": f"{len(guards)} guards",
                          "detail": f"{len(guards)} typeof guards on {len(names)} utils.js functions: "
                                    + ", ".join(names[:6]) + (" ..." if len(names) > 6 else "")})
        # E - scope-silent empty states on a dual-mode page (one row per distinct string)
        if DUAL_MODE.search(src):
            seen = set()
            for m in EMPTY_STATE.finditer(src):
                text = re.sub(r"\s+", " ", m.group(1)).strip()
                if text in seen:
                    continue
                seen.add(text)
                sites.append({"cls": "E", "page": page, "line": _line_of(src, m.start()), "key": text,
                              "detail": f'empty state "{text}" names neither the personal nor the hive list'})
        # F - stored role trusted without re-validation (one row per page)
        rm = ROLE_READ.search(src)
        if rm and not ROLE_REVALIDATES.search(src):
            sites.append({"cls": "F", "page": page, "line": _line_of(src, rm.start()), "key": "wh_hive_role",
                          "detail": "reads wh_hive_role from localStorage and never re-validates it against hive_members"})
        # G - stored hive name never reconciled (one row per page)
        nm = NAME_READ.search(src)
        if nm and "whReconcileHiveName" not in src:
            sites.append({"cls": "G", "page": page, "line": _line_of(src, nm.start()), "key": "wh_hive_name",
                          "detail": "shows wh_hive_name from localStorage and never calls whReconcileHiveName"})
        # H - hive restored by reload instead of in the page's own start-up (one row per page)
        hm = HIVE_READ.search(src)
        if hm and page not in OWNS_SEATING and not OWN_RESTORE.search(src):
            sites.append({"cls": "H", "page": page, "line": _line_of(src, hm.start()), "key": "whHiveRecovery",
                          "detail": "scopes by whHiveId() and relies on utils.js whHiveRecovery (render solo, reload once) "
                                    "instead of whEnsureHiveContext before its first hive-scoped read"})
    # J - journeys that are not live (committed results file)
    if sources is None and JOURNEYS.exists():
        j = json.loads(JOURNEYS.read_text(encoding="utf-8"))
        skip = _non_production()
        for row in j.get("journeys", []):
            if row.get("external") or row.get("live") or row.get("page") in skip:
                continue
            failing = "".join(k for k, v in (row.get("verdict") or {}).items() if v is False)
            sites.append({"cls": "J", "page": row.get("page"), "line": 0, "key": row.get("id"),
                          "persona": row.get("role") or "any",
                          "detail": f"journey {row.get('id')} ({row.get('role')}) fails lens(es) {failing}: {str(row.get('title', ''))[:90]}"})
    # K - design slop pairs the ratchet still holds (committed baseline; print-exempt primaries)
    if sources is None and DESIGN_BASELINE.exists():
        b = json.loads(DESIGN_BASELINE.read_text(encoding="utf-8"))
        skip = _non_production()
        for pair, n in sorted((b.get("counts") or {}).items()):
            if not n or " :: " not in pair:
                continue
            f, anti = pair.split(" :: ", 1)
            if f in skip:
                continue
            page = f if f.endswith(".html") and (ROOT / f).exists() else "index.html"   # shared chrome is met on the home
            sites.append({"cls": "K", "page": page, "line": 0, "key": pair,
                          "detail": f"{n} primary '{anti}' finding(s) in {f} still held by the design-detector ratchet"})
    # L and M in the shared chrome: met on every page that loads it, so the row is met on the home (K's precedent)
    chrome = {c: (sources.get(c, "") if sources is not None
                  else ((ROOT / c).read_text(encoding="utf-8", errors="replace") if (ROOT / c).exists() else ""))
              for c in CHROME if sources is None or c in sources}
    for c, src in chrome.items():
        if not src:
            continue
        for line, d in offered(src, None):
            sites.append({"cls": "L", "page": "index.html", "line": 0, "key": f"{c} -> {d}",
                          "personas": REFUSED_BY[gated[d]],
                          "detail": f"the shared {c} offers {d} ({c}:{line}) on every page it loads, and {d}'s own "
                                    f"start-up refuses {REFUSES[gated[d]]}"})
        if "WHNavTools" in src and "roles" not in _blank_comments(src) and c != "nav-hub.js":
            line = _line_of(src, src.index("WHNavTools"))
            sites.append({"cls": "L", "page": "index.html", "line": 0, "key": f"{c} -> every hub tool",
                          "personas": REFUSED_BY["supervisor"],
                          "detail": f"{c}:{line} searches the hub's whole tool list (window.WHNavTools) with no role "
                                    "check, so a worker's search offers the supervisor-only and admin pages the hub "
                                    "itself keeps out of their mode"})
        code = _blank_comments(src)
        nm_read = NAME_REMEMBERED.search(code)
        if nm_read:
            sites.append({"cls": "M", "page": "index.html", "line": 0, "key": f"{c} remembered name",
                          "personas": ["worker", "supervisor", "oversight"],
                          "detail": f"the shared {c} reads the device-remembered display name ({c}:"
                                    f"{_line_of(code, nm_read.start())}) on every page it loads"})
    # N - what the last pushed deployment stored that the site never serves, by kind (the git matcher, one place)
    if sources is None:
        try:
            from deploy_payload import dead_weight_at
            import subprocess
            ref = "origin/master"
            if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=ROOT, capture_output=True).returncode:
                ref = "HEAD"
            sha = subprocess.run(["git", "rev-parse", "--short", ref], cwd=ROOT, capture_output=True,
                                 text=True).stdout.strip()
            kinds: dict[str, list[dict]] = {}
            for g in dead_weight_at(ref):
                kinds.setdefault(_kind_of_place(g["place"]), []).append(g)
            for kind, gs in kinds.items():
                files, size = sum(g["files"] for g in gs), sum(g["bytes"] for g in gs)
                biggest = max(gs, key=lambda g: g["bytes"])["largest"]
                sites.append({"cls": "N", "page": "index.html", "line": 0, "key": kind, "persona": "oversight",
                              "detail": f"{files} file(s), {size / 1e6:.2f} MB that the deployment built from {ref} "
                                        f"({sha}) stored and production serves on request, while no page, script, "
                                        f"stylesheet, manifest or the service worker asks for them - "
                                        f"{', '.join(g['place'] for g in gs[:8])}{' ...' if len(gs) > 8 else ''}; "
                                        f"probe: https://workhiveph.com/{biggest}"})
        except Exception as e:   # no git, or no deploy tool: N seeds nothing rather than a guess
            print(f"  bug-hunt N: not measured ({e})", file=sys.stderr)
    sites.sort(key=lambda s: (s["cls"], s["page"], s["line"], s["key"]))
    return sites


def self_test() -> int:
    utils = "function whEnsureHiveContext(db){}\nfunction whHiveId(){}\nfunction whReconcileHiveName(db){}\n"
    pages = {
        "utils.js": utils,
        "skew.html": "<script>if (typeof whHiveId === 'function') {} if (typeof whNotDefined === 'function') {}</script>",
        "dual.html": "<script>let HIVE_ID = whHiveId(); if (!HIVE_ID) {} x.innerHTML = `<p>No parts yet.</p><p>No parts yet.</p>`; y = 'No jobs yet'</script>",
        "role.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role');</script>",
        "role_ok.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role'); await validateHiveMembership();</script>",
        "name.html": "<script>const HIVE_NAME = localStorage.getItem('wh_hive_name');</script>",
        "name_ok.html": "<script>const HIVE_NAME = localStorage.getItem('wh_hive_name'); whReconcileHiveName(db);</script>",
        "reload.html": "<script>let HIVE_ID = whHiveId();</script>",
        "own.html": "<script>let HIVE_ID = whHiveId(); await whEnsureHiveContext(db);</script>",
        "audit.html": "<h2>Supervisors only</h2>",
        "admin.html": "<script>if (!(await isPlatformAdmin(db))) {}</script><a href='audit.html'>x</a>",
        "links.html": "<a href='audit.html'>Audit</a><!-- <a href='admin.html'> --><script>go('admin.html')</script>",
        "named.html": "<script>let WORKER_NAME = localStorage.getItem('wh_last_worker'); el.textContent = WORKER_NAME;</script>",
        "search-overlay.js": "const hits = window.WHNavTools.filter(m);",
    }
    got = Counter((s["cls"], s["page"]) for s in collect(pages))
    want = {("D", "skew.html"): 1, ("E", "dual.html"): 2, ("F", "role.html"): 1, ("G", "name.html"): 1,
            ("H", "reload.html"): 1, ("H", "dual.html"): 1, ("H", "skew.html"): 0,
            # L: the live link and the scripted one count, the commented one does not, and a link inside an admin page
            # (whose audience is admitted everywhere) is no offer; the role-blind search is one more, met on the home
            ("L", "links.html"): 2, ("L", "admin.html"): 0, ("L", "index.html"): 1, ("M", "named.html"): 1}
    ok = all(got.get(k, 0) == v for k, v in want.items()) and ("D", "dual.html") not in got and ("F", "role_ok.html") not in got \
        and ("G", "name_ok.html") not in got and ("H", "own.html") not in got
    print(("PASS" if ok else "FAIL") + f" bug-hunt inventory self-test - {dict(got)}")
    return 0 if ok else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    sites = collect()
    if args.json:
        print(json.dumps(sites, indent=1, ensure_ascii=False))
        return 0
    by_cls = Counter(s["cls"] for s in sites)
    print("\nBUG-HUNT INVENTORY (production pages only)")
    print("=" * 74)
    print(f"  total measured defect sites: {len(sites)}")
    for c, label in (("D", "version skew silenced by a typeof guard   (layer H, per page)"),
                     ("E", "scope-silent empty state on a dual-mode page (layer F, per string)"),
                     ("F", "stored role trusted without re-validation  (layer AU, per page)"),
                     ("G", "stored hive name never reconciled          (layer D, per page)"),
                     ("H", "hive restored by reload, not in start-up   (layer F, per page)"),
                     ("J", "a live journey that is not live            (layer F, per journey)"),
                     ("K", "design slop the ratchet still holds        (layer F, per file :: antipattern)"),
                     ("L", "a control offered to a person it refuses   (layer AU, per control)"),
                     ("M", "copy contradicting who the person is       (layer AU, per page / component)"),
                     ("N", "a file every deployment stores, never served (layer H, per kind)")):
        print(f"    {c} · {label}: {by_cls.get(c, 0)}")
    print()
    for c in "DEFGHJKLMN":
        rows = [s for s in sites if s["cls"] == c]
        if not rows:
            continue
        print(f"  class {c} by page:")
        for pg, n in Counter(s["page"] for s in rows).most_common(8):
            print(f"    {pg:<32} {n:>3}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
