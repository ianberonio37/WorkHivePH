#!/usr/bin/env python3
"""seed_expansion_wave.py — the eight expansion waves of 2026-09-07, seeded as one change so the
denominator moves once and the header is honest from the first day (Ian: "let us expand and extend
the trajectories ... provide the number of new trajectories, update the open counts in the roadmap").

THE SPINE IS UFAI. Every row declares what it improves - Usability, Functionality, Adaptability or
Internal Control - at birth, alongside who is walking (`persona`), on what (`device`) and how they
arrived (`entry`). The framing is MIXED, on Ian's word: a person-feels row says what someone
experiences when it goes wrong; a contract row says what the platform MUST do, because a hostile
persona or a recovery path reads better as an obligation than as a feeling.

THE ROSTERS ARE READ, NOT REMEMBERED (the last wave's lesson, twenty times over): the Tagalog roster is
every root page without a `_t(` call, computed at plan time; the recovery roster is every control in
substrate/reference/destructive_control_registry.json; the thin-page roster is measured from the
registry itself. A roster typed from memory is a roster that drifts.

★×16: this file is the ONE place that decides how many rows the wave has. plan() emits them
wave-major, and tools/validate_trajectory_registry.py derives its expected ids from plan(), so the gate
and the seeder cannot disagree about the wave's size. tools/advance_trajectory.py stays the only
writer of status and basis; this seeder only creates.

  python tools/seed_expansion_wave.py --dry-run   # the per-wave table and the first row of each
  python tools/seed_expansion_wave.py             # write (idempotent on title+pages)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/ importable for critic_seed_missing

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
DESTRUCTIVE = ROOT / "substrate" / "reference" / "destructive_control_registry.json"
PREFIX = "EX"

# ── the pages, by the role they play (shared with seed_layer_ux_wave.py's vocabulary) ─────────────
INTERACTIVE = ["hive.html", "logbook.html", "inventory.html", "dayplanner.html", "alert-hub.html",
               "asset-hub.html", "community.html", "analytics.html", "marketplace.html",
               "shift-brain.html", "pm-scheduler.html", "skillmatrix.html", "achievements.html",
               "project-manager.html", "assistant.html", "voice-journal.html", "resume.html",
               "engineering-design.html", "marketplace-seller.html", "audit-log.html",
               "integrations.html", "project-report.html", "analytics-report.html", "report-sender.html"]
PUBLIC = ["index.html", "marketplace.html", "public-feed.html", "status.html",
          "marketplace-seller-profile.html", "ph-intelligence.html", "project-report.html"]
LISTS = ["logbook.html", "inventory.html", "community.html", "marketplace.html", "audit-log.html",
         "asset-hub.html", "pm-scheduler.html", "skillmatrix.html", "alert-hub.html", "hive.html"]
AI_SURFACES = ["assistant.html", "voice-journal.html", "shift-brain.html", "asset-hub.html",
               "resume.html", "analytics.html", "ai-quality.html", "agentic-rag-observability.html",
               "llm-observability.html", "community.html"]
CORE_JOURNEYS = ["index.html", "hive.html", "logbook.html", "inventory.html", "pm-scheduler.html",
                 "asset-hub.html", "community.html", "marketplace.html", "alert-hub.html", "analytics.html"]
SHIFT_PAGES = ["logbook.html", "shift-brain.html", "dayplanner.html", "pm-scheduler.html",
               "analytics.html", "report-sender.html"]
# the pages that are artifacts or catalogs, never a person's destination
NOT_A_DESTINATION = {"design-system.html", "symbol-gallery.html", "validator-catalog.html",
                     "promo-poster.html", "offline-fallback.html", "terms.html"}


def _root_pages() -> list[str]:
    return sorted(f for f in os.listdir(ROOT) if f.endswith(".html") and not f.startswith("_"))


def _english_only_pages() -> list[str]:
    """The Tagalog roster: every person-facing root page with no `_t(` call. Measured, not listed."""
    out = []
    for f in _root_pages():
        if f in NOT_A_DESTINATION:
            continue
        try:
            if "_t(" not in (ROOT / f).read_text(encoding="utf-8", errors="replace"):
                out.append(f)
        except OSError:
            pass
    return out


def _thin_pages(existing: list[dict], floor: int = 30) -> list[tuple[str, int]]:
    """(page, deficit) for every root page below the floor, from the registry itself."""
    c: Counter = Counter()
    for r in existing:
        if r.get("status") == "descoped":
            continue
        for p in (r.get("pages") or []):
            c[p] += 1
    return [(f, floor - c.get(f, 0)) for f in _root_pages()
            if f not in NOT_A_DESTINATION and c.get(f, 0) < floor]


def _destructive_controls() -> list[dict]:
    try:
        d = json.loads(DESTRUCTIVE.read_text(encoding="utf-8"))
    except Exception:
        return []
    # ★THE REGISTRY IS A DICT OF FILE -> CONTROLS, AND EACH CONTROL CARRIES THE CONFIRM'S FIRST WORDS.
    # The first version guessed a flat list with a `label` field and planned ZERO recovery rows - a
    # roster read from memory instead of from the file, the lesson this whole wave is built on.
    controls = d.get("controls") or {}
    out = []
    for path, items in (controls.items() if isinstance(controls, dict) else []):
        for c in (items if isinstance(items, list) else []):
            if not isinstance(c, dict):
                continue
            label = str(c.get("message_head") or c.get("label") or f"line {c.get('line', '?')}").strip().rstrip("\\")
            out.append({"page": os.path.basename(path), "label": label[:48] or "the control"})
    return out


# ── the waves ─────────────────────────────────────────────────────────────────────────────────────
# Each lens is written in the frame the wave declares. `cells` (PX) carry their own persona / device /
# entry; the others take the wave's default. `layers` is what the lens crosses.

PX_CELLS = [
    # (cell, persona, device, entry, layers, lens in a person's terms, roster)
    ("deep-link", "any", "phone-390", "deep-link", ["F", "H"],
     "You open this page from a link in a chat message and it has to make sense with no history", INTERACTIVE),
    ("first-time", "new-user", "phone-390", "hub-nav", ["F"],
     "It is your first time on this page, nobody is beside you, and it has to explain itself", INTERACTIVE),
    ("buyer", "buyer", "phone-390", "search-arrival", ["F", "D"],
     "You came to buy one part, and the page has to get you to it without making you a seller first",
     ["marketplace.html", "marketplace-seller-profile.html", "inventory.html", "index.html", "public-feed.html"]),
    ("data-volume", "fleet-supervisor", "desktop-1280", "hub-nav", ["D", "LB"],
     "This list holds a thousand rows now and the page has to stay a page, not a hang", LISTS),
    ("wide-pc", "oversight", "wide-1920", "hub-nav", ["F"],
     "On a 1920 monitor the content must use the screen without stranding itself or stretching a line past reading", INTERACTIVE),
    ("tablet", "worker", "tablet-768", "hub-nav", ["F"],
     "On a shared tablet at 768 the page must hold together in both orientations", INTERACTIVE),
    ("quota-spent", "worker", "phone-390", "hub-nav", ["RL", "A"],
     "The quota is gone and this page has to keep the rest of itself working and say what it cannot do",
     AI_SURFACES),
    ("expiry-mid-read", "worker", "phone-390", "hub-nav", ["AU", "AV"],
     "Your session ends while you are reading, not writing, and the page must not throw away where you were", INTERACTIVE),
    ("kiosk-print", "machine-client", "fixed-kiosk-print", "qr-print", ["F"],
     "This page is on a wall or a printout, unattended, and it must still be true and readable",
     ["status.html", "analytics.html", "dayplanner.html", "pm-scheduler.html", "alert-hub.html",
      "project-report.html", "analytics-report.html", "skillmatrix.html"]),
    ("email-arrival", "fleet-supervisor", "phone-390", "email-push", ["A", "F"],
     "You arrive from a notification and the page has to land you on the thing it notified you about",
     ["alert-hub.html", "logbook.html", "community.html", "marketplace.html", "pm-scheduler.html",
      "hive.html", "project-manager.html", "dayplanner.html"]),
    ("returner", "returner", "phone-390", "direct", ["AU", "F"],
     "You are back after weeks and this page has to show you where you left off, not a fresh start", INTERACTIVE),
]

TL_LENSES = [
    "Nagbabasa ka ng Tagalog muna, at ang pahinang ito ay dapat maintindihan nang hindi nagta-translate sa English",
    "Ang error sa pahinang ito ay dapat sabihin sa Tagalog kung ano ang nangyari at ano ang gagawin mo",
    "Kapag walang laman ang pahina, dapat sabihin nito sa Tagalog kung bakit, hindi lang blangko",
    "Ang bawat confirm at CTA sa pahinang ito ay dapat basahin sa Tagalog bago mo pindutin",
]

PF_LENSES = [
    "You open this page for the first time and can tell in one glance what it is for",
    "Every control on this page says what it will do before you press it",
    "This page says how fresh what you are seeing is",
    "When this page fails to load its data it tells you what is missing and what to do",
    "The most important number on this page can be traced to the rows behind it",
    "This page holds together on a phone with one thumb",
    "Nothing on this page moves under your finger after it has painted",
    "A keyboard-only person can reach every control on this page in a sensible order",
    "This page leads somewhere - it is a stop, not a cul-de-sac",
    "What you typed on this page survives a refresh, an interruption, and an expired session",
    "A person who does not have permission for this page is told so, kindly, and offered the way back",
    "This page's copy speaks the words a Philippine maintenance crew uses, not the platform's internals",
    "Two people on this page at once do not overwrite each other silently",
    "This page can be printed or shown on a wall and still be true",
]

HP_PERSONAS = [
    # (persona token, contract lens, roster, layers)
    ("adversary", "The platform must refuse an ex-employee whose session is still alive after they were removed from the hive",
     ["hive.html", "logbook.html", "inventory.html", "asset-hub.html", "audit-log.html", "community.html",
      "marketplace.html", "alert-hub.html", "dayplanner.html", "pm-scheduler.html", "analytics.html", "project-manager.html"],
     ["AU", "S"]),
    ("adversary", "The platform must give a competitor scraping the public surface nothing it does not give a stranger",
     ["index.html", "marketplace.html", "public-feed.html", "status.html", "marketplace-seller-profile.html",
      "ph-intelligence.html", "project-report.html", "learn/index.html"], ["S", "H"]),
    ("adversary", "The platform must refuse a seller who tries to rate, review or inflate their own standing",
     ["marketplace.html", "marketplace-seller.html", "marketplace-seller-profile.html", "community.html",
      "achievements.html", "skillmatrix.html"], ["S", "D"]),
    ("adversary", "The platform must bound what a supervisor can do in bulk, and record every bulk act with its actor",
     ["hive.html", "inventory.html", "pm-scheduler.html", "project-manager.html", "asset-hub.html",
      "audit-log.html", "platform-actions.html", "founder-console.html", "marketplace-admin.html"], ["S", "D", "L"]),
    ("adversary", "The platform must refuse an anonymous caller who forges another hive's id into a request",
     ["logbook.html", "inventory.html", "asset-hub.html", "community.html", "alert-hub.html",
      "voice-journal.html", "assistant.html", "marketplace.html"], ["S", "A"]),
    ("adversary", "The platform must not let a buyer disputing falsely take money or standing the seller has earned",
     ["marketplace.html", "marketplace-seller.html", "marketplace-seller-profile.html", "marketplace-admin.html"], ["S", "D"]),
    ("adversary", "The platform must bound and record what an insider can export, and say so to the people whose data it is",
     ["hive.html", "audit-log.html", "analytics-report.html", "report-sender.html", "project-report.html",
      "founder-console.html", "platform-actions.html", "integrations.html", "plant-connections.html"], ["S", "D", "L"]),
]

AT_LENSES = [
    "The AI on this page gives you a confident wrong answer and you have a way to flag it as wrong",
    "The AI on this page shows you what it answered FROM, so you can check it against the record",
    "You disagree with the AI on this page and there is a path to record your disagreement",
    "The AI on this page is out of quota and it says so, instead of answering with something thinner and not saying",
]

SB_LENSES = [
    ("At shift change, the person taking over can read what the last shift left in under a minute", "worker"),
    ("At 3am on the graveyard shift this page still works and does not assume anyone else is awake", "worker"),
    ("At month-end close this page's figures are the month's, not the calendar's UTC month", "fleet-supervisor"),
    ("On a weekend with one supervisor on call, this page does not wait on approvals nobody is there to give", "fleet-supervisor"),
    ("At the boundary of two shifts the page attributes work to the right shift, not to whoever saved last", "worker"),
]

AX_PERSONAS = [
    ("assistive-tech", "narrow-320", "A screen reader user completes this journey with what is announced, never with what is only seen"),
    ("assistive-tech", "desktop-1280", "A keyboard-only person completes this journey without a mouse, in a sensible order, seeing focus"),
    ("assistive-tech", "phone-390", "At 200% zoom a low-vision person completes this journey without horizontal scrolling or clipped text"),
    ("assistive-tech", "desktop-1280", "A colour-blind person completes this journey with nothing that is signalled by colour alone"),
]

WAVES: dict[str, dict] = {
    "PX": {"wave": f"{PREFIX}-PX", "name": "Persona x device x entry: the thin cells", "ufai": ["A", "U"], "framing": "person"},
    "TL": {"wave": f"{PREFIX}-TL", "name": "Tagalog-first persona", "ufai": ["U"], "framing": "person"},
    "PF": {"wave": f"{PREFIX}-PF", "name": "Per-page floor to 30", "ufai": ["U", "F"], "framing": "person"},
    "HP": {"wave": f"{PREFIX}-HP", "name": "Hostile personas", "ufai": ["I"], "framing": "contract"},
    "AT": {"wave": f"{PREFIX}-AT", "name": "AI trust: the confident wrong answer", "ufai": ["I", "U"], "framing": "person"},
    "RV": {"wave": f"{PREFIX}-RV", "name": "Recovery: I deleted the wrong thing", "ufai": ["I", "F"], "framing": "contract"},
    "SB": {"wave": f"{PREFIX}-SB", "name": "Shift boundary, month-end, 3am", "ufai": ["A"], "framing": "person"},
    "AX": {"wave": f"{PREFIX}-AX", "name": "Accessibility personas", "ufai": ["U", "A"], "framing": "person"},
}


def _short(page: str) -> str:
    return page.replace("/index.html", "").replace(".html", "").replace("-", " ")


def plan(existing: list[dict] | None = None) -> list[dict]:
    """Every row the wave would create, wave-major, in a stable order."""
    if existing is None:
        try:
            existing = json.loads(REGISTRY.read_text(encoding="utf-8"))["trajectories"]
        except Exception:
            existing = []
    known = set(_root_pages()) | {"learn/index.html"}
    rows: list[dict] = []

    # ★A MEASURED ROSTER MUST FREEZE THE MOMENT IT IS SEEDED. The first seed planned 725 rows, wrote
    # them, and the gate then re-ran plan() and derived a DIFFERENT sequence: the per-page deficits had
    # shrunk by exactly the rows just written, the Tagalog roster would shrink the moment a page gained
    # a _t() call, and the destructive roster moves with every control added. A plan that reads mutable
    # state cannot be the gate's source of truth (★×16). So each measured roster is REPLAYED from the
    # EX rows already in the registry when they exist, and measured only on the first seed.
    seeded = [t for t in existing if str(t.get("id", "")).startswith(PREFIX)]
    def _frozen(wave: str) -> list[str] | None:
        pages = []
        for t in seeded:
            if t.get("wave") == wave:
                for p in (t.get("pages") or []):
                    if p not in pages:
                        pages.append(p)
        return pages or None
    frozen_tl = _frozen(WAVES["TL"]["wave"])
    frozen_pf = _frozen(WAVES["PF"]["wave"])
    frozen_rv = [t for t in seeded if t.get("wave") == WAVES["RV"]["wave"]] or None

    def emit(code: str, title: str, pages: list[str], layers: list[str], persona: str, device: str,
             entry: str, story: str) -> None:
        spec = WAVES[code]
        rows.append({"wave": spec["wave"], "title": title, "pages": pages, "layers": layers,
                     "ufai": list(spec["ufai"]), "persona": persona, "device": device, "entry": entry,
                     "framing": spec["framing"], "story": story})

    # PX - the thin cells
    for cell, persona, device, entry, layers, lens, roster in PX_CELLS:
        for page in roster:
            if page in known:
                emit("PX", f"{lens} - {_short(page)}", [page], layers, persona, device, entry,
                     f"cell {cell}: {persona} on {device} arriving by {entry}")
    # TL - Tagalog first, roster measured once and then frozen
    for page in (frozen_tl or _english_only_pages()):
        for lens in TL_LENSES:
            emit("TL", f"{lens} - {_short(page)}", [page], ["F"], "worker", "phone-390", "hub-nav",
                 "a Filipino technician who reads Tagalog first; the page carried no _t() strings when seeded")
    # PF - the floor, measured once (against the registry BEFORE this wave) and then frozen per page:
    # the number of lenses a page received is replayed from its seeded rows, never re-derived
    if frozen_pf:
        _per_page = Counter(p for t in seeded if t.get("wave") == WAVES["PF"]["wave"] for p in (t.get("pages") or []))
        pf_plan = [(p, _per_page[p]) for p in frozen_pf]
    else:
        pf_plan = [(p, min(len(PF_LENSES), d)) for p, d in _thin_pages(existing)]
    for page, n_lenses in pf_plan:
        for lens in PF_LENSES[:max(0, n_lenses)]:
            emit("PF", f"{lens} - {_short(page)}", [page], ["F"], "any", "any", "hub-nav",
                 f"this page sat below the floor of 30 when the wave was seeded")
    # HP - hostile, contract framing, walked AS the persona
    for persona, lens, roster, layers in HP_PERSONAS:
        for page in roster:
            if page in known:
                emit("HP", f"{lens} - {_short(page)}", [page], layers, persona, "desktop-1280", "direct",
                     "walked as the hostile persona through PostgREST, never as the owner connection")
    # AT - AI trust
    for page in AI_SURFACES:
        if page in known:
            for lens in AT_LENSES:
                emit("AT", f"{lens} - {_short(page)}", [page], ["A", "F"], "worker", "phone-390", "hub-nav",
                     "a maintenance engineer about to act on what the AI said")
    # RV - recovery, one row per rostered destructive control, replayed verbatim once seeded
    if frozen_rv:
        for t in frozen_rv:
            emit("RV", t["title"], list(t.get("pages") or []), ["D", "F"], "worker", "phone-390", "hub-nav",
                 "a person who deleted the wrong thing; count(*) is blind to a soft delete, so the walk counts LIVE rows")
    else:
        for c in _destructive_controls():
            if c["page"] in known:
                emit("RV", f"After pressing \"{c['label']}\" by mistake, the platform must offer the way back and put it back - {_short(c['page'])}",
                     [c["page"]], ["D", "F"], "worker", "phone-390", "hub-nav",
                     "a person who deleted the wrong thing; count(*) is blind to a soft delete, so the walk counts LIVE rows")
    # SB - the boundaries of time
    for lens, persona in SB_LENSES:
        for page in SHIFT_PAGES:
            if page in known:
                emit("SB", f"{lens} - {_short(page)}", [page], ["C", "D"], persona, "phone-390", "hub-nav",
                     "the clock pinned to Asia/Manila at the boundary; the schedulers' writes read back")
    # AX - accessibility personas across the core journeys
    for persona, device, lens in AX_PERSONAS:
        for page in CORE_JOURNEYS:
            if page in known:
                emit("AX", f"{lens} - {_short(page)}", [page], ["F"], persona, device, "hub-nav",
                     "walked keyboard-only / forced-colors / 200% zoom with the a11y-path harness")
    for code in WAVES:
        WAVES[code]["_planned"] = sum(1 for r in rows if r["wave"] == WAVES[code]["wave"])
    return rows


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    existing = doc["trajectories"]
    have = {t["id"] for t in existing}
    rows = plan(existing)

    ufai_mix: Counter = Counter()
    for r in rows:
        for x in r["ufai"]:
            ufai_mix[x] += 1
    print("  %-6s %-42s %-8s %7s" % ("wave", "direction", "framing", "rows"))
    for code, spec in WAVES.items():
        print("  %-6s %-42s %-8s %7d" % (spec["wave"], spec["name"], spec["framing"], spec["_planned"]))
    print("  %-6s %-42s %-8s %7d" % ("", "TOTAL new trajectories", "", len(rows)))
    print("  UFAI mix of the new rows: " + " · ".join(f"{k} {ufai_mix.get(k, 0)}" for k in "UFAI"))
    scoped = [t for t in existing if t.get("status") != "descoped"]
    print(f"  program: {len(scoped)} in scope today -> {len(scoped) + len(rows)} after seeding")

    nxt = 1
    created = []
    for r in rows:
        while f"{PREFIX}{nxt}" in have:
            nxt += 1
        rid = f"{PREFIX}{nxt}"
        have.add(rid)
        created.append({"id": rid, "wave": r["wave"], "title": r["title"], "status": "specced", "pct": 5,
                        "pages": r["pages"], "layers": r["layers"], "ufai": r["ufai"], "persona": r["persona"],
                        "device": r["device"], "entry": r["entry"], "framing": r["framing"], "story": r["story"]})

    if args.dry_run:
        for code, spec in WAVES.items():
            first = next((c for c in created if c["wave"] == spec["wave"]), None)
            if first:
                print(f"  {first['id']:<7} {first['title'][:96]}")
        print("  (nothing written)")
        return 0

    seen = {(t.get("title"), tuple(t.get("pages") or [])) for t in existing}
    fresh = [c for c in created if (c["title"], tuple(c["pages"])) not in seen]
    doc["trajectories"] = existing + fresh
    doc["count"] = len(doc["trajectories"])
    _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    # the critic bank grows with the registry, from ONE place (validate_critic_registry R3 - 2026-09-07):
    # every new in-scope id gets its pending critic row here, never in a second script nobody runs.
    from critic_seed_missing import seed_missing  # noqa: E402  (tools/ is this file's directory)
    seed_missing()
    print(f"\n  wrote {len(fresh)} new row(s) into {REGISTRY.name} (registry now {doc['count']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
