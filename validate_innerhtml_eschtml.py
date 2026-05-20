"""
innerHTML escHtml Audit Validator (L0, ratcheted).
====================================================
Every `el.innerHTML = `template${interpolation}` assignment that
interpolates DB-or-user data MUST run the interpolation through
escHtml() / escapeHtml() / DOMPurify.sanitize() to prevent stored-XSS.

Heuristic
  Find every `*.innerHTML = ` assignment.
  Look at the RHS — if it contains ${expr} interpolation tokens
  WITHOUT `escHtml(` / `escapeHtml(` / `sanitize(` somewhere in the
  template, flag as RISK.

Exempt safe contexts:
  - innerHTML = ''       (clear; safe)
  - innerHTML = 'static'  (static literal; safe)
  - innerHTML = `<static>` (static template, no ${}; safe)

Allow with `// xss-allow: <reason>` near the assignment for cases
where the interpolated values are KNOWN-SAFE (UI-internal labels,
e.g. constants, statuses from a curated enum).

Output: innerhtml_eschtml_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "innerhtml_eschtml_report.json"
BASELINE_PATH = ROOT / "innerhtml_eschtml_baseline.json"

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

# `.innerHTML =` followed by a value expression that we capture up to the
# next `;` outside strings or a closing brace at end of line.
INNERHTML_RE = re.compile(
    r"""\.innerHTML\s*=\s*(?P<rhs>(?:[^;]|\\;){5,1200});""",
    re.DOTALL,
)

# Interpolation token inside template literals
INTERP_RE = re.compile(r"""\$\{[^}]+\}""")

ESCAPER_RE = re.compile(
    # `escHtml(...)`, `escapeHtml(...)`, `sanitize(...)`, `DOMPurify.sanitize(...)`,
    # `encodeURI(...)`, `encodeURIComponent(...)`, and the codebase's `e(...)` alias
    # for escHtml that's commonly aliased as `const e = escHtml` in render functions.
    r"""\b(?:escHtml|escapeHtml|sanitize|DOMPurify\.sanitize|encodeURI(?:Component)?|e)\("""
)

ALLOW_RE = re.compile(r"xss-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('innerhtml_eschtml: ...')` for coverage credit.
CHECK_NAMES = ["innerhtml_eschtml"]


def main() -> int:
    per_page = []
    total_assignments = 0
    total_risk = 0
    seen: set = set()

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = HTML_COMMENT_RE.sub("", page.read_text(encoding="utf-8", errors="replace"))
        risks = []
        for m in INNERHTML_RE.finditer(body):
            total_assignments += 1
            rhs = m.group("rhs")
            # Has interpolation?
            interps = INTERP_RE.findall(rhs)
            if not interps: continue  # Static template, safe
            # Each interpolation that contains a variable reference (not a
            # call to an escaper) is a risk. We check: does the WHOLE rhs
            # have any escaper call?
            if ESCAPER_RE.search(rhs): continue
            # Allow window
            win = body[max(0, m.start() - 300):m.end() + 100]
            if ALLOW_RE.search(win): continue
            # Skip if the RHS is just `<svg ...>` / static-looking — be lenient
            # by only flagging if the interp expression itself looks like data
            # (has a `.` member access or `(`, not just a const literal).
            data_like = any(re.search(r"[.()[\]]", i) for i in interps)
            if not data_like: continue
            key = (name, m.start())
            if key in seen: continue
            seen.add(key)
            risks.append({
                "snippet":    rhs[:80].replace("\n", " "),
                "interps":    interps[:3],
                "offset":     m.start(),
            })
        per_page.append({"page": name, "risks": risks})
        total_risk += len(risks)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("risk", 0)
        except Exception: baseline = 0
    else:
        baseline = total_risk
        BASELINE_PATH.write_text(json.dumps({"risk": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_risk < baseline:
        baseline = total_risk
        BASELINE_PATH.write_text(json.dumps({"risk": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_assignments": total_assignments,
                    "total_risk": total_risk, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\ninnerHTML escHtml Audit Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:        {len(per_page)}")
    print(f"  innerHTML assigns:    {total_assignments}")
    print(f"  XSS-risk patterns:    {total_risk}  (baseline: {baseline})")
    if total_risk == 0:
        print("\n  PASS — every interpolating innerHTML assignment uses escHtml/sanitize.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["risks"]: continue
        print(f"  {entry['page']}")
        for r in entry["risks"]:
            print(f"    → innerHTML = `... {r['interps'][0]} ...`  (no escHtml in template)")
            shown += 1
            if shown >= 20:
                print("    ... (more in report)")
                break
        if shown >= 20: break
    return 1 if total_risk > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
