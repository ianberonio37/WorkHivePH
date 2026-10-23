#!/usr/bin/env python3
"""slow-read-honest - SL A4 (2026-10-19): when a page's reads are slow it says it is waiting, when they hang it gives up
ONCE at the client's timeout and says the read failed, and nothing on it goes on claiming to load, to be empty, or to be
fresh.

WHAT THE A4 WALK FOUND (receipts SL935-SL964: 30 pages, phone-390 and desktop-1280, each as its row's cast, every data
read answered 5 s late, then every data read hung with the platform's own 6 s client timeout):
  * the client asked every timed-out read FOUR times. supabase-js 2.110 retries a rejected GET three more times (1, 2,
    4 s apart) unless the rejection is named AbortError, and the shell's timeout aborts with a TimeoutError - so at the
    production 45 s timeout a dead backend held each read 3 min 7 s, and a page whose reads chain waited that per link
    (measured: v_hives_truth asked at 0.3, 7.3, 15.3 and 25.3 s on three pages; marketplace's counts 62 s).
  * the settle pass knew one skeleton spelling (.wh-skeleton): community's pre-JS feed and leaderboard shapes
    (.skeleton) shimmered for the whole 75 s under "part of this page could not be loaded".
  * resume painted nothing in its form until its identity and role reads answered (63 s blank with reads hung), then
    said "Nothing here yet." in every section under "this is a loading problem, not an empty resume".
  * report-sender's contacts card kept "Checking your saved contacts..." beside the settle pass's "Not loaded"; the
    settle pass did not know "Checking"; skill-matrix's shapes kept shimmering beside its settled line; a source chip
    read "Read failed · Checking · shift plan".
  * an unanswered hive lookup walled a solo owner with "Supervisor access only" (integrations) - a reason never checked;
    a walled worker's page carried a "Live · refreshed on load" figures line (plant-connections) the shell then turned
    into "showing the last data loaded"; a role check that could not be asked walled in silence.
  * two admin pages hid the whole document while the admin check ran - a blank screen, nothing said - and
    Marketplace Admin showed its moderation tiles as bare dashes to everyone until the answer.
  * project-report's chooser listed live project names and statuses with no source line; analytics told a hive with 8
    PM assets "No PM assets or scope items found."
  * the shared failure vocabulary every prover imports (tools/session_signals.mjs) matched only a straight apostrophe,
    so the platform's own curly "Couldn’t load ..." was graded silent.

WHAT THIS HOLDS (static; the live floor stays with waiting-is-spoken and skeleton_resolves):
  1. SHARED - utils.js: a REST timeout is handed to the client as an AbortError (no silent retries); the settle pass
     settles plain skeleton shapes while a service is still failing, knows "Checking", hides a settled line's shapes,
     tells pages the reads failed (wh:reads-failed) and drops a chip's "Checking" clause; the hive lookup and the role
     check carry a third answer ('could not ask'); the retired-overlay inert pass leaves an admin gate's pending line
     alone.
  2. PAGES - each fixed site keeps its fix (an anchor per site, below).
  3. VOCABULARY - tools/session_signals.mjs's FAILURE_SRC matches the curly apostrophe.

    python tools/validate_slow_read_honest.py
    python tools/validate_slow_read_honest.py --self-test
"""
from __future__ import annotations

import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (page, regex that must match the code with comments stripped, what breaks without it)
ANCHORS = [
    ("ai-quality.html", r"whListSkeleton\(document\.getElementById\('content'\), 4, 'your AI quality figures'\)",
     "ai-quality shows a blank minute while its reads wait - no skeleton until they answer"),
    ("report-sender.html", r"addEventListener\('wh:reads-failed'",
     "report-sender's contacts card keeps 'Checking your saved contacts' beside 'Not loaded'"),
    ("report-sender.html", r"!_rsContactsSettled && _rsTransportFailed",
     "report-sender's verdict keeps promising a contact count after the service stopped answering"),
    ("resume.html", r"logPageView\(db\);\s*const _sec0 = document\.getElementById\('sections'\);\s*if \(_sec0[^\n]*whListSkeleton\(_sec0, 4, 'your resume'\)",
     "resume's form region is blank until the identity and role reads answer"),
    ("resume.html", r"_cloudLoadFailed\s*\?\s*'Not loaded - your saved resume could not be read",
     "resume says 'Nothing here yet.' in every section under 'not an empty resume'"),
    ("integrations.html", r"if \(!HIVE_ID && _seat && _seat\.unread\)",
     "integrations walls with 'Supervisor access only' off a hive lookup that never answered"),
    ("integrations.html", r"id=\"it-access-pending\"",
     "the console's place on integrations is silent while its access is asked"),
    ("integrations.html", r"html:not\(\.wh-nonsup\) #it-access-pending \{ display: none; \}",
     "a cached supervisor sees 'Checking your access' under the console itself"),
    ("integrations.html", r"window\._whRoleUnread === true",
     "integrations walls on the device's role in silence when the role could not be asked"),
    ("plant-connections.html", r"window\.__pcWalled = true;",
     "a walled worker's page names figures it never read ('Live · refreshed on load')"),
    ("plant-connections.html", r"if \(window\.__pcWalled\) return;",
     "the load-time figures line is painted over a wall"),
    ("plant-connections.html", r"window\._whRoleUnread === true",
     "plant-connections walls on the device's role in silence when the role could not be asked"),
    ("agentic-rag-observability.html", r"pend\.setAttribute\('data-wh-gate-pending', '1'\)",
     "the observability page is a blank screen while its admin check runs"),
    ("agentic-rag-observability.html", r"window\.addEventListener\('DOMContentLoaded', function \(\) \{\s*pending\(\);",
     "the observability page's pending line is never shown"),
    ("llm-observability.html", r"pend\.setAttribute\('data-wh-gate-pending', '1'\)",
     "LLM observability is a blank screen while its admin check runs"),
    ("llm-observability.html", r"window\.addEventListener\('DOMContentLoaded', function \(\) \{\s*pending\(\);",
     "LLM observability's pending line is never shown"),
    ("marketplace-admin.html", r"_mpaPending\(true\);\s*const _retiredOv",
     "Marketplace Admin shows its moderation tiles as bare dashes to everyone while the admin check runs"),
    ("marketplace-admin.html", r"const _aR = await adminAnswer\(\);\s*_mpaPending\(false\);",
     "Marketplace Admin's retired path never takes its pending line down"),
    ("marketplace-admin.html", r"const _a = await adminAnswer\(\);\s*_mpaPending\(false\);",
     "Marketplace Admin's live path never shows its console after the check"),
    ("project-report.html", r"_chooserRead = !recentErr;",
     "project-report's chooser lists live projects with no source line"),
    ("project-report.html", r"if \(_chooserRead && typeof renderSourceChip === 'function'\)",
     "project-report's chooser source line is never painted"),
    ("analytics.html", r"No PM scope items were due in this period",
     "analytics tells a hive with PM assets 'No PM assets or scope items found.'"),
]
# a sentence that must never come back
FORBIDDEN = [
    ("analytics.html", "No PM assets or scope items found.", "the false 'no PM assets' sentence is back on analytics"),
]


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


def _fn(text: str, name: str) -> str:
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", text)
    if not m:
        return ""
    depth, i = 0, m.end() - 1
    for j in range(i, min(len(text), i + 60000)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return text[i:i + 60000]


def shared_problems(utils: str) -> list[str]:
    u = _code(utils)
    bad = []
    if not re.search(r"if \(_svc === 'rest' && err && err\.name === 'TimeoutError'\) throw new DOMException\(String\(err\.message \|\| 'WH_DB_TIMEOUT'\), 'AbortError'\);", u):
        bad.append("utils.js: a REST timeout reaches supabase-js as a TimeoutError - it retries every timed-out read three "
                   "more times (4 x 45 s + 7 s before a page can say it failed)")
    st = _fn(u, "_whSettleStuckLoaders")
    if not st:
        bad.append("utils.js: _whSettleStuckLoaders is gone")
    else:
        if "dispatchEvent(new CustomEvent('wh:reads-failed'))" not in st:
            bad.append("utils.js: the settle pass no longer tells pages the reads failed (wh:reads-failed) - a page's own "
                       "'still checking' state outlives the service")
        if not re.search(r"var PROG = /\^\(Computing\|Loading\|Counting\|Reading\|Rolling up\|Fetching\|Building\|Checking\)", st):
            bad.append("utils.js: the settle pass does not know 'Checking...' - a frozen check line survives a dead backend")
        if "_box.querySelectorAll('.skeleton, [class*=\"skel-\"]')" not in st:
            bad.append("utils.js: a settled line leaves its container's shapes shimmering beside 'Not loaded'")
        if not (re.search(r"if \(Object\.keys\(window\._whConnFailedSvcs \|\| \{\}\)\.length\) \{", st)
                and "var _isShape = function (el)" in st and "whListError(_hosts[hq], _skelMsg" in st):
            bad.append("utils.js: the settle pass knows only .wh-skeleton - a page's plain pre-JS shapes shimmer under the "
                       "failure notice until its own reads reach them")
        if not re.search(r"_fn\.nodeValue = _fn\.nodeValue\.replace\(/\^\\s\*Checking\\b\\s\*·\\s\*/, ''\);", st):
            bad.append("utils.js: a failed chip still says 'Read failed · Checking'")
    eh = _fn(u, "whEnsureHiveContext")
    # [^{}]* between the flag and the return: the helpers now also keep the error beside the flag
    # (window._whHiveSeatUnreadError / _whRoleUnreadError, 2026-10-23) - the flag and the null answer are what count
    if not re.search(r"if \(mem\.error\) \{ window\._whHiveSeatUnread = true;[^{}]*return null; \}", eh):
        bad.append("utils.js: whEnsureHiveContext answers an unreadable lookup and 'no hive' the same - a gate walls on a "
                   "reason it never checked")
    sh = _fn(u, "whStartupHive")
    if "out.unread = !out.id && window._whHiveSeatUnread === true;" not in sh:
        bad.append("utils.js: whStartupHive does not pass on 'the hive lookup never answered'")
    rr = _fn(u, "whReconcileHiveRole")
    if not re.search(r"if \(!res \|\| res\.error\) \{ window\._whRoleUnread = true;[^{}]*return null; \}", rr):
        bad.append("utils.js: whReconcileHiveRole cannot say it could not ask - a wall on the device's role reads as the "
                   "server's fresh answer")
    if "sib.hasAttribute('data-wh-gate-pending')" not in u:
        bad.append("utils.js: the retired-overlay inert pass silences an admin gate's pending line")
    return bad


def page_problems(pages: dict[str, str]) -> list[str]:
    bad = []
    for page, rx, why in ANCHORS:
        if not re.search(rx, _code(pages.get(page, ""))):
            bad.append(f"{page}: {why}")
    for page, s, why in FORBIDDEN:
        if s in _code(pages.get(page, "")):
            bad.append(f"{page}: {why}")
    return bad


def vocab_problems(signals: str) -> list[str]:
    # the constant is string pieces joined with + up to its semicolon; the pieces hold no semicolons
    m = re.search(r"export const FAILURE_SRC =([\s\S]*?);", signals)
    if not m:
        return ["tools/session_signals.mjs: FAILURE_SRC not found"]
    rx = re.compile("".join(a or b for a, b in re.findall(r"\"([^\"]*)\"|'([^']*)'", m.group(1))), re.I)
    bad = []
    for s in ("Couldn’t load your skill matrix. Your levels are unknown right now, not zero.",
              "Couldn’t load the community feed - WorkHive did not answer."):
        if not rx.search(s):
            bad.append(f"tools/session_signals.mjs: FAILURE_SRC does not match the platform's curly '{s[:40]}...' - a page "
                       "that says it failed is graded silent")
    if rx.search("Your skill matrix"):
        bad.append("tools/session_signals.mjs: FAILURE_SRC matches ordinary copy")
    return bad


def load_pages() -> dict[str, str]:
    return {Path(p).name: Path(p).read_text(encoding="utf-8") for p in glob.glob(str(ROOT / "*.html"))
            if not re.search(r"backup|\.bak", Path(p).name)}


def problems(utils: str, pages: dict[str, str], signals: str) -> list[str]:
    return shared_problems(utils) + page_problems(pages) + vocab_problems(signals)


def run() -> int:
    bad = problems((ROOT / "utils.js").read_text(encoding="utf-8"), load_pages(),
                   (ROOT / "tools" / "session_signals.mjs").read_text(encoding="utf-8"))
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL slow-read-honest - {len(bad)} problem(s)")
        return 1
    print(f"PASS slow-read-honest - a timed-out read fails once (no silent client retries); the settle pass settles every "
          f"skeleton spelling, knows 'Checking', tells pages the reads failed; the hive lookup and role check say 'could not "
          f"ask'; {len(ANCHORS)} page fixes hold; the failure vocabulary reads curly apostrophes")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    u = (ROOT / "utils.js").read_text(encoding="utf-8")
    pages = load_pages()
    sig = (ROOT / "tools" / "session_signals.mjs").read_text(encoding="utf-8")
    expect("the real tree passes", not problems(u, pages, sig))
    expect("a REST timeout left as TimeoutError fails", bool(shared_problems(u.replace(
        "if (_svc === 'rest' && err && err.name === 'TimeoutError') throw new DOMException", "if (false) throw new DOMException"))))
    expect("the plain-shape settle branch removed fails", bool(shared_problems(u.replace(
        "whListError(_hosts[hq], _skelMsg", "void(_hosts[hq], _skelMsg"))))
    expect("'Checking' dropped from the settle pass fails", bool(shared_problems(u.replace(
        "|Fetching|Building|Checking)\\b", "|Fetching|Building)\\b"))))
    # regex mutants: a literal .replace() went silently no-op when the helpers grew an error beside the flag
    hive_mut = re.sub(r"if \(mem\.error\) \{ window\._whHiveSeatUnread = true;[^{}]*return null; \}", "if (mem.error) return null;", u)
    role_mut = re.sub(r"if \(!res \|\| res\.error\) \{ window\._whRoleUnread = true;[^{}]*return null; \}", "if (!res || res.error) return null;", u)
    expect("the hive lookup's third answer removed fails", hive_mut != u and bool(shared_problems(hive_mut)))
    expect("the role check's third answer removed fails", role_mut != u and bool(shared_problems(role_mut)))
    mut = dict(pages)
    mut["resume.html"] = mut["resume.html"].replace("const _sec0 = document.getElementById('sections');", "const _sec0 = null;")
    expect("resume's early skeleton removed fails", any("resume.html" in b for b in page_problems(mut)))
    mut = dict(pages)
    mut["integrations.html"] = mut["integrations.html"].replace("if (!HIVE_ID && _seat && _seat.unread)", "if (false)")
    expect("integrations' could-not-ask wall removed fails", any("integrations.html" in b for b in page_problems(mut)))
    mut = dict(pages)
    mut["marketplace-admin.html"] = mut["marketplace-admin.html"].replace("    _mpaPending(true);\n", "\n")
    expect("Marketplace Admin's pending line removed fails", any("marketplace-admin.html" in b for b in page_problems(mut)))
    mut = dict(pages)
    mut["analytics.html"] = mut["analytics.html"].replace("No PM scope items were due in this period, so there is nothing to measure compliance against yet. Scope items are added to each asset in PM Scheduler.", "No PM assets or scope items found.")
    expect("analytics' false 'no PM assets' sentence back fails", any("analytics.html" in b for b in page_problems(mut)))
    expect("a straight-only failure apostrophe fails", bool(vocab_problems(sig.replace("couldn['’]?t", "couldn'?t"))))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
