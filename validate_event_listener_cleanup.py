"""
Event Listener Cleanup Validator (L0, ratcheted).
===================================================
Pages with `addEventListener` calls on transient elements (created
in render functions, not stable window/document) should pair them
with `removeEventListener` or rely on element removal to clean them.

Heuristic
  Count `addEventListener` calls per file vs `removeEventListener` calls.
  Flag files with > 10 add calls and 0 remove calls (likely accumulating
  listeners on each render).

Output: event_listener_cleanup_report.json. Exit 1 on regression.
Allow with `// listener-cleanup-allow: <reason>` near a hot loop.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "event_listener_cleanup_report.json"
BASELINE_PATH = ROOT / "event_listener_cleanup_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "engineering-design.js", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

ADD_RE    = re.compile(r"""\baddEventListener\(""")
REMOVE_RE = re.compile(r"""\bremoveEventListener\(""")
ALLOW_RE = re.compile(r"listener-cleanup-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('event_listener_cleanup: ...')` for coverage credit.
CHECK_NAMES = ["event_listener_cleanup"]


# A listener bound to nodes that were JUST rebuilt is self-cleaning: the old nodes (and their
# listeners) are discarded by the innerHTML assignment, which this file's own docstring already
# allows for ("rely on element removal to clean them") but could not detect. voice-journal.html
# crossed the 10-add threshold purely on rebuild-scoped binds and flipped the ratchet red with no
# new leak. The pattern exempted is deliberately TIGHT -- a querySelectorAll(...).forEach bind
# that follows an innerHTML/insertAdjacentHTML/replaceChildren on the same short span:
#     root.innerHTML = chips.join("");
#     root.querySelectorAll(".filter-chip").forEach(btn => btn.addEventListener("click", ...))
# A bare document/window bind is NOT exempted, because nothing removes those.
REBUILD_RE = __import__("re").compile(
    r"(?:innerHTML\s*=|insertAdjacentHTML\(|replaceChildren\()[\s\S]{0,400}?"
    r"querySelectorAll\([\s\S]{0,200}?forEach\([\s\S]{0,200}?$")


def _rebuild_scoped(body, pos):
    return bool(REBUILD_RE.search(body[max(0, pos - 700):pos]))

def selftest() -> int:
    # Rebuild-scoped binds are exempted. That exemption must stay TIGHT: a bare document/window
    # bind has nothing to clean it up and must still count.
    sprawl  = "document.addEventListener(" + "'click'" + ", f);"
    rebuild = ("root.innerHTML = html;" + chr(10) +
               "root.querySelectorAll('.x').forEach(b => b.addEventListener('click', f));")
    detached = ("root.innerHTML = html;" + chr(10) * 40 +
                "window.addEventListener('resize', f);")
    cases = [
        ("a bare document bind is still counted", not _rebuild_scoped(sprawl, sprawl.index("addEventListener"))),
        ("a rebuild-scoped bind is exempted", _rebuild_scoped(rebuild, rebuild.index("addEventListener"))),
        ("a window bind far below a rebuild is still counted",
         not _rebuild_scoped(detached, detached.index("addEventListener"))),
    ]
    ok = all(v for _n, v in cases)
    for name, v in cases:
        print(("  PASS  " if v else "  FAIL  ") + name)
    print("  selftest: " + ("teeth intact" if ok else "VACUOUS - the exemption swallows real sprawl"))
    return 0 if ok else 1

def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    per_page = []
    total_risk = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = HTML_COMMENT_RE.sub("", page.read_text(encoding="utf-8", errors="replace"))
        if ALLOW_RE.search(body):
            per_page.append({"page": name, "add": 0, "remove": 0, "allowed": True})
            continue
        all_adds = [m.start() for m in ADD_RE.finditer(body)]
        rebuild  = [o for o in all_adds if _rebuild_scoped(body, o)]
        adds     = len(all_adds) - len(rebuild)
        removes  = len(REMOVE_RE.findall(body))
        # Heuristic threshold — 10+ UNMANAGED adds with zero removes is suspect. Rebuild-scoped
        # binds are excluded above: the nodes they attach to are replaced wholesale on re-render.
        risky = adds >= 10 and removes == 0
        if risky:
            total_risk += 1
        per_page.append({"page": name, "add": adds, "remove": removes,
                         "add_raw": len(all_adds), "rebuild_scoped": len(rebuild),
                         "risky": risky})

    risky_pages = [p for p in per_page if p.get("risky")]

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("risky", 0)
        except Exception: baseline = 0
    else:
        baseline = len(risky_pages)
        BASELINE_PATH.write_text(json.dumps({"risky": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(risky_pages) < baseline:
        baseline = len(risky_pages)
        BASELINE_PATH.write_text(json.dumps({"risky": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "risky_pages": len(risky_pages),
                    "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nEvent Listener Cleanup Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  risky pages:      {len(risky_pages)}  (baseline: {baseline})")
    if not risky_pages:
        print("\n  PASS — no pages with 10+ adds / 0 removes pattern.")
        return 0
    for p in risky_pages[:15]:
        print(f"  {p['page']}  adds={p['add']}  removes=0")
    return 1 if len(risky_pages) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
