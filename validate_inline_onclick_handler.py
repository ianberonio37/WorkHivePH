"""
Inline onclick Handler Existence Validator (L0, ratcheted).
============================================================
Every `onclick="fnName(...)"` (and onchange / onsubmit / oninput /
onkeydown / onkeyup / onblur / onfocus / onload) must reference a
function defined in the page's <script> blocks or in an imported JS
file. If the function got renamed during a refactor but the inline
handler wasn't updated, clicking the button silently does nothing.

Output: inline_onclick_handler_report.json. Exit 1 on regression.
Allow with `<!-- handler-allow: <reason> -->` near the element.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "inline_onclick_handler_report.json"
BASELINE_PATH = ROOT / "inline_onclick_handler_baseline.json"

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

# Match `onEVENT="fnName(...)"`. Capture the function NAME (first identifier
# before the parens). Ignore `onEVENT="someInlineJS()"` where the inline JS
# is just `this.something()` or similar object access.
INLINE_HANDLER_RE = re.compile(
    r"""\bon(?:click|change|submit|input|keydown|keyup|blur|focus|load|mouseenter|mouseleave)\s*=\s*['"`](?P<body>[^'"`]+)['"`]""",
    re.IGNORECASE,
)
# Extract the first identifier-call from the handler body
FIRST_FN_RE = re.compile(r"""^\s*([a-zA-Z_$][\w$]*)\s*\(""")

# Function definitions in <script> blocks
FN_DEF_PATTERNS = [
    re.compile(r"""\bfunction\s+([a-zA-Z_$][\w$]*)\s*\("""),
    re.compile(r"""\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)"""),
    re.compile(r"""\bwindow\.([a-zA-Z_$][\w$]*)\s*="""),
    re.compile(r"""^([a-zA-Z_$][\w$]*)\s*\([^)]*\)\s*\{""", re.MULTILINE),  # top-level
]

# Browser globals + utility helpers that don't need to be defined locally
BROWSER_GLOBALS = {
    "alert", "confirm", "prompt", "console", "window", "document", "history",
    "location", "navigator", "scrollTo", "scrollBy", "open", "close", "print",
    "blur", "focus", "setTimeout", "setInterval", "clearTimeout", "clearInterval",
    "fetch", "URL", "Date", "JSON", "Object", "Array", "Math", "Number", "String",
    "Boolean", "Promise", "Map", "Set", "RegExp",
    # WorkHive-wide utilities loaded via shared scripts
    "escHtml", "showToast", "pushNotif", "log", "log_", "track",
    "triggerInstall", "togglePersona",
}

ALLOW_RE = re.compile(r"handler-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _load_shared_fns() -> set[str]:
    """Function names defined in the platform-wide shared JS modules."""
    names: set[str] = set()
    for js_name in ("utils.js", "nav-hub.js", "companion-launcher.js",
                    "search-overlay.js", "wh-persona.js", "voice-handler.js",
                    "wh-ga4.js"):
        p = ROOT / js_name
        if not p.exists(): continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for pat in FN_DEF_PATTERNS:
            for m in pat.finditer(text):
                names.add(m.group(1))
    return names


# Sentinel binding: name the L2 test `test('inline_onclick_handler: ...')` for coverage credit.
CHECK_NAMES = ["inline_onclick_handler"]


def main() -> int:
    shared_fns = _load_shared_fns()

    per_page = []
    total_handlers = 0
    total_orphan = 0
    seen: set = set()

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        raw = page.read_text(encoding="utf-8", errors="replace")

        # Extract <script> bodies for function defs. We don't strip comments
        # because we WANT to see inline handlers; only strip HTML comments.
        page_fns: set[str] = set()
        for pat in FN_DEF_PATTERNS:
            for m in pat.finditer(raw):
                page_fns.add(m.group(1))

        # Now find inline handlers (only in non-comment HTML)
        body = HTML_COMMENT_RE.sub("", raw)
        orphans = []
        for m in INLINE_HANDLER_RE.finditer(body):
            handler = m.group("body").strip()
            fm = FIRST_FN_RE.match(handler)
            if not fm: continue  # Not a function call (e.g. inline expression)
            fn = fm.group(1)
            total_handlers += 1
            if fn in BROWSER_GLOBALS or fn in shared_fns or fn in page_fns:
                continue
            # Allow window
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win): continue
            key = (name, fn)
            if key in seen: continue
            seen.add(key)
            orphans.append({"handler": fn, "snippet": handler[:60]})

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
        "summary": {"pages_scanned": len(per_page), "total_handlers": total_handlers,
                    "total_orphans": total_orphan, "baseline": baseline,
                    "shared_fns_known": len(shared_fns)},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nInline onclick Handler Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  shared fns:       {len(shared_fns)}")
    print(f"  inline handlers:  {total_handlers}")
    print(f"  orphan handlers:  {total_orphan}  (baseline: {baseline})")
    if total_orphan == 0:
        print("\n  PASS — every inline onclick/onchange/... handler resolves to a defined function.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["orphans"]: continue
        print(f"  {entry['page']}")
        for o in entry["orphans"]:
            print(f"    → {o['handler']}()  — no such function in page or shared modules")
            shown += 1
            if shown >= 25:
                print("    ... (more in report)")
                break
        if shown >= 25: break
    return 1 if total_orphan > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
