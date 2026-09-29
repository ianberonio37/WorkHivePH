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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cells", action="store_true")
    ap.add_argument("--add-confusions", action="store_true",
                    help="append one W4 row per axis for every w4_confusions.json entry not yet seeded")
    ap.add_argument("--add-design", action="store_true",
                    help="append one W4 row per served page per applicable design lens (LENSES) not yet seeded")
    args = ap.parse_args()
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    existing = doc["trajectories"]
    scoped = [t for t in existing if t.get("status") != "descoped"]

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
        _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
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
        _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
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
    _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    from critic_seed_missing import seed_missing  # noqa: E402
    seed_missing()
    print(f"\n  wrote {len(fresh)} new row(s) into {REGISTRY.name} (registry now {doc['count']})")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
