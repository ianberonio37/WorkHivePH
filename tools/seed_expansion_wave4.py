#!/usr/bin/env python3
"""seed_expansion_wave4.py - WAVE 4 (2026-09-14): every served page x every action x every layer, LIVED start to end.

Ian, 2026-09-14: "still there are AI sloppiness ... overlapping and overflowing in using the platform through
phone ... journeys trajectories more deeper, start from the start to end for every page, such as in connection
pages, where you have to search in the internet any files then upload it ... not only the companion, it should
be the whole nav-hub ... just put the number of trajectories so that we won't be lost ... expand and extend: we
have to cover, explore, experience those uncovered, unexplored, and unexperienced layers."
Plan: ~/.claude/plans/optimized-swimming-lovelace.md.

THE NUMBER IS MEASURED HERE AND PRINTED WITH ITS ARITHMETIC (a plan is the number of trajectories, lived start
to end - feedback_a_plan_is_the_number_of_trajectories_lived_start_to_end). Nothing below is hand-typed:

  new rows = (action stories + nav-hub stories + layer stories) x 3 axes

  action stories  one start-to-end journey per distinct action a person can take on a served page.
                  An app page's denominator is its PKS substrate map (substrate/page/<page>.md - DB writes as
                  table.op, RPC calls, edge invokes; feedback_substrate_page_maps_beat_fresh_greps), each item
                  VERIFIED against the page's current source (drift since the map was built is dropped, never
                  invented); plus one upload story on each of the seven upload pages (a REAL internet-sourced
                  file with a provenance manifest); plus one export/print story where the page calls
                  window.print; plus, on a page with no persisted action at all, one story per distinct
                  primary-styled control (minimum one: the page's primary link). A learn article's actions are
                  its page-owned CTA destinations (the tool the guide is about, the sign-up line, its named
                  calculator, a related guide); a calculator is one story (search-arrival -> worked example ->
                  compute -> export/print -> CTA); a public-root page is one.
  nav-hub stories the WHOLE shell - fab, panel, the six modes, global search, tiles, quick, companion,
                  feedback, assist row, connectivity pill + detail, close - once per page whose source loads
                  nav-hub.js.
  layer stories   one lived journey per (served page, full-stack layer) cell that no gated >=4-page journey
                  has lived, MINUS the cells an action story on that page already lives (an action IS the F
                  story of its page; a write IS its D story). The lenses are LAYER_LENS's own sentences.
  axes            phone-390 English · narrow-320 English · phone-390 Filipino.

THE ROSTERS FREEZE ON SEEDING (the wave-2/3 lesson, the *x16 rule): once any W4 row exists, plan() REPLAYS the
seeded rows verbatim, because every cell this file measures is covered the moment the rows are written, and
validate_trajectory_registry.py derives its expected ids from plan(). The MEASUREMENT (page_layer_cells) stays
callable un-frozen, so the scoreboard can state lived / not-lived as the walks close rows.

  python tools/seed_expansion_wave4.py --dry-run   # the arithmetic per class and per axis, sample rows
  python tools/seed_expansion_wave4.py --cells     # the PAGE x LAYER measurement only
  python tools/seed_expansion_wave4.py             # write (idempotent on title+pages), then the critic rows
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_expansion_wave3 import (  # noqa: E402  - reused, never re-typed
    HIVES, LAYER_LENS, LAYER_SET, NOT_A_DESTINATION, _NAV_OFFERED, _entry_chain, _glob, _hop_ok, _short,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
import registry_io as _rio  # the registry UNION: main file + the cube shard (tools/registry_io.py, 2026-10-26)
PREFIX = "W4"
WAVE = "W4"
WAVE_NAME = "Wave 4: every page x every action x every layer, lived start to end"

# (device, language, tier) - tier A is the base story, B the same story on the other axes (wave 3's meaning)
AXES = [("phone-390", "en", "A"), ("narrow-320", "en", "B"), ("phone-390", "fil", "B")]
PUBLIC_ROOT = ["about", "feedback", "privacy-policy", "terms-of-service"]
# the seven upload pages: fixture kind, what the real file is, the tables the upload lands in (readers are the
# effect pages). Ian's example: integrations (upload the CMMS export) -> plant-connections (sync status) ->
# asset-hub (the assets) -> pm-scheduler (they are schedulable).
UPLOAD_PAGES = OrderedDict([
    ("integrations.html", ("cmms-export", "a real CMMS / SAP-PM export (.csv/.xlsx) or OEM manual (.pdf/.docx)",
                           ["external_sync", "asset_nodes", "pm_assets", "inventory_items", "logbook"])),
    ("logbook.html", ("fault-photo", "a real nameplate or fault photo", ["logbook"])),
    ("inventory.html", ("part-photo", "a real spare-part photo", ["inventory_items"])),
    ("marketplace.html", ("listing-photo", "a real listing photo", ["marketplace_listings"])),
    ("marketplace-seller.html", ("listing-photo", "a real listing photo", ["marketplace_listings"])),
    ("resume.html", ("technician-resume", "a real maintenance-technician resume", ["resume_documents"])),
    ("voice-journal.html", ("audio-clip", "a real short audio clip, played into the microphone", ["logbook"])),
])
FIXTURES = "_fixtures"
ACTION_LAYERS = {"write": ["D", "F"], "rpc": ["A", "F"], "edge": ["A", "C"], "upload": ["D", "F", "AV"],
                 "print": ["F", "H"], "cta": ["F"], "compute": ["F", "D"], "learn-cta": ["F", "H"]}
ACTION_UFAI = {"write": ["F", "I"], "rpc": ["F"], "edge": ["F", "A"], "upload": ["F", "I"],
               "print": ["A", "F"], "cta": ["U", "F"], "compute": ["F", "A"], "learn-cta": ["U", "F"]}
NAV_HUB_LAYERS, NAV_HUB_UFAI = ["F", "CA"], ["U", "A"]
PERSON_LAYERS = {"F", "CA"}           # every other layer story is a contract the platform must keep
CONTINUATION = ["hive.html", "analytics.html", "audit-log.html", "logbook.html", "index.html"]
# ★THE PADDING WAS ROLE-BLIND, SO WORKER JOURNEYS WERE PADDED WITH SUPERVISOR SURFACES (2026-09-29).
# `_path` pads every journey from CONTINUATION to reach min_pages, and two of its five entries are pages
# the hub does NOT offer a worker: asked of nav-hub.js through check_journey_paths.hub_roles(),
# `analytics.html` is ['supervisor','engineer'] and `audit-log.html` is ['supervisor'] (while `hive.html`
# and `logbook.html` are ['field','supervisor'], so those two were always fine). Result: W41468
# `persona: worker` seeded `index.html -> hive.html -> ai-quality.html -> analytics.html`, and W45761
# `persona: worker` seeded `... -> analytics.html -> hive.html -> audit-log.html` - routes their own cast
# cannot walk. check_journey_paths reported it from the other end as 19 archetypes whose "CAST's own hub
# mode cannot reach" the destination.
# `_hop_ok`/`_NAV_OFFERED` ask whether the platform offers a hop to SOMEONE, never whether THIS cast can
# reach it, which is why the seeder could satisfy "every hop follows an offered route" (0 findings) and
# still hand a worker a supervisor's page.
# These are the hub's ACTUAL field-mode destinations, read from nav-hub.js and not assumed: asset-hub,
# dayplanner, hive, inventory, logbook, pm-scheduler, shift-brain, voice-journal (+ index.html, the
# landing page, which carries no `roles:` because it is nobody's drawer entry).
CONTINUATION_FIELD = ["hive.html", "logbook.html", "pm-scheduler.html", "inventory.html", "index.html"]
_CAST_SUP = __import__("re").compile(r"supervisor|oversight|owner|engineer|manager", re.I)


def _hub_roles() -> dict:
    """Which hub modes each destination is offered to, read by the GATE's parser so there is exactly one
    reader of nav-hub.js. Returns {} if the gate is unavailable, which leaves the historical vote intact
    rather than silently reassigning every persona on an import error."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from check_journey_paths import hub_roles
        return hub_roles()
    except Exception:
        return {}


def _cast_of(persona_str: str) -> str:
    """field vs supervisor, by the SAME rule check_journey_paths.cast_mode applies to the row it writes.
    Duplicating the regex here rather than importing keeps the seeder standalone; the selftest below
    pins the two against each other so they cannot drift."""
    return "supervisor" if _CAST_SUP.search(persona_str or "") else "field"
NAV_HUB_STOPS = ["hive.html", "assistant.html", "logbook.html", "alert-hub.html"]
ANON_VERTICAL = {"learn": "a search result for a learn article", "calc": "a free calculator someone linked",
                 "public": "a search result for the platform itself"}

_SRC: dict[str, str] = {}


def _src(page: str) -> str:
    if page not in _SRC:
        try:
            _SRC[page] = (ROOT / page).read_text(encoding="utf-8", errors="replace")
        except OSError:
            _SRC[page] = ""
    return _SRC[page]


def retired_pages() -> set[str]:
    """Pages whose whole surface is the retirement overlay (`id="wh-retired-overlay"`) - the SAME marker
    tools/check_journey_paths.py reads. ★THE FIRST SEED ROUTED 20 JOURNEYS THROUGH THEM AND WROTE ~180 ROWS
    ON THEM (2026-09-14): founder-console, marketplace-admin, llm-observability and agentic-rag-observability
    are served files whose only content is a 'moved to Grafana / Platform Actions' card, so an action story
    on one is a journey nobody can walk and a route through one is worse than no route. The overlay's own id
    is the marker, never a mention of it - platform-actions.html names it in a comment and is live."""
    return {f for f in os.listdir(ROOT) if f.endswith(".html") and 'id="wh-retired-overlay"' in _src(f)}


def served_pages() -> dict[str, list[str]]:
    """The served pages: root/app minus the reference/print pages the roadmap already excludes and minus the
    retired pages, 54 articles + the hub, 60 calculators, the four public-root directories. Measured from
    disk, never listed."""
    retired = retired_pages()
    root = sorted(f for f in os.listdir(ROOT) if f.endswith(".html") and not f.startswith("_")
                  and f not in NOT_A_DESTINATION and f not in retired)
    learn = _glob("learn/*/index.html") + ["learn/index.html"]
    calc = _glob("tools/*/index.html")
    pub = [f"{d}/index.html" for d in PUBLIC_ROOT if (ROOT / d / "index.html").exists()]
    return {"root": root, "learn": learn, "calc": calc, "public": pub}


def page_class(page: str) -> str:
    if page.startswith("learn/"):
        return "learn"
    if page.startswith("tools/"):
        return "calc"
    if "/" in page:
        return "public"
    return "root"


# -- actions per page, MEASURED -------------------------------------------------------------------------
def _map_items(page: str, label: str) -> list[str]:
    mp = ROOT / "substrate" / "page" / (page[:-5] + ".md")
    if not mp.exists():
        return []
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*[^:]*:\s*(.*)",
                  mp.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return []
    return [x.strip("` ") for x in m.group(1).split(",")
            if x.strip("` ") and not x.strip("` ").startswith("(none")]


def _write_in_source(src: str, item: str) -> bool:
    if "." not in item:
        return False
    table, op = item.rsplit(".", 1)
    return bool(re.search(r"\.from\(\s*['\"]" + re.escape(table) + r"['\"]\s*\)[\s\S]{0,200}?\." + op + r"\s*\(",
                          src))


def app_actions(page: str) -> list[tuple[str, str]]:
    """(kind, subject) for an app page: verified substrate items, the upload, the print, or the primary CTA."""
    src = _src(page)
    out: list[tuple[str, str]] = []
    out += [("write", x) for x in _map_items(page, "DB writes") if _write_in_source(src, x)]
    out += [("rpc", x) for x in _map_items(page, "RPC calls")
            if re.search(r"\.rpc\(\s*['\"]" + re.escape(x) + r"['\"]", src)]
    out += [("edge", x) for x in _map_items(page, "Edge invokes") if x in src]
    if page in UPLOAD_PAGES:
        out.append(("upload", UPLOAD_PAGES[page][0]))
    elif re.search(r'type=["\']file["\']', src):
        out.append(("upload", "file"))
    if "window.print(" in src:
        out.append(("print", "window.print"))
    if not out:
        labels = []
        for attrs, inner in re.findall(r"<button\b([^>]*)>([\s\S]*?)</button>", src):
            cls = re.search(r'class=["\']([^"\']*)', attrs)
            cls = cls.group(1) if cls else ""
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
            if re.search(r"btn-primary|primary|cta|submit", cls + " " + attrs) and label and len(label) < 40:
                labels.append(label)
        out += [("cta", lb) for lb in sorted(set(labels))] or [("cta", "the page's primary link")]
    return out


def learn_actions(page: str) -> list[tuple[str, str]]:
    src = _src(page)
    if page == "learn/index.html":
        out = []
        if "lh-cta" in src:
            out.append(("learn-cta", "open-workhive"))
        if "lh-more" in src or "lh-search" in src:
            out.append(("cta", "find-a-guide"))
        return out or [("cta", "the page's primary link")]
    slug = page.split("/")[1]
    out: list[tuple[str, str]] = []
    for href in re.findall(r'<a href="([^"]+)" class="cta-btn">', src):
        out.append(("learn-cta", f"named-tool:{href}"))
    if 'class="cta-secondary"' in src:
        out.append(("learn-cta", "sign-up"))
    calcs = sorted(set(re.findall(r'href="/tools/([a-z0-9\-]+)/"', src)))
    if calcs:
        out.append(("learn-cta", f"named-calculator:{calcs[0]}"))
    rel = sorted(set(re.findall(r'href="/learn/([a-z0-9\-]+)/"', src)) - {slug})
    if rel:
        out.append(("learn-cta", f"related-guide:{rel[0]}"))
    return out or [("cta", "the page's primary link")]


def calc_cta_target(page: str) -> str:
    m = re.search(r'href="/([a-z0-9\-]+\.html)[^"]*"[^>]*class="cta"|class="cta"[^>]*href="/([a-z0-9\-]+\.html)',
                  _src(page))
    return (m.group(1) or m.group(2)) if m else "engineering-design.html"


def page_actions(page: str) -> list[tuple[str, str]]:
    cls = page_class(page)
    if cls == "root":
        return app_actions(page)
    if cls == "learn":
        return learn_actions(page)
    if cls == "calc":
        return [("compute", calc_cta_target(page))]
    return [("cta", "the page's primary link")]


def nav_hub_hosts() -> list[str]:
    # ★NOT the reference/print pages (2026-09-14, the ratchet threw on architecture.html): a page in
    # NOT_A_DESTINATION loads nav-hub.js but is a diagram/reference surface, not a journey host - its hub
    # panel is not the full one, so a nav-hub walk hangs on #wh-hub-search. The served-page roster already
    # excludes these; the host roster must too.
    retired = retired_pages()
    return sorted(f for f in os.listdir(ROOT) if f.endswith(".html") and not f.startswith("_")
                  and "nav-hub.js" in _src(f) and f not in retired and f not in NOT_A_DESTINATION)


# -- effect pages: who reads what a page writes ---------------------------------------------------------
_READERS: dict[str, list[str]] = {}


def readers(table: str, roots: list[str]) -> list[str]:
    if table not in _READERS:
        _READERS[table] = [
            p for p in roots
            if re.search(r"\.from\(\s*['\"]" + re.escape(table) + r"['\"]\s*\)\s*\.\s*select", _src(p))
            or re.search(r"\.from\(\s*['\"]v_" + re.escape(table) + r"_truth['\"]", _src(p))]
    return _READERS[table]


def _effects(page: str, kind: str, subject: str, roots: list[str]) -> list[str]:
    if kind == "write":
        table = subject.rsplit(".", 1)[0]
        rs = [p for p in readers(table, roots) if p != page]
        rs = sorted(rs, key=lambda p: (p not in _NAV_OFFERED, not _hop_ok(page, p), p))[:2]
        if table == "hive_audit_log" or "hive_audit_log.insert" in _map_items(page, "DB writes"):
            rs.append("audit-log.html")
        return rs
    if kind == "upload" and page in UPLOAD_PAGES:
        out: list[str] = []
        for t in UPLOAD_PAGES[page][2]:
            for p in readers(t, roots):
                if p != page and p not in out:
                    out.append(p)
        return out[:3]
    if kind == "learn-cta":
        if subject.startswith("named-tool:"):
            target = subject.split(":", 1)[1].lstrip("/").split("?")[0] or "index.html"
            return (["index.html", "hive.html", target] if target not in ("index.html", "")
                    else ["index.html", "hive.html", "logbook.html"])
        if subject.startswith("named-calculator:"):
            return [f"tools/{subject.split(':', 1)[1]}/index.html", "index.html", "hive.html"]
        if subject.startswith("related-guide:"):
            return [f"learn/{subject.split(':', 1)[1]}/index.html", "index.html", "hive.html"]
        return ["index.html", "hive.html", "logbook.html"]          # sign-up / open-workhive
    if kind == "compute":
        return ["index.html", "hive.html", subject]
    return []


def _path(start: list[str], page: str, effects: list[str], min_pages: int = 4,
          cast: str = "supervisor") -> list[str]:
    """The route a person actually takes: every hop entered the way the platform parents it (the wave-3
    _entry_chain), the page, the pages its effect crosses, and the platform's own continuation until the
    journey spans at least four pages (feedback_a_journey_path_is_a_route_not_a_list)."""
    pages: list[str] = []

    def add(p: str) -> None:
        if p in pages:
            return
        if pages and p not in _NAV_OFFERED and not _hop_ok(pages[-1], p):
            hops = [h for h in _entry_chain(p, pages[-1], pages) if h not in pages]
            # ★THE BOARD IS THE ROUTE THE PLATFORM OFFERS WHEN NO PARENT CHAIN DOES (2026-09-14, the first
            # seed): check_journey_paths reported logbook -> plant-connections and alert-hub -> audit-log as
            # hops that follow no offered route and said, itself, "route it through hive.html". hive.html is
            # the board every signed-in person returns to and links every hive surface; when the parent
            # chain is empty, the person goes home first.
            if not hops and pages[-1] != "hive.html" and p != "hive.html" and _hop_ok("hive.html", p):
                hops = ["hive.html"] if "hive.html" not in pages else []
                if "hive.html" in pages and pages[-1] != "hive.html":
                    hops = ["hive.html"]          # returning to the board is a real hop even if already visited
            for hop in hops:
                pages.append(hop)
        pages.append(p)

    for s in start:
        add(s)
    add(page)
    for e in effects:
        add(e)
    # Pad only from surfaces THIS cast is offered. `cast` defaults to "supervisor" so an un-updated
    # caller keeps the old, widest list rather than silently narrowing a supervisor journey.
    for c in (CONTINUATION_FIELD if cast == "field" else CONTINUATION):
        if len(pages) >= min_pages:
            break
        add(c)
    return pages


def _start(page: str) -> list[str]:
    if page_class(page) != "root":
        return []                                   # search-arrival lands ON the page
    if page == "index.html":
        return []
    if page == "hive.html":
        return ["index.html"]
    return ["index.html", "hive.html"]


# -- the (page, layer) grid, MEASURED and never frozen ---------------------------------------------------
def page_layer_cells(existing: list[dict]) -> dict:
    """lived = a gated (locked/locking) journey of >=4 pages names the page and the layer; covered = any
    in-scope row names both; uncovered = no row; unexperienced = rows but none lived."""
    roster = [p for cls in served_pages().values() for p in cls]
    rset = set(roster)
    alias = {f"{d}.html": f"{d}/index.html" for d in PUBLIC_ROOT}
    lived: set = set()
    covered: set = set()
    for t in existing:
        if t.get("status") == "descoped":
            continue
        pages = [alias.get(p.replace("\\", "/").lstrip("/"), p.replace("\\", "/").lstrip("/"))
                 for p in (t.get("pages") or []) if isinstance(p, str)]
        lays = t.get("layers") or []
        journey = len(pages) >= 4 and t.get("status") in ("locked", "locking")
        for p in pages:
            if p not in rset:
                continue
            for lay in lays:
                covered.add((p, lay))
                if journey:
                    lived.add((p, lay))
    cells = [(p, lay) for p in roster for lay in LAYER_SET]
    not_lived = [c for c in cells if c not in lived]
    uncovered = [c for c in not_lived if c not in covered]
    by_layer = {lay: sum(1 for p, l2 in not_lived if l2 == lay) for lay in LAYER_SET}
    by_class = Counter(page_class(p) for p, _l in not_lived)
    return {"roster": roster, "cells": len(cells), "lived": lived, "covered": covered, "not_lived": not_lived,
            "uncovered": len(uncovered), "unexperienced": len(not_lived) - len(uncovered),
            "by_layer": by_layer, "by_class": dict(by_class),
            "pages_with_none_lived": sum(1 for p in roster if not any((p, lay) in lived for lay in LAYER_SET))}


# -- the rows ---------------------------------------------------------------------------------------------
def _verb(kind: str, subject: str, page: str) -> str:
    if kind == "write":
        table, op = subject.rsplit(".", 1)
        return f"{op} a {table} row and follow it to its terminus"
    if kind == "rpc":
        return f"call rpc {subject} and read what it returns"
    if kind == "edge":
        return f"invoke {subject} and see the answer land with provenance"
    if kind == "upload":
        desc = UPLOAD_PAGES[page][1] if page in UPLOAD_PAGES else "a real file found on the internet"
        return f"upload {desc} and follow it to where it lands"
    if kind == "print":
        return "print or export this page and read the artifact"
    if kind == "compute":
        return "arrive from a search result, work the example, compute, export or print, follow the CTA"
    if kind == "learn-cta":
        what, _, rest = subject.partition(":")
        return {"named-tool": f"follow the tool this guide is about ({rest})",
                "named-calculator": f"open its named calculator ({rest})",
                "related-guide": f"read on to a related guide ({rest})",
                "sign-up": "join from this guide (the sign-up line)",
                "open-workhive": "open WorkHive, free, from the hub"}.get(what, f"follow {subject}")
    return f"take the primary action '{subject}' and see what changes"


def _persona_by_page(existing: list[dict]) -> dict[str, str]:
    per: dict[str, Counter] = {}
    for t in existing:
        if t.get("status") == "descoped":
            continue
        for p in (t.get("pages") or []):
            per.setdefault(p, Counter())[t.get("persona") or "any"] += 1
    out = {}
    for p, c in per.items():
        for k, _n in c.most_common():
            if k not in ("any", "?"):
                out[p] = k
                break
    # ★A VOTE OVER HISTORY PERPETUATES HISTORY'S MISTAKES (2026-09-29). The loop above picks whichever
    # persona the most existing rows already used for a page, so once any wave attached `worker` to a
    # supervisor-only surface, every later wave inherited it by majority. That is the second half of the
    # journey-paths red: after the padding was made cast-aware, the only unreachable page left in a field
    # route was the row's OWN SUBJECT - `ai-quality.html` (hub ['supervisor']), `analytics.html`
    # (['supervisor','engineer']), `audit-log.html` (['supervisor']) - carrying persona `worker`. A field
    # protagonist cannot be the subject of a page the hub never offers them.
    # So the vote is now CHECKED against what the hub offers, asked of check_journey_paths.hub_roles()
    # rather than re-parsed here: one reader of nav-hub.js, so the seeder and the gate cannot disagree
    # about who a page is for.
    roles = _hub_roles()
    for p, k in list(out.items()):
        r = roles.get(p)
        if r and _cast_of(k) not in r:
            out[p] = "supervisor" if "supervisor" in r else r[0]
    return out


def plan(existing: list[dict] | None = None) -> list[dict]:
    if existing is None:
        try:
            existing = json.loads(REGISTRY.read_text(encoding="utf-8"))["trajectories"]
        except Exception:
            existing = []
    seeded = [t for t in existing if str(t.get("id", "")).startswith(PREFIX)]
    if seeded:
        keep = ("wave", "title", "pages", "layers", "ufai", "persona", "device", "entry", "framing", "story",
                "journey", "axis", "w4")
        return [{k: t[k] for k in keep if k in t} for t in seeded]

    scoped = [t for t in existing if t.get("status") != "descoped"]
    classes = served_pages()
    roots = classes["root"]
    roster = [p for cls in classes.values() for p in cls]
    persona_of = _persona_by_page(scoped)
    grid = page_layer_cells(scoped)
    rows: list[dict] = []
    hub_hosts = nav_hub_hosts()

    def persona(page: str) -> str:
        return "anon" if page_class(page) != "root" else persona_of.get(page, "worker")

    def entry(page: str) -> str:
        return "search-arrival" if page_class(page) != "root" else ("direct" if page == "index.html" else "hub-nav")

    def vertical(page: str) -> str:
        cls = page_class(page)
        idx = roster.index(page) if page in roster else 0
        return ANON_VERTICAL[cls] if cls != "root" else HIVES[idx % len(HIVES)]

    def emit(title: str, pages: list[str], layers: list[str], ufai: list[str], page: str, framing: str,
             story: str, stage: str, archetype: str, device: str, lang: str, tier: str, w4: dict) -> None:
        rows.append({
            "wave": WAVE, "title": f"{title} - {_short(page)} · {device} {lang}", "pages": list(pages),
            "layers": list(layers), "ufai": list(ufai), "persona": persona(page), "device": device,
            "entry": entry(page), "framing": framing, "story": story,
            "journey": {"archetype": archetype, "stage": stage, "vertical": vertical(page), "pair": "",
                        "language": lang, "moment": "present", "condition": "normal", "tier": tier,
                        "pages": list(pages)},
            "axis": {"device": device, "language": lang}, "w4": w4})

    record = ("; the per-step overlap/occlusion record is taken after every step, at rest and after its "
              "interaction, at this axis's width and language")
    action_cells: set = set()
    per_class_actions: Counter = Counter()
    for page in roster:
        acts = page_actions(page)
        per_class_actions[page_class(page)] += len(acts)
        for kind, subject in acts:
            layers = ACTION_LAYERS[kind]
            for lay in layers:
                action_cells.add((page, lay))
            pages = _path(_start(page), page, _effects(page, kind, subject, roots),
                          cast=_cast_of(persona(page)))
            fixture = UPLOAD_PAGES[page][0] if (kind == "upload" and page in UPLOAD_PAGES) else None
            story = (f"{persona(page)} arrives by {entry(page)}, reaches {_short(page)} through the platform's "
                     f"own navigation, {_verb(kind, subject, page)}, and follows the effect to its terminus "
                     f"across {' -> '.join(_short(p) for p in pages)}" + record
                     + (f"; the file is a real one found on the internet, downloaded once into "
                        f"{FIXTURES}/{fixture}/ with its provenance in manifest.json, uploaded in the journey "
                        f"and followed" if fixture else ""))
            w4 = {"kind": "action", "action": {"kind": kind, "subject": subject}}
            if fixture:
                w4["fixture"] = fixture
            for device, lang, tier in AXES:
                emit(f"Lived start to end: {_verb(kind, subject, page)}", pages, layers, ACTION_UFAI[kind],
                     page, "person", story, "acquire" if page_class(page) != "root" else "operate",
                     f"W4-action:{kind}", device, lang, tier, w4)

    for page in hub_hosts:
        pages = [page] + [s for s in NAV_HUB_STOPS if s != page][:3]
        story = (f"{persona(page)} opens #wh-hub-fab on {_short(page)}: the panel inside the viewport, each of "
                 "the six wh-hub-mode-btn modes, #wh-hub-global-search (type, #wh-hub-no-results, pick a "
                 "#wh-hub-tiles tile and arrive), #wh-hub-quick, #wh-hub-open-companion (neither panel nor fab "
                 "may cover the page's primary control; close returns focus), #wh-hub-open-feedback, "
                 "#wh-hub-assist-row, #wh-hub-conn-pill + #wh-hub-conn-detail with the offline queue count, "
                 "close - every control announced in the page's language; continues to "
                 f"{' -> '.join(_short(p) for p in pages[1:])}" + record)
        for device, lang, tier in AXES:
            emit("The whole nav-hub, every control, on this page", pages, NAV_HUB_LAYERS, NAV_HUB_UFAI, page,
                 "person", story, "operate", "W4-nav-hub", device, lang, tier, {"kind": "nav-hub", "host": page})

    layer_cells = [c for c in grid["not_lived"] if c not in action_cells]
    for page, lay in layer_cells:
        lens, ufai = LAYER_LENS[lay]
        pages = _path(_start(page), page, [], cast=_cast_of(persona(page)))
        story = (f"{persona(page)} lives layer {lay} on {_short(page)} start to end: "
                 f"{lens[0].lower() + lens[1:]}; provoked, observed and followed across "
                 f"{' -> '.join(_short(p) for p in pages)}" + record)
        for device, lang, tier in AXES:
            emit(f"{lens}, lived start to end", pages, [lay], ufai, page,
                 "person" if lay in PERSON_LAYERS else "contract", story, "maintain", f"W4-layer:{lay}",
                 device, lang, tier, {"kind": "layer", "layer": lay})

    plan.arithmetic = {                                        # type: ignore[attr-defined]
        "actions_by_class": dict(per_class_actions), "actions": sum(per_class_actions.values()),
        "nav_hub": len(hub_hosts),
        "grid": {k: v for k, v in grid.items() if k not in ("lived", "covered", "not_lived", "roster")},
        "layer_cells_not_lived": len(grid["not_lived"]), "layer_cells_deduped": len(layer_cells),
        "layer_by_class": dict(Counter(page_class(p) for p, _l in layer_cells)),
        "layer_by_layer": dict(Counter(lay for _p, lay in layer_cells)),
        "per_axis": sum(per_class_actions.values()) + len(hub_hosts) + len(layer_cells), "axes": len(AXES),
        "total": (sum(per_class_actions.values()) + len(hub_hosts) + len(layer_cells)) * len(AXES),
    }
    return rows


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


CONFUSIONS = ROOT / "w4_confusions.json"


def confusion_rows(existing: list[dict]) -> list[dict]:
    """★THE CONFUSION LEDGER BECOMES TRAJECTORIES (Ian, 2026-09-14: "even you sometimes confused like the sign
    in, that is why we have to have more trajectories, targeting that makes you confused, and work our way to
    improve it - it is the same way improving our UFAI UI UX platform wide"). Every entry in w4_confusions.json -
    a point where a walk hesitated, mis-clicked, waited without knowing, or read a sentence it could not act on -
    becomes one W4 row per axis (kind 'confusion'), lived start to end on the page where it was met. Entries
    already seeded (matched by confusion id in the row's w4 block) are skipped, so the ledger can grow and this
    can be re-run; rows are appended with the next ids and plan() replays them like every other W4 row."""
    if not CONFUSIONS.exists():
        return []
    ledger = json.loads(CONFUSIONS.read_text(encoding="utf-8"))
    seeded = {(t.get("w4") or {}).get("confusion") for t in existing if (t.get("w4") or {}).get("kind") == "confusion"}
    scoped = [t for t in existing if t.get("status") != "descoped"]
    persona_of = _persona_by_page(scoped)
    roots = served_pages()["root"]
    rows: list[dict] = []
    for e in ledger.get("entries", []):
        if e["id"] in seeded:
            continue
        # ★A RETRACTED ENTRY IS NOT A CONFUSION TO LIVE (C14, 2026-09-14): "FAB covered by the sticky CTA" was a walk
        # artifact (the hub stands down behind the sign-in modal by design; the walk had never signed in). The ledger
        # keeps the retraction as a record - seeding three rows to live a defect that does not exist would be a
        # manufactured target, and a walk could only ever "pass" them by finding nothing.
        if "retract" in str(e.get("status", "")).lower():
            continue
        page = e.get("host") or (e["page"] if e["page"].endswith(".html") else "achievements.html")
        component = e["page"] if e["page"].endswith(".js") else None
        persona = "anon" if page_class(page) != "root" else persona_of.get(page, "worker")
        pages = _path(_start(page), page, [], cast=_cast_of(persona))
        entry = "search-arrival" if page_class(page) != "root" else ("direct" if page == "index.html" else "hub-nav")
        idx = roots.index(page) if page in roots else 0
        short = _short(page) + (f" ({component})" if component else "")
        for device, lang, tier in AXES:
            rows.append({
                "wave": WAVE,
                "title": f"Lived start to end: the confusion {e['id']} ({e.get('kind', 'unclassified')}) at {short}: {e['confusion'][:72].rstrip()} - {_short(page)} · {device} {lang}",
                "pages": list(pages), "layers": list(e.get("layers") or ["F"]), "ufai": list(e.get("ufai") or ["U"]),
                "persona": persona, "device": device, "entry": entry, "framing": "person",
                "story": (f"{persona} meets, on {_short(page)}, the confusion the walk {e.get('walk', '?')} met on {e.get('seen', '?')}: "
                          f"{e['confusion']} The improvement it must live: {e.get('improvement', '?')} Walked start to end across "
                          f"{' -> '.join(_short(p) for p in pages)}; the per-step overlap/occlusion record is taken after every step at this axis"),
                "journey": {"archetype": f"W4-confusion:{e['id']}", "stage": "operate", "vertical": HIVES[idx % len(HIVES)] if page_class(page) == "root" else ANON_VERTICAL[page_class(page)],
                            "pair": "", "language": lang, "moment": "present", "condition": "normal", "tier": tier, "pages": list(pages)},
                "axis": {"device": device, "language": lang},
                "w4": {"kind": "confusion", "confusion": e["id"], "component": component, "improvement": e.get("improvement", "")},
            })
    return rows


# ★THE DESIGN LENSES BECOME TRAJECTORIES (Ian, 2026-09-15: "your own designing skills are all slop, AI Sloppiness so to
# speak ... we have to use them [the installed design skills and the Figma / Playwright / DevTools MCPs] as we move
# forward by to these trajectories and add more number of our trajectories" - and "use the existing roadmap for
# trajectories and update it", so these are wave-4 rows, kind 'design', appended like the confusion rows). One row
# per served page per applicable lens. A lens is a skill's own playbook applied LIVE through the MCPs at phone-390
# AND desktop-1280 in one batched round (Impeccable's verify rule); every finding is fixed through the craft floor,
# re-verified live, and the mechanical detector (impeccable detect --json) is clean on the page. One axis per row:
# wave 4's narrow-320 / Filipino rows already cover the fit axes, and the copy lens walks both languages itself.
# The order of LENSES is the order a page is walked: mechanical lenses first, so critique scores the FIXED page and
# the Figma frame captures it.
DESIGN_VIEWPORTS = ["phone-390", "desktop-1280"]
LENSES = OrderedDict([
    ("slop", {"ask": "no generic AI pattern survives on this page", "classes": ("root", "calc", "learn", "public"),
              "layers": ["F"], "ufai": ["U"], "languages": ["en"], "instrument": "playwright-mcp",
              "playbook": "redesign-existing-projects audit + design-taste-frontend banned patterns + impeccable craft-floor 'Refuse'",
              "closes": "every generic pattern fixed or brief-justified; impeccable detect --json reports 0 primary findings on the page and the shared chrome it loads"}),
    ("craft", {"ask": "type, spacing, contrast and depth meet the craft floor", "classes": ("root", "calc", "learn", "public"),
               "layers": ["F"], "ufai": ["U"], "languages": ["en"], "instrument": "playwright-mcp",
               "playbook": "impeccable craft-floor 'Verify': contrast >= 4.5:1, body measure 65-75ch, spacing rhythm, type ramp and weight steps, tabular numerals, real depth",
               "closes": "every Verify line measured green from computed styles at both viewports; detector --scope type,layout clean"}),
    ("audit", {"ask": "accessibility, performance, theming, responsiveness and implementation integrity each score 3 or better", "classes": ("root", "calc", "learn", "public"),
               "layers": ["F", "A"], "ufai": ["A", "U"], "languages": ["en"], "instrument": "playwright-mcp",
               "playbook": "impeccable audit.md - five dimensions scored 0-4 (a11y, performance, theming, responsive, implementation integrity) with Chrome DevTools for contrast, focus order, reduced motion, layout thrash",
               "closes": "every dimension >= 3 after the fix batch; scores before and after in the receipt"}),
    ("copy", {"ask": "every control names its action and every error names the problem and the way out, in English and Filipino", "classes": ("root", "calc", "learn", "public"),
              "layers": ["F", "CA"], "ufai": ["U"], "languages": ["en", "fil"], "instrument": "playwright-mcp",
              "playbook": "impeccable clarify.md (message hierarchy, actions, forms, errors, empty/loading/success states) + harden.md (text overflow, i18n, error handling, edge cases)",
              "closes": "every control, error and state correct in both languages; nothing overflows at 320 or 390"}),
    ("motion", {"ask": "every animation is justified, ease-out, under 300 ms, GPU-only, interruptible and honours reduced motion", "classes": ("root", "calc"),
                "layers": ["F"], "ufai": ["U"], "languages": ["en"], "instrument": "playwright-mcp",
                "playbook": "emil-design-eng + review-animations STANDARDS.md (ten non-negotiable standards) + find-animation-opportunities; figma-implement-motion when the comp carries motion",
                "closes": "0 standard violations measured on the page's transitions; one authored moment, not scattered effects"}),
    ("figma", {"ask": "the page's design source lives in Figma, built from the platform's own tokens and components, and agrees with the live page", "classes": ("root",),
               "layers": ["F"], "ufai": ["U"], "languages": ["en"], "instrument": "playwright-mcp + figma-mcp",
               "playbook": "figma-use + figma-generate-library (the --wh-* tokens as variables, the shared chrome as components, once) + figma-generate-design alongside generate_figma_design (the live page captured at both viewports into the same file); figma-design-to-code implements the comp",
               "closes": "the WorkHive Figma file holds the page at both viewports (node ids in the receipt), the tokens are variables, and get_screenshot of the frame agrees with the live capture after the other lenses' fixes"}),
    ("critique", {"ask": "a design director's review scores every Nielsen heuristic 3 or better and finds the page specific to this product", "classes": ("root",),
                  "layers": ["F"], "ufai": ["U"], "languages": ["en"], "instrument": "playwright-mcp",
                  "playbook": "impeccable critique.md - design specificity, ten heuristics scored 0-4, cognitive load, emotional journey; Assessment A (design review) and B (detector + browser evidence) as two isolated subagents",
                  "closes": "no heuristic below 3; priority issues fixed and re-scored; the critique snapshot persisted"}),
])


def design_rows(existing: list[dict]) -> list[dict]:
    """One W4 row per served page per applicable lens (kind 'design'), appended with the next ids; (page, lens)
    pairs already seeded are skipped so the lens table can grow and this can be re-run; plan() replays them."""
    seeded = {((t.get("w4") or {}).get("page"), (t.get("w4") or {}).get("lens"))
              for t in existing if (t.get("w4") or {}).get("kind") == "design"}
    scoped = [t for t in existing if t.get("status") != "descoped"]
    persona_of = _persona_by_page(scoped)
    classes = served_pages()
    roster = [p for cls in classes.values() for p in cls]
    rows: list[dict] = []
    arithmetic: dict = {"by_class": Counter(), "by_lens": Counter()}
    for page in roster:
        cls = page_class(page)
        persona = "anon" if cls != "root" else persona_of.get(page, "worker")
        pages = _path(_start(page), page, [], cast=_cast_of(persona))
        entry = "search-arrival" if cls != "root" else ("direct" if page == "index.html" else "hub-nav")
        idx = roster.index(page)
        vertical = ANON_VERTICAL[cls] if cls != "root" else HIVES[idx % len(HIVES)]
        for lens, L in LENSES.items():
            if cls not in L["classes"] or (page, lens) in seeded:
                continue
            arithmetic["by_class"][cls] += 1
            arithmetic["by_lens"][lens] += 1
            rows.append({
                "wave": WAVE,
                "title": f"Design lens {lens}: {L['ask']} - {_short(page)} · phone-390 en",
                "pages": list(pages), "layers": list(L["layers"]), "ufai": list(L["ufai"]),
                "persona": persona, "device": "phone-390", "entry": entry, "framing": "person",
                "story": (f"{persona} arrives by {entry}, reaches {_short(page)} through the platform's own navigation "
                          f"({' -> '.join(_short(p) for p in pages)}); the {lens} lens is applied live through the "
                          f"{L['instrument']} at {' and '.join(DESIGN_VIEWPORTS)} in one batched round ({L['playbook']}); "
                          f"every finding is fixed through the craft floor and re-verified live; it closes when {L['closes']}"),
                "journey": {"archetype": f"W4-design:{lens}", "stage": "acquire" if cls != "root" else "operate",
                            "vertical": vertical, "pair": "", "language": "en", "moment": "present",
                            "condition": "normal", "tier": "A", "pages": list(pages)},
                "axis": {"device": "phone-390", "language": "en"},
                "w4": {"kind": "design", "lens": lens, "page": page, "viewports": list(DESIGN_VIEWPORTS),
                       "languages": list(L["languages"]), "instrument": L["instrument"], "playbook": L["playbook"],
                       "closes": L["closes"]},
            })
    design_rows.arithmetic = arithmetic
    return rows


# ════════════════════════════════════════════════════════════════════════════════════════════
# LAYER-UX x PERSONA (Ian, 2026-09-30: "extend the numbers ... with this kind of deeper walk per
# every production page ... for different personas ... every Full Stack Architectural Layer").
#
# THE TWO GAPS, both measured from the registry rather than typed:
#   A - LAYER BREADTH. The LX wave exists for 6 of 13 layers (CI L LB H RL S). Seven layers -
#       F D A CA AU C AV - have no layer-UX wave at all.
#   B - PERSONA DEPTH. 289 of the 335 existing LX rows carry persona "any": the wave asks what A
#       PERSON feels when a layer misbehaves, never what THIS person feels. 45 of 156
#       (persona x layer) cells are empty, and assistive-tech sits on 1 of 13 layers.
#
# BOTH VIEWPORTS IN ONE ROW (Ian: "have you considered also the two viewports, the desktop and
# phone?"). The first draft of this seeder took one axis, reasoning that a persona's Auth or
# Caching experience does not change between 320px and 390px - true, and beside the point: those
# are two PHONE widths. At 1280 the Frontend layer is a different layout, and the personas split
# by device (oversight works at a desk; driver-worker is one-handed in a van). The registry shows
# the skew: desktop-1280 550 rows against phone-390 6,220 - under 9% desktop-class. So a row
# carries BOTH viewports and closes only when measured at both, which is exactly the convention
# DESIGN_VIEWPORTS already sets for the design lens. It costs no extra rows.
#
# The felt sentence per layer is NOT re-typed here: LAYER_LENS (seed_expansion_wave3) already
# carries one for all 13 layers plus its ufai dims, and the CA sentence there is the same one
# prove_w4_layer_ca.mjs walks. Re-typing it is how two vocabularies drift apart.
LX_PREFIX = "LXP"   # its own id space; LX1..LX335 belong to the original layer-UX wave
LX_VIEWPORTS = ["phone-390", "desktop-1280"]
LX_INSTRUMENT = "playwright-mcp + postgres-mcp"
# personas that can hold a session; "any"/"anon" are not persona-depth subjects
LX_SIGNED_IN = ["worker", "supervisor", "fleet-supervisor", "solo-owner", "driver-worker",
                "oversight", "buyer", "machine-client", "new-user", "returner",
                "assistive-tech", "adversary"]


def _lx_subject(t: dict) -> str | None:
    """The app surface a journey LANDS on - its last page. Calculators, learn articles and the
    public pages are not layer-UX subjects: they carry no session, so no persona x layer cell."""
    pages = t.get("pages") or []
    if not pages:
        return None
    subj = pages[-1]
    return subj if subj.endswith(".html") and "/" not in subj else None


def _lx_state(scoped: list[dict]) -> tuple[dict, set, list]:
    """Measured, from the registry: where each persona already goes, which (persona, layer) cells
    are already populated, and the app roster. Nothing here is a constant."""
    persona_pages: dict[str, set] = {}
    cells: set = set()
    roster: set = set()
    # ★THE PLAN MUST BE A PURE FUNCTION OF THE PRE-EXISTING PROGRAM (2026-09-30). These rows are what
    # FILLS the empty cells, so counting them here would close the gaps they were seeded to close and
    # the plan would shrink to zero the moment it ran. tools/validate_trajectory_registry.py derives
    # this wave's id range from plan() the way it does for every other wave, and a plan that changes
    # after seeding cannot be checked against the registry at all. Excluding our own kind keeps the
    # answer identical before and after the write.
    # ★AND THE TWO WAVES SEEDED AFTER IT ARE EXCLUDED FOR THE SAME REASON (2026-10-06). The layer floor (LXC) and
    # the LLM layer (LM) add persona journeys onto app pages and would add cells - and Gap B below is "the
    # persona x layer cells no row covers", so a new LXC row on a Gap-B cell would make the LXP REPLAY stop
    # generating that cell's rows and renumber every later LXP id. Excluding them keeps the replay identical
    # before and after they land; their own plans measure what they need directly.
    # ★AND THE BUG-HUNT WAVE (BRH, 2026-10-14), FOR THE SAME REASON - met the hard way: seeding its 237 rows made
    # the LXP replay expect a different wave for LXP159.. (a returner now "reached" pages only BRH had put them on),
    # and the registry gate failed on rows nobody had touched. A replay's INPUTS must not depend on the present.
    # ★AND THE THREE WAVES OF 2026-10-14 (SL sub-layers, ENH enhancements, OPC the operator console), for the same
    # reason a third time: SL alone puts 3,959 persona journeys onto 158 pages, and every one the LXP replay could see
    # would move a Gap-B cell and renumber the ids after it. Excluded BEFORE they were seeded, not after the gate reds.
    scoped = [t for t in scoped if (t.get("lx") or {}).get("kind") not in ("layer-ux", "layer-floor", "llm")
              and (t.get("brh") or {}).get("kind") != "bug-hunt"
              and not t.get("sl") and not t.get("enh") and not t.get("opc")]
    for t in scoped:
        # ★"REACHES" IS ANY APP PAGE ON THE JOURNEY, NOT ITS LAST ONE. _path() appends the platform's
        # own continuation until a journey spans four pages, so pages[-1] is where the route ENDS, not
        # what the row is about - which is why audit-log.html appears as the last page of 4,804 rows
        # (45% of the program) without 4,804 journeys being about audit-log. A persona demonstrably
        # reaches every app page on its route, so Gap B seeds against all of them.
        app = [x for x in (t.get("pages") or []) if x.endswith(".html") and "/" not in x]
        if not app:
            continue
        roster.update(app)
        p = t.get("persona")
        if p in LX_SIGNED_IN:
            persona_pages.setdefault(p, set()).update(app)
            for l in (t.get("layers") or []):
                cells.add((p, l))
    return persona_pages, cells, sorted(roster)


# ★NON-PRODUCTION SUBJECTS - NEVER SEED A PERSONA JOURNEY ONTO ONE (Ian, 2026-09-30: "why you are
# including the non-production pages in the trajectories?"). The scope was already written down in this
# function's own docstring quote - "every PRODUCTION page ... for different personas" - and violated
# anyway: the first seed took served_pages() wholesale and put 297 rows onto retired, admin-only and
# infrastructure surfaces. validate_auto_discovery.NON_TOOL_PAGES has named each of these for months, and
# is deliberately NOT reused verbatim here: it means "not a worker TOOL page", which also catches
# index.html, public-feed.html and the seller dashboard - all genuinely production. The three admin
# CONSOLES (founder-console, marketplace-admin, platform-actions) are likewise kept IN scope: Ian and
# platform staff use them daily and they hold live controls.
LX_NON_PRODUCTION = {
    "architecture.html",              # RETIRED 2026-05-13, archival, never in nav
    "symbol-gallery.html",            # RETIRED 2026-05-13, archival, never in nav
    "platform-health.html",           # retired Phase 7, deprecated banner only
    "llm-observability.html",         # admin/devops observability dashboard
    "agentic-rag-observability.html",  # admin-only Phase 8 observability dashboard
    "validator-catalog.html",         # admin/devops validator browser
    "status.html",                    # admin/devops local status page
    "design-system.html",             # internal reference (Ian 2026-07-17: "internal tool page, NOT family")
    "promo-poster.html",              # admin/marketing poster generator
    "offline-fallback.html",          # the service-worker offline shell; nobody navigates to it
    "voice-journal.html",             # untracked WIP companion, not a shipped tool page
}


def layer_ux_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One deep-walk row per (persona, layer, page), appended with the next free LX ids. Already
    seeded triples are skipped so the persona list and the layer table can grow and this can be
    re-run; plan() replays them.

    ★THE SCOPE FILTER APPLIES TO NEW ROWS ONLY, AND THAT ASYMMETRY IS LOAD-BEARING (2026-09-30).
    replay=True must keep reproducing the wave as it was FIRST SEEDED, including the 297 rows since
    descoped as non-production, because LXP ids are POSITIONAL: validate_trajectory_registry rebuilds
    them as LXP1..LXP<n> by enumerating this function's output, so dropping rows from the replay would
    renumber every later id and silently reattach banked evidence - LXP619 carries a real receipt - to a
    different trajectory. So replay answers "what was planned" (history, ids stable) while the forward
    path answers "what is in scope now" (production subjects only). The descoped rows keep their skip
    keys, so they are never re-created either way."""
    seeded = set() if replay else {
        ((t.get("lx") or {}).get("persona"), (t.get("lx") or {}).get("layer"),
         (t.get("lx") or {}).get("page"))
        for t in existing if (t.get("lx") or {}).get("kind") == "layer-ux"}
    # ★AND THE REPLAY'S *INPUTS* MUST BE WHOLE TOO, not only its output (2026-10-05). This line dropped descoped
    # rows unconditionally, which quietly contradicted the ★ note above: `scoped` feeds persona_pages / cells /
    # roster / have_lx, so descoping ANY row changes what the replay generates and therefore renumbers LXP ids.
    # Measured: descoping eight rows that targeted terms.html (a page that is not on disk and never was) renamed
    # LXP569's wave from LXP-AU to LXP-CA and failed the registry gate on rows nobody had touched. History cannot
    # be re-derived through a present-tense filter - on replay the input is every row that was there.
    scoped = existing if replay else [t for t in existing if t.get("status") != "descoped"]
    persona_pages, cells, roster = _lx_state(scoped)
    have_lx = {t["wave"].split("-", 1)[1] for t in scoped
               if str(t.get("wave", "")).startswith("LX-") and t["wave"].split("-", 1)[1] in LAYER_SET}
    missing_lx = [l for l in LAYER_SET if l not in have_lx]

    rows: list[dict] = []
    arithmetic = {"gap_a": Counter(), "gap_b": Counter()}
    # Forward path only - see the docstring's ★ note on why the replay must stay whole.
    out_of_scope = set() if replay else LX_NON_PRODUCTION

    def _row(persona: str, layer: str, page: str, gap: str) -> dict:
        ask, dims = LAYER_LENS[layer]
        pages = _path(_start(page), page, [], cast=_cast_of(persona))
        entry = "direct" if page == "index.html" else "hub-nav"
        vertical = HIVES[roster.index(page) % len(HIVES)]
        who = "a person" if persona == "any" else persona
        return {
            "wave": f"LXP-{layer}",
            "title": f"{ask} - {who} · {_short(page)}",
            "pages": list(pages),
            "layers": [layer],
            "ufai": list(dims),
            "persona": persona,
            "device": "any",                      # the row spans both viewports, so it is not one device
            "entry": entry,
            "framing": "person",
            "story": (f"{who} arrives by {entry} and reaches {_short(page)} through the platform's own "
                      f"navigation ({' -> '.join(_short(p) for p in pages)}), signed in as that persona; "
                      f"the {layer} layer is exercised live through the {LX_INSTRUMENT} at "
                      f"{' and '.join(LX_VIEWPORTS)} in one batched round, and the walk records what the "
                      f"PERSON experiences when it misbehaves, not whether the layer is internally "
                      f"correct; it closes when the row's ask is answered from the page itself at both "
                      f"viewports, with the database read as the witness where the layer writes"),
            "journey": {"archetype": f"LXP-{layer}:{persona}", "stage": "operate", "vertical": vertical,
                        "pair": "", "language": "en", "moment": "present", "condition": "normal",
                        "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "lx": {"kind": "layer-ux", "layer": layer, "persona": persona, "page": page, "gap": gap,
                   "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT, "ask": ask,
                   "closes": (f"the {layer} ask is answered from {_short(page)} itself at both viewports, "
                              f"as {who}, with a receipt naming the layer, the persona signed in, and "
                              f"steps at phone-390 AND desktop-1280")},
        }

    # GAP A - the seven layers with no LX wave at all, at the existing wave's own fidelity
    for layer in missing_lx:
        for page in roster:
            if ("any", layer, page) in seeded or page in out_of_scope:
                continue
            arithmetic["gap_a"][layer] += 1
            rows.append(_row("any", layer, page, "A-layer-breadth"))

    # GAP B - the empty (persona, layer) cells, only on pages that persona demonstrably reaches
    for persona in LX_SIGNED_IN:
        missing = [l for l in LAYER_SET if (persona, l) not in cells]
        for layer in missing:
            for page in sorted(persona_pages.get(persona, ())):
                if (persona, layer, page) in seeded or page in out_of_scope:
                    continue
                arithmetic["gap_b"][persona] += 1
                rows.append(_row(persona, layer, page, "B-persona-depth"))

    # ★EMITTED LAYER-MAJOR, so each LX-<layer> sub-wave owns a CONTIGUOUS id range. The gate builds
    # its expected id list wave by wave (validate_trajectory_registry: expected = T1..T500 + [i for w
    # in NAMED_WAVE_ORDER for i in NAMED_WAVES[w]]), so a plan that interleaves waves across the two
    # gaps produces ids the gate can never match - it read "ids are not exactly ... in order" on a
    # registry that was otherwise correct. The existing LX plan already emits layer-major for exactly
    # this reason; this sorts to the same contract. Stable within a layer: gap A before gap B, then
    # persona, then page.
    rows.sort(key=lambda r: (LAYER_SET.index(r["lx"]["layer"]), r["lx"]["gap"],
                             r["lx"]["persona"], r["lx"]["page"]))
    layer_ux_rows.arithmetic = arithmetic
    return rows


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# BRP · THE BUG-REPRO WAVE (Ian, 2026-10-04)
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# Ian: "we have to expand and extend the number of trajectories in our roadmap, where we have to bug
# reproduced and fix, so that it would improve the entire Full Stack SaaS Layers and its UFAI UI UX for
# my entire platform."
#
# A bug-repro trajectory is NOT "go look at page X". Every row names ONE concrete site, the MECHANISM
# that makes it wrong, a REPRODUCTION that can be made to fail on demand, and the FIX. Its size is
# derived from tools/bug_repro_inventory.py, which measures the real source against the real schema -
# never typed, never invented, and nothing seeds a row unless it can be measured.
#
# THE WAVE OPENS ON THE CLASS IAN HIT HIMSELF. On 2026-10-04 the logbook's "select an asset" was empty
# while Asset Hub showed the same assets. One scoped ownership by worker_name (a localStorage display
# string), the other by auth_uid. bind_asset_nodes_submitter() ALWAYS binds auth_uid but only overwrites
# worker_name when a hive_members row matches on hive_id = NEW.hive_id - never true for a personal asset
# (hive_id NULL) - so the name is frozen at whatever the client sent while the uid stays correct forever.
# Fixed, gated (logbook-asset-picker-identity), and then the sweep found the same shape at 84 more sites.
BRP_PREFIX = "BRP"
BRP_CLASS = {
    "A": ("AU", "returner",
          "ownership asked by DISPLAY NAME where the table carries auth_uid",
          "drift the signed-in display name by one character and the person's own rows vanish from this "
          "surface while a surface that scopes on auth_uid still shows them",
          "union the auth_uid query in beside the name query - never swap, because rows whose auth_uid "
          "was never bound (service-role and seeded inserts) are findable only by name"),
    "B": ("D", "any",
          "the truth VIEW drops the auth_uid its BASE table carries",
          "no consumer of this view can ask the ownership question correctly at all: select auth_uid "
          "from the view and it is not there, while the base table has it",
          "add auth_uid to the view (keeping security_invoker and the column grants intact), then scope "
          "every consumer on it - one view fixes every reader at once"),
    "C": ("D", "any",
          "no identity column anywhere on the relation",
          "ownership is only ever expressible as a name, so there is nothing correct to scope on - the "
          "repro is the schema read itself",
          "a migration adding auth_uid (bound by trigger on insert, like asset_nodes) before the "
          "client-side fix is even sayable"),
}


def bug_repro_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per MEASURED defect site, from tools/bug_repro_inventory.collect().

    Skip key is (cls, page, line, table) so the inventory can grow and this can be re-run. replay=True
    returns the full planned set, for the same reason layer_ux_rows does: the registry validator rebuilds
    BRP ids POSITIONALLY by enumerating this function, so dropping rows from the replay would renumber
    every later id and reattach banked evidence to a different trajectory.
    """
    # ★REPLAY READS THE REGISTRY, NOT THE WORLD (2026-10-04, and the gate caught this within the hour).
    # The first version re-ran collect() for replay=True, the way layer_ux_rows replays its own plan. That
    # is safe there because the LXP plan derives from the REGISTRY's persona x layer gaps, which do not
    # move when a bug is fixed. A BRP plan derives from live SOURCE and live SCHEMA - so the moment
    # migration 20261004000001 gave the truth views their auth_uid, sites that had been class B became
    # class A, the class-major ordering shifted, and every positional id after the first reclassified site
    # pointed at a different trajectory: "FAIL BRP55: wave BRP-B != declared named wave BRP-A". A wave
    # whose ids renumber themselves every time the platform IMPROVES is unusable - banked evidence would
    # silently reattach to another row. So replay is ANCHORED to what was actually seeded, in id order,
    # and the registry is the record. Discovery still measures live, through the forward path below.
    if replay:
        out = []
        for t in sorted((x for x in existing if (x.get("brp") or {}).get("kind") == "bug-repro"),
                        key=lambda x: int(str(x["id"])[len(BRP_PREFIX):] or 0)):
            out.append({"wave": t["wave"], "brp": t["brp"]})
        bug_repro_rows.arithmetic = {c: sum(1 for r in out if r["brp"]["cls"] == c)
                                     for c in ("A", "B", "C")}
        return out

    # ★THE SKIP KEY IS CLASS-AGNOSTIC, because a site's CLASS MOVES AS THE PLATFORM IS FIXED. It was
    # (cls, page, line, table) for one run, and the moment the truth views gained auth_uid the 21 class-B
    # sites re-measured as class A at the same (page, line, table) - so the forward path reported 19 of
    # them as NEW and would have seeded a second row for a site that already had one. A site is the same
    # site whichever class it currently falls in; the class is a property of the world right now, not an
    # identity. A row whose class has since moved is not re-seeded, and the walk sees the real state.
    # ★A SITE'S IDENTITY IS NOT ITS LINE NUMBER (2026-10-04). The skip key was
    # (page, line, table), and every fix in this wave adds an explanatory comment - which pushes every
    # LATER site in that file down. After one page was fixed the dry-run offered 16 "new" rows that were
    # all already-seeded sites wearing new line numbers, and seeding them would have duplicated the wave.
    # So the key is (page, table) plus the ORDINAL of that pair, which survives comment insertion. The
    # ordinal is derived by COUNTING existing rows per (page, table) rather than stored on them, so this
    # needs no migration of the 80 rows already written: iterate the measured sites in the same stable
    # order collect() emits and spend one unit of budget per existing row.
    from collections import Counter as _Counter
    budget = _Counter()
    for t in existing:
        b = t.get("brp") or {}
        if b.get("kind") == "bug-repro":
            budget[(b.get("page"), b.get("table"))] += 1

    from bug_repro_inventory import collect
    sites = collect()

    rows: list[dict] = []
    for s in sites:
        cls, page, line, table = s["cls"], s["page"], s["line"], s["table"]
        if budget[(page, table)] > 0:
            budget[(page, table)] -= 1          # this measured site is already carried by an existing row
            continue
        layer, persona, mech, repro, fix = BRP_CLASS[cls]
        pages = _path(_start(page), page, [], cast=_cast_of(persona))
        who = "a person" if persona == "any" else persona
        rows.append({
            "wave": f"BRP-{cls}",
            "title": (f"{mech} - {_short(page)}:{line} reads {table} - {who}"),
            "pages": list(pages),
            "layers": [layer],
            "ufai": list(LAYER_LENS[layer][1]),
            "persona": persona,
            "device": "any",
            "entry": "direct" if page == "index.html" else "hub-nav",
            "framing": "person",
            "story": (f"{who} reaches {_short(page)} and the surface asks the wrong question about who "
                      f"owns the rows it shows: {_short(page)}:{line} filters {table} on worker_name. "
                      f"MECHANISM: {mech}. REPRO: {repro}. FIX: {fix}. The row closes only when the "
                      f"reproduction is made to FAIL on demand and a gate holds the fix, measured at "
                      f"{' and '.join(LX_VIEWPORTS)}"),
            "journey": {"archetype": f"BRP-{cls}:{persona}", "stage": "operate",
                        "vertical": HIVES[line % len(HIVES)], "pair": "", "language": "en",
                        "moment": "present", "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "brp": {"kind": "bug-repro", "cls": cls, "page": page, "line": line, "table": table,
                    "relation_kind": s.get("kind"), "base_table": s.get("base_table"),
                    "bound_to": s.get("bound_to"), "layer": layer, "persona": persona,
                    "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                    "mechanism": mech, "repro": repro, "fix": fix,
                    "closes": (f"the reproduction is demonstrated FAILING on demand, the fix lands, and a "
                               f"registered gate reddens when the fix is reverted (mutation-verified) - "
                               f"not merely 'the page looks right now'")},
        })
    # Class-major so each BRP-<cls> sub-wave owns a CONTIGUOUS id range; the gate builds its expected id
    # list wave by wave and a plan that interleaves classes produces ids it can never match.
    rows.sort(key=lambda r: (r["brp"]["cls"], r["brp"]["page"], r["brp"]["line"]))
    bug_repro_rows.arithmetic = {c: sum(1 for r in rows if r["brp"]["cls"] == c) for c in ("A", "B", "C")}
    return rows


# ════════════════════════════════════════════════════════
# LXC · THE PERSONA x LAYER FLOOR (Ian, 2026-10-06)
# ════════════════════════════════════════════════════════
# Ian: "then you have to decide, which layers we have to make more trajectories on top of our trajectories
# roadmap". Every layer had passed its 90-row target 7-50x, so the weakness was never the layer's SIZE - it was the
# persona x layer CELLS: the supervisor held 2 rows on Logs, 3 on Security, 5 on Auth; driver-worker 1 on
# Availability. LXC seeds each signed-in persona's thin cell up to LXC_FLOOR, on pages that persona already reaches
# and that are not yet seeded for the cell.
#
# ★ITS OWN ID SPACE, NOT A GAP C INSIDE layer_ux_rows (decided while building it). layer_ux_rows emits LAYER-MAJOR
# and the validator rebuilds LXP ids POSITIONALLY from its replay - rows added to layer F's block would shift every
# D/A/CA/... id after it, which is the ★×16 trap this repo has hit twice. So: LXC1.., waves LXC-<layer>, appended
# BRH · THE BUG-HUNT WAVE (Ian, 2026-10-14): "expand and extend the numbers of our trajectories roadmap to hunt and
# sort out bugs, painpoints, gaps, defects ... anything that affects my platform ... the same flow that we use MCP walk,
# with open and closed. I will let you decide the numbers of trajectories first." The number is MEASURED by
# tools/bug_hunt_inventory.py: seven defect classes met in a real person's hands on 2026-10-13/14 (Ian's missing
# logbook assets and what the MCP journey of his phone found behind them), generalised to every production page
# against the real source and the committed evidence artifacts - never typed. Its own id space (BRH1..), class-major,
# with a replay ANCHORED to the registry so a class can shrink as sites are fixed without renumbering a row.
BRH_PREFIX = "BRH"
BRH_CLASS = {
    "D": ("H", "returner",
          "version skew silenced by a typeof guard: the page calls utils.js functions it does not insist on",
          "serve yesterday's utils.js to the page's <script src> (the hour a cached script outlived a deploy) and "
          "every guarded call silently does nothing - no restore, no error, a wrong default rendered as fact",
          "the page detects a shared function it depends on is missing, fetches utils.js past the HTTP cache and "
          "reloads once per tab (the logbook pattern), or stops guarding what it requires"),
    "E": ("F", "solo-owner",
          "an empty state that does not say which list it is",
          "with no hive stored on the device and no personal rows, the page reads 'No X yet.' while the hive holds "
          "X - the person cannot tell the personal list from the hive's, nor how to get to the hive's",
          "the empty state names its scope (personal vs hive) and offers the other list - 'Show my hive's X' re-seats "
          "the hive from the account (whEnsureHiveContext)"),
    "F": ("AU", "supervisor",
          "a stored role trusted without re-validation",
          "demote the signed-in supervisor on the server (hive_members.role = worker); the page still renders the "
          "supervisor controls from localStorage wh_hive_role, and a write through them is refused by RLS with no "
          "honest sentence",
          "re-validate the role against the membership row (by auth_uid) before gating any control on it, the way "
          "logbook/asset-hub/pm-scheduler already do, and write the corrected role back"),
    "G": ("D", "returner",
          "a stored hive name that is never reconciled",
          "rename the hive from another device; this page keeps showing the old name in its chrome and board title "
          "for as long as the device keeps wh_hive_name",
          "call whReconcileHiveName(db) once on load (it exists in utils.js) and repaint what shows the name"),
    "H": ("F", "returner",
          "the hive is restored by a reload instead of in the page's own start-up",
          "delete the stored hive, open the page directly: it renders in personal mode first, then utils.js "
          "whHiveRecovery seats the hive and reloads - a flash of the wrong view and a double load on every such visit",
          "call whEnsureHiveContext(db) in the page's start-up before its first hive-scoped read and set "
          "window.WH_SEATS_HIVE_ITSELF (the logbook/asset-hub pattern); hive-restore-adoption counts the adopters"),
    "J": ("F", "any",
          "a live-as-a-user journey that is not live",
          "run `node tools/live_page_journeys.mjs --journey <id>`: a lens the journey promises fails on the real page",
          "fix the page (or, if the journey's premise went stale on purpose, the journey - by the page's own rule), "
          "then re-run it alone and fold it into the sweep with tools/fold_journey_rerun.py; live-page-journeys ratchets"),
    "K": ("F", "any",
          "design slop the detector ratchet still holds",
          "run `impeccable detect --json <file>`: the (file :: antipattern) pair reports the count the baseline holds",
          "fix every finding of that antipattern in that file by the craft floor and DESIGN.md, verify at 320/390/1280, "
          "then `prove_design_detector_ratchet.py --rebase` writes the lower count; the pair closes at zero"),
    # ...and three more, from what Ian pointed out on 2026-10-14 (§BRH.2), measured the same way
    "L": ("AU", "worker",
          "a control offered to a person the page behind it refuses",
          "sign in as a person the destination refuses (a worker for a supervisors-only page, anyone but a platform "
          "admin for a founder page) and open the page: the link, nav entry or search result is there, and tapping it "
          "lands on 'Supervisors only' or an admin refusal - the product offered a door it then shuts in their face",
          "show the control only to the people the destination admits, decided from the verified account (the role "
          "re-read from hive_members, isPlatformAdmin) - never from a remembered role or a chosen nav mode - through "
          "one shared rule the chrome applies, so a new link to a gated page cannot skip it"),
    "M": ("AU", "returner",
          "copy that says two contradictory things about who the person is",
          "leave a display name on the device (wh_last_worker) and open the page three ways - session expired with its "
          "refresh refused, signed out, signed in: no sentence may call the person by name as if they were working "
          "while another says they are not signed in, and nothing may tell a signed-in person to sign in",
          "every identity sentence reads the verified session (restoreIdentityFromSession); the remembered name only "
          "says WHO to sign in as ('Your session ended. Sign in to continue as Jun.'), and a signed-out page shows one "
          "state, not two"),
    "N": ("H", "oversight",
          "a file every deployment stores that the site never serves",
          "compare what the deployment uploads (the git tree minus .vercelignore) with what the site's pages, scripts, "
          "stylesheets, precache list and manifest request: the kind ships files no one asks for, every deployment "
          "stores another copy against the 10 GB allowance, and production serves them on request (curl -I -> 200)",
          ".vercelignore is an allowlist of what the site serves and deploy-payload holds it (a requested file left "
          "out, a development artifact shipped, or the payload over budget fails); after the deploy the probe answers "
          "404"),
    # ...and ten more, from Supabase's two emails of 2026-10-20 (§BRH.8), measured from production's own advisor and
    # schema (supabase_advisor_evidence.json). Each row is an API probe made as the person the defect exposes, walked by
    # platform staff from the home (N's precedent); a production fix closes on the advisor's re-read after Ian's push.
    "P": ("S", "oversight",
          "a public table anyone holding the public key can read, because row-level security is off",
          "with only the site's public (anon) key, GET /rest/v1/<table>?select=* - every row comes back; the advisor's "
          "rls_disabled_in_public names the table",
          "enable row-level security with a policy that admits exactly the readers the product needs (a public SELECT "
          "for reference data a signed-out page reads, the hive's members, or nobody for a server-only table the service "
          "role reads past RLS), revoke what no reader uses, and hold every public table to RLS on"),
    "Q": ("S", "oversight",
          "an object production holds that no migration creates",
          "diff production's schema fingerprint against the migrations: the object exists only in production, so no "
          "review, gate or local walk ever saw it (debug_definer_all_workers() handed anyone the top ten workers' names "
          "and account ids)",
          "drop it by migration, every overload by name, or adopt it into a migration if the product needs it; a drift "
          "check compares production's fingerprint with the migrations before a push"),
    "R": ("S", "oversight",
          "a view that runs as its owner, past the reader's row policies",
          "as anon, or as a member of another hive, select from the view: it returns rows the base tables' policies "
          "refuse that reader, because a SECURITY DEFINER view checks only its owner's rights",
          "security_invoker = true with base-table policies that admit what the view is meant to show (or the projection "
          "moved into a function that checks its caller); the advisor's security_definer_view reads zero"),
    "S": ("S", "oversight",
          "a SECURITY DEFINER function anyone may execute, whose body checks no caller",
          "with only the public key, POST /rest/v1/rpc/<function>: it runs as its owner, past every policy, for a caller "
          "it never asks about (enqueue_user_push queued a Web Push to any account with any link; "
          "consume_ai_global_budget spent the platform's daily AI budget)",
          "revoke EXECUTE from PUBLIC, anon and authenticated where only the service role or another definer calls it; "
          "where a signed-out page genuinely needs it, prove it returns only public facts and keep it; a gate holds every "
          "anon-executable definer function to a declared reason"),
    "T": ("S", "oversight",
          "a function whose search_path the caller can change",
          "the advisor's function_search_path_mutable names it: its unqualified names resolve through the caller's "
          "search_path, so an object the caller can create (a temporary table or function) can stand in for the one the "
          "body means",
          "pin it (ALTER FUNCTION ... SET search_path = '' with every name schema-qualified, or = public, pg_temp), then "
          "call it once to prove the body still resolves; the advisor reads zero"),
    "U": ("S", "oversight",
          "an extension installed in the public schema",
          "the advisor's extension_in_public names it: its functions and types sit beside the API's own objects in the "
          "schema PostgREST exposes",
          "move it to the extensions schema (ALTER EXTENSION ... SET SCHEMA extensions) with every reference to its types "
          "updated, proven on a replay of the schema - or record why it must stay"),
    "V": ("S", "oversight",
          "a materialized view the API serves past every row policy",
          "a materialized view cannot carry row-level security: as a member of one hive (and, until 2026-10-21, as anon), "
          "select it with another hive's id - that hive's figures come back",
          "revoke SELECT from anon and authenticated, serve each hive its own rows through a function that checks "
          "membership (user_can_access_hive), and point the page's read at it"),
    "W": ("S", "oversight",
          "sign-up and password change accept passwords known to be leaked",
          "the advisor's auth_leaked_password_protection: Supabase Auth's check against breached-password lists is off, "
          "so a password from a public breach is accepted at sign-up and on a password change",
          "on the free plan (Supabase's own check is a Pro feature, and the platform stays free): the page that sets a "
          "password asks the Pwned Passwords range API before it sends one - only the first 5 characters of the "
          "password's SHA-1 leave the browser - under a CSP and a service worker that let it through "
          "(gate breached-password-check)"),
    "X": ("CI", "oversight",
          "API access that rests on Supabase's automatic grant, which stops on 2026-10-30",
          "replay the schema with the automatic grant off - what a local supabase db reset, a preview branch or a new "
          "project gets from 2026-10-30 - and read the objects as the role: 'permission denied'",
          "a migration that grants the role what it holds today, explicitly, object by object (generated from the live "
          "ACL, revokes included), and a gate that every new public table or view carries its own GRANT in the migration "
          "that creates it"),
    "Y": ("S", "oversight",
          "a revoke a migration meant, which does not hold",
          "has_function_privilege('anon', <function>, 'execute') is true although a migration revoked it - Supabase "
          "grants EXECUTE to anon explicitly on every new function, so 'revoke ... from public' never reaches it, and "
          "DROP + CREATE restores the defaults (enqueue_user_push, open in production from 2026-09-01)",
          "revoke from anon (and authenticated where the migration meant it) explicitly, every overload by name; a gate "
          "holds every function a migration closed to anon closed, including after a re-creation"),
    # ...and six more, from Ian's 2026-10-21 message (§BRH.9): "my platform always free ... I am not upgrading to pro".
    # Measured in free_plan_evidence.json from the public repository's deployment record, production (read-only, through
    # the Supabase connector) and the local tree. Every fix stays on the free plans - no paid feature is a fix.
    "Z": ("H", "oversight",
          "deployments that outgrow the free plan's 10 GB of Deployment Storage",
          "count the deployments Vercel recorded on the repository and what each build uploads: the denylist "
          ".vercelignore uploaded 612.7 MB a build for a 19.5 MB site, Hobby keeps the newest production builds, and "
          "the allowance read 70-75% of 10 GB",
          "the allowlist .vercelignore (19.7 MB a build) shipped, so the protected builds are the small kind; a second "
          "project that builds the same repository removed; and a gate that bounds what every build uploads times the "
          "builds Hobby keeps under a tenth of the allowance"),
    "AA": ("RL", "oversight",
           "a table that grows with every use and that nothing ever purges",
           "read the table's insert and delete counters and the scheduled jobs: rows arrive with every use, none leave, "
           "and the free plan's 500 MB database fills (cron.job_run_details: 77 MB, 443,228 runs, ~5,800 a day)",
           "a scheduled purge (pg_cron, free) with a window the platform states - operational history a week, telemetry "
           "90 days - never an audit trail's stated window; and a gate that every operational table has its purge"),
    "AB": ("RL", "worker",
           "a photo stored inside a table row as base64 text",
           "read the column: data:image/... text in the row, so the database grows by every photo and every list read "
           "of the row ships every photo in free egress (logbook 22 photos, 4.35 MB; 23 list reads on 7 pages)",
           "photos stored in Supabase Storage (1 GB free), compressed before upload, the row keeping only the object's "
           "path; list reads select a thumbnail path, never the image; the stored rows moved once and checked"),
    "AC": ("AV", "oversight",
           "the AI's reference corpus or its embeddings missing in production",
           "count production's knowledge tables against the corpus the AI is built and tested on: standards and "
           "persona knowledge are empty there, and the embedding outbox fills with no relay draining it",
           "the reference corpora loaded into production with their embeddings, a relay that drains the outbox on free "
           "infrastructure (a scheduled edge function), the backlog embedded, and a check that production's corpus "
           "matches what the AI expects"),
    "AD": ("A", "worker",
           "a page that calls a function production refuses its caller",
           "as a signed-in member, call the function the page calls: production refuses it (authenticated has no "
           "EXECUTE), so the page falls back on every load without saying so",
           "the page asks what production lets its reader ask (a function that answers for the reader's own hive, or "
           "the stored figure), and a gate compares every function a page calls with what production grants its reader"),
    "AE": ("A", "oversight",
           "a free-plan gap the platform covers with nothing",
           "read the free plan: Supabase Free keeps no daily backups and pauses a project after 7 days of low activity",
           "a free substitute that runs on its own: a scheduled dump of the database to storage the owner keeps "
           "(backups), and a scheduled request that keeps the project active (pausing) - each proven by its own run"),
    # AF..AL - what the 2026-10-24 release left open (Ian, 2026-10-24: "be proactive ... make a necessary and
    # appropriate number of trajectories"), measured by tools/release_followup_evidence.py
    "AF": ("CI", "oversight",
           "a post-deploy check that cannot reach the signed-in product on production",
           "run the post-deploy smoke's signed-in tier after a deploy: production has no account it can sign in with, "
           "and the instrument seeds a local hive, worker and role into storage instead of asking the server",
           "a production smoke identity - an account and its own bench hive holding no tenant's data, credentials only "
           "in .env - and a smoke that reads the account's hive and role from the server after sign-in and refuses to "
           "act outside the bench hive"),
    "AG": ("CI", "supervisor",
           "a page never seen signed in on production after a deploy",
           "after a deploy, open the page on production signed in as a member: the public tier walks the sitemap and "
           "the signed-in tier has never run, so a page whose script throws for a member ships unseen",
           "the post-deploy smoke opens the page on production as the bench hive's supervisor after every deploy - its "
           "own UI drawn, not thin, not signed out, no page error - and the deploy's runbook entry records the result"),
    "AH": ("CI", "supervisor",
           "a critical path never walked on production after a deploy",
           "after a deploy, sign in, save a logbook entry, ask the AI, double-tap a parts reservation and read the logs "
           "on production: the runbook's Tier 0 is manual and was not run for the 2026-10-24 deploy",
           "the flow walked on production in the bench hive after every deploy, its writes undone, and its receipt in "
           "the deploy's runbook entry"),
    "AI": ("D", "supervisor",
           "a breakdown cause the analytics cannot group: free text beside the form's list",
           "record one breakdown by voice and one by the form with the same cause on the same machine: the voice entry "
           "keeps the cause as said, analytics groups root_cause by its exact text, so the repeat is never counted, the "
           "Pareto splits one cause into two bars and the multi-symptom scan counts two causes",
           "every writer stores a cause from the form's list and keeps what was said beside it; repeat failures, the "
           "Pareto and the failure-signature scan group by the listed cause; stored free-text causes are given theirs, "
           "locally and in production; a gate holds every writer and every grouping to the list"),
    "AJ": ("CI", "oversight",
           "an adoption census that credits a lookalike class",
           "give a page only heat-tile, pulse-card or stat-pill: the census credits it as a .tile, .card or .pill "
           "adopter, because its matcher treats '-' as a word edge - the floor counts pages that never used the "
           "component",
           "the census matches class tokens exactly, each lowered floor named with the pages that were never adopters, "
           "and each such page either converges on the canonical component or is recorded as a justified bespoke "
           "container"),
    "AK": ("D", "oversight",
           "free credit the solvency check does not hold to its policy",
           "issue a starter grant twice to one seller, above the knob, or to an unverified seller: the solvency gate's "
           "one rule (vouchers <= revenue) never reads starter_grant, and the console's cover shows 0.00x with no reason",
           "the solvency gate holds every starter grant to its policy - once per verified seller, the knob's amount, "
           "inside the supply cap - and the console splits what is owed by its backing (top-ups, free starter credit), "
           "so a low cover reads with its reason"),
    "AL": ("A", "worker",
           "a release that shipped ahead of its data move",
           "on production after the 2026-10-24 deploy, open a logbook entry or part that has a photo: the pages read "
           "only the stored path and the copy pass has not run, so the photo shows nothing",
           "the owner's copy pass run on production (photos to Storage, compared byte for byte, the inline text kept), "
           "every moved photo seen on its page, then --clear; and a deploy gate that names any data move a release's "
           "pages depend on and refuses the push until production shows it done"),
    # ...and two Ian met in his own hands on 2026-10-26 (§BRH.11): "users should have something icon where they can
    # just click or tap to easily install it" / "when you put it at the top, all of it is being swallowed at the top"
    "AM": ("F", "worker",
           "an install icon a person cannot find",
           "open the page on a phone and on a desktop, signed in, with the app not installed: nothing at rest offers to "
           "put WorkHive on the home screen - the landing's one button is hidden below md and waits for "
           "beforeinstallprompt, which iOS never fires; the manifest's icons are one 640x640 transparent PNG declared "
           "192 and 512 and maskable, the apple-touch-icon is not square",
           "an install control visible at rest on every hub host (the hub's assist row, and the landing hero at phone "
           "width) that acts per platform - Chromium: the deferred prompt; iOS WebKit: the Share -> Add to Home Screen "
           "steps with the icon shown; desktop: install - and hides itself under display-mode: standalone; true 192, "
           "512, maskable and 180 renditions cut from the 1024 source; a standalone start that lands a signed-in person "
           "at their home; measured at phone-390 chromium, desktop-1280 chromium and phone-390 webkit"),
    "AN": ("F", "returner",
           "the hub's panel opens where a person cannot see it",
           "open the hub where the FAB rests, then drag the FAB to the top of the screen and open it again, at 390 in "
           "WebKit and Chromium: the panel grows upward from a bottom anchor and never flips, nothing reads the top "
           "safe-area inset, the stored position is clamped once at load and never on resize - so the opened panel's "
           "body sits above the viewport with a sliver showing, and iOS's collapsing toolbar moves the goalposts",
           "one change in nav-hub.js: the panel flips below the FAB when the FAB is in the top half (or re-anchors), "
           "the top clamp reads env(safe-area-inset-top), the stored position is re-clamped on resize; held by a gate "
           "(hub-panel-on-screen: a planted top-anchored FAB must open a panel wholly inside the viewport whose header "
           "hit-tests to itself), walked on every host at 390 WebKit and Chromium and 1280"),
    # ...and one the OWN AI failure-mode lens left measured on 2026-10-26/27 (§OWN): the companion's browser assembles a
    # prompt that only an unread field and a cache that always throws ever receive
    "AO": ("AV", "worker",
           "a client assembly no reader reads",
           "ask the companion one question with the network panel open: before the ai-gateway call the browser runs the "
           "full platform snapshot, the scraper function, recent memory, cross-hive context, the glossary and the "
           "canonical-data read, builds a system prompt from them and sends it as context.platform_prompt - which no "
           "edge function reads - then hands the same block to _cacheOfflineSnapshot, which JSON.parses text, throws "
           "and inserts nothing into a table nothing reads",
           "remove the per-turn reads whose only consumer is the unread prompt (or move what the reply genuinely needs "
           "server-side, as the documents/standards/facts were), drop the offline cache that cannot write, update the "
           "six gates that assert the wiring (offline-resilience-phase6, voice-canonical-anchor, voice-companion-phase1, "
           "memory-integrity, dialog-followup-handlers, agent-memory-persist) to assert what reaches the model instead; "
           "measured: time and requests before the gateway call, before and after, at 390 and 1280"),
    # ...and what removing AO exposed (2026-10-27): the ~60 per-turn steering anchors the companion builds go nowhere
    "AP": ("AV", "worker",
           "steering the companion never receives",
           "say the trigger to the voice companion (e.g. 'Tagalog na', 'mas maikli', 'magtatrabaho ako sa live panel') with "
           "the network panel open: the detector fires and appends its instruction to perTurnAnchors, and no request carries "
           "it - ai-gateway builds the voice-journal prompt from the transcript alone, so the reply ignores the instruction "
           "(the language stays, the length stays, the safety gate is never stated)",
           "decide per anchor, with a default: a behaviour the MODEL must apply moves server-side - the gateway detects it "
           "from the transcript and adds the instruction to the system prompt it builds (safety gates first: LOTO, hot work, "
           "confined space, PPE, crisis); a behaviour the PAGE applies (a timer, a share link, an erasure) keeps its client "
           "action and drops the dead instruction; a claim with neither is removed with its detector. Proven by a walk that "
           "says the trigger and reads the reply, and a gate that fails when the anchor is again built and sent nowhere"),
}


# the page a person meets a shared script's code on (a BRH site whose `page` is a script, not a page)
SCRIPT_HOST = {"voice-handler.js": "hive.html", "nav-hub.js": "index.html", "utils.js": "index.html"}


def _gate_checked_cast(page: str, candidates: list[str]) -> str:
    """The first candidate whose own route to `page` the journey-paths gate accepts - sublayer_inventory.casts' rule,
    for one page: the seeder and the gate cannot disagree about who may walk a row. The gate's link graph and hub
    readers are built once per seeding run."""
    import check_journey_paths as cjp
    memo = _gate_checked_cast.__dict__
    if "links" not in memo:
        memo["links"] = cjp.link_graph()
        memo["offered"], memo["parented"] = cjp.hub_offered_and_parented()
    paths = {f"{page}|{p}": _path(_start(page), page, [], cast=_cast_of(p)) for p in candidates}
    bad = {a for a, *_r in cjp.role_blocked_hops(paths, {k: _cast_of(k.split("|")[1]) for k in paths}, memo["links"])}
    bad |= {a for a, *_r in cjp.broken_hops(paths, memo["offered"], memo["parented"], memo["links"])}
    return next((p for p in candidates if f"{page}|{p}" not in bad), candidates[0])


# ★A ONE-ROW-PER-PAGE CLASS IS CARRIED BY ITS PAGE, NOT ITS KEY (2026-10-14, §BRH.2). D's key is the guard COUNT
# ('17 guards'), so a page whose count moved looked like a new site and the first re-measure offered nine duplicate
# D rows. D, F, G and H are one row per page by construction; L (per control), M (per page, constant key), N (per
# kind) and E/J/K (per string, journey, pair) keep their keys.
BRH_PER_PAGE = {"D", "F", "G", "H"}


def _brh_carry(cls, page, key):
    return (cls, page) if cls in BRH_PER_PAGE else (cls, page, key)


def bug_hunt_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per MEASURED defect site, from tools/bug_hunt_inventory.collect(). replay=True returns what was SEEDED,
    in id order, from the registry's own brh metadata - the record, so a fixed site vanishing from the inventory
    never renumbers a banked row (the BRP/LXC rule)."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("brh") or {}).get("kind") == "bug-hunt"),
                        key=lambda x: int(str(x["id"])[len(BRH_PREFIX):] or 0))
        bug_hunt_rows.arithmetic = {}
        return [{"wave": t["wave"], "brh": t["brh"]} for t in seeded]
    carried = Counter()
    for t in existing:
        b = t.get("brh") or {}
        if b.get("kind") == "bug-hunt":
            carried[_brh_carry(b.get("cls"), b.get("page"), b.get("key"))] += 1
    from bug_hunt_inventory import collect
    rows: list[dict] = []
    for s in collect():
        cls, page, line, key = s["cls"], s["page"], s["line"], s["key"]
        if carried[_brh_carry(cls, page, key)] > 0:
            carried[_brh_carry(cls, page, key)] -= 1    # this measured site is already carried by an existing row
            continue
        layer, persona, mech, repro, fix = BRH_CLASS[cls]
        persona = s.get("persona") or persona
        if s.get("personas"):            # L, M: the first candidate whose route to the page the gate accepts
            persona = _gate_checked_cast(page, list(s["personas"]))
        # a founder surface the hub offers nobody is reached DIRECTLY by platform staff (SL's rule for `oversight`):
        # a hub route to it is a hop no page offers, and journey-paths refuses it
        direct = persona == "oversight" and page != "index.html"
        # a site in a shared SCRIPT is met on a page: the journey walks to the page that hosts it, while brh.page keeps
        # the code location (2026-10-27 - AO/AP's voice-handler.js was a journey hop no page links, and journey-paths
        # refused all 68 rows). The companion is met on the hive board.
        walk = page if page.endswith(".html") else SCRIPT_HOST.get(page, "hive.html")
        pages = [walk] if direct else _path(_start(walk), walk, [], cast=_cast_of(persona))
        who = "a person" if persona == "any" else persona
        where = f"{_short(page)}:{line}" if line else _short(page)
        rows.append({
            "wave": f"BRH-{cls}",
            "title": f"{mech} - {where} · {key[:60]} - {who}",
            "pages": list(pages),
            "layers": [layer],
            "ufai": list(LAYER_LENS[layer][1]),
            "persona": persona,
            "device": "any",
            "entry": "direct" if (page == "index.html" or direct) else "hub-nav",
            "framing": "person",
            "story": (f"{who} reaches {_short(page)} and meets a defect of a class a real person met on 2026-10-13/14: "
                      f"{s['detail']}. MECHANISM: {mech}. REPRO: {repro}. FIX: {fix}. The row closes only when the "
                      f"reproduction is made to FAIL on demand, the fix lands, and a gate holds it, measured at "
                      f"{' and '.join(LX_VIEWPORTS)}"),
            "journey": {"archetype": f"BRH-{cls}:{persona}", "stage": "operate",
                        "vertical": HIVES[(line or len(key)) % len(HIVES)], "pair": "", "language": "en",
                        "moment": "present", "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "brh": {"kind": "bug-hunt", "cls": cls, "page": page, "line": line, "key": key, "detail": s["detail"],
                    "layer": layer, "persona": persona, "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                    "mechanism": mech, "repro": repro, "fix": fix,
                    "closes": ("the reproduction is demonstrated FAILING on demand, the fix lands, and a registered "
                               "gate reddens when the fix is reverted - not merely 'the page looks right now'")},
        })
    rows.sort(key=lambda r: (r["brh"]["cls"], r["brh"]["page"], r["brh"]["line"], r["brh"]["key"]))
    bug_hunt_rows.arithmetic = {c: sum(1 for r in rows if r["brh"]["cls"] == c) for c in BRH_CLASS}
    return rows


# after BRP, with a replay ANCHORED to the registry the way bug_repro_rows' is.
LXC_PREFIX = "LXC"
LXC_FLOOR = 12


def _lx_like_row(persona: str, layer: str, page: str, roster: list, wave: str, kind: str, gap: str) -> dict:
    """The LXP row shape, for a wave seeded after LXP. A copy of layer_ux_rows._row's body rather than a refactor of
    it, deliberately: that nested builder is what the LXP replay runs, and any change to it is a change to 2,206
    positional ids. The cost is two places that say the same sentence; the gate catches the one that drifts."""
    ask, dims = LAYER_LENS[layer]
    pages = _path(_start(page), page, [], cast=_cast_of(persona))
    entry = "direct" if page == "index.html" else "hub-nav"
    vertical = HIVES[roster.index(page) % len(HIVES)] if page in roster else HIVES[0]
    who = "a person" if persona == "any" else persona
    return {
        "wave": wave,
        "title": f"{ask} - {who} · {_short(page)}",
        "pages": list(pages),
        "layers": [layer],
        "ufai": list(dims),
        "persona": persona,
        "device": "any",
        "entry": entry,
        "framing": "person",
        "story": (f"{who} arrives by {entry} and reaches {_short(page)} through the platform's own navigation "
                  f"({' -> '.join(_short(p) for p in pages)}), signed in as that persona; the {layer} layer is "
                  f"exercised live through the chrome-devtools MCP at {' and '.join(LX_VIEWPORTS)} in one batched "
                  f"round, with the postgres MCP as the witness where the layer writes, and the walk records what "
                  f"the PERSON experiences when it misbehaves"),
        "journey": {"archetype": f"{wave}:{persona}", "stage": "operate", "vertical": vertical, "pair": "",
                    "language": "en", "moment": "present", "condition": "normal", "tier": "A", "pages": list(pages)},
        "axis": {"device": "phone-390", "language": "en"},
        "lx": {"kind": kind, "layer": layer, "persona": persona, "page": page, "gap": gap,
               "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT, "ask": ask,
               "closes": (f"the {layer} ask is answered from {_short(page)} itself at both viewports, as {who}, "
                          f"with a receipt naming the layer, the persona signed in, and steps at phone-390 AND "
                          f"desktop-1280")},
    }


def layer_floor_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """Rows that lift every signed-in persona's thin (persona, layer) cell to LXC_FLOOR. replay=True returns what
    was SEEDED, in id order - the registry is the record, so the floor can move as cells fill without renumbering."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("lx") or {}).get("kind") == "layer-floor"),
                        key=lambda x: int(str(x["id"])[len(LXC_PREFIX):] or 0))
        layer_floor_rows.arithmetic = {}
        return [{"wave": t["wave"], "lx": t["lx"]} for t in seeded]
    scoped = [t for t in existing if t.get("status") != "descoped"]
    persona_pages, _cells, roster = _lx_state(scoped)
    act = Counter()
    for t in scoped:
        p = t.get("persona") or (t.get("lx") or {}).get("persona") or "any"
        for l in (t.get("layers") or []):
            act[(p, l)] += 1
    seeded = {((t.get("lx") or {}).get("persona"), (t.get("lx") or {}).get("layer"), (t.get("lx") or {}).get("page"))
              for t in existing if (t.get("lx") or {}).get("kind") in ("layer-ux", "layer-floor")}
    rows, arithmetic = [], {"by_persona": Counter(), "by_layer": Counter(), "short_cells": []}
    for persona in LX_SIGNED_IN:
        reach = sorted(set(persona_pages.get(persona, ())) - LX_NON_PRODUCTION)
        for layer in LAYER_SET:
            need = LXC_FLOOR - act[(persona, layer)]
            if need <= 0:
                continue
            take = [pg for pg in reach if (persona, layer, pg) not in seeded][:need]
            if len(take) < need:
                arithmetic["short_cells"].append((persona, layer, need, len(take)))
            for pg in take:
                rows.append(_lx_like_row(persona, layer, pg, roster, f"{LXC_PREFIX}-{layer}", "layer-floor",
                                         "C-floor"))
                arithmetic["by_persona"][persona] += 1
                arithmetic["by_layer"][layer] += 1
    # layer-major, so each LXC-<layer> wave owns a contiguous id range (the validator builds wave by wave)
    rows.sort(key=lambda r: (LAYER_SET.index(r["lx"]["layer"]), r["lx"]["persona"], r["lx"]["page"]))
    layer_floor_rows.arithmetic = arithmetic
    return rows


# ════════════════════════════════════════════════════════
# LM · THE LLM LAYER - a 14th layer, with sub-layers inside (Ian, 2026-10-06)
# ════════════════════════════════════════════════════════
# Ian: "I also can't see why we haven't consider to make trajectories for my LLMs of my platform wide, we have to
# treat it also another layer which inside its LLM Layer there are also like sub-layers like a Full stack SaaS for
# LLMs". Measured: 40 edge functions reach a model or an embedding/speech provider, and until now every one was
# walked only under A ("the call answered") or C - never whether the ANSWER was grounded, valid, affordable or
# honest. Ian chose ONE 14th layer with its sub-layers inside, and LOCAL STUBS FIRST with the live model only for
# Grounding and Routing (batched, the spend stated before each batch).
LM_PREFIX = "LM"
# emitted in HARM order - each LM-<sub> wave owns a contiguous id range in this order
LM_SUBLAYERS = {
    "X": ("Safety, privacy & guardrails",
          "The platform must keep this page's AI from leaking one plant's records into another's answer, and from "
          "obeying instructions hidden in what people typed", ["I"]),
    "G": ("Grounding & citations",
          "The platform must make this page's AI answer from this hive's own records, point at them, and say when "
          "it has nothing to go on", ["F", "I"]),
    "S": ("Structure & schema",
          "The platform must make whatever this page's AI generates complete and valid in the shape the page "
          "renders", ["F"]),
    "R": ("Routing, fallback & cost",
          "The platform must answer within this hive's AI budget, and still answer when a model fails", ["A", "I"]),
    "P": ("Prompt & context",
          "The platform must give this page's AI the context of this person, this hive and this asset", ["F"]),
    "A": ("Agents & approval",
          "The platform must let the AI propose and the person approve, with the record showing which", ["I"]),
    "V": ("Voice & vision",
          "The platform must turn what this person says or photographs into the entry they meant", ["U", "F"]),
    "L": ("Latency & waiting",
          "The platform must show the AI is working and keep a slow answer instead of losing it", ["U", "A"]),
    "E": ("Evals & quality gates",
          "The platform must measure this page's AI quality rather than claim it", ["I"]),
    "O": ("Observability",
          "The platform must let someone see afterwards what this page's AI did and why", ["I"]),
}
LM_LIVE_SUBS = ("G", "R")                       # live model, batched, spend stated (Ian's choice)
LM_PERSON_SUBS = ("P", "G", "X", "A", "V")      # where the PERSON changes the answer; R/L/E/O/S are the same for all
LM_DEPTH = ("worker", "supervisor", "fleet-supervisor", "solo-owner", "assistive-tech")
LM_INSTRUMENT_LOCAL = "playwright-mcp + postgres-mcp"
LM_INSTRUMENT_LIVE = "playwright-mcp + live-model"
# measured 2026-10-06: the edge functions whose source reaches a model or an embedding / speech provider
LM_MODEL_FNS = frozenset((
    "agentic-rag-loop ai-eval-runner ai-gateway ai-orchestrator amc-orchestrator analytics-orchestrator "
    "asset-brain-query batch-risk-scoring data-fabric-normalizer embed-entry engineering-bom-sow "
    "engineering-calc-agent failure-signature-scan fmea-populator gcash-receipt-ocr hierarchical-summarizer "
    "intelligence-report marketplace-listing-assist pdf-ingest platform-gateway project-orchestrator resume-extract "
    "resume-polish scheduled-agents semantic-fact-extractor semantic-search shift-planner-orchestrator "
    "temporal-rag-orchestrator tts-speak vehicle-doc-extract visual-defect-capture voice-action-router "
    "voice-embeddings voice-journal-agent voice-logbook-entry voice-model-call voice-report-intent "
    "voice-semantic-rag voice-transcribe walkthrough-analyzer").split())


def _lm_surfaces(roster: list) -> tuple[dict, str, set]:
    """{page: [its own model functions]} for production pages, the companion's host page, and the voice pages.
    Read from the substrate's per-page 'Edge invokes' line plus the page's own .js - the AI_SURFACES_MANIFEST's
    per-page list is stale (hive and asset-hub read empty there while both call ai-gateway)."""
    surfaces, voice = {}, set()
    for page in roster:
        if page in LX_NON_PRODUCTION:
            continue
        fns = set()
        sub = ROOT / "substrate" / "page" / (page[:-5] + ".md")
        if sub.exists():
            m = re.search(r"\*\*Edge invokes\*\*: (.*)", sub.read_text(encoding="utf-8", errors="ignore"))
            if m:
                fns |= set(re.findall(r"`([a-z0-9-]+)`", m.group(1)))
        js = ROOT / (page[:-5] + ".js")
        if js.exists():
            fns |= set(re.findall(r"functions/v1/([a-z0-9-]+)", js.read_text(encoding="utf-8", errors="ignore")))
        hit = sorted(fns & LM_MODEL_FNS)
        if hit:
            surfaces[page] = hit
        html = (ROOT / page).read_text(encoding="utf-8", errors="ignore") if (ROOT / page).exists() else ""
        if re.search(r"voice-handler\.js|wh-tts\.js", html) or any(f.startswith("voice-") for f in hit):
            voice.add(page)
    hosts = [p for p in roster if p not in LX_NON_PRODUCTION and p not in surfaces and (ROOT / p).exists()
             and "companion-launcher.js" in (ROOT / p).read_text(encoding="utf-8", errors="ignore")]
    return surfaces, (sorted(hosts)[0] if hosts else "index.html"), voice


def llm_layer_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per (sub-layer, persona, AI surface). replay=True returns what was SEEDED, in id order."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("lx") or {}).get("kind") == "llm"),
                        key=lambda x: int(str(x["id"])[len(LM_PREFIX):] or 0))
        llm_layer_rows.arithmetic = {}
        return [{"wave": t["wave"], "lx": t["lx"]} for t in seeded]
    scoped = [t for t in existing if t.get("status") != "descoped"]
    persona_pages, _cells, roster = _lx_state(scoped)
    surfaces, companion_host, voice = _lm_surfaces(roster)
    seeded = {((t.get("lx") or {}).get("persona"), (t.get("lx") or {}).get("sublayer"),
               (t.get("lx") or {}).get("surface")) for t in existing if (t.get("lx") or {}).get("kind") == "llm"}
    targets = [(p, p, surfaces[p]) for p in sorted(surfaces)] + [("companion", companion_host, ["ai-gateway"])]

    def _row(sub: str, persona: str, surface: str, page: str, fns: list) -> dict:
        name, ask, dims = LM_SUBLAYERS[sub]
        live = sub in LM_LIVE_SUBS
        pages = _path(_start(page), page, [], cast=_cast_of(persona))
        entry = "direct" if page == "index.html" else "hub-nav"
        vertical = HIVES[roster.index(page) % len(HIVES)] if page in roster else HIVES[0]
        who = "a person" if persona == "any" else persona
        where = f"the companion on {_short(page)}" if surface == "companion" else _short(page)
        instr = LM_INSTRUMENT_LIVE if live else LM_INSTRUMENT_LOCAL
        return {
            "wave": f"{LM_PREFIX}-{sub}",
            "title": f"{ask} - {who} · {where}",
            "pages": list(pages),
            "layers": ["LM"],
            "ufai": list(dims),
            "persona": persona,
            "device": "any",
            "entry": entry,
            "framing": "person",
            "story": (f"{who} reaches {where} through the platform's own navigation and asks its AI what this "
                      f"person would ask ({', '.join(fns)}); the {name} sub-layer is walked through the "
                      f"chrome-devtools MCP at {' and '.join(LX_VIEWPORTS)}, "
                      + ("against the LIVE model - batched, the token spend stated before the batch, because "
                         "here the model's own behaviour is the claim"
                         if live else
                         "against the local stack, with the witness from the ai-eval harness, the gateway's "
                         "local debug echo or the AI gates - no paid call")
                      + ", and the walk records what the PERSON experiences, not whether the model is clever"),
            "journey": {"archetype": f"LM-{sub}:{persona}", "stage": "operate", "vertical": vertical, "pair": "",
                        "language": "en", "moment": "present", "condition": "normal", "tier": "A",
                        "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "lx": {"kind": "llm", "layer": "LM", "sublayer": sub, "persona": persona, "page": page,
                   "surface": surface, "functions": list(fns), "viewports": list(LX_VIEWPORTS),
                   "instrument": instr, "live_model": live, "ask": ask,
                   "closes": (f"the LM-{sub} ask is answered from {where} itself at both viewports, as {who}, with "
                              f"a receipt naming the sub-layer, the persona signed in, steps at phone-390 AND "
                              f"desktop-1280, and "
                              + ("the live model and the tokens it spent" if live else
                                 "the local witness (eval harness / debug echo / AI gate) that settles it"))},
        }

    rows, arithmetic = [], {"baseline": 0, "depth": Counter(), "by_sub": Counter(), "surfaces": len(targets)}
    for sub in LM_SUBLAYERS:
        plan = [("any", t) for t in targets]
        if sub in LM_PERSON_SUBS:
            for persona in LM_DEPTH:
                reach = set(persona_pages.get(persona, ()))
                plan += [(persona, t) for t in targets if t[0] == "companion" or t[1] in reach]
        if sub == "V":
            plan += [("driver-worker", t) for t in targets if t[0] == "companion" or t[1] in voice]
        if sub == "X":
            plan += [("adversary", t) for t in targets]
        for persona, (surface, page, fns) in plan:
            if (persona, sub, surface) in seeded:
                continue
            rows.append(_row(sub, persona, surface, page, fns))
            arithmetic["by_sub"][sub] += 1
            if persona == "any":
                arithmetic["baseline"] += 1
            else:
                arithmetic["depth"][persona] += 1
    llm_layer_rows.arithmetic = arithmetic
    return rows


# ════════════════════════════════════════════════════════
# SL · ENH · OPC - THE SUB-LAYERS, THE ENHANCEMENTS, THE OPERATOR CONSOLE (Ian, 2026-10-14)
# ════════════════════════════════════════════════════════
# Ian, after the real cause of his missing logbook assets turned out to be a CSP without `wss:` (WebKit threw on the
# realtime socket and the start-up died): "I am pretty sure that is belong to a layer or sublayer of our full stack
# architectural layer SaaS, so we have to dig deeper to make numbers trajectories for each full stack architectural
# layer and sublayers of my SaaS ... for every production/public/founder pages." Three waves, each in its OWN id space
# with a replay ANCHORED to the registry's own metadata (the BRP/BRH rule), each sized by its inventory - never typed:
#   SL   tools/sublayer_inventory.py        one row per (page, layer, sub-layer) cell, 52 sub-layers, 158 pages
#   ENH  tools/enhancement_inventory.py     one row per capability a page lacks (the solar power-station planner first)
#   OPC  tools/operator_console_inventory.py one row per panel the ONE operator console must hold, persona oversight
SL_PREFIX, ENH_PREFIX, OPC_PREFIX = "SL", "ENH", "OPC"
OPC_KIND_WAVE = OrderedDict([("operations", "O"), ("grafana", "G"), ("feed", "F"), ("developer", "D")])
OPC_KIND_NAME = {"O": "operations queues and actions", "G": "Grafana as live numbers in-page",
                 "F": "the error feed and the gate board", "D": "the Developer tab"}


def _seeded(existing: list, field: str, kind: str, prefix: str) -> list:
    """What a wave SEEDED, in id order, from the registry's own metadata - the record its replay must return."""
    return sorted((x for x in existing if (x.get(field) or {}).get(kind[0]) == kind[1]),
                  key=lambda x: int(str(x["id"])[len(prefix):] or 0))


def _cell_route(page: str, cls: str, persona: str, roles: dict) -> tuple[list, str]:
    """(pages, entry) for a page-scoped row. A public page is reached from a search result and the row lives on it;
    a founder surface the hub offers nobody is opened directly by URL; every other page is reached through the
    platform's own navigation, padded from the surfaces THIS cast is offered (the LXP/BRH route)."""
    if cls == "public":
        return [page], "search-arrival"
    if persona == "anon":          # a production page only a signed-out visitor reaches (public-feed): a shared link
        return [page], "direct"
    if cls == "founder" and not roles.get(page):
        return [page], "direct"
    return _path(_start(page), page, [], cast=_cast_of(persona)), ("direct" if page == "index.html" else "hub-nav")


def _hive_for(page: str) -> str:
    return HIVES[sum(map(ord, page)) % len(HIVES)]


def _sl_how_closes(code: str, page: str, who: str, webkit: bool, instrument: str) -> tuple[str, str]:
    """The (how it is walked, when it closes) sentences of an SL row, by its declared instrument - one place, so a row
    re-declared to a truer instrument is re-texted by the same words a fresh seed would use."""
    engine_txt = " in real WebKit as well as Chromium (WebKit throws where Chromium stays silent)" if webkit else ""
    if instrument.startswith("library"):
        return (f"It is settled in a batch by a registered prover over every page of its roster (the W4 contract-layer "
                f"precedent: the served bytes, the scan, the ratchet){engine_txt}",
                f"a registered prover settles {code} on {_short(page)}, its receipt names the sub-layer, and the gate "
                f"reddens when the fix is reverted")
    if instrument.startswith("invoke"):
        return (f"It is proven AS A PERSON, never through a browser or the owner connection: a member of ANOTHER hive, on "
                f"the authenticated path (role authenticated + their JWT claims, in a rolled-back transaction), asks each "
                f"table {_short(page)} reads or writes, with the page's own member as the control",
                f"a foreign-hive member receives zero of this hive's rows (or is refused the write) while the page's own "
                f"member is served, and a registered gate reddens when the policy is loosened")
    return (f"It is walked live as {who} through the chrome-devtools MCP at {' and '.join(LX_VIEWPORTS)}{engine_txt}, "
            f"with the condition induced (an init script that makes a subsystem throw, a refused route, a demoted role, "
            f"a renamed hive, a 1,000-row list), the postgres MCP the witness where it writes",
            f"the {code} ask is answered from {_short(page)} itself at phone-390 AND desktop-1280 as {who}"
            f"{' in WebKit and Chromium' if webkit else ''}, on a receipt naming the layer, the sub-layer, the persona"
            f"{' and the engine' if webkit else ''}, and a gate holds what the walk found")


def sublayer_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per measured (page, layer, sub-layer) cell, layer-major so each SL-<layer> owns a contiguous id range.
    replay=True returns what was SEEDED, in id order - the record, so a roster tightened later never renumbers."""
    if replay:
        sublayer_rows.arithmetic = {}
        return [{"wave": t["wave"], "sl": t["sl"]} for t in _seeded(existing, "sl", ("kind", "sublayer"), SL_PREFIX)]
    from sublayer_inventory import SUBLAYERS, casts, collect, page_classes
    from backfill_trajectory_layers import NAMES as _LNAMES
    scoped = [t for t in existing if t.get("status") != "descoped"]
    classes = page_classes()
    cast = casts(scoped, classes)
    roles = _hub_roles()
    carried = {((t.get("sl") or {}).get("layer"), (t.get("sl") or {}).get("sublayer"), (t.get("sl") or {}).get("page"))
               for t in existing if (t.get("sl") or {}).get("kind") == "sublayer"}
    rows, arithmetic = [], {"by_layer": Counter(), "by_class": Counter(), "webkit": 0}
    for c in collect(classes=classes):
        layer, code, page, cls = c["layer"], c["sublayer"], c["page"], c["class"]
        if (layer, code, page) in carried:
            continue
        name, ask, roster = SUBLAYERS[layer][code]
        persona = cast.get(page) or ("anon" if cls == "public" else "worker")
        who = "a person" if persona == "any" else ("an anonymous visitor" if persona == "anon" else persona)
        pages, entry = _cell_route(page, cls, persona, roles)
        webkit = c["engine"] == "webkit"
        how, closes = _sl_how_closes(code, page, who, webkit, c["instrument"])
        rows.append({
            "wave": f"{SL_PREFIX}-{layer}",
            "title": f"{code} · {ask} - {who} · {_short(page)}",
            "pages": list(pages),
            "layers": [layer],
            "ufai": list(LAYER_LENS[layer][1]),
            "persona": persona,
            "device": "any",
            "entry": entry,
            "framing": "person",
            "story": (f"{who} reaches {_short(page)} ({' -> '.join(_short(p) for p in pages)}) and the "
                      f"{_LNAMES.get(layer, layer)} layer's sub-layer {code}, {name}, is exercised there: {ask}. "
                      f"{how}. It closes when {closes}"),
            "journey": {"archetype": f"{SL_PREFIX}-{code}:{persona}", "stage": "operate", "vertical": _hive_for(page),
                        "pair": "", "language": "en", "moment": "present", "condition": "normal", "tier": "A",
                        "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "sl": {"kind": "sublayer", "layer": layer, "sublayer": code, "name": name, "page": page,
                   "page_class": cls, "roster": roster, "persona": persona, "viewports": list(LX_VIEWPORTS),
                   "instrument": c["instrument"], "engine": c["engine"], "ask": ask, "closes": closes},
        })
        arithmetic["by_layer"][layer] += 1
        arithmetic["by_class"][cls] += 1
        arithmetic["webkit"] += webkit
    sublayer_rows.arithmetic = arithmetic
    return rows


def enhancement_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per measured missing capability, class-major (ENH-S first: the solar power-station planner)."""
    if replay:
        enhancement_rows.arithmetic = {}
        return [{"wave": t["wave"], "enh": t["enh"]}
                for t in _seeded(existing, "enh", ("kind", "enhancement"), ENH_PREFIX)]
    from enhancement_inventory import CLASSES, collect
    from sublayer_inventory import casts, page_classes
    scoped = [t for t in existing if t.get("status") != "descoped"]
    classes = page_classes()
    cast = casts(scoped, classes)
    roles = _hub_roles()
    cls_of = {p: k for k, v in classes.items() for p in v}
    carried = Counter(((t.get("enh") or {}).get("cls"), (t.get("enh") or {}).get("page"), (t.get("enh") or {}).get("key"))
                      for t in existing if (t.get("enh") or {}).get("kind") == "enhancement")
    rows, arithmetic = [], Counter()
    for s in collect():
        k = (s["cls"], s["page"], s["key"])
        if carried[k] > 0:
            carried[k] -= 1
            continue
        label, layer = CLASSES[s["cls"]]
        page = s["page"]
        pcls = cls_of.get(page) or ("public" if "/" in page else "production")
        persona = cast.get(page) or ("anon" if pcls == "public" else "worker")
        who = "an anonymous visitor" if persona == "anon" else persona
        pages, entry = _cell_route(page, pcls, persona, roles)
        ask = f"The platform must {s['ask']}"
        what = f"{s['key']} on the solar power-station planner" if s["cls"] == "S" else s["key"]
        prover = s["cls"] == "J"
        instrument = ("library sweep (tools/live_page_journeys.mjs, the journey runner, in Chromium and WebKit)"
                      if prover else LX_INSTRUMENT)
        closes = (f"a live journey for {_short(page)} exists, passes in Chromium and WebKit, and the live-page-journeys "
                  f"gate holds it" if prover else
                  # ENH-R (Ian, 2026-10-19): provenance leaves the space a person reads first
                  f"every source line and how-it-is-computed note on {_short(page)} sits in its one Sources area at the "
                  f"foot of the page - none above the page's own content at phone-390 or desktop-1280, each still "
                  f"readable there as {who} - and a gate fails on the page as it was"
                  if s["cls"] == "R" else
                  f"the capability is BUILT on {_short(page)} itself (not described), used end to end as {who} at "
                  f"phone-390 AND desktop-1280, and a gate fails on the page as it was before the build")
        rows.append({
            "wave": f"{ENH_PREFIX}-{s['cls']}",
            "title": f"{ask} ({what}) - {who} · {_short(page)}",
            "pages": list(pages),
            "layers": [layer],
            "ufai": list(LAYER_LENS[layer][1]),
            "persona": persona,
            "device": "any",
            "entry": entry,
            "framing": "person",
            "story": (f"{who} reaches {_short(page)} ({' -> '.join(_short(p) for p in pages)}) wanting what the page "
                      f"does not yet give: {s['detail']}. {ask}. ENHANCEMENT ({label}): it is built, then walked live "
                      f"through the chrome-devtools MCP at {' and '.join(LX_VIEWPORTS)}. It closes when {closes}"),
            "journey": {"archetype": f"{ENH_PREFIX}-{s['cls']}:{persona}", "stage": "operate",
                        "vertical": _hive_for(page), "pair": "", "language": "en", "moment": "present",
                        "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "enh": {"kind": "enhancement", "cls": s["cls"], "page": page, "page_class": pcls, "key": s["key"],
                    "detail": s["detail"], "ask": ask, "layer": layer, "persona": persona,
                    "viewports": list(LX_VIEWPORTS), "instrument": instrument, "closes": closes},
        })
        arithmetic[s["cls"]] += 1
        arithmetic["public" if pcls == "public" else "production"] += 1
    enhancement_rows.arithmetic = arithmetic
    return rows


def operator_console_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per panel the ONE operator console must hold, grouped by kind (OPC-O operations first)."""
    if replay:
        operator_console_rows.arithmetic = {}
        return [{"wave": t["wave"], "opc": t["opc"]}
                for t in _seeded(existing, "opc", ("kind", "operator-console"), OPC_PREFIX)]
    from operator_console_inventory import CONSOLE, collect, key as _panel_key
    cells = collect()
    raw = dict(collect.arithmetic)
    carried = {((t.get("opc") or {}).get("surface"), (t.get("opc") or {}).get("panel"))
               for t in existing if (t.get("opc") or {}).get("kind") == "operator-console"}
    # ★A MOVED PANEL IS STILL ITS ROW (OPC build, 2026-10-22). The console now carries the headings of the panels it took
    # over ("GCash receipts needing your eyes", "Recent decisions", "Estimated 30-day ROI"), and the inventory reads the
    # console first, so each comes back as a console cell - which is the row already seeded under its old home, not a new
    # one. Same title, same panel: the inventory's own exact-fold rule.
    carried_keys = {_panel_key(p) for _, p in carried if p}
    rows, arithmetic = [], Counter()
    for c in cells:
        if (c["surface"], c["panel"]) in carried:
            continue
        if c["surface"] == CONSOLE and _panel_key(c["panel"]) in carried_keys:
            continue
        wave = OPC_KIND_WAVE[c["kind"]]
        panel = c["panel"].replace(" - ", " – ")
        live = c["kind"] in ("grafana", "feed")
        where = c["surface"] + (" (also: " + "; ".join(c["also_on"]) + ")" if c["also_on"] else "")
        closes = (f"'{panel}' is in the one operator console ({_short(CONSOLE)}, un-retired), "
                  + ("showing the live number with a link to its dashboard, " if live else "acted on in place, ")
                  + "walked as oversight at phone-390 AND desktop-1280 with its data live, and its old home "
                    "redirects to the console or is retired")
        rows.append({
            "wave": f"{OPC_PREFIX}-{wave}",
            "title": f"The platform must give the founder {panel} in the one operator console - oversight · "
                     f"{_short(CONSOLE)} (today: {c['surface']})",
            "pages": [CONSOLE],
            "layers": ["F", "L"] if live else ["F"],
            "ufai": ["U", "F", "I"],
            "persona": "oversight",
            "device": "any",
            "entry": "direct",
            "framing": "person",
            "story": (f"The founder signs in and opens the one operator console and finds '{panel}' there, where "
                      f"today it lives on {where}. OPERATOR CONSOLE ({OPC_KIND_NAME[wave]}): built into "
                      f"{_short(CONSOLE)}, then walked live as oversight through the chrome-devtools MCP at "
                      f"{' and '.join(LX_VIEWPORTS)}. It closes when {closes}"),
            "journey": {"archetype": f"{OPC_PREFIX}-{wave}:oversight", "stage": "operate", "vertical": _hive_for(panel),
                        "pair": "", "language": "en", "moment": "present", "condition": "normal", "tier": "A",
                        "pages": [CONSOLE]},
            "axis": {"device": "phone-390", "language": "en"},
            "opc": {"kind": "operator-console", "surface": c["surface"], "panel": c["panel"], "panel_kind": c["kind"],
                    "also_on": list(c["also_on"]), "page": CONSOLE, "persona": "oversight",
                    "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT, "closes": closes},
        })
        arithmetic[wave] += 1
    rows.sort(key=lambda r: list(OPC_KIND_WAVE.values()).index(r["wave"].split("-", 1)[1]))
    arithmetic.update({"raw": raw.get("raw", 0), "exact": raw.get("exact", 0), "near": raw.get("near", 0)})
    operator_console_rows.arithmetic = arithmetic
    return rows


# ★KEEP ABREAST (KA1.., 2026-10-26) - Ian: "add necessary appropriate numbers of my SEO AEO GEO ... my issue is, it's like
# static, I want it always keeping up to date, or that will trigger or trip that we need ... to keep abreast also." The
# population is tools/freshness_trip.py's census (the public URLs, the evidence spine, the English prompt set, the
# scoreboard's components) - one place decides the size; the registry is the inbox the trip re-opens into.
KA_PREFIX = "KA"
KA_LENS = {
    # lens: (wave, layers, ufai, persona, entry, stage, trips it re-opens on, the ask)
    "R": ("KA-R", ["F", "H"], ["F", "A"], "anon", "search-arrival", "acquire", ["refresh", "sitemap-promise"],
          "this page's five freshness surfaces agree (JSON-LD dateModified, the visible Last-updated line, the sitemap "
          "lastmod, the markdown twin, the IndexNow push); it is inside its kind's window or holds an open refresh; "
          "when it is refreshed the diff is content, never a date alone"),
    "E": ("KA-E", ["CI"], ["I", "A"], "oversight", "direct", "comply", ["evidence"],
          "this external source is within its TTL; when it is re-fetched a changed sha produces a diff note and a "
          "recorded decision on the lever it anchors - the engines change, and the platform notices"),
    "S": ("KA-S", ["H"], ["A", "F"], "anon", "search-arrival", "acquire", ["push"],
          "this URL was pushed to the index (an IndexNow receipt) after its last change; its indexed state is read "
          "when the Search Console credential exists, never assumed"),
    "V": ("KA-V", ["LM"], ["F", "U"], "anon", "search-arrival", "acquire", ["voice"],
          "the page this prompt expects to be cited is citation-eligible now (answer-first, twin current, facts inside "
          "their window); the monthly run records cited / mentioned / recommended per engine; a drop trips a review"),
    "B": ("KA-B", ["CI"], ["I", "F"], "oversight", "direct", "comply", ["board", "roster", "push", "voice"],
          "this instrument tells the truth about itself: it reads a live measure or says it cannot, regenerates on the "
          "board, and its trip reaches the roadmap header, the board and the nightly CI"),
}
KA_BOARD_UNITS = [
    ("seo_scoreboard.py: deployed to production", "the [IAN] component reads prod by HEAD-probing sitemap.xml, robots.txt and the IndexNow key file, not a typed 0/1"),
    ("seo_scoreboard.py: GSC + Bing reporting", "the component reads credential presence and a successful pull; Ian creates the free Search Console / Bing Webmaster access (one shared Ian-gated step)"),
    ("seo_scoreboard.py: entity resolvable (sameAs)", "the component reads whether the Organization's sameAs URLs exist and resolve (index.html declares sameAs: [] today)"),
    ("seo_scoreboard.py: live SOV baseline", "the component reads geo_sov_baseline.json's age, not a typed 0/1"),
    ("seo_scoreboard.py: off-site channels active", "the component names the three channels and reads what evidence of each exists on disk"),
    ("seo_scoreboard.py: AIO entity resolvable", "the component shares the GEO sameAs read instead of a second typed 0/1"),
    ("seo_scoreboard.py: third-party listicle inclusion", "the component reads a recorded inclusion URL or says none"),
    ("seo_scoreboard.py on the board", "the scoreboard regenerates on every full board run (gate seo-scoreboard), never by hand"),
    ("the trip on the roadmap header", "update_trajectory_scoreboard.py prints KEEP ABREAST from seo_trip_report.json, never hand-typed"),
    ("the trip on the board", "gate seo-trip (WARN) writes seo_trip_report.json on every full run"),
    ("the trip in the nightly CI", "the keep-abreast job reddens only when a trip is past its grace"),
    ("robots.txt against the crawler roster", "every AI user-agent the harvested roster names has a decided line in robots.txt"),
    ("the sitemap's promise", "gate sitemap-promise holds <lastmod> to each page's own dateModified and <changefreq> to the kind's window"),
]


def keep_abreast_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per unit of the KEEP ABREAST census (tools/freshness_trip.py): the public URLs twice (KA-R the refresh,
    KA-S the push), every SEO evidence chunk (KA-E), every English SOV prompt (KA-V), and the board's own instruments
    (KA-B). replay=True returns what was SEEDED, in id order, from the registry's ka metadata (the BRP/BRH rule)."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("ka") or {}).get("kind") == "keep-abreast"),
                        key=lambda x: int(str(x["id"])[len(KA_PREFIX):] or 0))
        keep_abreast_rows.arithmetic = {}
        return [{"wave": t["wave"], "ka": t["ka"]} for t in seeded]
    import freshness_trip as ft
    c = ft.census()
    have = {((x.get("ka") or {}).get("lens"), (x.get("ka") or {}).get("unit")) for x in existing if (x.get("ka") or {}).get("kind") == "keep-abreast"}
    units: list[tuple[str, str, list[str], str, str]] = []     # (lens, unit, aliases, page, detail)
    for u in c["url_list"]:
        units.append(("R", u["path"], [u["slug"]], u["path"], f"{u['kind']} · window {u['window_days']}d · lastmod {u['lastmod'] or '-'} · "
                      f"dateModified {u['date_modified'] or 'none declared'}"))
    for ch in c["spine_chunks"]:
        units.append(("E", ch["slug"], [], "index.html", f"ttl {ch['ttl_days']}d · age {ch['age_days']}d · "
                      + (f"anchors {', '.join(ch['cited_by'][:3])}" if ch["cited_by"] else "SEO-topic chunk no gate or doc cites yet")))
    for u in c["url_list"]:
        units.append(("S", u["path"], [u["slug"]], u["path"], f"last IndexNow push {c['last_push']}"))
    for p in ft.prompts():
        units.append(("V", p.get("id") or p.get("query", "")[:60], [], "index.html",
                      f"prompt '{p.get('query', '')[:90]}' expects {p.get('expected_cite', '?')}"))
    for name, detail in KA_BOARD_UNITS:
        units.append(("B", name, [], "founder-console.html", detail))
    rows: list[dict] = []
    order = {"R": 0, "E": 1, "S": 2, "V": 3, "B": 4}
    for lens, unit, aliases, page, detail in sorted(units, key=lambda t: (order[t[0]], t[1])):
        if (lens, unit) in have:
            continue
        wave, layers, ufai, persona, entry, stage, trips, ask = KA_LENS[lens]
        pages = [page] if page == "index.html" or lens in ("E", "B", "V") else ["index.html", page] if persona == "anon" else [page]
        who = "a person" if persona == "anon" and lens in ("R", "S") else persona
        short = unit if len(unit) <= 60 else unit[:57] + "..."
        rows.append({
            "wave": wave,
            "title": f"{ask.split(';')[0][:90]} - {short} · {who}",
            "pages": pages,
            "layers": list(layers),
            "ufai": list(ufai),
            "persona": persona,
            "device": "any",
            "entry": entry,
            "framing": "person",
            "story": (f"{who} reaches {_short(pages[-1])} and the KEEP ABREAST lens {lens} is asked of {unit}: {ask}. MEASURED: {detail}. "
                      f"The row closes on the instrument its lens names (the five-surface paired write, the re-fetch with a diff note, "
                      f"the IndexNow receipt, the monthly SOV sheet, the live read on the scoreboard) at {' and '.join(LX_VIEWPORTS)} "
                      f"where a page is involved; tools/freshness_trip.py --seed re-opens it when its unit trips again"),
            "journey": {"archetype": f"{wave}:{persona}", "stage": stage, "vertical": HIVES[len(unit) % len(HIVES)], "pair": "",
                        "language": "en", "moment": "present", "condition": "normal", "tier": "A", "pages": pages},
            "axis": {"device": "phone-390", "language": "en"},
            "ka": {"kind": "keep-abreast", "lens": lens, "unit": unit, "aliases": aliases, "trips": list(trips), "ask": ask,
                   "detail": detail, "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                   "closes": "the lens's instrument proves the unit, and the trip (freshness_trip.py) is quiet for it"},
        })
    keep_abreast_rows.arithmetic = {k: sum(1 for r in rows if r["ka"]["lens"] == k) for k in KA_LENS}
    return rows


# ★THE CUBE (CX1.., 2026-10-26) - Ian: "add more appropriate number of open trajectories ... for the U x F x A x I x UI x UX
# x each architectural full stack saas layers x each production pages x each public pages x personas x journey scenarios";
# decided the same day: EVERY GATE-ADMITTED PERSONA. The population is tools/cube_census.py (one place decides the size):
# U/F/I x applicable layer x admitted persona, A x applicable layer, and the (page, rubric class) cells never graded.
CX_PREFIX = "CX"
CX_WAVE = {"production": "CX-PROD", "founder": "CX-FND", "public": "CX-PUB"}
CX_PILLAR = {
    "U": ("the person can tell", ["U"]),
    "F": ("it is true and wired", ["F"]),
    "I": ("this persona may, and may not", ["I"]),
    "A": ("at phone-390 and desktop-1280, offline and on 429", ["A"]),
}


def cube_rows(existing: list[dict], replay: bool = False, only_class: str | None = None) -> list[dict]:
    """One row per EMPTY applicable cell of the cube, plus one per (page, rubric class) never graded (CX-UX). replay=True
    returns what was SEEDED, in id order, from the registry's cx metadata (the BRP/BRH rule)."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("cx") or {}).get("kind") in ("cube", "cube-ux")),
                        key=lambda x: int(str(x["id"])[len(CX_PREFIX):] or 0))
        cube_rows.arithmetic = {}
        return [{"wave": t["wave"], "cx": t["cx"]} for t in seeded]
    import cube_census as cc
    from sublayer_inventory import casts as _casts
    c = cc.census()
    cast_of_page = _casts(existing, c["classes"])
    have = {((x.get("cx") or {}).get("kind"), (x.get("cx") or {}).get("page"), (x.get("cx") or {}).get("pillar"),
             (x.get("cx") or {}).get("layer"), (x.get("cx") or {}).get("persona"), (x.get("cx") or {}).get("rubric_class"))
            for x in existing if (x.get("cx") or {}).get("kind") in ("cube", "cube-ux")}
    rows: list[dict] = []
    order = {"production": 0, "founder": 1, "public": 2}
    for cell in sorted(c["cells"], key=lambda z: (order[z["cls"]], z["page"], z["layer"], z["pillar"], z["persona"] or "")):
        if only_class and only_class != cell["cls"]:
            continue
        key = ("cube", cell["page"], cell["pillar"], cell["layer"], cell["persona"], None)
        if key in have:
            continue
        page, layer, pillar = cell["page"], cell["layer"], cell["pillar"]
        persona = cell["persona"] or cast_of_page.get(page) or ("anon" if cell["cls"] == "public" else "worker")
        ask, _dims = LAYER_LENS[layer]
        frame, ufai = CX_PILLAR[pillar]
        who = "a person" if persona == "any" else persona
        if cell["cls"] == "public" or persona == "anon":
            pages, entry = (["index.html", page] if page != "index.html" else [page]), "search-arrival"
        elif persona == "oversight" and page != "index.html" and not _hub_roles().get(page):
            pages, entry = [page], "direct"
        else:
            pages, entry = _path(_start(page), page, [], cast=_cast_of(persona)), ("direct" if page == "index.html" else "hub-nav")
        rows.append({
            "wave": CX_WAVE[cell["cls"]],
            "title": f"{frame}: {ask[:80]} - {who} · {_short(page)}",
            "pages": list(pages),
            "layers": [layer],
            "ufai": list(ufai),
            "persona": persona,
            "device": "any",
            "entry": entry,
            "framing": "person",
            "story": (f"{who} reaches {_short(page)} ({' -> '.join(_short(p) for p in pages)}) and the {layer} layer's ask - {ask} - is read "
                      f"through the {pillar} lens: {frame}. One walk of this page as this persona answers every layer x pillar row of "
                      f"the cell (the LX batch rule); the contract sub-layers close by the registered library prover; measured at "
                      f"{' and '.join(LX_VIEWPORTS)}, WebKit where the sub-layer is engine-sensitive"),
            "journey": {"archetype": f"{CX_WAVE[cell['cls']]}:{persona}", "stage": "operate" if cell["cls"] != "public" else "acquire",
                        "vertical": HIVES[(len(page) + len(layer)) % len(HIVES)], "pair": "", "language": "en", "moment": "present",
                        "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "cx": {"kind": "cube", "cls": cell["cls"], "page": page, "pillar": pillar, "layer": layer, "persona": cell["persona"],
                   "cast": persona, "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                   "closes": f"the {layer} ask is answered through the {pillar} lens from {_short(page)} itself, as {who}, with a receipt"},
        })
    if not only_class or only_class == "ux":
        for cell in sorted(c["ux"], key=lambda z: (order[z["cls"]], z["page"], z["rubric_class"])):
            key = ("cube-ux", cell["page"], None, None, None, cell["rubric_class"])
            if key in have:
                continue
            page = cell["page"]
            persona = cast_of_page.get(page) or ("anon" if cell["cls"] == "public" else "worker")
            who = "a person" if persona == "any" else persona
            pages = ["index.html", page] if (cell["cls"] == "public" and page != "index.html") else [page]
            rows.append({
                "wave": "CX-UX",
                "title": f"the rubric class {cell['rubric_class']} question asked of this page - {who} · {_short(page)}",
                "pages": pages, "layers": ["F"], "ufai": ["U"], "persona": persona, "device": "any",
                "entry": "search-arrival" if cell["cls"] == "public" else "hub-nav", "framing": "person",
                "story": (f"{who} reaches {_short(page)} and the critic asks every dimension of rubric class {cell['rubric_class']} "
                          f"(ufai-rubric-spec.json) of it - no row on this page has ever been graded on that class; the walk is "
                          f"critiqued when it lands, at {' and '.join(LX_VIEWPORTS)}"),
                "journey": {"archetype": f"CX-UX:{persona}", "stage": "operate" if cell["cls"] != "public" else "acquire",
                            "vertical": HIVES[len(page) % len(HIVES)], "pair": "", "language": "en", "moment": "present",
                            "condition": "normal", "tier": "A", "pages": pages},
                "axis": {"device": "phone-390", "language": "en"},
                "cx": {"kind": "cube-ux", "cls": cell["cls"], "page": page, "rubric_class": cell["rubric_class"], "cast": persona,
                       "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                       "closes": f"rubric class {cell['rubric_class']} graded on {_short(page)} by the critic deepwalk, with findings fixed"},
            })
    cube_rows.arithmetic = {"by_wave": Counter(r["wave"] for r in rows), "walk_cells": c["walk_cells"], "table": c["table"]}
    return rows


# ★WHAT I ADD FROM MY OWN READING (OWN1.., 2026-10-26) - Ian: "from your understanding of all my number trajectories, you have
# to add more necessary and appropriate number of trajectories from your own." The population is tools/own_lenses_census.py.
OWN_PREFIX = "OWN"


def own_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """One row per empty cell of the nine OWN lenses (tools/own_lenses_census.py). replay=True returns what was SEEDED."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("own") or {}).get("kind") == "own"),
                        key=lambda x: int(str(x["id"])[len(OWN_PREFIX):] or 0))
        own_rows.arithmetic = {}
        return [{"wave": t["wave"], "own": t["own"]} for t in seeded]
    import own_lenses_census as oc
    from sublayer_inventory import casts as _casts, page_classes as _pc
    c = oc.census()
    classes = _pc()
    cast_of_page = _casts(existing, classes)
    have = {((x.get("own") or {}).get("lens"), (x.get("own") or {}).get("unit"), (x.get("own") or {}).get("ask"))
            for x in existing if (x.get("own") or {}).get("kind") == "own"}
    rows: list[dict] = []
    for cell in c["cells"]:
        if (cell["lens"], cell["unit"], cell["ask"]) in have:
            continue
        page = cell["page"]
        persona = cell.get("persona") or cast_of_page.get(page) or "worker"
        who = "a person" if persona == "any" else persona
        is_public = page.startswith("learn/") or page.startswith("tools/") or page in ("about/index.html", "feedback/index.html")
        if is_public or persona == "anon":
            pages, entry = (["index.html", page] if page != "index.html" else [page]), "search-arrival"
        elif persona == "oversight" and page != "index.html":
            pages, entry = [page], "direct"
        else:
            pages, entry = _path(_start(page), page, [], cast=_cast_of(persona)), ("direct" if page == "index.html" else "hub-nav")
        unit = cell["unit"] if len(cell["unit"]) <= 50 else cell["unit"][:47] + "..."
        rows.append({
            "wave": "OWN",
            "title": f"{cell['lens']}: {cell['ask'][:70]} - {unit} · {who}",
            "pages": list(pages), "layers": [cell["layer"]], "ufai": list(cell["ufai"]), "persona": persona, "device": "any",
            "entry": entry, "framing": "person",
            "story": (f"{who} meets the {cell['lens']} lens on {cell['unit']}: {cell['ask']}. MEASURED: {cell['detail']}. The row closes on "
                      f"the instrument the lens names - psql for jobs, the refused-route fixture for dependencies, --engine webkit, "
                      f"two browser contexts, emulateMedia/zoom, chrome-devtools CPU throttling - at {' and '.join(LX_VIEWPORTS)} where a "
                      f"page is involved"),
            "journey": {"archetype": f"OWN:{persona}", "stage": "operate" if not is_public else "acquire",
                        "vertical": HIVES[len(cell["unit"]) % len(HIVES)], "pair": "", "language": "en", "moment": "present",
                        "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "own": {"kind": "own", "lens": cell["lens"], "unit": cell["unit"], "ask": cell["ask"], "page": page, "detail": cell["detail"],
                    "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                    "closes": f"the {cell['lens']} ask is proven on {cell['unit']} with a receipt"},
        })
    own_rows.arithmetic = {"by_lens": Counter(r["own"]["lens"] for r in rows), "population": c["population"]}
    return rows


# ★THE OUTCOME WAVES (SE1.., OUT1.., JS1..; 2026-10-26) - Ian's model: the five lenses improve the person's self-efficacy and
# the platform's system characteristics, which raise intention to use and satisfaction, which lead to usage. The population
# is tools/trajectory_outcome_gaps.py (one place decides the size); the dependent variables join the registry as rows.
SE_PREFIX, OUT_PREFIX, JS_PREFIX = "SE", "OUT", "JS"
SE_LAYERS = {"mastery": ["F", "L"], "vicarious": ["F", "CA"], "verbal persuasion": ["CA", "L"], "emotional state": ["F", "D"]}


def _outcome_route(page: str, persona: str) -> tuple[list[str], str]:
    is_public = page.startswith("learn/") or page.startswith("tools/") or page in ("about/index.html", "feedback/index.html")
    if is_public or persona == "anon":
        return (["index.html", page] if page != "index.html" else [page]), "search-arrival"
    if persona == "oversight" and page != "index.html":
        return [page], "direct"
    return _path(_start(page), page, [], cast=_cast_of(persona)), ("direct" if page == "index.html" else "hub-nav")


def self_efficacy_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """Wave SE: one row per (page, source of self-efficacy) the census finds empty. replay=True returns what was SEEDED."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("se") or {}).get("kind") == "self-efficacy"),
                        key=lambda x: int(str(x["id"])[len(SE_PREFIX):] or 0))
        self_efficacy_rows.arithmetic = {}
        return [{"wave": t["wave"], "se": t["se"]} for t in seeded]
    import trajectory_outcome_gaps as og
    pg = og.pages()
    rows: list[dict] = []
    for c in og.se_cells(existing, pg):
        page, src, persona = c["page"], c["source"], c["persona"]
        pages, entry = _outcome_route(page, persona)
        who = "a first-timer" if persona == "anon" else f"a first-time {persona}"
        rows.append({
            "wave": "SE",
            "title": f"self-efficacy · {src}: {c['ask'].split('(')[0].strip()[:78]} - {_short(page)} · {who}",
            "pages": list(pages), "layers": list(SE_LAYERS[src]), "ufai": ["U", "F"], "persona": persona, "device": "any", "entry": entry,
            "framing": "person",
            "story": (f"{who} reaches {_short(page)} ({' -> '.join(_short(p) for p in pages)}) and the {src} source of self-efficacy is asked of "
                      f"it: {c['ask']}. Primary action: {c['primary']}. Fixture: {c['fixture']}. Measured at {' and '.join(LX_VIEWPORTS)}; the row "
                      f"closes when the first-timer completes the task unaided (mastery) or the page shows / says / forgives as asked"),
            "journey": {"archetype": f"SE:{src}", "stage": "acquire" if persona == "anon" else "operate", "vertical": HIVES[len(page) % len(HIVES)],
                        "pair": "", "language": "en", "moment": "present", "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "se": {"kind": "self-efficacy", "page": page, "source": src, "ask": c["ask"], "primary": c["primary"], "fixture": c["fixture"],
                   "viewports": list(LX_VIEWPORTS), "instrument": LX_INSTRUMENT,
                   "closes": f"the {src} source is proven on {_short(page)} as {who} at both viewports, with a receipt"},
        })
    self_efficacy_rows.arithmetic = {"by_source": Counter(r["se"]["source"] for r in rows), "population": og.pages().get("production") and
                                     {"production": len(pg["production"]), "calculators": len(pg["calc"]), "learn": len(pg["learn"])}}
    return rows


def outcome_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """Wave OUT: one row per (page, outcome) plus the console's figure surfaces and the never-typed gates."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("out") or {}).get("kind") == "outcomes"),
                        key=lambda x: int(str(x["id"])[len(OUT_PREFIX):] or 0))
        outcome_rows.arithmetic = {}
        return [{"wave": t["wave"], "out": t["out"]} for t in seeded]
    import trajectory_outcome_gaps as og
    pg = og.pages()
    rows: list[dict] = []
    for c in og.out_cells(existing, pg):
        page, oc, persona = c["page"], c["outcome"], c["persona"]
        pages, entry = _outcome_route(page, persona)
        rows.append({
            "wave": "OUT",
            "title": f"outcome · {oc}: {c['ask'].split('(')[0].strip()[:78]} - {_short(page)} · {persona}",
            "pages": list(pages), "layers": ["L", "D"], "ufai": ["F", "I"], "persona": persona, "device": "any", "entry": entry,
            "framing": "person",
            "story": (f"{persona} reaches {_short(page)} and the outcome '{oc}' becomes a figure the roadmap can hold: {c['ask']}. The figure "
                      f"carries its period and its basis beside it (a qualifier near its figure); tools/prove_outcome_figures.py recomputes it "
                      f"through psql and the row closes when the console's number equals the ledger's"),
            "journey": {"archetype": f"OUT:{oc}", "stage": "grow", "vertical": HIVES[len(page) % len(HIVES)], "pair": "", "language": "en",
                        "moment": "present", "condition": "normal", "tier": "A", "pages": list(pages)},
            "axis": {"device": "phone-390", "language": "en"},
            "out": {"kind": "outcomes", "page": page, "outcome": oc, "ask": c["ask"], "viewports": list(LX_VIEWPORTS),
                    "instrument": "psql + playwright-mcp (the console figure against the ledger)",
                    "closes": f"the '{oc}' figure for {_short(page)} is computed from analytics_events, shown with its period and basis, and equals the psql recomputation"},
        })
    outcome_rows.arithmetic = {"by_outcome": Counter(r["out"]["outcome"] for r in rows)}
    return rows


def journey_condition_rows(existing: list[dict], replay: bool = False) -> list[dict]:
    """Wave JS: every stage degraded (archetype x condition not yet walked), the daily archetypes aged, the two-sided
    marketplace archetypes recast from the seller's side."""
    if replay:
        seeded = sorted((x for x in existing if (x.get("js") or {}).get("kind") in ("condition", "moment", "seller-recast", "seller-floor")),
                        key=lambda x: int(str(x["id"])[len(JS_PREFIX):] or 0))
        journey_condition_rows.arithmetic = {}
        return [{"wave": t["wave"], "js": t["js"]} for t in seeded]
    import trajectory_outcome_gaps as og
    import seed_expansion_wave3 as w3
    cond_text = dict(w3.CONDITIONS)
    mom_text = dict(w3.MOMENTS)
    rows: list[dict] = []
    for c in og.js_cells(existing, og.pages()):
        a, axis, val = c["archetype"], c["axis"], c["value"]
        persona = c["persona"] or "worker"
        pages = list(c["pages"])
        if axis == "recast":
            vertical = c.get("vertical", HIVES[0])
            kind, cond, mom = "seller-recast", "normal", "present"
            title = f"journey {a} from the seller's side: {c['title'][:70]} - {vertical}"
            story = (f"{c['title']} - walked with the SELLER as the walker ({vertical}), the side the buyer's rows never cast: the listing, the "
                     f"hail, the acceptance, the dispute as the provider meets them, at {' and '.join(LX_VIEWPORTS)}")
        elif axis == "condition":
            vertical = HIVES[len(a) % len(HIVES)]
            kind, cond, mom = "condition", val, "present"
            title = f"journey {a} degraded - {cond_text.get(val, val)}: {c['title'][:60]}"
            story = (f"{c['title']} - lived start to end {cond_text.get(val, val)} (the W4 --condition fixture: 3G route delay with aborts, a refused "
                     f"dependency, a release mid-walk), as {persona}, at {' and '.join(LX_VIEWPORTS)}; the postgres MCP the witness")
        else:
            vertical = HIVES[len(a) % len(HIVES)]
            kind, cond, mom = "moment", "normal", val
            title = f"journey {a} aged - {mom_text.get(val, val)}: {c['title'][:60]}"
            story = (f"{c['title']} - lived {mom_text.get(val, val)} (the --moment fixture: a hive with that much history behind every screen), "
                     f"as {persona}, at {' and '.join(LX_VIEWPORTS)}")
        rows.append({
            "wave": "JS", "title": title, "pages": pages, "layers": list(c["layers"]), "ufai": list(c["ufai"]), "persona": persona,
            "device": "any", "entry": c.get("entry") or "hub-nav", "framing": "person", "story": story,
            "journey": {"archetype": a, "stage": c["stage"], "vertical": vertical, "pair": c.get("pair") or "", "language": "en",
                        "moment": mom, "condition": cond, "tier": "A", "pages": pages},
            "axis": {"device": "phone-390", "language": "en"},
            "js": {"kind": kind, "archetype": a, "axis": axis, "value": val, "vertical": vertical, "viewports": list(LX_VIEWPORTS),
                   "instrument": "playwright-mcp + postgres-mcp (prove_full_journeys.mjs --condition / --moment)",
                   "closes": f"{a} walked start to end under this {axis} at both viewports, every hop a route the cast may walk, with a receipt"},
        })
    journey_condition_rows.arithmetic = {"by_axis": Counter(f"{r['js']['axis']}:{r['js']['value']}" for r in rows)}
    return rows


def _place_by_wave(existing: list, created: list) -> list:
    """Each new row goes directly after the last row of its own wave, or after the last row of its id space for a
    wave's first row, so every wave stays one contiguous block in the order validate_trajectory_registry replays.
    ★OPC106..109 (2026-10-22) were appended after the ENH-R block and failed the gate's order check: OPC-O and OPC-G
    rows must follow OPC32 and OPC82, the last rows of their waves, not the end of the registry."""
    out = list(existing)
    for r in created:
        prefix = re.match(r"[A-Z]+", r["id"]).group(0)
        idx = max((i for i, t in enumerate(out) if t.get("wave") == r["wave"]), default=None)
        if idx is None:
            idx = max((i for i, t in enumerate(out) if re.fullmatch(rf"{prefix}\d+", t["id"])), default=len(out) - 1)
        out.insert(idx + 1, r)
    return out


def _append_own_space(existing: list, rows: list, prefix: str) -> list:
    have = {t["id"] for t in existing}
    nxt, created = 1, []
    for r in rows:
        while f"{prefix}{nxt}" in have:
            nxt += 1
        rid = f"{prefix}{nxt}"
        have.add(rid)
        created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))
    return created


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cells", action="store_true")
    ap.add_argument("--add-confusions", action="store_true",
                    help="append one W4 row per axis for every w4_confusions.json entry not yet seeded")
    ap.add_argument("--add-design", action="store_true",
                    help="append one W4 row per served page per applicable design lens (LENSES) not yet seeded")
    ap.add_argument("--add-layer-ux", action="store_true",
                    help="append one LX row per (persona, layer, page) for every empty persona x layer cell, both viewports")
    ap.add_argument("--add-layer-floor", action="store_true",
                    help="LXC (2026-10-06): lift every signed-in persona's thin persona x layer cell to LXC_FLOOR")
    ap.add_argument("--add-llm-layer", action="store_true",
                    help="LM (2026-10-06): the 14th layer - one row per (sub-layer, persona, AI surface)")
    ap.add_argument("--add-bug-repro", action="store_true",
                    help="append one BRP row per MEASURED defect site (tools/bug_repro_inventory.py), both viewports")
    ap.add_argument("--add-bug-hunt", action="store_true",
                    help="BRH (2026-10-14): append one row per MEASURED defect site (tools/bug_hunt_inventory.py), both viewports")
    ap.add_argument("--add-sublayers", action="store_true",
                    help="SL (2026-10-14): one row per (page, layer, sub-layer) cell (tools/sublayer_inventory.py)")
    ap.add_argument("--add-enhancements", action="store_true",
                    help="ENH (2026-10-14): one row per capability a page lacks (tools/enhancement_inventory.py)")
    ap.add_argument("--add-operator-console", action="store_true",
                    help="OPC (2026-10-14): one row per panel the one operator console holds "
                         "(tools/operator_console_inventory.py)")
    ap.add_argument("--add-keep-abreast", action="store_true",
                    help="KA (2026-10-26): one row per unit of the KEEP ABREAST census (tools/freshness_trip.py) - the "
                         "public URLs (refresh, push), the SEO evidence spine, the English SOV prompts, the board's instruments")
    ap.add_argument("--add-cube", action="store_true",
                    help="CX (2026-10-26): one row per EMPTY cell of the cube (tools/cube_census.py) - U/F/I x layer x admitted "
                         "persona, A x layer, and the (page, rubric class) cells never graded")
    ap.add_argument("--class", dest="only_class", choices=["production", "founder", "public", "ux"],
                    help="--add-cube: seed one page class (or the UX face) at a time")
    ap.add_argument("--add-own", action="store_true",
                    help="OWN (2026-10-26): one row per empty cell of the nine lenses in tools/own_lenses_census.py")
    ap.add_argument("--add-self-efficacy", action="store_true",
                    help="SE (2026-10-26): one row per (page, source of self-efficacy) - tools/trajectory_outcome_gaps.py")
    ap.add_argument("--add-outcomes", action="store_true",
                    help="OUT (2026-10-26): one row per (page, outcome: use / return / repeat use) + the console figures and gates")
    ap.add_argument("--add-journey-conditions", action="store_true",
                    help="JS (2026-10-26): every stage degraded, the daily archetypes aged, the seller's side of the trade archetypes")
    args = ap.parse_args()
    doc = _rio.load_doc()
    existing = doc["trajectories"]
    scoped = [t for t in existing if t.get("status") != "descoped"]

    if args.add_layer_floor or args.add_llm_layer:
        # ★BOTH SEED INTO THEIR OWN ID SPACE, appended after every existing wave (the BRP pattern), and print THE
        # NUMBER from the plan itself - Ian asked to see the new rows before anything is written (2026-10-06).
        if args.add_layer_floor:
            rows = layer_floor_rows(existing)
            a = layer_floor_rows.arithmetic
            label, prefix = "LXC layer floor", LXC_PREFIX
        else:
            rows = llm_layer_rows(existing)
            a = llm_layer_rows.arithmetic
            label, prefix = "LM layer", LM_PREFIX
        if not rows:
            print(f"  {label}: nothing to add - every planned row is already seeded")
            return 0
        created = _append_own_space(existing, rows, prefix)
        print(f"  THE NUMBER, measured from the registry ({label}):")
        if args.add_layer_floor:
            print(f"    floor {LXC_FLOOR} per signed-in persona x layer cell")
            print("    by persona  " + " · ".join(f"{k} {v}" for k, v in a["by_persona"].most_common()))
            print("    by layer    " + " · ".join(f"{k} {v}" for k, v in a["by_layer"].most_common()))
            for p, l, need, got in a["short_cells"]:
                print(f"    short: {p} x {l} needed {need}, only {got} unseeded reached page(s)")
        else:
            print(f"    {a['surfaces']} AI surfaces (incl. the companion) x {len(LM_SUBLAYERS)} sub-layers = "
                  f"{a['baseline']} baseline rows (persona any)")
            print("    persona depth  " + " · ".join(f"{k} {v}" for k, v in a["depth"].most_common())
                  + f"  = {sum(a['depth'].values())}")
            print("    by sub-layer   " + " · ".join(f"{k} {a['by_sub'][k]}" for k in LM_SUBLAYERS))
        print(f"    = {len(created)} new rows ({created[0]['id']}..{created[-1]['id']}), each walked at "
              f"{' and '.join(LX_VIEWPORTS)}")
        print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(created)} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:140]}")
            print(f"  {created[-1]['id']:<7} {created[-1]['title'][:140]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = existing + created
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402  - the same flow BRP and LXP follow
        seed_missing()
        print(chr(10) + f"  wrote {len(created)} {label} row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0
    if args.add_sublayers or args.add_enhancements or args.add_operator_console:
        # ★THE THREE WAVES OF 2026-10-14, each into its OWN id space, each printing THE NUMBER from its inventory before
        # anything is written (Ian asks to see the new rows first - feedback_extend_the_existing_roadmap_never_a_side_program).
        if args.add_sublayers:
            rows, label, prefix = sublayer_rows(existing), "SL sub-layer", SL_PREFIX
            a = sublayer_rows.arithmetic
        elif args.add_enhancements:
            rows, label, prefix = enhancement_rows(existing), "ENH enhancement", ENH_PREFIX
            a = enhancement_rows.arithmetic
        else:
            rows, label, prefix = operator_console_rows(existing), "OPC operator console", OPC_PREFIX
            a = operator_console_rows.arithmetic
        if not rows:
            print(f"  {label}: every measured cell is already seeded - nothing to add")
            return 0
        created = _append_own_space(existing, rows, prefix)
        print(f"  THE NUMBER, measured by the inventory (never typed) - {label}:")
        if args.add_sublayers:
            from sublayer_inventory import CLASSES as _SLC, SUBLAYERS as _SLS
            per = Counter((r["sl"]["layer"], r["sl"]["page_class"]) for r in created)
            subs = Counter(r["sl"]["sublayer"] for r in created)
            print(f"    {'layer':<6} {'production':>10} {'founder':>8} {'public':>7} {'rows':>6}   sub-layers")
            for lay, s in _SLS.items():
                n = [per[(lay, k)] for k in _SLC]
                print(f"    {lay:<6} {n[0]:>10} {n[1]:>8} {n[2]:>7} {sum(n):>6}   "
                      + " · ".join(f"{c} {subs[c]}" for c in s))
            tot = [sum(per[(lay, k)] for lay in _SLS) for k in _SLC]
            print(f"    {'all':<6} {tot[0]:>10} {tot[1]:>8} {tot[2]:>7} {sum(tot):>6}   "
                  f"({sum(len(s) for s in _SLS.values())} sub-layers; engine webkit on {a['webkit']} rows)")
        elif args.add_enhancements:
            from enhancement_inventory import CLASSES as _EC
            for c, (lab, lay) in _EC.items():
                print(f"    {c} · {lab:<54} (layer {lay:<2}): {a.get(c, 0)}")
            print(f"    public {a.get('public', 0)} · production {a.get('production', 0)}")
        else:
            print(f"    measured {a['raw']} panel cells - {a['exact']} same panel on two surfaces - {a['near']} console "
                  f"panels that are Grafana panels")
            for w, nm in OPC_KIND_NAME.items():
                print(f"    {OPC_PREFIX}-{w} · {nm:<40} {a.get(w, 0)}")
        print(f"    = {len(created)} new rows ({created[0]['id']}..{created[-1]['id']}), each walked at "
              f"{' and '.join(LX_VIEWPORTS)}")
        print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(created)} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:150]}")
            print(f"  {created[-1]['id']:<7} {created[-1]['title'][:150]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = _place_by_wave(existing, created)
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402  - the same flow BRP, LXP, LXC, LM and BRH follow
        seed_missing()
        print("\n" + f"  wrote {len(created)} {label} row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0
    if args.add_self_efficacy or args.add_outcomes or args.add_journey_conditions:
        # ★THE OUTCOME WAVES (2026-10-26): each into its own id space, THE NUMBER from tools/trajectory_outcome_gaps.py first
        if args.add_self_efficacy:
            rows, label, prefix = self_efficacy_rows(existing), "SE self-efficacy", SE_PREFIX
            a = self_efficacy_rows.arithmetic
            detail = "    by source   " + " · ".join(f"{k} {v}" for k, v in a["by_source"].items())
        elif args.add_outcomes:
            rows, label, prefix = outcome_rows(existing), "OUT outcomes", OUT_PREFIX
            a = outcome_rows.arithmetic
            detail = "    by outcome  " + " · ".join(f"{k} {v}" for k, v in a["by_outcome"].items())
        else:
            rows, label, prefix = journey_condition_rows(existing), "JS journey scenarios", JS_PREFIX
            a = journey_condition_rows.arithmetic
            detail = "    by axis     " + " · ".join(f"{k} {v}" for k, v in sorted(a["by_axis"].items()))
        if not rows:
            print(f"  {label}: every measured cell is already seeded - nothing to add")
            return 0
        created = _append_own_space(existing, rows, prefix)
        print(f"  THE NUMBER, measured by tools/trajectory_outcome_gaps.py (never typed) - {label}:")
        print(detail)
        print(f"    = {len(created)} new rows ({created[0]['id']}..{created[-1]['id']}), each walked at {' and '.join(LX_VIEWPORTS)}")
        print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(created)} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:140]}")
            print(f"  {created[-1]['id']:<7} {created[-1]['title'][:140]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = _place_by_wave(existing, created)
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402
        seed_missing()
        print("\n" + f"  wrote {len(created)} {label} row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0
    if args.add_cube or args.add_own:
        if args.add_cube:
            rows, label, prefix = cube_rows(existing, only_class=args.only_class), "CX cube", CX_PREFIX
            a = cube_rows.arithmetic
        else:
            rows, label, prefix = own_rows(existing), "OWN own-reading", OWN_PREFIX
            a = own_rows.arithmetic
        if not rows:
            print(f"  {label}: every measured cell is already seeded - nothing to add")
            return 0
        created = _append_own_space(existing, rows, prefix)
        print(f"  THE NUMBER, measured by the census (never typed) - {label}:")
        if args.add_cube:
            for cls, t in a["table"].items():
                print(f"    {cls:<11} pages {t['pages']:>4} · walk cells {t['walk_cells']:>4} · U/F/I x layer x persona empty "
                      f"{t['persona_empty']:>6} of {t['persona_cells']:>6} · A x layer empty {t['layer_empty']:>4} of {t['layer_cells']:>5} · UX {t['ux_empty']:>4}")
            print("    by wave  " + " · ".join(f"{k} {v}" for k, v in a["by_wave"].items()) + f"  ({a['walk_cells']} walk cells in all)")
        else:
            print("    population  " + " · ".join(f"{k} {v}" for k, v in a["population"].items()))
            print("    by lens     " + " · ".join(f"{k} {v}" for k, v in a["by_lens"].items()))
        print(f"    = {len(created)} new rows ({created[0]['id']}..{created[-1]['id']}), each walked at {' and '.join(LX_VIEWPORTS)}")
        print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(created)} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:140]}")
            print(f"  {created[-1]['id']:<7} {created[-1]['title'][:140]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = _place_by_wave(existing, created)
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402
        seed_missing()
        print("\n" + f"  wrote {len(created)} {label} row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0
    if args.add_keep_abreast:
        rows = keep_abreast_rows(existing)
        if not rows:
            print("  keep-abreast: every unit of the census is already seeded - nothing to add")
            return 0
        a = keep_abreast_rows.arithmetic
        created = _append_own_space(existing, rows, KA_PREFIX)
        print("  THE NUMBER, measured by tools/freshness_trip.py's census (never typed) - KEEP ABREAST:")
        for lens, (wave, layers, _u, persona, _e, _s, trips, ask) in KA_LENS.items():
            print(f"    {wave} · {ask[:70]:<70} ({'/'.join(layers)}, {persona}; re-opens on {', '.join(trips)}): {a.get(lens, 0)}")
        print(f"    = {len(created)} new KA rows ({created[0]['id']}..{created[-1]['id']})")
        print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(created)} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:140]}")
            print(f"  {created[-1]['id']:<7} {created[-1]['title'][:140]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = _place_by_wave(existing, created)
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402  - the same flow BRP, LXP, LXC, LM, BRH, SL, ENH and OPC follow
        seed_missing()
        print("\n" + f"  wrote {len(created)} keep-abreast row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0
    if args.add_bug_hunt:
        rows = bug_hunt_rows(existing)
        if not rows:
            print("  bug-hunt: every measured defect site is already seeded - nothing to add")
            return 0
        a = bug_hunt_rows.arithmetic
        created = _append_own_space(existing, rows, BRH_PREFIX)
        print("  THE NUMBER, measured against the real source and the committed evidence (never typed):")
        for cls, (layer, _p, mech, _r, _f) in BRH_CLASS.items():
            print(f"    class {cls} · {mech[:62]:<62} (layer {layer}): {a.get(cls, 0)}")
        print(f"    = {len(created)} new BRH rows ({created[0]['id']}..{created[-1]['id']})"
              f", each reproduced and fixed at {' and '.join(LX_VIEWPORTS)}")
        print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(created)} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:140]}")
            print("  (nothing written)")
            return 0
        # ★THE WAVE STAYS ONE BLOCK (2026-10-14, §BRH.2). The registry validator expects every named wave's ids in
        # seeding order, and SL, ENH and OPC were seeded after BRH237 - so later BRH rows go directly after the last
        # BRH row, never at the end, or BRH238.. would sit after OPC and fail the order check.
        last = max((i for i, t in enumerate(existing) if str(t.get("id", "")).startswith(BRH_PREFIX)
                    and str(t["id"])[len(BRH_PREFIX):].isdigit()), default=len(existing) - 1)
        doc["trajectories"] = existing[:last + 1] + created + existing[last + 1:]
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402  - the same flow BRP, LXP, LXC and LM follow
        seed_missing()
        print("\n" + f"  wrote {len(created)} bug-hunt row(s) into {REGISTRY.name} after {existing[last]['id']} "
              f"(registry now {doc['count']})")
        return 0
    if args.add_bug_repro:
        rows = bug_repro_rows(existing)
        if not rows:
            print("  bug-repro: every measured defect site is already seeded - nothing to add")
            return 0
        a = bug_repro_rows.arithmetic
        # BRP ids live in their OWN space (BRP1..), for the same reason LXP does: the registry validator
        # rebuilds them positionally, so they must never be interleaved with another wave's numbering.
        have = {t["id"] for t in existing}
        nxt = 1
        created = []
        for r in rows:
            while f"{BRP_PREFIX}{nxt}" in have:
                nxt += 1
            rid = f"{BRP_PREFIX}{nxt}"
            have.add(rid)
            created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))
        print("  THE NUMBER, measured against the real source and the real schema (never typed):")
        for c, label in (("A", "ownership by DISPLAY NAME where auth_uid exists  (layer AU)"),
                         ("B", "truth VIEW drops the auth_uid its base table has (layer D)"),
                         ("C", "no identity column anywhere - needs a migration  (layer D)")):
            print(f"    class {c} · {label}: {a.get(c, 0)}")
        print(f"    = {len(created)} new BRP rows ({created[0]['id']}..{created[-1]['id']})"
              f", each reproduced and fixed at {' and '.join(LX_VIEWPORTS)}")
        after = len(scoped) + len(created)
        print(f"  program: {len(scoped)} in scope today -> {after} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:140]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = existing + created
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402
        seed_missing()
        print(chr(10) + f"  wrote {len(created)} bug-repro row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0

    if args.add_layer_ux:
        rows = layer_ux_rows(existing)
        if not rows:
            print("  layer-ux: every (persona, layer, page) triple is already seeded - nothing to add")
            return 0
        a = layer_ux_rows.arithmetic
        # LX ids live in their own space (LX1..) alongside the existing LX-CI/LX-S rows
        have = {t["id"] for t in existing}
        nxt = 1
        created = []
        for r in rows:
            while f"{LX_PREFIX}{nxt}" in have:
                nxt += 1
            rid = f"{LX_PREFIX}{nxt}"
            have.add(rid)
            created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))
        print("  THE NUMBER, measured (empty persona x layer cells x the pages each persona reaches):")
        print("    gap A, layer breadth  " + " · ".join(f"{k} {v}" for k, v in sorted(a["gap_a"].items()))
              + f"  = {sum(a['gap_a'].values())}")
        print("    gap B, persona depth  " + " · ".join(f"{k} {v}" for k, v in sorted(a["gap_b"].items()))
              + f"  = {sum(a['gap_b'].values())}")
        print(f"    = {len(created)} new LX rows ({created[0]['id']}..{created[-1]['id']})"
              f", each walked at {' and '.join(LX_VIEWPORTS)}")
        after = len(scoped) + len(created)
        print(f"  program: {len(scoped)} in scope today -> {after} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:130]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = existing + created
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402
        seed_missing()
        print(f"\n  wrote {len(created)} layer-ux row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0

    if args.add_design:
        have = {t["id"] for t in existing}
        rows = design_rows(existing)
        if not rows:
            print("  design: every (page, lens) pair is already seeded - nothing to add")
            return 0
        a = design_rows.arithmetic
        nxt = 1
        created = []
        for r in rows:
            while f"{PREFIX}{nxt}" in have:
                nxt += 1
            rid = f"{PREFIX}{nxt}"
            have.add(rid)
            created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))
        print("  THE NUMBER, measured (served pages x applicable lenses):")
        print("    by class " + " · ".join(f"{k} {v}" for k, v in a["by_class"].items()))
        print("    by lens  " + " · ".join(f"{k} {v}" for k, v in a["by_lens"].items()))
        print(f"    = {len(created)} new W4 design rows ({created[0]['id']}..{created[-1]['id']})")
        after = len(scoped) + len(created)
        closed = sum(1 for t in scoped if t.get("status") == "locked")
        print(f"  program: {len(scoped)} in scope today -> {after} after seeding")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:130]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = existing + created
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402
        seed_missing()
        print(f"\n  wrote {len(created)} design row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0

    if args.add_confusions:
        have = {t["id"] for t in existing}
        rows = confusion_rows(existing)
        if not rows:
            print("  confusions: every ledger entry is already seeded - nothing to add")
            return 0
        nxt = 1
        created = []
        for r in rows:
            while f"{PREFIX}{nxt}" in have:
                nxt += 1
            rid = f"{PREFIX}{nxt}"
            have.add(rid)
            created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))
        by_c = Counter(r["w4"]["confusion"] for r in created)
        print("  confusions -> rows: " + " · ".join(f"{k} x{v}" for k, v in sorted(by_c.items()))
              + f"  = {len(created)} new W4 rows ({created[0]['id']}..{created[-1]['id']})")
        if args.dry_run:
            print(f"  {created[0]['id']:<7} {created[0]['title'][:120]}")
            print("  (nothing written)")
            return 0
        doc["trajectories"] = existing + created
        doc["count"] = len(doc["trajectories"])
        _rio.save_doc(doc)
        from critic_seed_missing import seed_missing  # noqa: E402
        seed_missing()
        print(f"\n  wrote {len(created)} confusion row(s) into {REGISTRY.name} (registry now {doc['count']})")
        return 0

    if args.cells:
        g = page_layer_cells(scoped)
        print(f"  PAGE x LAYER: {len(g['roster'])} pages x {len(LAYER_SET)} layers = {g['cells']} cells · "
              f"lived {len(g['lived'])} · not lived {len(g['not_lived'])} (uncovered {g['uncovered']} · "
              f"unexperienced {g['unexperienced']}) · pages with no layer lived {g['pages_with_none_lived']}")
        print("  not lived by layer: " + " · ".join(f"{k} {v}" for k, v in
                                                     sorted(g["by_layer"].items(), key=lambda kv: -kv[1])))
        print("  not lived by class: " + " · ".join(f"{k} {v}" for k, v in g["by_class"].items()))
        return 0

    have = {t["id"] for t in existing}
    rows = plan(existing)
    a = getattr(plan, "arithmetic", None)
    if a:
        print("  THE NUMBER, measured:")
        print("    action stories   " + " · ".join(f"{k} {v}" for k, v in a["actions_by_class"].items())
              + f"  = {a['actions']}")
        print(f"    nav-hub stories  {a['nav_hub']} (pages whose source loads nav-hub.js)")
        g = a["grid"]
        print(f"    layer stories    {a['layer_cells_not_lived']} cells not lived of {g['cells']} "
              f"(uncovered {g['uncovered']} · unexperienced {g['unexperienced']}) - "
              f"{a['layer_cells_not_lived'] - a['layer_cells_deduped']} lived by an action story on the same "
              f"page = {a['layer_cells_deduped']}   by class "
              + " · ".join(f"{k} {v}" for k, v in a["layer_by_class"].items()))
        print("                     by layer " + " · ".join(
            f"{k} {v}" for k, v in sorted(a["layer_by_layer"].items(), key=lambda kv: -kv[1])))
        print(f"    per axis         {a['actions']} + {a['nav_hub']} + {a['layer_cells_deduped']} = {a['per_axis']}")
        print(f"    x {a['axes']} axes        = {a['total']} new trajectories")
        after = len(scoped) + len(rows)
        print(f"  program: {len(scoped)} in scope today -> {after} after seeding "
              f"({100.0 * len(scoped) / after:.1f}% closed on seed day)")
    else:
        print(f"  W4 already seeded: plan() replays {len(rows)} rows")
    kinds = Counter(r["w4"]["kind"] for r in rows)
    print("  rows by kind: " + " · ".join(f"{k} {v}" for k, v in kinds.items())
          + " · by axis: " + " · ".join(
              f"{d}/{lg} {sum(1 for r in rows if r['axis'] == {'device': d, 'language': lg})}" for d, lg, _t in AXES))
    print(f"  >=4 pages: {sum(1 for r in rows if len(r['pages']) >= 4)}/{len(rows)}")

    nxt = 1
    created = []
    for r in rows:
        while f"{PREFIX}{nxt}" in have:
            nxt += 1
        rid = f"{PREFIX}{nxt}"
        have.add(rid)
        created.append(dict({"id": rid, "status": "specced", "pct": 5}, **r))

    if args.dry_run:
        for kind in ("action", "nav-hub", "layer"):
            for c in created:
                if c["w4"]["kind"] == kind:
                    print(f"  {c['id']:<7} {c['title'][:110]}")
                    print(f"          {' -> '.join(c['pages'])}")
                    break
        up = next((c for c in created if c["w4"].get("fixture")), None)
        if up:
            print(f"  upload  {up['id']} {up['title'][:100]}\n          {' -> '.join(up['pages'])}")
        print("  (nothing written)")
        return 0

    seen = {(t.get("title"), tuple(t.get("pages") or [])) for t in existing}
    fresh = [c for c in created if (c["title"], tuple(c["pages"])) not in seen]
    doc["trajectories"] = existing + fresh
    doc["count"] = len(doc["trajectories"])
    _rio.save_doc(doc)
    from critic_seed_missing import seed_missing  # noqa: E402
    seed_missing()
    print(f"\n  wrote {len(fresh)} new row(s) into {REGISTRY.name} (registry now {doc['count']})")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
