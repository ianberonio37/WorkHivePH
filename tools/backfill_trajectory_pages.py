#!/usr/bin/env python3
"""backfill_trajectory_pages.py — Phase 0.1 of the UFAI Critic Deepwalk extension (2026-09-01).

T1-T200 carry NO machine-readable pages/cells (their routes live in `basis` free-text + the Story
grammar in UFAI_TRAJECTORY_ROADMAP.md); 140 of T201-T500 have pages:[] (machine channels) whose
HUMAN-FACING ECHO surface must be resolved so every in-scope trajectory is walkable or carries an
explicit no_ui_basis. This tool PROPOSES pages[] + cells[] + walk parameters per trajectory:

  sources, in descending trust:
    basis   — *.html / learn/... path mentions accumulated by past walk receipts
    story   — the 199/199-consistent Story grammar (persona, device, entry, intent)
    echo    — for machine arcs: keyword -> the surface where a human SEES the machine's effect

Dry-run by default: writes .tmp/trajectory_pages_backfill_proposal.json and touches NOTHING.
--apply merges pages/cells into trajectory_registry.json (append-only basis note per row).
Runs from .tmp/ during the board; lands in tools/ + applies only after the board completes.
Self-test: --self-test (a basis naming pages must resolve; a machine arc must get an echo or
needs_review; a resolved row must carry a cell)."""
from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
ROADMAP = ROOT / "UFAI_TRAJECTORY_ROADMAP.md"
PROPOSAL = ROOT / ".tmp" / "trajectory_pages_backfill_proposal.json"

PAGE_RE = re.compile(r"\b((?:learn|tools)/[a-z0-9-]+/index\.html|[a-z0-9][a-z0-9-]*\.html)\b")
# files named in basis text that are FIXTURES/REPORTS, not walkable surfaces
NOT_A_SURFACE = re.compile(r"(?:^|/)(?:_fixtures|node_modules)|-test\.html$|\.html\.md$")

# Story grammar: device + persona (v1 prose) -> v2 cell vocabulary + precise walk params
VIEWPORTS = [
    (re.compile(r"\b320\b|budget.?android|small.?phone", re.I), "narrow-320", 320),
    (re.compile(r"\bphone\b|\b390\b|mobile", re.I), "narrow-320", 390),
    (re.compile(r"\b1920\b|wide.?screen|desktop", re.I), "wide-1920", 1920),
    (re.compile(r"\bPC\b|\b1280\b|desk", re.I), "wide-1920", 1280),
    (re.compile(r"\b768\b|tablet", re.I), "wide-1920", 768),
    (re.compile(r"kiosk|print", re.I), "fixed-kiosk-print", 1280),
]
ACTORS = [
    (re.compile(r"screen.?reader|assistive|a11y|switch.?access|voice.?control|low.?vision|one.?hand|motor|dyslex", re.I), "assistive-tech"),
    (re.compile(r"attacker|adversar|hostile|malicious|tamper", re.I), "adversary"),
    (re.compile(r"auditor|inspector|regulator|compliance|HR|investor|owner|founder|manager|oversight", re.I), "oversight"),
    (re.compile(r"webhook|API|machine|cron|integration bot", re.I), "machine-client"),
]
INTENTS = [
    (re.compile(r"attack|exfiltrat|escalat|inject|bypass", re.I), "attack"),
    (re.compile(r"audit|verif|inspect|investigat|review", re.I), "audit"),
    (re.compile(r"comply|compliance|regulat|retention|legal|OSHS|ISO", re.I), "comply"),
]

# SURFACE map for UI arcs whose basis names no .html but whose title/story plainly names the
# surface (the T2/T12/T66 class). Checked BEFORE echo - product keywords beat echo keywords.
SURFACE_MAP = [
    (re.compile(r"voice.?journal|mic\b", re.I), ["voice-journal.html"]),
    (re.compile(r"shift.?(handover|brain|plan)", re.I), ["shift-brain.html"]),
    (re.compile(r"learn article|learn/|SEO|search arrival", re.I), ["learn/ai-work-assistant-maintenance-technicians/index.html", "index.html"]),
    (re.compile(r"engineering calc|BOM/SOW|calc agent", re.I), ["engineering-design.html"]),
    (re.compile(r"analytics.?report", re.I), ["analytics-report.html"]),
    (re.compile(r"project.?report", re.I), ["project-report.html"]),
    (re.compile(r"project (import|manager)|change order", re.I), ["project-manager.html"]),
    (re.compile(r"PH.?Intelligence|market.?intel", re.I), ["ph-intelligence.html"]),
    (re.compile(r"resume", re.I), ["resume.html"]),
    (re.compile(r"companion|persona switch|Zaniah|Hezekiah", re.I), ["assistant.html"]),
    (re.compile(r"asset (brain|hub)|ask one asset", re.I), ["asset-hub.html"]),
    (re.compile(r"temporal RAG|ask.*assistant|assistant", re.I), ["assistant.html"]),
    (re.compile(r"availability|provider", re.I), ["marketplace-seller.html"]),
    (re.compile(r"nav.?hub|global search|FAB", re.I), ["hive.html", "logbook.html"]),
    (re.compile(r"joins? via code|invited|onboard", re.I), ["index.html", "hive.html"]),
    (re.compile(r"day.?2|re.?engag|first.?week|return", re.I), ["index.html", "hive.html"]),
    (re.compile(r"pm.?(scheduler|task|compliance)|preventive", re.I), ["pm-scheduler.html"]),
    (re.compile(r"dayplanner|plan.*week", re.I), ["dayplanner.html"]),
    (re.compile(r"skill", re.I), ["skillmatrix.html"]),
    (re.compile(r"achievement|XP|badge", re.I), ["achievements.html"]),
    (re.compile(r"alert", re.I), ["alert-hub.html"]),
    (re.compile(r"analytics", re.I), ["analytics.html"]),
    (re.compile(r"display.?name|identity edge", re.I), ["hive.html", "community.html"]),
    (re.compile(r"role.?s day|persona\)|plant manager|executive|engineer role", re.I), ["hive.html", "analytics.html", "logbook.html"]),
    (re.compile(r"cross.?device|continuity", re.I), ["hive.html", "logbook.html"]),
    (re.compile(r"sunlight|contrast|glance", re.I), ["logbook.html", "hive.html", "pm-scheduler.html"]),
    (re.compile(r"rage.?tap|double.?submit|every committing", re.I), ["logbook.html", "inventory.html", "pm-scheduler.html"]),
    # W-wave adversary-in-browser arcs: the attacked surface + where the attempt echoes
    (re.compile(r"mass assignment|profile update", re.I), ["hive.html", "resume.html"]),
    (re.compile(r"enumerate users|signup error", re.I), ["index.html"]),
    (re.compile(r"invite.?code", re.I), ["hive.html", "index.html"]),
    (re.compile(r"file.?upload|smuggl", re.I), ["logbook.html", "community.html"]),
    (re.compile(r"signed.?url", re.I), ["voice-journal.html", "asset-hub.html"]),
    (re.compile(r"prompt injection", re.I), ["assistant.html"]),
    # Y-wave human personas: the surface their day actually lives on
    (re.compile(r"assessor|maintenance history", re.I), ["logbook.html", "audit-log.html", "analytics-report.html"]),
    (re.compile(r"contractor|multiple hives", re.I), ["hive.html", "logbook.html"]),
    (re.compile(r"vendor|OEM|support engineer", re.I), ["asset-hub.html", "logbook.html"]),
    (re.compile(r"retiring|hands over", re.I), ["hive.html", "audit-log.html"]),
    (re.compile(r"temp worker|seasonal", re.I), ["index.html", "hive.html", "logbook.html"]),
    (re.compile(r"regulator|public tools claim", re.I), ["tools/mtbf-calculator/index.html"]),
    (re.compile(r"cross.?region sale|tax", re.I), ["marketplace.html"]),
    (re.compile(r"proration|plan change|payout|overdraw|negative.?balance", re.I), ["marketplace-seller.html", "founder-console.html"]),
]

# Condition/journey arcs (the platform under a CONDITION, not one surface): walk the core set
# with the condition applied. Requires a real condition keyword - zero-signal stays unresolved.
CONDITION_RE = re.compile(
    r"interrupt|shared device|clock|skew|storm|max.*length|race|repaint|focus|stream|month|year"
    r"|escalation|power user|retention|archive|seed|demo|share card|OG\b|arrival|AEO|meta.?journey"
    r"|game.?day|release|migration|upgrade|longitudinal|lifecycle|honesty|truth|latency|degrad"
    r"|color.?blind|switch.?access|voice.?control|reflow|announce|live.?region|touch target"
    r"|skip.?link|landmark|timezone|midnight|cache|unicode|emoji|pagination|precision|centavo"
    r"|enum|collision|aggregate|half.?state|referential|deprecat|retired|renamed|reproducib"
    r"|sunset|consent|config|failover|cold.?start|storage unavailable|region.?wide", re.I)

# ECHO map for machine-channel arcs: where a human SEES the machine's effect.
# Keyed by story/title keywords; value = (echo pages, why).
ECHO_MAP = [
    (re.compile(r"webhook|bounce|resend|delivery", re.I), ["audit-log.html", "report-sender.html"],
     "webhook writes surface in the audit trail + the sender's delivery status"),
    (re.compile(r"BOLA|BFLA|IDOR|object.level|function.level", re.I), ["alert-hub.html", "audit-log.html"],
     "an authz probe's refusal/attempt surfaces to supervisors via alerts + audit"),
    (re.compile(r"listing|marketplace|seller|buyer|order|RFQ", re.I), ["marketplace.html"],
     "the marketplace surface renders what the API wrote"),
    (re.compile(r"logbook|work.?order|job", re.I), ["logbook.html"],
     "the logbook renders what the API wrote"),
    (re.compile(r"inventory|stock|part", re.I), ["inventory.html"],
     "the inventory surface renders what the API wrote"),
    (re.compile(r"notification|push|digest", re.I), ["alert-hub.html"],
     "notifications surface in the alert hub"),
    (re.compile(r"rate.?limit|quota|budget|cost", re.I), ["llm-observability.html", "founder-console.html"],
     "quota/cost effects surface on the observability consoles"),
    (re.compile(r"jwt|token|session|auth", re.I), ["index.html", "hive.html"],
     "auth outcomes surface at sign-in and the hive shell"),
    (re.compile(r"community|post|reply|moderat", re.I), ["community.html"],
     "community surfaces render what the API wrote/moderated"),
    (re.compile(r"audit|trace|log", re.I), ["audit-log.html"], "the audit trail is the echo"),
    # Z/AE data-pathology + infra arcs: induced via machine channels, FELT on these surfaces
    (re.compile(r"timezone|midnight", re.I), ["shift-brain.html", "dayplanner.html"],
     "a timezone-crossing shift renders in the shift plan + day view"),
    (re.compile(r"migration half.?state", re.I), ["hive.html"], "the shell is where a half-state is felt"),
    (re.compile(r"stale cache", re.I), ["hive.html", "logbook.html"], "a stale read is felt on the read surfaces"),
    (re.compile(r"unicode|emoji", re.I), ["community.html", "hive.html"], "names render on rosters + posts"),
    (re.compile(r"soft.?delete|aggregate", re.I), ["analytics.html"], "an aggregate leak is read on analytics"),
    (re.compile(r"enum drift|status value", re.I), ["logbook.html", "pm-scheduler.html"], "statuses render on work surfaces"),
    (re.compile(r"id collision|shared table", re.I), ["marketplace.html"], "the shared-table surface"),
    (re.compile(r"pagination", re.I), ["logbook.html", "inventory.html"], "long lists live here"),
    (re.compile(r"precision|centavo|currency", re.I), ["marketplace.html", "founder-console.html"], "money renders here"),
    (re.compile(r"referential repair|tenant boundary", re.I), ["inventory.html", "audit-log.html"], "repair effects surface here"),
    (re.compile(r"failover|write storm", re.I), ["logbook.html", "alert-hub.html"], "a failed write is felt at the write surface + alerts"),
    (re.compile(r"cold.?start", re.I), ["assistant.html"], "edge-fn latency is felt on the AI surface"),
    (re.compile(r"storage unavailable|upload wave", re.I), ["voice-journal.html", "logbook.html"], "uploads live here"),
    (re.compile(r"region.?wide|graceful", re.I), ["hive.html", "logbook.html"], "global degradation is felt on the core shell"),
]


def _load():
    return json.loads(io.open(REGISTRY, encoding="utf-8").read())


def _story_blocks() -> dict:
    """T<n> -> the Story line from the roadmap spec (T1-T200)."""
    try:
        text = io.open(ROADMAP, encoding="utf-8", errors="replace").read()
    except Exception:
        return {}
    out = {}
    for m in re.finditer(r"^### (T\d+) ", text, re.M):
        tid = m.group(1)
        block = text[m.end():m.end() + 3000]
        sm = re.search(r"\*\*Story\*\*:?\s*(.+?)(?:\n- \*\*|\n###)", block, re.S)
        if sm and tid not in out:
            out[tid] = re.sub(r"\s+", " ", sm.group(1)).strip()[:400]
    return out


def _pages_from_text(text: str) -> list[str]:
    hits = [p for p in PAGE_RE.findall(text or "") if not NOT_A_SURFACE.search(p)]
    ranked = [p for p, _ in Counter(hits).most_common()]
    return [p for p in ranked if (ROOT / p).exists()][:6]


def _cell_from_story(story: str, title: str) -> tuple[str, int]:
    s = (story or "") + " " + (title or "")
    viewport, px = "wide-1920", 1280
    for rx, v, p in VIEWPORTS:
        if rx.search(s):
            viewport, px = v, p
            break
    actor = next((a for rx, a in ACTORS if rx.search(s)), "operate-user")
    if actor == "operate-user":
        actor = "oversight" if re.search(r"supervisor|admin", s, re.I) else "assistive-tech" if "reader" in s else "oversight" if "audit" in s.lower() else "worker"
    # v2 vocabulary has no plain worker actor; the walk params carry the persona - the cell uses the
    # nearest matrix actor (oversight for supervisor-role stories, assistive-tech only when assistive).
    if actor == "worker":
        actor = "oversight" if re.search(r"supervisor", s, re.I) else "assistive-tech" if re.search(r"assistive", s, re.I) else "oversight"
    intent = next((i for rx, i in INTENTS if rx.search(s)), "operate")
    return f"{viewport}|{actor}|browser-ui|{intent}", px


def _echo_for(story: str, title: str) -> tuple[list[str], str] | None:
    s = (story or "") + " " + (title or "")
    for rx, pages, why in ECHO_MAP:
        if rx.search(s):
            existing = [p for p in pages if (ROOT / p).exists()]
            if existing:
                return existing, why
    return None


def build_proposal(reg: dict, stories: dict) -> dict:
    rows, stats = [], Counter()
    for t in reg["trajectories"]:
        tid, status = t["id"], t["status"]
        if status == "descoped":
            stats["descoped"] += 1
            continue
        pages = list(t.get("pages") or [])
        story = t.get("story") or stories.get(tid) or ""
        row = {"id": tid, "title": t.get("title", ""), "wave": t.get("wave"), "source": None,
               "pages_proposed": [], "cell_proposed": None, "walk_viewport_px": None,
               "confidence": None, "needs_review": False, "evidence": ""}
        if pages:
            row.update(source="registry", pages_proposed=pages,
                       cell_proposed=(t.get("cells") or [None])[0], confidence="high")
            stats["already-paged"] += 1
        else:
            basis_pages = _pages_from_text(t.get("basis") or "")
            cell, px = _cell_from_story(story, t.get("title", ""))
            row["cell_proposed"], row["walk_viewport_px"] = cell, px
            if basis_pages:
                row.update(source="basis", pages_proposed=basis_pages, confidence="high",
                           evidence=f"basis names {len(basis_pages)} surface(s)")
                stats["basis-resolved"] += 1
            elif (surf := next((pg for rx, pg in SURFACE_MAP
                                if rx.search(story + " " + t.get("title", ""))), None)):
                existing = [p for p in surf if (ROOT / p).exists()]
                row.update(source="surface-map", pages_proposed=existing, confidence="medium",
                           evidence="title/story names the surface")
                stats["surface-resolved"] += 1
            else:
                echo = _echo_for(story, t.get("title", ""))
                if echo:
                    row.update(source="echo", pages_proposed=echo[0], confidence="medium",
                               needs_review=True, evidence=echo[1])
                    stats["echo-resolved"] += 1
                elif CONDITION_RE.search(story + " " + t.get("title", "")) and not (
                        t.get("cells") and all(("api-direct" in c or "webhook-inbound" in c) for c in t["cells"])):
                    # condition/journey arc over UI (shared device, clock skew, interruption storm,
                    # meta-journeys): the surface is the PLATFORM under a condition - walk the core
                    # set with the condition applied; the walk session confirms/adjusts per arc.
                    row.update(source="condition-core", needs_review=True, confidence="low",
                               pages_proposed=["hive.html", "logbook.html", "pm-scheduler.html", "inventory.html"],
                               evidence="condition/journey arc - representative core set under the arc's condition")
                    stats["condition-core"] += 1
                else:
                    row.update(source="unresolved", needs_review=True, confidence="none",
                               evidence="no basis pages, no echo keyword hit - candidate no_ui_basis, claim only after a manual echo hunt")
                    stats["unresolved"] += 1
        rows.append(row)
    return {"_doc": "Phase 0.1 backfill proposal - PROPOSED walk targets per in-scope trajectory; "
                    "apply merges into trajectory_registry.json AFTER the board completes.",
            "stats": dict(stats), "rows": rows}


def main() -> int:
    reg = _load()
    proposal = build_proposal(reg, _story_blocks())
    PROPOSAL.parent.mkdir(exist_ok=True)
    tmp = PROPOSAL.with_suffix(".tmp")
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(proposal, indent=1))
    tmp.replace(PROPOSAL)
    s = proposal["stats"]
    print(f"proposal written: {PROPOSAL.name}")
    for k in sorted(s):
        print(f"  {k:16} {s[k]}")
    if "--apply" in sys.argv:
        print("APPLY refused from .tmp/ staging - land this tool in tools/ post-board first.")
        return 1
    return 0


def self_test() -> int:
    fails = []
    reg = {"trajectories": [
        {"id": "T900", "status": "locking", "title": "worker logs a job",
         "basis": "walked logbook.html:210 and hive.html banner", "pages": [], "cells": []},
        {"id": "T901", "status": "locking", "title": "webhook bounce dedupe",
         "story": "a webhook retries a bounce delivery", "basis": "", "pages": [], "cells": []},
        {"id": "T902", "status": "locking", "title": "quantum flux modulation",
         "story": "nothing matches this", "basis": "", "pages": [], "cells": []},
    ]}
    p = build_proposal(reg, {"T900": "worker, phone 390, entry = nav, intent = log the job"})
    rows = {r["id"]: r for r in p["rows"]}
    if rows["T900"]["source"] != "basis" or "logbook.html" not in rows["T900"]["pages_proposed"]:
        fails.append("basis naming pages must resolve from basis")
    if rows["T900"]["cell_proposed"] is None or "narrow-320" not in rows["T900"]["cell_proposed"]:
        fails.append("a phone-390 story must yield a narrow cell")
    if rows["T901"]["source"] != "echo" or not rows["T901"]["pages_proposed"]:
        fails.append("a webhook machine arc must resolve an ECHO surface")
    if rows["T902"]["source"] != "unresolved" or not rows["T902"]["needs_review"]:
        fails.append("a no-hit arc must land unresolved + needs_review, never silently paged")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS backfill_trajectory_pages self-test (basis-resolve / story-cell / echo / unresolved-honesty)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
