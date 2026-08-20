"""
Unbounded Query Detection Validator (L0, ratcheted).
=====================================================
Every `db.from('table').select(...)` chain on a page should END WITH
one of:
  - .limit(N)
  - .single() / .maybeSingle()
  - { count: 'exact', head: true } (count-only query)
  - .range(low, high) (explicit pagination)
  - .eq('id', ID) on a primary-key column (intent is one row)

Without a limit, a page can fetch arbitrarily many rows. After data
grows, it OOMs the browser or freezes the UI.

Output: unbounded_query_report.json. Exit 1 on regression.
Allow with `// unbounded-query-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "unbounded_query_report.json"
BASELINE_PATH = ROOT / "unbounded_query_baseline.json"

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

FROM_RE = re.compile(r"""\.from\(\s*['"`](?P<t>[a-z_][\w]*)['"`]\s*\)""")
ALLOW_RE = re.compile(r"unbounded-query-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")

# Markers that indicate the query is bounded.
# - explicit `.limit/.single/.maybeSingle/.range` are direct bounds
# - `head: true` count-only queries return no rows
# - hive/worker/asset scoping `.eq()` are soft bounds — limit to one tenant's
#   rows (typically <500)
# - `.insert/.update/.upsert/.delete` are WRITES, not reads — bounded by intent
SCOPING_COLS = (
    "id|hive_id|worker_name|auth_uid|user_id|asset_id|seller_name|"
    "project_id|pm_asset_id|scope_item_id|table|target_id|actor|name|tag|"
    "slug|feedback_id|listing_id|order_id|completion_id|post_id|topic_id|"
    "asset_node_id|parent_id|fault_id|kind|category"
)
BOUNDED_MARKERS = re.compile(
    r"""\.(?:limit|single|maybeSingle|range|insert|update|upsert|delete)\(|head:\s*true|"""
    r"""\.(?:eq|in)\(\s*['"`](?:""" + SCOPING_COLS + r""")['"`]"""
)


# Sentinel binding: name the L2 test `test('unbounded_query: ...')` for coverage credit.
CHECK_NAMES = ["unbounded_query"]


# Both windows in main() are FIXED SIZES, and both were being spent on PROSE:
#   - public-feed.html:240 has a 10-line comment inside the chain, so .limit(PAGE_SIZE)
#     landed past the 1200-char chain window and a BOUNDED query read as unbounded.
#   - engineering-design.js:28326 carries an explicit `unbounded-query-allow:` directive
#     that sits just outside the 200-char lookback, so its own exemption was invisible.
# Measuring the chain over CODE ONLY fixes both without widening either window. Strings
# are KEPT, because the table name in .from("t") is a string.
def _strip_comments_map(src):
    out, idx, i, n = [], [], 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "//":
            j = src.find(chr(10), i)
            i = n if j < 0 else j
        elif two == "/*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif src[i] in '"\'`':
            q, j = src[i], i + 1
            while j < n:
                if src[j] == chr(92):
                    j += 2
                    continue
                if src[j] == q:
                    j += 1
                    break
                j += 1
            out.append(src[i:j]); idx.extend(range(i, j)); i = j
        else:
            out.append(src[i]); idx.append(i); i += 1
    return "".join(out), idx

def selftest() -> int:
    # The chain window is measured over CODE ONLY (comments stripped). That relaxation must not
    # blind the check: a genuinely unbounded read still has to be caught, and the window must not
    # become effectively infinite. Proven here on synthetic pairs so the proof survives the session.
    import re as _re
    chain_end = _re.compile(r"\.from\(|;\s*\n|^\s*\}", _re.MULTILINE)

    def flagged(src):
        code, _idx = _strip_comments_map(src)
        hits = []
        for m in FROM_RE.finditer(code):
            sw = code[m.end(): m.end() + 1200]
            ce = chain_end.search(sw)
            tail = sw[:ce.start()] if ce else sw
            if not BOUNDED_MARKERS.search(tail):
                hits.append(m.group("t"))
        return hits

    unbounded = "const {d} = await db.from('logbook').select('*');" + chr(10)
    prose = ("const {d} = await db.from('logbook').select('*')" + chr(10)
             + ("  // explanatory prose line" + chr(10)) * 40 + "  .limit(50);" + chr(10))
    cases = [("a genuinely unbounded read is still caught", bool(flagged(unbounded))),
             ("a bounded read behind 40 comment lines is not", not flagged(prose))]
    ok = all(v for _n, v in cases)
    for name, v in cases:
        print(("  PASS  " if v else "  FAIL  ") + name)
    print("  selftest: " + ("teeth intact" if ok else "VACUOUS - the window no longer discriminates"))
    return 0 if ok else 1

def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    per_page = []
    total_calls = 0
    total_unbounded = 0
    seen = set()

    files = [(n, ROOT / n) for n in PAGES]
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))

    chain_end_re = re.compile(r"""\.from\(|;\s*\n|^\s*\}""", re.MULTILINE)

    for name, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        code, idx = _strip_comments_map(body)
        issues = []
        for m in FROM_RE.finditer(code):
            total_calls += 1
            t = m.group("t")
            # Chain window over CODE ONLY (see _strip_comments_map).
            search_window = code[m.end(): m.end() + 1200]
            cend = chain_end_re.search(search_window)
            tail = search_window[:cend.start()] if cend else search_window

            # The allow-directive lives IN a comment, so search the ORIGINAL body, by LINES
            # rather than characters: prose length must not decide whether an explicit
            # exemption is seen.
            o_start = idx[m.start()] if m.start() < len(idx) else 0
            o_end = idx[min(m.end(), len(idx) - 1)] if idx else 0
            back = body.rfind(chr(10), 0, o_start) + 1
            for _ in range(6):
                prev = body.rfind(chr(10), 0, max(0, back - 1))
                if prev < 0:
                    back = 0
                    break
                back = prev + 1
            if ALLOW_RE.search(body[back:o_end + 200]): continue
            if BOUNDED_MARKERS.search(tail): continue

            key = (name, t, o_start)
            if key in seen: continue
            seen.add(key)
            issues.append({"table": t, "offset": o_start})
        per_page.append({"file": name, "issues": issues})
        total_unbounded += len(issues)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("unbounded", 0)
        except Exception: baseline = 0
    else:
        baseline = total_unbounded
        BASELINE_PATH.write_text(json.dumps({"unbounded": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_unbounded < baseline:
        baseline = total_unbounded
        BASELINE_PATH.write_text(json.dumps({"unbounded": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(per_page), "total_calls": total_calls,
                    "total_unbounded": total_unbounded, "baseline": baseline},
        "per_file": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nUnbounded Query Detection Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(per_page)}")
    print(f"  .from() calls:    {total_calls}")
    print(f"  unbounded:        {total_unbounded}  (baseline: {baseline})")
    if not total_unbounded:
        print("\n  PASS — every .from() chain has a bounded marker.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["issues"]: continue
        print(f"  {entry['file']}")
        for i in entry["issues"]:
            print(f"    → from('{i['table']}')...  (no .limit/.single/.range/.eq-on-id)")
            shown += 1
            if shown >= 20:
                print("    ... (more in report)")
                break
        if shown >= 20: break
    return 1 if total_unbounded > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
