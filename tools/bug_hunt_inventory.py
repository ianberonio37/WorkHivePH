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

TEN MORE, from Supabase's two emails of 2026-10-20 (Ian, 2026-10-21: "I just got an email from Vercel and Supabase,
kindly check those and add appropriate number of trajectories"). The emails named one lint - rls_disabled_in_public,
critical - and the October 30 change to the Data API's automatic grant; the advisor they link held the rest. Read
through the claude.ai Supabase connector (read-only) into the committed supabase_advisor_evidence.json
(tools/supabase_advisor_evidence.py), one row per site:
  P  a public table anyone can read         row-level security off on a public table the API serves
  Q  an object only production holds        no migration creates it (ten hand-made debug_* functions, anon-executable)
  R  a view that runs as its owner          SECURITY DEFINER view: the reader's own row policies never apply
  S  a definer function that asks no one    anon may execute it and its body checks no caller
  T  a search_path the caller can change    the function resolves unqualified names through the caller's path
  U  an extension in the public schema      its objects sit in the schema the API exposes
  V  a materialized view past every policy  no RLS is possible on it; the API served it to anon and every member
  W  leaked passwords accepted              Supabase Auth's leaked-password protection is off
  X  access that rests on the automatic     per (role, kind of object): what the role holds that no migration granted
     grant ending 2026-10-30                - lost on any replay of the schema from that day (db reset, a branch)
  Y  a revoke that does not hold            a migration closed a function to anon, and anon can still run it
The Vercel email (Deployment Storage, 75% of 10 GB, 2026-10-13) is the one class N already holds.

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
ADVISOR = ROOT / "supabase_advisor_evidence.json"   # P..Y, read from production's advisor (tools/supabase_advisor_evidence.py)
FREE_PLAN = ROOT / "free_plan_evidence.json"        # Z..AE, the two free plans (tools/free_plan_evidence.py)
RELEASE_FOLLOWUP = ROOT / "release_followup_evidence.json"   # AF..AL, what the 2026-10-24 release left open
#                                                            (tools/release_followup_evidence.py)

GUARD = re.compile(r"typeof\s+(wh[A-Za-z0-9_]+)\s*(?:===|==)\s*'function'")
DEFINED = re.compile(r"^(?:async\s+)?function\s+(wh[A-Za-z0-9_]+)\s*\(|^\s*window\.(wh[A-Za-z0-9_]+)\s*=", re.M)
# D's heal (2026-10-14): the block tools/render_skew_heal.py writes right after a page's utils.js tag names every
# utils.js function the page relies on; a page whose block names them all is healed and leaves the inventory
HEAL_RX = re.compile(r'<script data-wh-skew-heal="([^"]*)"')


def skew_needs(src: str, defined: set) -> list[str]:
    """The utils.js functions a page guards with typeof - exactly what an older cached utils.js would silently drop.
    The one measurement the inventory, render_skew_heal.py and its gate share."""
    return sorted({m.group(1) for m in GUARD.finditer(src) if m.group(1) in defined})


def skew_healed(src: str) -> set:
    m = HEAL_RX.search(src)
    return set(m.group(1).split()) if m else set()
DUAL_MODE = re.compile(r"is\('hive_id',\s*null\)|hive_id\.is\.null|!HIVE_ID\b")
EMPTY_STATE = re.compile(r"[>`'\"]\s*(No [a-z][^<`'\"]{3,60}?yet\.?)")
ROLE_READ = re.compile(r"localStorage\.getItem\(\s*'wh_hive_role'\s*\)")
ROLE_REVALIDATES = re.compile(r"from\(\s*'hive_members'\s*\)[^;]{0,300}select\([^)]*role|from\(\s*'v_worker_truth'|"
                              r"get_hive_board_dashboard|validateHiveMembership|validateMembership|"
                              r"whReconcileHiveRole\(", re.S)   # utils.js: the membership row by auth_uid (BRH-F, 2026-10-14)
ROLE_DECL = re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*localStorage\.getItem\(\s*'wh_hive_role'\s*\)")


def _live_uses(src: str, name: str) -> int:
    """Uses of `name` outside comments, line by line on the RAW source (the block-comment blanker is naive about "/*"
    inside strings - accept="image/*" swallowed resume.html's real code)."""
    n = 0
    for line in src.split("\n"):
        for m in re.finditer(r"\b%s\b" % re.escape(name), line):
            pre = line[:m.start()]
            if re.search(r"(?<!:)//|/\*", pre) or pre.lstrip().startswith("*"):
                continue
            n += 1
    return n


def _dead_role_read(src: str) -> bool:
    """A role read that is declared and never used again is no trust: nothing compares or shows it (marketplace-admin's
    HIVE_ROLE - its gate is the server's platform-admin check; BRH153 refuted live, 20 vs 20 controls)."""
    d = ROLE_DECL.search(src)
    return bool(d) and len(ROLE_READ.findall(src)) == 1 and _live_uses(src, d.group(1)) == 1


NAME_READ = re.compile(r"localStorage\.getItem\(\s*'wh_hive_name'\s*\)")
HIVE_READ = re.compile(r"\bwhHiveId\(\)")
OWN_RESTORE = re.compile(r"\bwhEnsureHiveContext\(|\bwhStartupHive\(")
STARTUP_HIVE = re.compile(r"\bwhStartupHive\(")   # seats a wiped hive AND reconciles the name in the page's start-up

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
            # A control GATED from birth is not a site: its reproduction cannot be made to fail. The marker is the
            # one validate_gated_offers verifies (offered only after the server answers). OPC (2026-10-22) added
            # three such console links - ai-quality, audit-log, marketplace - which read as new sites (2026-10-24).
            if "gated-offer-ok" in src[max(0, m.start() - 700):m.start()]:
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
        # D - version skew silenced by typeof guards (one row per page: the heal is per page). A function the page's
        # heal block names is no longer silent - an older utils.js without it is refetched and the page reloaded
        unhealed = set(skew_needs(src, defined)) - skew_healed(src)
        guards = [(m.group(1), _line_of(src, m.start())) for m in GUARD.finditer(src) if m.group(1) in unhealed]
        if guards:
            names = sorted({g for g, _ in guards})
            sites.append({"cls": "D", "page": page, "line": guards[0][1], "key": f"{len(guards)} guards",
                          "detail": f"{len(guards)} typeof guards on {len(names)} utils.js functions: "
                                    + ", ".join(names[:6]) + (" ..." if len(names) > 6 else "")})
        # E - scope-silent empty states on a dual-mode page (one row per distinct string). A sentence misleads in ONE
        # state: a member's page in personal mode. A page that seats the hive in its own start-up (whStartupHive /
        # whEnsureHiveContext, or a page that owns seating) never reaches that state, so its sentences speak for the
        # hive's lists - the scope-empty gate proves it per page in a browser (BRH-E, 2026-10-15)
        if DUAL_MODE.search(src) and page not in OWNS_SEATING and not OWN_RESTORE.search(src):
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
        if rm and not ROLE_REVALIDATES.search(src) and not _dead_role_read(src):
            sites.append({"cls": "F", "page": page, "line": _line_of(src, rm.start()), "key": "wh_hive_role",
                          "detail": "reads wh_hive_role from localStorage and never re-validates it against hive_members"})
        # G - stored hive name never reconciled (one row per page)
        nm = NAME_READ.search(src)
        # whStartupHive (utils.js, BRH-G/H 2026-10-15) reconciles the name in the page's start-up - the fix. Looked for in
        # the RAW source, like whReconcileHiveName beside it: the comment-blanker is naive about "/*" inside strings
        # (accept="image/*" opens a "comment" that swallows real code - it hid resume.html's call)
        if nm and "whReconcileHiveName" not in src and not STARTUP_HIVE.search(src):
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
            # shared chrome is met on the home - but a script ONE page loads is met on that page (engineering-design.js
            # draws engineering-design.html's reports; casting it on the home would walk a page that never runs it)
            page = f if f.endswith(".html") and (ROOT / f).exists() else _page_loading(f) or "index.html"
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
    # P..Y - what Supabase's advisor and production's schema said (2026-10-21), one row per site
    if sources is None and ADVISOR.exists():
        sites += advisor_sites(json.loads(ADVISOR.read_text(encoding="utf-8")))
    # Z..AE - what keeps the platform on the two free plans (2026-10-21), from free_plan_evidence.json
    if sources is None and FREE_PLAN.exists():
        sites += free_plan_sites(json.loads(FREE_PLAN.read_text(encoding="utf-8")))
    # AF..AL - what the 2026-10-24 release left open, from release_followup_evidence.json
    if sources is None and RELEASE_FOLLOWUP.exists():
        sites += release_followup_sites(json.loads(RELEASE_FOLLOWUP.read_text(encoding="utf-8")))
    sites.sort(key=lambda s: (s["cls"], s["page"], s["line"], s["key"]))
    return sites


def free_plan_sites(ev: dict) -> list[dict]:
    """One site per measured way the platform could leave a free plan (free_plan_evidence.json). Ian, 2026-10-21: "my
    platform always free ... I am not upgrading to pro". Vercel Hobby holds 10 GB of deployments; Supabase Free holds a
    500 MB database, keeps no daily backups and pauses a project after a week of low activity."""
    out = []

    def add(cls: str, key: str, detail: str, page: str = "index.html", persona: str = "oversight", line: int = 0) -> None:
        out.append({"cls": cls, "page": page, "line": line, "key": key, "persona": persona, "detail": detail})

    v = ev.get("vercel") or {}
    dash = v.get("dashboard") or {}
    series = dash.get("storage_gb_by_day") or {}
    for proj, p in (v.get("projects") or {}).items():
        if proj == "Production":
            if series:      # what Vercel's own Usage page drew, not the emailed figure
                last = max(series)
                read = f"{series[last]} of {v.get('allowance_gb')} GB on {last}"
            else:
                read = f"{v.get('reported_use_pct')}% of {v.get('allowance_gb')} GB"
            add("Z", proj, f"Vercel built the production project {p['deployments']} times ({p['first']} to {p['last']}); each "
                           f"build stored {v.get('payload_mb_denylist')} MB under the denylist .vercelignore, and Hobby keeps the "
                           f"newest production builds - Deployment Storage read {read} for a site of "
                           f"{v.get('payload_mb_allowlist')} MB")
        elif dash.get("projects") and proj.split(" /")[0] not in dash["projects"]:
            continue    # the repository keeps a deleted project's records; Vercel stores nothing for it (2026-10-21)
        else:
            add("Z", proj, f"a second Vercel project, '{proj.split(' /')[0]}', built this repository {p['deployments']} times "
                           f"({p['first']} to {p['last']}) and still holds the builds Hobby protects - storage for a project "
                           f"nobody serves")
    for t in ev.get("growth_no_purge", []):
        rows = t.get("rows")
        per = f", about {t['per_day']:,} more a day" if t.get("per_day") else ""
        add("AA", t["table"], f"{t['table']} holds {rows:,} rows{per} and nothing ever removes one "
                              f"({t.get('size') or str(round((t.get('bytes') or 0) / 1e6, 1)) + ' MB'}) - operational records "
                              f"that grow with every use toward the free plan's 500 MB database")
    for c in ev.get("inline_photos", []):
        add("AB", c["column"], f"{c['rows']} photos are stored inside {c['column']} as base64 text ({c['bytes'] / 1e6:.2f} MB): "
                               f"they count against the free 500 MB database, and every read of the row carries them")
    by_page: dict[str, list] = {}
    for r in ev.get("photo_reads", []):
        by_page.setdefault(r["page"], []).append(r)
    for page, rs in sorted(by_page.items()):
        add("AB", "list reads", f"{len(rs)} list read(s) on {page} ship the inline photo column "
                                f"({', '.join(str(r['src']) + ':' + str(r['line']) + ' ' + r['cols'] for r in rs[:6])}"
                                f"{' ...' if len(rs) > 6 else ''}) - every load pays for every photo in free egress",
            page=page, persona="worker", line=rs[0]["line"])
    for c in ev.get("corpus", []):
        add("AC", c["table"], f"production's {c['table']} holds {c['prod_rows']} rows ({c['prod_embedded']} embedded) where the "
                              f"AI is built on {c['local_rows']} - the assistant answers production's questions without the "
                              f"reference it was given")
    ob = ev.get("outbox") or {}
    if ob and not ob.get("relay_job"):
        add("AC", "embedding_outbox", f"production's embedding outbox holds {ob.get('queued')} rows and has drained "
                                      f"{ob.get('drained')}: no relay runs in production (tools/drain_embedding_outbox.py runs "
                                      f"only locally), so nothing a person writes there is embedded or found again")
    vj = ev.get("voice_journal") or {}
    if vj and (vj.get("embedded") or 0) < (vj.get("rows") or 0):
        add("AC", "voice_journal_entries", f"{(vj['rows'] or 0) - (vj['embedded'] or 0)} of {vj['rows']} voice journal "
                                           f"entries in production were never embedded - a person's own notes the assistant "
                                           f"cannot find")
    for r in ev.get("refused", []):
        for page in r.get("pages") or ["index.html"]:
            add("AD", r["function"], f"{page} calls {r['function']}(), which production refuses a signed-in member "
                                     f"(authenticated may not execute it) - every load falls back without saying so",
                page=page, persona="worker")
    for gp in ev.get("plan_gaps", []):
        add("AE", gp["key"], f"{gp['what']} - a gap the platform must cover itself, on free services, without a paid plan")
    return out


def release_followup_sites(ev: dict) -> list[dict]:
    """One site per item the 2026-10-24 release left open (release_followup_evidence.json). Ian, 2026-10-24: "make a
    necessary and appropriate number of trajectories" - so each is counted from what was measured, never typed."""
    out = []

    def add(cls: str, key: str, detail: str, page: str = "index.html", persona: str = "oversight", line: int = 0) -> None:
        out.append({"cls": cls, "page": page, "line": line, "key": key, "persona": persona, "detail": detail})

    sm = ev.get("smoke") or {}
    if sm.get("hive_line"):
        add("AF", "post_deploy_smoke.mjs",
            f"the post-deploy smoke's signed-in tier seeds a local hive into storage (tools/post_deploy_smoke.mjs:"
            f"{sm['hive_line']}: {', '.join(sm.get('seeded_keys') or [])}) instead of asking the server who the account "
            f"is - against production it would claim a hive the account is not in", line=sm["hive_line"])
    if not sm.get("has_identity"):
        add("AF", "production smoke identity",
            "production has no account the smoke can sign in with (WH_SMOKE_EMAIL is not in .env), so the 2026-10-24 "
            "deploy's signed-in tier and its critical paths were not run")
    ran = (sm.get("last_report") or {}).get("tier2_pages", 0)
    total = len(sm.get("app_pages") or [])
    for name in sm.get("app_pages") or []:
        add("AG", "signed in on production",
            f"{name}.html was not opened signed in on production after the 2026-10-24 deploy (the smoke's signed-in tier "
            f"ran {ran} of {total} pages) - a page whose script throws for a member ships unseen",
            page=f"{name}.html", persona="supervisor")
    flow_page = {1: "index.html", 2: "logbook.html", 3: "assistant.html", 4: "asset-hub.html", 5: "index.html"}
    for f in ev.get("tier0") or []:
        add("AH", f"flow {f['n']}",
            f"Tier-0 flow {f['n']} - {f['flow']} - was not walked on production after the 2026-10-24 deploy (the runbook's "
            f"Tier 0 is manual and needs a production account)",
            page=flow_page.get(f["n"], "index.html"), persona="oversight" if f["n"] == 5 else "supervisor")
    rc = ev.get("root_causes") or {}
    n = len(rc.get("vocabulary") or [])
    for w in rc.get("writers") or []:
        add("AI", f"writer {Path(w['file']).name}",
            f"{w['how']} ({w['file']}:{w['line']}) - a breakdown's cause stored as said, beside the logbook form's {n} "
            f"causes", page=w["page"], persona="supervisor", line=w["line"])
    for r in rc.get("readers") or []:
        add("AI", f"reader {Path(r['file']).name}:{r['line']}",
            f"{r['how']} ({r['file']}:{r['line']}) - a cause recorded in other words never meets its twin from the form",
            page=r["page"], persona="supervisor", line=r["line"])
    if rc.get("local_free_text"):
        p = rc.get("prod") or {}
        add("AI", "stored free text",
            f"{rc['local_free_text']} breakdown causes stored locally sit outside the form's {n} causes "
            f"({p.get('free_text', '?')} of {p.get('causes', '?')} in production) - each one its own bar in the Pareto",
            page="analytics.html", persona="supervisor")
    for x in ev.get("lookalikes") or []:
        pages = x.get("pages") or []
        add("AJ", f".{x['class']}",
            f"the adoption census credits {len(pages)} page(s) as .{x['class']} adopters ({x['component']}) because a "
            f"class such as heat-{x['class']} contains '-{x['class']}': {', '.join(pages[:6])}"
            f"{' ...' if len(pages) > 6 else ''} - the floor counts pages that never used the component")
    cr = ev.get("credits") or {}
    p = cr.get("prod") or {}
    if not cr.get("gate_holds_grant_policy"):
        add("AK", "solvency gate",
            f"validate_credit_solvency's one rule is vouchers <= revenue; starter grants (production: {p.get('starter_grants')} "
            f"grant, {(p.get('ledger_totals') or {}).get('starter_grant')} credits) are free credit it never holds to "
            f"their policy - once per verified seller, the knob's amount, inside the supply cap")
    if not cr.get("console_names_backing"):
        add("AK", "cover reason",
            f"the operator console's liability cover reads 0.00x in red on production ({p.get('topups')} credits of "
            f"top-ups, {(p.get('ledger_totals') or {}).get('starter_grant')} of free starter credit) and says nothing "
            f"about why - what is owed is not split by its backing", page="founder-console.html")
    for ph in ev.get("photos") or []:
        add("AL", ph["table"],
            f"production's {ph['table']} holds {ph['inline']} photos inline and {ph['stored']} in Storage, while the pages "
            f"read only the stored path since the 2026-10-24 deploy - {ph['inline']} photos show nothing until the "
            f"owner's copy pass runs", page=ph["page"], persona="worker")
    return out


def advisor_sites(ev: dict) -> list[dict]:
    """One site per finding in supabase_advisor_evidence.json. The walk is an API probe made as the person the defect
    exposes, so every row is met on the home and walked by platform staff (N's precedent)."""
    out = []

    def add(cls: str, key: str, detail: str) -> None:
        out.append({"cls": cls, "page": "index.html", "line": 0, "key": key, "persona": "oversight", "detail": detail})

    for t in ev.get("P_rls_disabled", []):
        add("P", t, f"public.{t} has row-level security off and the API serves it - anyone holding the site's public key "
                    f"reads every row (production advisor, rls_disabled_in_public, {ev['read']})")
    for o in ev.get("Q_prod_only", []):
        add("Q", o, f"production holds {o} and no migration creates it - anon may execute it, and no review, gate or "
                    f"local walk has ever seen it (schema fingerprint, {ev['read']})")
    for v in ev.get("R_definer_views", []):
        add("R", v, f"public.{v} is a SECURITY DEFINER view: it reads its base tables with its owner's rights, so the "
                    f"reader's own row policies never apply (production advisor, security_definer_view)")
    for f in ev.get("S_anon_definer_unchecked", []):
        add("S", f["name"], f"anon may execute public.{f['name']}(), a SECURITY DEFINER function whose body checks no "
                            f"caller{' and WRITES' if f.get('writes') else ''} - it runs as its owner, past every policy, "
                            f"for anyone holding the public key")
    for f in ev.get("T_search_path_mutable", []):
        add("T", f, f"public.{f}() resolves unqualified names through the caller's search_path (production advisor, "
                    f"function_search_path_mutable)")
    for e in ev.get("U_extension_in_public", []):
        add("U", e, f"the {e} extension is installed in public, the schema the API exposes (production advisor)")
    for m in ev.get("V_matview_in_api", []):
        add("V", m, f"public.{m} is a materialized view - no row-level security can apply to it - and the API served it "
                    f"to anon and to every signed-in member, every hive's rows (production advisor, materialized_view_in_api)")
    for d in ev.get("W_leaked_password_protection", []):
        add("W", "leaked-password protection", f"Supabase Auth accepts passwords known to be leaked: {d}")
    for c in ev.get("X_api_grant_cells", []):
        objs = c["objects"]
        add("X", f"{c['role']} · {c['kind']}",
            f"{len(objs)} public {c['kind']}{'s' if len(objs) != 1 else ''} the {c['role']} role reaches today with no "
            f"migration granting it ({', '.join(objs[:6])}{' ...' if len(objs) > 6 else ''}) - the access rests on "
            f"Supabase's automatic grant, which stops for new tables and every replay of the schema on 2026-10-30")
    for r in ev.get("Y_revokes_that_do_not_hold", []):
        add("Y", f"{r['name']}({r['args'][:60]})",
            f"{r['revoked_in']} revoked public.{r['name']}() from {'/'.join(r['revoked_from'])}, and anon can execute it "
            f"today: {r['why']}")
    return out


def _page_loading(script: str) -> str | None:
    """The one production page whose markup loads `script` (src="script"), or None when none or several do."""
    rx = re.compile(r"""<script\b[^>]*\bsrc=["'](?:\./)?%s(?:\?[^"']*)?["']""" % re.escape(script), re.I)
    hits = [p for p in sorted(os.path.basename(x) for x in glob.glob(str(ROOT / "*.html")))
            if rx.search((ROOT / p).read_text(encoding="utf-8", errors="replace"))]
    return hits[0] if len(hits) == 1 else None


def self_test() -> int:
    utils = "function whEnsureHiveContext(db){}\nfunction whHiveId(){}\nfunction whReconcileHiveName(db){}\n"
    pages = {
        "utils.js": utils,
        "skew.html": "<script>if (typeof whHiveId === 'function') {} if (typeof whNotDefined === 'function') {}</script>",
        # D: a heal block naming every guarded function takes the page out; one naming only some leaves it in
        "healed.html": "<script data-wh-skew-heal=\"whHiveId whEnsureHiveContext\"></script>"
                       "<script>if (typeof whHiveId === 'function') {} if (typeof whEnsureHiveContext === 'function') {}</script>",
        "half.html": "<script data-wh-skew-heal=\"whHiveId\"></script>"
                     "<script>if (typeof whHiveId === 'function') {} if (typeof whEnsureHiveContext === 'function') {}</script>",
        "dual.html": "<script>let HIVE_ID = whHiveId(); if (!HIVE_ID) {} x.innerHTML = `<p>No parts yet.</p><p>No parts yet.</p>`; y = 'No jobs yet'</script>",
        # E: the same page seating its hive in its own start-up never falls into personal mode for a member
        "dual_seated.html": "<script>let HIVE_ID = whHiveId(); const _s = whStartupHive(db); if (!HIVE_ID) {} x.innerHTML = `<p>No parts yet.</p>`</script>",
        "role.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role'); if (HIVE_ROLE === 'supervisor') {}</script>",
        # F: the shared reconcile clears it; so does a read nothing compares or shows (a comment naming it is no use)
        "role_rec.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role'); await whReconcileHiveRole(db); if (HIVE_ROLE) {}</script>",
        "role_dead.html": "<script>const HIVE_ROLE = localStorage.getItem('wh_hive_role') || '';\n  /* supersedes HIVE_ROLE */\n// HIVE_ROLE\n</script>",
        # ...but a URL's // before a real use is not a comment
        "role_url.html": "<script>const HIVE_ROLE = localStorage.getItem('wh_hive_role');\nfetch('https://x/' + HIVE_ROLE);</script>",
        "role_ok.html": "<script>let HIVE_ROLE = localStorage.getItem('wh_hive_role'); await validateHiveMembership();</script>",
        "name.html": "<script>const HIVE_NAME = localStorage.getItem('wh_hive_name');</script>",
        "name_ok.html": "<script>const HIVE_NAME = localStorage.getItem('wh_hive_name'); whReconcileHiveName(db);</script>",
        "reload.html": "<script>let HIVE_ID = whHiveId();</script>",
        "own.html": "<script>let HIVE_ID = whHiveId(); await whEnsureHiveContext(db);</script>",
        # G + H: one start-up call settles both
        "startup.html": "<script>let HIVE_ID = whHiveId(); let HIVE_NAME = localStorage.getItem('wh_hive_name'); "
                        "const h = await whStartupHive(db);</script>",
        "audit.html": "<h2>Supervisors only</h2>",
        "admin.html": "<script>if (!(await isPlatformAdmin(db))) {}</script><a href='audit.html'>x</a>",
        "links.html": "<a href='audit.html'>Audit</a><!-- <a href='admin.html'> --><script>go('admin.html')</script>",
        "named.html": "<script>let WORKER_NAME = localStorage.getItem('wh_last_worker'); el.textContent = WORKER_NAME;</script>",
        "search-overlay.js": "const hits = window.WHNavTools.filter(m);",
    }
    got = Counter((s["cls"], s["page"]) for s in collect(pages))
    want = {("D", "skew.html"): 1, ("D", "healed.html"): 0, ("D", "half.html"): 1, ("E", "dual.html"): 2, ("F", "role.html"): 1, ("F", "role_url.html"): 1, ("G", "name.html"): 1,
            ("H", "reload.html"): 1, ("H", "dual.html"): 1, ("H", "skew.html"): 0,
            # L: the live link and the scripted one count, the commented one does not, and a link inside an admin page
            # (whose audience is admitted everywhere) is no offer; the role-blind search is one more, met on the home
            ("L", "links.html"): 2, ("L", "admin.html"): 0, ("L", "index.html"): 1, ("M", "named.html"): 1}
    ok = all(got.get(k, 0) == v for k, v in want.items()) and ("D", "dual.html") not in got and ("F", "role_ok.html") not in got \
        and ("G", "name_ok.html") not in got and ("H", "own.html") not in got         and ("G", "startup.html") not in got and ("H", "startup.html") not in got \
        and ("E", "dual_seated.html") not in got and ("F", "role_rec.html") not in got and ("F", "role_dead.html") not in got
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
                     ("N", "a file every deployment stores, never served (layer H, per kind)"),
                     ("P", "a public table anyone can read (RLS off)   (layer S, per table)"),
                     ("Q", "an object only production holds            (layer S, per object)"),
                     ("R", "a view that runs as its owner              (layer S, per view)"),
                     ("S", "a definer function that asks no caller     (layer S, per function)"),
                     ("T", "a search_path the caller can change        (layer S, per function)"),
                     ("U", "an extension in the public schema          (layer S, per extension)"),
                     ("V", "a materialized view past every policy      (layer S, per view)"),
                     ("W", "leaked passwords accepted                  (layer S, one setting)"),
                     ("X", "access resting on the grant ending 10-30   (layer CI, per role x kind)"),
                     ("Y", "a revoke a migration meant, not holding    (layer S, per function)"),
                     ("Z", "deployments that outgrow Vercel's 10 GB    (layer H, per project)"),
                     ("AA", "a table that grows with no purge           (layer RL, per table)"),
                     ("AB", "a photo stored inside a row               (layer RL, per column / page)"),
                     ("AC", "the AI's corpus missing in production      (layer AV, per table)"),
                     ("AD", "a function production refuses its caller   (layer A, per page)"),
                     ("AE", "a free-plan gap covered by nothing         (layer A, per gap)"),
                     ("AF", "a post-deploy check that cannot sign in    (layer CI, per instrument)"),
                     ("AG", "a page never seen signed in on production  (layer CI, per page)"),
                     ("AH", "a critical path never walked on production (layer CI, per flow)"),
                     ("AI", "a breakdown cause analytics cannot group   (layer D, per writer / reader)"),
                     ("AJ", "an adoption census crediting a lookalike   (layer CI, per class)"),
                     ("AK", "free credit the solvency check never holds (layer D, per check)"),
                     ("AL", "a release shipped ahead of its data move   (layer A, per table)")):
        print(f"    {c} · {label}: {by_cls.get(c, 0)}")
    print()
    for c in list("DEFGHJKLMNPQRSTUVWXY") + ["Z", "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK", "AL"]:
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
