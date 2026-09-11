#!/usr/bin/env python3
"""backfill_trajectory_layers.py — give every trajectory a full-stack LAYER, so the program can be
counted per layer (Ian, 2026-09-06: "improve the UFAI UI UX for every Full Stack SaaS Layer I have").

WHY THIS EXISTS. `trajectory_registry.json` rows already carry a `layers` list, and the P-program
seeder fills it from LENS_LAYERS / LAYERS in tools/seed_p_program_catalog.py. But it was only ever
written by that seeder, so on 2026-09-06 it was populated on 704 rows and EMPTY on 725 - every T
(500), VP (200), VD (15) and VM (10) row. Those are the persona journeys, which is to say the half
of the program that is most about what a person experiences. A per-layer number over half the rows
is not a number, so nothing could be said about which layer is thin until this ran.

HOW IT DECIDES. The same principle the seeder settled on: **layers belong to the LENS, not the
wave.** A journey's title is its lens ("Worker logs a repair one-handed on phone, with photo"), so
the mapping reads the title and assigns every layer the journey actually crosses - that one touches
Frontend (the phone), APIs (the write), Database (the row) and Storage (the photo). Multi-tagging is
the established shape here, not a hedge: 597 of the already-tagged rows carry more than one layer.

A row that matches nothing gets ["F"], because a UFAI trajectory is a USER-journey arc by
definition and the surface a person meets it on is the frontend. That default is stated rather than
silent, and `--report` prints how many rows leaned on it so it can never quietly become the answer.

  python tools/backfill_trajectory_layers.py            # write (idempotent)
  python tools/backfill_trajectory_layers.py --dry-run  # show the before/after table only
  python tools/backfill_trajectory_layers.py --report   # per-layer totals over the WHOLE registry
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

NAMES = {
    "A": "APIs & Backend Logic", "AU": "Auth & Permissions", "S": "Security & RLS",
    "RL": "Rate Limiting", "CI": "CI/CD & Version Control", "D": "Database & Storage",
    "F": "Frontend", "L": "Error Tracking & Logs", "AV": "Availability & Recovery",
    "CA": "Caching & CDN", "H": "Hosting & Deployment", "C": "Cloud & Compute",
    "LB": "Load Balancing & Scaling",
}

# Each rule adds its layers when the pattern matches the row's TITLE. Rules are additive - a journey
# crosses everything it touches - and ordered only for readability.
RULES: list[tuple[str, list[str]]] = [
    # ── Frontend: anything a person looks at, types into, or navigates
    (r"render|CSS|contrast|escHtml|layout|copy|empty state|tap target|safe area|landscape|reflow|"
     r"keyboard|semantics|announcement|screen reader|phone|mobile|one-handed|glass|on screen|"
     r"modal|form|wizard|nav|arrival|reads|browses|sees|understands|legible", ["F"]),
    # ── Auth & Permissions
    (r"sign[- ]?in|sign[- ]?up|signed[- ]?out|session|login|log in|auth|password|invite|join|"
     r"member|role|supervisor|permission|onboard|account|identity|expiry|returns after", ["AU"]),
    # ── Security & RLS
    (r"tenant|RLS|BOLA|BFLA|cross-hive|foreign hive|refusal|authz|forged|escalat|inject|XSS|"
     r"secret|leak|another hive|not allowed|gated action", ["S"]),
    # ── Database & Storage
    (r"canonical|tile ==|ledger|truth|cap is not|reconcile|row|record|entry|logbook|inventory|"
     r"photo|upload|file|attach|export|import|history|lineage|audit", ["D"]),
    # ── APIs & Backend Logic
    (r"edge function|contract & failure|provider fallback|orchestrat|webhook|API|invoke|"
     r"AI |assistant|companion|RAG|agent|semantic|voice|brief|generat", ["A"]),
    # ── Availability & Recovery
    (r"degrad|offline|outage|retry|reconnect|backfill|storm|500|recovery|health|incident|"
     r"partition|expiry mid|unavailable|fails|failure|down", ["AV"]),
    # ── Caching & CDN
    (r"cache|CDN|stale|service worker|shell|_headers|precache|revalidat", ["CA"]),
    # ── Error Tracking & Logs
    (r"\blog\b|logs|trace|error tracking|crash|observab|correlat|greppable|diagnos", ["L"]),
    # ── Rate Limiting
    (r"rate.?limit|quota|throttl|abuse|burst|too many|cooldown", ["RL"]),
    # ── Cloud & Compute
    (r"cold start|compute|cron|scheduled|background job|worker process|queue|batch", ["C"]),
    # ── Load Balancing & Scaling
    (r"scal|concurren|throughput|N\+1|at 20 members|at scale|volume|pagination|load more|"
     r"many rows|large hive|grows", ["LB"]),
    # ── CI/CD & Version Control
    (r"the gate actually runs|deploy|release|version|rollout|flag|migration ship", ["CI"]),
    # ── Hosting & Deployment
    (r"prod-only|deployed origin|hosting|redirect|robots|sitemap|canonical URL|domain|DNS|"
     r"public arrival|crawler|SEO|AEO", ["H"]),
    # ── The persona-journey vocabulary. The first pass left 258 rows on the default, and reading them
    # showed the gap was in the RULES, not in the rows: "Worker completes an assigned PM task",
    # "Seller lists a part with credit reservation", "GCash top-up: the money-in loop" all cross real
    # layers that the lens-shaped patterns above never name. These rules speak the way a journey title
    # speaks - in verbs a person performs and nouns a product has.
    (r"\bconvert|conversion|funnel|from search|lands on|arrives", ["H", "F"]),
    (r"\blists?\b|creates?|issues?|submits?|posts?|saves?|writes?|approves?|assigns?|schedules?|"
     r"completes?|logs\b|records?|updates?|edits?|deletes?", ["D", "A"]),
    (r"PM task|spare part|\bpart\b|\bjob\b|listing|order|inquiry|dispute|credit|top-?up|price|"
     r"pricing|payment|money|invoice|escrow|reservation|stock|asset|equipment", ["D"]),
    (r"multi-?hive|switches hives|another hive|hives\b|tenant", ["AU", "S"]),
    (r"notification|digest|alert|e-?mail|reaches the user|inbox|push\b|announce", ["A", "AV"]),
    (r"search|discovery|browse|filter|sort|find\b|query", ["F", "D"]),
    (r"KPI|analytics|report|metric|dashboard|console|chart|score|leaderboard|reputation", ["D", "F"]),
    (r"persona|manager|executive|contractor|supplier|guest|preview|buyer|seller|stakeholder|"
     r"engineer|technician|planner|visitor|new user|returning", ["F"]),
    (r"promise|page:|deep walk|lane\b|surface\b|comprehension|coherence|quality|transparency|"
     r"honesty|trust|safety|verifies|walks the", ["F"]),
    (r"lifecycle|longitudinal|over N|end-to-end|ripple|chain|hand-?off|the return path", ["A", "D"]),
    (r"language|Filipino|Tagalog|translation|i18n|locale", ["F"]),
    # ── The cross-cutting UX sweeps. Reading the second pass's 130 leftovers showed most are
    # frontend-first by nature ("Iconography & affordance recognition", "Print reality") and a
    # handful quietly cross a second layer nobody would guess from the noun alone: a retention
    # policy is Database, a renamed page is Hosting, a consent moment is Security.
    (r"sweep|census|benchmark|reality|hygiene|literacy|recognition|vocabulary|help system|"
     r"findability|iconograph|affordance|print|kiosk|wall-display|screenshot|share culture|"
     r"tremor|gloved|motor|jargon|pull-help|big screen", ["F"]),
    (r"duplicate|cardinality|zero, one|maximum-length|max-length|dates|times|PHT|clock|skew|"
     r"archive|retention|deletion|forget me|compliance|evidence|freshness|normalizer|race\b|"
     r"where old data goes", ["D"]),
    (r"404|renamed|security-header|headers|Turnstile|bot-defense|privacy|consent|sensitive|"
     r"hardening|first-run", ["S", "H"]),
    (r"presence|multi-?tab|who.s really here|real-?time", ["A"]),
]
COMPILED = [(re.compile(p, re.I), ls) for p, ls in RULES]
DEFAULT = ["F"]


def layers_for(title: str) -> tuple[list[str], bool]:
    """Every layer this journey crosses, and whether the default had to carry it."""
    out: list[str] = []
    for rx, ls in COMPILED:
        if rx.search(title or ""):
            for x in ls:
                if x not in out:
                    out.append(x)
    if not out:
        return list(DEFAULT), True
    return out, False


def _atomic_write(path: Path, text: str) -> None:
    """Never open(w) the registry directly: a crash mid-write would truncate the SSOT."""
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
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    ap.add_argument("--report", action="store_true", help="per-layer totals over the whole registry")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = doc["trajectories"]

    before_tagged = sum(1 for r in rows if r.get("layers"))
    filled, defaulted = 0, []
    for r in rows:
        if r.get("layers"):
            continue
        ls, used_default = layers_for(r.get("title", ""))
        if used_default:
            defaulted.append(r["id"])
        r["layers"] = ls
        filled += 1

    after_tagged = sum(1 for r in rows if r.get("layers"))
    counts: collections.Counter = collections.Counter()
    for r in rows:
        for x in (r["layers"] if isinstance(r.get("layers"), list) else [r.get("layers")]):
            if x:
                counts[x] += 1

    print(f"  tagged before {before_tagged} -> after {after_tagged}  (of {len(rows)} rows; {filled} filled)")
    if defaulted:
        print(f"  {len(defaulted)} row(s) matched no rule and took the stated default {DEFAULT}: "
              f"{', '.join(defaulted[:8])}{' ...' if len(defaulted) > 8 else ''}")
    print()
    print("  %-4s %-28s %6s" % ("code", "layer", "rows"))
    for code in sorted(NAMES, key=lambda k: -counts.get(k, 0)):
        print("  %-4s %-28s %6d" % (code, NAMES[code], counts.get(code, 0)))

    if args.dry_run or args.report:
        print("\n  (nothing written)")
        return 0

    doc["trajectories"] = rows
    _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"\n  wrote {REGISTRY.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
