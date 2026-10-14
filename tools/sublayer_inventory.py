#!/usr/bin/env python3
"""sublayer_inventory.py - the MEASURED population for the SUB-LAYER wave (SL), 2026-10-14.

Ian, 2026-10-14, after the release that found the real cause of his missing logbook assets (a CSP without `wss:`
-> WebKit throws on the realtime socket -> the logbook's start-up dies before it loads the assets): *"I am pretty
sure that is belong to a layer or sublayer of our full stack architectural layer SaaS, so we have to dig deeper to
make numbers trajectories for each full stack architectural layer and sublayers of my SaaS, with the aim to improve
our overall UFAI UI UX of my platform for every production/public/founder pages."*

Until this wave the 14 full-stack layers carried ONE ask each and only LM had sub-layers (10). The issue that bit
was sub-layer H1 (the headers the edge serves) meeting A3/AV1 (a start-up that must survive an optional subsystem),
and nothing in the program could have named it: a layer-wide ask is answered by the first page that passes it.

THE NUMBER IS DERIVED, NEVER TYPED (the BRP/BRH rule). One cell per (page, layer, sub-layer) where the page's own
source puts it in the sub-layer's ROSTER:
  ALL      every page of the class (a contract every page must keep: phone fit, headers, a gate ...)
  <regex>  the page's source contains what the sub-layer governs (a realtime channel, a write, a date, an upload)

Page classes, measured from disk:
  production  the served app pages (seed_expansion_wave4.served_pages()['root']) minus LX_NON_PRODUCTION minus the
              founder surfaces below
  founder     Ian's admin / founder / developer surfaces (FOUNDER_PAGES that exist on disk, retired ones included:
              the operator console un-retires founder-console.html, and these pages had layers with ZERO rows)
  public      the learn guides + their hub, the calculators, the four public-root pages

The rosters are the ones measured on 2026-10-14 and approved in direction, kept verbatim so the number Ian saw is
the number seeded - with ONE honest restatement: C2's regex ended in `window`, which matches `window.` in every
script, so it measured ALL; it is declared ALL here (same 158 cells) and its ask says what every page owes.
A roster regex is a CANDIDATE reach, not a verdict: a walk that finds a page outside the sub-layer's real reach
closes its row with that reading as the witness (the W4 n/a precedent), and the regex is tightened here on the
forward path only - the seeder's replay is anchored to the registry, so no id ever moves.

Deterministic: page sources + one committed snapshot (production_error_groups.json, read once from production's
client_errors so the registry validator's replay never touches production).

    python tools/sublayer_inventory.py              # the human report (the per-layer table)
    python tools/sublayer_inventory.py --json       # the machine population (what the seeder reads)
    python tools/sublayer_inventory.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

ERROR_GROUPS = ROOT / "production_error_groups.json"
CLASSES = ("production", "founder", "public")
# Ian's admin / founder / developer surfaces - the 12 measured on 2026-10-14 (the operator console's scatter)
FOUNDER_PAGES = (
    "founder-console.html", "marketplace-admin.html", "platform-actions.html", "llm-observability.html",
    "agentic-rag-observability.html", "architecture.html", "validator-catalog.html", "symbol-gallery.html",
    "ai-quality.html", "audit-log.html", "status.html", "design-system.html",
)

# {layer: {code: (name, ask, roster)}} - emitted in LAYER_SET order, so each SL-<layer> wave owns a contiguous id
# range. An ask is "The platform must ..." and never contains " - " (the ledger reads a title's lens up to it).
SUBLAYERS: "OrderedDict[str, OrderedDict[str, tuple[str, str, str]]]" = OrderedDict([
    ("F", OrderedDict([
        ("F1", ("render contract: empty, loading and error states",
                "The platform must give this page an honest empty, loading and error state, each saying which list "
                "it is and what to do next",
                r"empty-state|No .{3,40}yet|skeleton|whListSkeleton|Could not load")),
        ("F2", ("phone fit at 320 and 390, and 1280",
                "The platform must fit this page at 320 and 390 wide and at 1280, with nothing clipped, overlapped "
                "or scrolled sideways", "ALL")),
        ("F3", ("reachable: focus, labels, 44px targets",
                "The platform must let every control on this page be reached, named and pressed: a visible focus, "
                "a label a screen reader speaks, a 44px target", "ALL")),
        ("F4", ("copy: plain words, honest labels",
                "The platform must say what this page means in the plain words a crew uses, with no label that "
                "claims more than the figure behind it", "ALL")),
        ("F5", ("craft: tokens, motion, no slop",
                "The platform must build this page from the design tokens and the motion rules, with nothing the "
                "design detector flags", "ALL")),
    ])),
    ("D", OrderedDict([
        ("D1", ("provenance: source chip, truth view",
                "The platform must show where each figure on this page came from: its source chip and the truth "
                "view it reads", r"wh-source-chip|renderSourceChip|_truth")),
        ("D2", ("ownership keyed by identity, not name",
                "The platform must decide whose rows this page shows by the signed-in account, never by a display "
                "name", r"auth_uid|worker_name")),
        ("D3", ("retention, soft-delete, backfill",
                "The platform must keep what this page deletes recoverable for its retention window, and backfill "
                "what it adds", r"deleted_at|soft.?delete|backfill|retention")),
        ("D4", ("files and storage buckets",
                "The platform must store the files this page takes in the right bucket under the right owner, and "
                "serve them back", r"storage\.from\(|upload\(|accept=\"")),
    ])),
    ("A", OrderedDict([
        ("A1", ("a refusal has a sentence",
                "The platform must answer every refused or failed request on this page with a sentence a person "
                "can act on", r"whReadError|whWriteError|showToast")),
        ("A2", ("no double submit, idempotent writes",
                "The platform must write once when a person taps twice or the network retries, on every write this "
                "page makes", r"\.insert\(|\.upsert\(|\.update\(")),
        ("A3", ("the start-up survives an optional subsystem failing",
                "The platform must finish this page's start-up when an optional subsystem (realtime, analytics, "
                "voice, storage, a device API) throws or is blocked",
                r"\.channel\(|logPageView\(|indexedDB|speechSynthesis|getUserMedia|navigator\.geolocation|"
                r"Notification\.|navigator\.share|navigator\.clipboard")),
        ("A4", ("slow reads: skeleton, timeout, freshness",
                "The platform must show a skeleton, time out, and say how fresh the data is when this page's reads "
                "are slow", r"whListSkeleton|whFreshnessFooter|WH_DB_TIMEOUT|_timeoutFetch")),
    ])),
    ("CA", OrderedDict([
        ("CA1", ("shell precache and version",
                 "The platform must precache this page's shell under the current version and replace it on the next "
                 "deploy", r"serviceWorker|sw\.js")),
        ("CA2", ("cache headers per asset class",
                 "The platform must serve this page and every asset it loads with the cache header its class needs: "
                 "HTML fresh, scripts revalidated, images long-lived", "ALL")),
        ("CA3", ("version skew, page against script",
                 "The platform must notice when this page runs with an older shared script and heal it, never "
                 "silently skip the missing call", r"typeof wh[A-Za-z]+ === 'function'")),
        ("CA4", ("offline fallback and the kept copy",
                 "The platform must show this page's kept copy or the offline fallback when the network is gone, "
                 "and say which one it is", r"offline|navigator\.onLine")),
    ])),
    ("AU", OrderedDict([
        ("AU1", ("session expiry and refresh",
                 "The platform must refresh or end this page's session honestly: never act on an expired one, never "
                 "lose the person's work", r"getSession\(|whSignInWall|restoreIdentityFromSession")),
        ("AU2", ("role gating re-validated on the server",
                 "The platform must re-check on the server the role this page gates its controls on, not trust the "
                 "role the device remembers", r"HIVE_ROLE|wh_hive_role")),
        ("AU3", ("identity is the account, not the name",
                 "The platform must treat the signed-in account as this page's identity, so a renamed or shared "
                 "name never moves anyone's rows", r"WORKER_NAME|wh_last_worker")),
        ("AU4", ("admin and founder gates",
                 "The platform must keep this page's admin and founder controls behind a gate the server enforces",
                 r"isPlatformAdmin|marketplace_platform_admins|wh_local_founder|data-wh-gate")),
    ])),
    ("AV", OrderedDict([
        ("AV1", ("the start-up completes on every engine, WebKit included",
                 "The platform must complete this page's start-up on every engine people use, WebKit on an iPhone "
                 "included, with nothing written to client_errors", "ALL")),
        ("AV2", ("offline queue and sync",
                 "The platform must queue what this page writes while offline and sync it once, in order, when the "
                 "network returns", r"offline-queue|syncOfflineQueue|whOfflineQueue")),
        ("AV3", ("degraded mode: poll when live is off",
                 "The platform must keep this page current by polling when the live channel is blocked or down, and "
                 "say that it is not live", r"whRealtimeSubscribe|rtConn\(|whPoll\(")),
        ("AV4", ("recovery: reload once, never loop",
                 "The platform must recover this page with at most one reload, never a loop",
                 r"location\.reload\(|wh_utils_refetched|wh_hive_recovered")),
    ])),
    ("C", OrderedDict([
        ("C1", ("the hive's day and clock, Manila",
                "The platform must date this page's records by the hive's day in Manila, not the device's clock",
                r"whManilaYmd|whManilaMidnight|toLocaleDateString|toLocaleTimeString|Asia/Manila")),
        ("C2", ("period, window and as-of labels",
                "The platform must state which period, window or as-of date every figure on this page belongs to",
                "ALL")),
        ("C3", ("time on exports and prints",
                "The platform must stamp what this page prints or exports with the time and the period it covers",
                r"print|export|csv|pdf")),
    ])),
    ("S", OrderedDict([
        ("S1", ("read scope: tenant isolation",
                "The platform must show this page only the rows of the hive and the person it is entitled to",
                r"\.from\(|\.rpc\(")),
        ("S2", ("write policies: WITH CHECK",
                "The platform must refuse, with a sentence, every write this page attempts outside its tenant",
                r"\.insert\(|\.upsert\(|\.update\(|\.delete\(")),
        ("S3", ("CSP and security headers for what the page loads",
                "The platform must name in this page's CSP exactly the origins it loads from, sockets included, "
                "and nothing more", r"https://|wss://|<script src=\"https://")),
        ("S4", ("escaping: no raw HTML from data",
                "The platform must escape every piece of stored text this page renders, so data can never become "
                "markup", r"innerHTML|escHtml")),
        ("S5", ("no secret or key in the page",
                "The platform must ship this page with no secret, service key or private token in what a browser "
                "receives", "ALL")),
    ])),
    ("H", OrderedDict([
        ("H1", ("CSP and permission headers for what the page does",
                "The platform must serve this page with the CSP and Permissions-Policy that let it do what it does "
                "on every engine (a socket, a camera, a microphone) and nothing else", "ALL")),
        ("H2", ("the cache-control contract",
                "The platform must serve this page under the cache-control contract its class promises, at the "
                "edge and locally alike", "ALL")),
        ("H3", ("PWA: manifest, install, shell",
                "The platform must let this page install and open as the app, with its manifest, icons and shell "
                "intact", r"manifest|serviceWorker|pwa-install")),
        ("H4", ("deploy rollout: bump and skew",
                "The platform must roll this page out so a returning device moves to the new version within one "
                "visit, never half new and half old", r"CACHE_NAME|sw\.js|typeof wh[A-Za-z]+ === 'function'")),
    ])),
    ("L", OrderedDict([
        ("L1", ("client errors captured with context, and read",
                "The platform must capture every error this page throws, with the page, the person and the engine, "
                "and someone must read it", "ALL")),
        ("L2", ("audit trail on every write",
                "The platform must leave a readable trail of who changed what on this page",
                r"writeAuditLog|hive_audit_log|\.insert\(|\.update\(")),
        ("L3", ("analytics events for the page",
                "The platform must record this page's use as events someone can count",
                r"logPageView\(|analytics_events|whTrack\(")),
        ("L4", ("the sentence a person saw is logged",
                "The platform must log the sentence this page showed a person when something failed, not only the "
                "code", r"showToast|whReadError|whWriteError")),
    ])),
    ("LB", OrderedDict([
        ("LB1", ("row caps and pagination",
                 "The platform must page or cap every list on this page and say when more exists than it shows",
                 r"\.limit\(|Load more|showall")),
        ("LB2", ("query cost and indexes",
                 "The platform must keep this page's queries on an index as its tables grow",
                 r"\.from\(")),
        ("LB3", ("render budget on long lists",
                 "The platform must keep this page responsive with a thousand rows in its longest list",
                 r"\.map\(|forEach\(")),
        ("LB4", ("no refresh storms",
                 "The platform must refresh this page on a bounded cadence, never two refreshers feeding each other",
                 r"setInterval|whPoll\(|refresh")),
    ])),
    ("RL", OrderedDict([
        ("RL1", ("AI and model budget",
                 "The platform must keep what this page spends on AI and functions inside its hive's budget, and say "
                 "when it is spent", r"ai-gateway|aiAnswered|functions/v1/|companion-launcher")),
        ("RL2", ("429s and limits say so",
                 "The platform must tell a person, in a sentence, when this page has hit a limit and when to try "
                 "again", r"429|rate.?limit|whRequireOnline")),
        ("RL3", ("debounce and poll intervals",
                 "The platform must debounce this page's typing and space its polling so one person cannot flood "
                 "the backend", r"debounce|setInterval|setTimeout\(")),
    ])),
    ("CI", OrderedDict([
        ("CI1", ("a gate holds this page's contract",
                 "The platform must have a registered gate that reddens when this page's contract breaks", "ALL")),
        ("CI2", ("a live journey lives on this page, in Chromium and WebKit",
                 "The platform must keep a live journey on this page that passes in Chromium and in WebKit", "ALL")),
        ("CI3", ("ratchets: design, phone fit, a11y",
                 "The platform must hold this page under the design, phone-fit and accessibility ratchets, so a "
                 "count can only fall", "ALL")),
        ("CI4", ("registered in every page list",
                 "The platform must list this page in every registry that enumerates pages (nav, shell, sitemap, "
                 "gates)", "ALL")),
    ])),
])
# How a sub-layer's rows close. CONTRACT sub-layers close in batches by a registered prover over every page (the W4
# contract-layer precedent: headers by the served bytes, secrets by a scan, a11y by axe); every other sub-layer is a
# PERSON walk as the page's cast with the failure or condition induced (addInitScript, page.route, a demoted role, a
# renamed hive, a 1,000-row list), at phone-390 and desktop-1280.
CONTRACT = frozenset(("F2", "F3", "F5", "CA2", "H1", "H2", "H4", "S3", "S4", "S5", "L1", "CI1", "CI2", "CI3", "CI4"))
INSTRUMENT_WALK = "playwright-mcp + postgres-mcp"
INSTRUMENT_PROVER = "library sweep (a registered batch prover over every page - the W4 contract-layer precedent)"
# ★A REFUSAL IS PROVEN AS THE PERSON, NEVER BY A BROWSER OR THE OWNER CONNECTION (2026-10-14). S1 and S2 were seeded as
# browser walks; a browser cannot show that a read was REFUSED, and the postgres MCP connects as the table owner (it
# bypasses RLS). The honest instrument is the one the W4 S layer closed 900/900 rows with: a foreign-hive member's
# identity on the authenticated path (tools/prove_w4_layer_s.py's recipe), requiring zero of this hive's rows.
INVOKE = frozenset(("S1", "S2"))
INSTRUMENT_INVOKE = "invoke + PostgREST as the caller (never the owner connection)"
# Engine-sensitive: these are walked in REAL WebKit as well (Playwright's WebKit, installed from the Z: drive). AV1
# and CI2 on every page; every F sub-layer on a page production's client_errors has named.
WEBKIT_SUBS = frozenset(("AV1", "CI2"))
# a signed-in persona whose vote counts as a page's cast (the hostile and edge personas never define a page's cast)
_CAST_VOTERS = ("worker", "supervisor", "fleet-supervisor", "solo-owner", "driver-worker", "oversight", "buyer",
                "machine-client")


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def page_classes() -> "OrderedDict[str, list[str]]":
    """{class: [pages]}, measured from disk by the seeder's own served_pages() - never listed here."""
    from seed_expansion_wave4 import LX_NON_PRODUCTION, served_pages
    sp = served_pages()
    founder = sorted(p for p in FOUNDER_PAGES if (ROOT / p).exists())
    production = sorted(p for p in sp["root"] if p not in LX_NON_PRODUCTION and p not in FOUNDER_PAGES)
    public = sorted(sp["learn"] + sp["calc"] + sp["public"])
    return OrderedDict([("production", production), ("founder", founder), ("public", public)])


def error_pages() -> set:
    """Pages production's client_errors has named, from the committed snapshot (never a live read)."""
    if not ERROR_GROUPS.exists():
        return set()
    try:
        doc = json.loads(ERROR_GROUPS.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {g.get("page") for g in (doc.get("groups") or []) if g.get("page")}


def casts(existing: list[dict], classes: dict) -> dict:
    """{page: persona} - the page's own cast. public, and a page only a signed-OUT visitor can reach (public-feed):
    anon. A founder surface the hub offers nobody: `oversight`, the platform-staff persona. Every other page: the
    signed-in persona most rows walked it as, AMONG THOSE WHOSE OWN ROUTE TO IT THE JOURNEY-PATHS GATE ACCEPTS.

    ★A VOTE OVER HISTORY KEEPS HISTORY'S MISTAKES, AND A PAGE'S OWN HUB ROLES ARE NOT ITS ROUTE (2026-10-14, the
    first seed of this wave). The vote put `worker` on the founder console; restricting it to the page's hub roles
    fixed that and still cast `worker` on analytics-report, a page the hub lists for nobody - whose route runs through
    analytics.html, offered to supervisors and engineers only - and `worker` on public-feed, which only the landing
    page's signed-out block links. journey-paths caught both. So each candidate is now walked through the GATE'S OWN
    readers (role_blocked_hops, broken_hops) on the exact route the seeder would give it, and the first that passes
    is the cast: the seeder and the gate cannot disagree about who may walk a page."""
    from check_journey_paths import broken_hops, hub_offered_and_parented, link_graph, role_blocked_hops, \
        signed_out_only
    from seed_expansion_wave4 import _cast_of, _hub_roles, _path, _start
    roles = _hub_roles()
    outonly = signed_out_only()
    vote: dict[str, Counter] = {}
    for t in existing:
        if t.get("status") == "descoped" or t.get("persona") not in _CAST_VOTERS:
            continue
        for pg in (t.get("pages") or []):
            vote.setdefault(pg, Counter())[t["persona"]] += 1
    out, candidates = {}, {}
    for cls, pages in classes.items():
        for page in pages:
            if cls == "public" or page in outonly:
                out[page] = "anon"
            elif cls == "founder" and not roles.get(page):
                out[page] = "oversight"
            else:
                ranked = [p for p, _n in (vote.get(page) or Counter()).most_common()]
                candidates[page] = list(dict.fromkeys(ranked + ["supervisor"]))
    paths = {f"{pg}|{p}": _path(_start(pg), pg, [], cast=_cast_of(p)) for pg, ps in candidates.items() for p in ps}
    links = link_graph()
    offered, parented = hub_offered_and_parented()
    bad = {a for a, *_r in role_blocked_hops(paths, {k: _cast_of(k.split("|")[1]) for k in paths}, links)}
    bad |= {a for a, *_r in broken_hops(paths, offered, parented, links)}
    for page, ps in candidates.items():
        out[page] = next((p for p in ps if f"{page}|{p}" not in bad), ps[0])
    return out


def collect(sources: dict | None = None, classes: dict | None = None) -> list[dict]:
    """Every measured cell, layer-major in SUBLAYERS order, then sub-layer, then class, then page.
    `sources`/`classes` let the self-test pass page text in."""
    classes = classes if classes is not None else page_classes()
    cache: dict[str, str] = {}

    def read(p: str) -> str:
        if sources is not None:
            return sources.get(p, "")
        if p not in cache:
            try:
                cache[p] = (ROOT / p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                cache[p] = ""
        return cache[p]

    errs = error_pages() if sources is None else set()
    cells = []
    for layer, subs in SUBLAYERS.items():
        for code, (name, _ask, roster) in subs.items():
            rx = None if roster == "ALL" else re.compile(roster)
            for cls in CLASSES:
                for page in classes.get(cls, []):
                    if rx is not None and not rx.search(read(page)):
                        continue
                    webkit = code in WEBKIT_SUBS or (layer == "F" and page in errs)
                    cells.append({"layer": layer, "sublayer": code, "name": name, "page": page, "class": cls,
                                  "roster": roster, "engine": "webkit" if webkit else "chromium",
                                  "instrument": INSTRUMENT_PROVER if code in CONTRACT else
                                  INSTRUMENT_INVOKE if code in INVOKE else INSTRUMENT_WALK})
    return cells


def self_test() -> int:
    classes = OrderedDict([("production", ["app.html", "quiet.html"]), ("founder", ["console.html"]),
                           ("public", ["learn/x/index.html"])])
    sources = {
        "app.html": "<script>db.channel('x'); db.from('t').insert({}); if (typeof whHiveId === 'function') {}</script>",
        "quiet.html": "<p>static</p>",
        "console.html": "<script>isPlatformAdmin(); x.innerHTML = escHtml(y)</script>",
        "learn/x/index.html": "<article>window.print()</article>",
    }
    got = collect(sources, classes)
    have = {(c["sublayer"], c["page"]) for c in got}
    want_in = {("A3", "app.html"), ("A2", "app.html"), ("CA3", "app.html"), ("AU4", "console.html"),
               ("S4", "console.html"), ("C3", "learn/x/index.html"), ("F2", "quiet.html"), ("C2", "quiet.html")}
    want_out = {("A3", "quiet.html"), ("A2", "console.html"), ("AU4", "app.html"), ("C3", "quiet.html")}
    alls = sum(1 for subs in SUBLAYERS.values() for (_n, _a, r) in subs.values() if r == "ALL")
    asks_ok = all(" - " not in a for subs in SUBLAYERS.values() for (_n, a, _r) in subs.values())
    ok = (want_in <= have and not (want_out & have) and asks_ok
          and sum(1 for c in got if c["page"] == "quiet.html") == alls
          and all(c["engine"] == "webkit" for c in got if c["sublayer"] in WEBKIT_SUBS)
          and sum(len(s) for s in SUBLAYERS.values()) == 52)
    print(("PASS" if ok else "FAIL") + f" sub-layer inventory self-test - {len(got)} cells, {alls} ALL sub-layers, "
          f"asks lens-safe={asks_ok}")
    return 0 if ok else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit the machine population")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    classes = page_classes()
    cells = collect(classes=classes)
    if args.json:
        print(json.dumps(cells, indent=1, ensure_ascii=False))
        return 0
    from backfill_trajectory_layers import NAMES
    per = Counter((c["layer"], c["class"]) for c in cells)
    per_sub = Counter(c["sublayer"] for c in cells)
    print("\nSUB-LAYER INVENTORY - one cell per (page, layer, sub-layer) in the sub-layer's roster")
    print("=" * 96)
    print("  pages: " + " · ".join(f"{k} {len(v)}" for k, v in classes.items())
          + f" = {sum(len(v) for v in classes.values())}")
    print(f"  {'layer':<34} {'production':>10} {'founder':>8} {'public':>7} {'rows':>6}   sub-layers")
    for layer, subs in SUBLAYERS.items():
        row = [per[(layer, k)] for k in CLASSES]
        print(f"  {layer + ' ' + NAMES.get(layer, ''):<34} {row[0]:>10} {row[1]:>8} {row[2]:>7} {sum(row):>6}   "
              + " · ".join(f"{c} {per_sub[c]}" for c in subs))
    tot = [sum(per[(l, k)] for l in SUBLAYERS) for k in CLASSES]
    print(f"  {'all (' + str(sum(len(s) for s in SUBLAYERS.values())) + ' sub-layers)':<34} {tot[0]:>10} {tot[1]:>8} "
          f"{tot[2]:>7} {sum(tot):>6}")
    wk = sum(1 for c in cells if c["engine"] == "webkit")
    print(f"  engine webkit: {wk} cells (AV1 + CI2 everywhere, F on {len(error_pages())} page(s) production's "
          f"client_errors named)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
