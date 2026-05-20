"""
getElementById Orphan Setter Validator (L0, ratcheted).
========================================================
Mirror of validate_orphan_kpi_tiles.py: that one finds HTML elements
with no JS setter; THIS one finds JS setters with no HTML element.

  Page calls `document.getElementById('foo-thing')` but no
  `<* id="foo-thing">` exists on the page. JS errors silently (returns
  null) or worse — `null.textContent = '...'` throws and stops the
  whole load sequence.

Allow with `<!-- gid-allow: <reason> -->` or `// gid-allow: <reason>`.
Output: getelementbyid_orphan_setter_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "getelementbyid_orphan_setter_report.json"
BASELINE_PATH = ROOT / "getelementbyid_orphan_setter_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

GET_RE = re.compile(r"""\bgetElementById\(\s*['"`](?P<id>[a-z][\w-]+)['"`]\s*\)""", re.IGNORECASE)
QS_RE  = re.compile(r"""\bquerySelector(?:All)?\(\s*['"`]#(?P<id>[a-z][\w-]+)['"`]\s*\)""", re.IGNORECASE)
HTML_ID_RE = re.compile(r"""\bid\s*=\s*['"`](?P<id>[a-z][\w-]+)['"`]""", re.IGNORECASE)
# Dynamic id construction: getElementById('prefix-' + var + '-suffix')
DYN_RE = re.compile(r"""\bgetElementById\(\s*['"`]([a-z][\w-]*?)['"`]\s*\+""", re.IGNORECASE)
ALLOW_RE = re.compile(r"gid-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('getelementbyid_orphan_setter: ...')` for coverage credit.
CHECK_NAMES = ["getelementbyid_orphan_setter"]


def main() -> int:
    per_page = []
    total_orphan = 0
    total_lookups = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        raw = page.read_text(encoding="utf-8", errors="replace")
        body = HTML_COMMENT_RE.sub("", raw)

        # All HTML ids declared anywhere on the page
        page_ids = {m.group("id") for m in HTML_ID_RE.finditer(body)}
        # Dynamic prefixes used by setCard-style dispatch — collect them so we
        # can match `id="prefix-X"` HTML elements as "covered" by dynamic JS.
        dyn_prefixes = {m.group(1) for m in DYN_RE.finditer(body)}

        orphans: list[dict] = []
        seen: set = set()

        for pat in (GET_RE, QS_RE):
            for m in pat.finditer(body):
                gid = m.group("id")
                total_lookups += 1
                if gid in seen: continue
                seen.add(gid)
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win): continue

                if gid in page_ids: continue

                # Dynamic match: if the JS contains `getElementById('PFX-' + var)`,
                # and HTML has `id="PFX-something"`, count as covered.
                covered_dyn = False
                for pfx in dyn_prefixes:
                    if any(html_id.startswith(pfx) for html_id in page_ids):
                        # Only credit if the lookup id ALSO starts with that prefix
                        if gid.startswith(pfx):
                            covered_dyn = True
                            break
                if covered_dyn: continue

                orphans.append({"id": gid, "offset": m.start()})

        per_page.append({"page": name, "orphans": orphans})
        total_orphan += len(orphans)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("orphans", 0)
        except Exception: baseline = 0
    else:
        baseline = total_orphan
        BASELINE_PATH.write_text(json.dumps({"orphans": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_orphan < baseline:
        baseline = total_orphan
        BASELINE_PATH.write_text(json.dumps({"orphans": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_lookups": total_lookups,
                    "total_orphans": total_orphan, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\ngetElementById Orphan Setter Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  lookups:          {total_lookups}")
    print(f"  orphan setters:   {total_orphan}  (baseline: {baseline})")
    if total_orphan == 0:
        print("\n  PASS — every getElementById/querySelector('#X') has a matching <X> in HTML.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["orphans"]: continue
        print(f"  {entry['page']}")
        for o in entry["orphans"]:
            print(f"    → getElementById('{o['id']}')  — no <#{o['id']}> in HTML")
            shown += 1
            if shown >= 30:
                print("    ... (more in report)")
                break
        if shown >= 30: break
    return 1 if total_orphan > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
