#!/usr/bin/env python3
"""seed_layer_ux_wave.py — the LAYER-UX WAVE: bring every full-stack layer to the program's target
density, asking what a PERSON FEELS when that layer misbehaves (Ian, 2026-09-06: "improve the UFAI
UI UX for every Full Stack SaaS Layer I have" + "those layers that have less trajectories, we have
to make more for those").

WHAT MAKES THESE ROWS DIFFERENT. The existing program asks whether a surface is correct. These ask
what the person on the other side experiences when the layer beneath it fails - the distinction Ian
chose explicitly. "Cache-Control matches the declared policy" is an assertion about a header;
"after a deploy you are shown yesterday's page and nothing tells you" is a trajectory. Only the
second one has a person in it, and only the second one can be walked as a journey.

WHY THESE SIX LAYERS. After tools/backfill_trajectory_layers.py gave all 1,429 rows a layer, the
generated header could finally state the deficit against the 90-row target:
    CI 15 (+75) · L 31 (+59) · LB 33 (+57) · H 38 (+52) · RL 45 (+45) · S 66 (+24)  =  312 rows
The other seven layers are already at or past target and get nothing here - the point is the thin
ones, not a uniform sprinkle.

THE HOSTING LAYER IS WHY THIS WAVE EXISTS AT ALL. On 2026-09-06 a walk found the repo shipping
Cloudflare `_headers` and a `netlify.toml` to a VERCEL host, so no security header had ever been
served in production and `/_fixtures/` answered 200. 1,429 trajectories, and not one of them asked
what the deployed origin actually hands a person.

Rows are emitted at `status: specced` with no basis. tools/advance_trajectory.py remains the only
writer of status and basis; this file only creates.

  python tools/seed_layer_ux_wave.py --dry-run   # the plan and the arithmetic
  python tools/seed_layer_ux_wave.py             # write (idempotent - existing LX ids are left alone)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/ importable for critic_seed_missing

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
ROSTER = ROOT / "substrate" / "reference" / "page_roster.json"

TARGET = 90

# ── The surfaces each layer's lenses are asked on ────────────────────────────────────────────────
# Not every layer belongs on every page. A rate-limit refusal is felt where a person SPENDS one (the
# AI and write surfaces); a deploy-staleness is felt where they return daily. Rosters are named per
# layer so a row can never be about a page the question does not apply to.
DAILY = ["hive.html", "logbook.html", "inventory.html", "dayplanner.html", "alert-hub.html",
         "asset-hub.html", "community.html", "analytics.html", "marketplace.html", "shift-brain.html",
         "pm-scheduler.html", "skillmatrix.html", "achievements.html", "project-manager.html",
         "index.html"]
SPENDERS = ["assistant.html", "voice-journal.html", "shift-brain.html", "logbook.html",
            "resume.html", "engineering-design.html", "analytics.html", "asset-hub.html",
            "community.html", "marketplace.html", "ai-quality.html", "agentic-rag-observability.html",
            "hive.html", "alert-hub.html", "dayplanner.html"]
PUBLIC = ["index.html", "learn/index.html", "marketplace.html", "public-feed.html", "status.html",
          "marketplace-seller-profile.html", "architecture.html", "design-system.html",
          "symbol-gallery.html", "validator-catalog.html", "offline-fallback.html",
          "ph-intelligence.html", "project-report.html"]
BOUNDARY = ["hive.html", "logbook.html", "inventory.html", "asset-hub.html", "community.html",
            "marketplace.html", "marketplace-admin.html", "founder-console.html",
            "platform-actions.html", "audit-log.html", "integrations.html", "plant-connections.html"]
GROWING = ["logbook.html", "inventory.html", "community.html", "marketplace.html", "hive.html",
           "audit-log.html", "analytics.html", "asset-hub.html", "dayplanner.html",
           "pm-scheduler.html", "project-manager.html", "public-feed.html", "skillmatrix.html",
           "alert-hub.html",
           # marketplace-seller: a seller's own listing set is the surface that grows fastest per person,
           # and it was the one page short of the 90-row target on the first seeding.
           "marketplace-seller.html"]

# ── The lenses. Each is a sentence about a person, and each row is that sentence on one surface ──
WAVES: dict[str, dict] = {
    "CI": {
        "wave": "LX-CI",
        "roster": DAILY,
        "lenses": [
            "A release lands mid-session and the page you are using changes under you, unannounced",
            "A feature arrives half-on: the button is there, the thing behind it is not",
            "A migration ships ahead of the screen that needs it, so your data looks wrong for a day",
            "You cannot tell which version you are on when you report that something broke",
            "A rollback takes back the change and your unsaved work with it",
        ],
    },
    "L": {
        "wave": "LX-L",
        "roster": DAILY,
        "lenses": [
            "The error you hit leaves no trace anyone can find afterwards",
            "You are told 'something went wrong' on a page whose log knew exactly what",
            "You have nothing to quote to support: no id, no time, no name for what failed",
            "Your failure reached nobody - no alert, no counter, no one looking",
        ],
    },
    "LB": {
        "wave": "LX-LB",
        "roster": GROWING,
        "lenses": [
            "As the hive grows past twenty people, this page gets slower and never says so",
            "The list stops paginating and you cannot reach what you know is there",
            "The export quietly carries less than the screen showed you",
            "Two of you act at the same moment and one of you loses without being told",
        ],
    },
    "H": {
        "wave": "LX-H",
        "roster": PUBLIC,
        "lenses": [
            "A feature that works locally is dead in production because the origin sends no header for it",
            "The link you were given 404s in production and opens fine for the person who wrote it",
            "A redirect loses what you arrived with: the query, the anchor, the invite",
            "An asset is re-downloaded every visit because the deployed origin never told the browser to keep it",
        ],
    },
    "RL": {
        "wave": "LX-RL",
        "roster": SPENDERS,
        "lenses": [
            "You are refused and not told when you may come back",
            "Someone else in your hive spent the limit and you are the one who is stopped",
            "Your retry makes it worse, and nothing warns you that it will",
        ],
    },
    "S": {
        "wave": "LX-S",
        "roster": BOUNDARY,
        "lenses": [
            "You are refused in a way that tells you nothing you can act on, or more than you should know",
            "You can see the thing but must not act on it, and the page does not say which",
        ],
    },
}


def _atomic_write(path: Path, text: str) -> None:
    """Never open(w) the SSOT: a crash mid-write would truncate the registry."""
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


def _known_pages() -> set:
    return {p["path"] for p in json.loads(ROSTER.read_text(encoding="utf-8"))["pages"]}


def plan() -> list[dict]:
    """Every row this wave would create, in a stable order (lens-major, then surface)."""
    known = _known_pages()
    rows: list[dict] = []
    for code, spec in WAVES.items():
        n = 0
        for lens in spec["lenses"]:
            for page in spec["roster"]:
                if page not in known:                    # a roster entry must name a page that exists
                    continue
                n += 1
                rows.append({
                    "layer": code,
                    "wave": spec["wave"],
                    "title": f"{lens} - {page[:-5].replace('-', ' ')}",
                    "pages": [page],
                    "layers": [code],
                })
        spec["_planned"] = n
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    existing = doc["trajectories"]
    have = {t["id"] for t in existing}

    # what each layer holds today, so the plan can be read against the deficit it is closing
    from collections import Counter
    lc: Counter = Counter()
    for t in existing:
        if t.get("status") == "descoped":
            continue
        for x in (t.get("layers") or []):
            lc[x] += 1

    rows = plan()
    print("  %-4s %6s %8s %8s %9s" % ("layer", "now", "target", "planned", "after"))
    for code, spec in WAVES.items():
        now = lc.get(code, 0)
        print("  %-4s %6d %8d %8d %9d" % (code, now, TARGET, spec["_planned"], now + spec["_planned"]))
    print("  %-4s %6s %8s %8d" % ("", "", "TOTAL", len(rows)))

    # ids continue the existing scheme with an LX prefix, which collides with no T/P/VP/VD/VM row
    nxt = 1
    created = []
    for r in rows:
        while f"LX{nxt}" in have:
            nxt += 1
        rid = f"LX{nxt}"
        have.add(rid)
        created.append({
            "id": rid,
            "wave": r["wave"],
            "title": r["title"],
            "status": "specced",
            "pct": 5,
            "pages": r["pages"],
            "layers": r["layers"],
        })

    if args.dry_run:
        print(f"\n  would create {len(created)} row(s); first: {created[0]['id']} \"{created[0]['title'][:70]}\"")
        print("  (nothing written)")
        return 0

    # idempotent: a title+page pair that already exists is not created twice
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
    if len(fresh) != len(created):
        print(f"  {len(created) - len(fresh)} row(s) already existed and were left alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
