#!/usr/bin/env python3
"""refusal-has-a-sentence - SL A1 (2026-10-19): every refused or failed request is answered with a sentence a person can
act on - naming the cause it actually was, to the reader it actually is.

WHAT THE A1 WALK FOUND (receipts SL851-SL882: 32 pages, phone-390 and desktop-1280, each as its row's cast, the page's own
reads failed 500 / refused with PostgREST's stock 42501 / its start-up edge call answered with the platform's real 429):
  * the shared refusal sentences spoke only to a member: a signed-out visitor of the public feed read "You do not have
    access ... with this account. Your session is fine. Ask a supervisor" - no account, no session, no supervisor.
  * the page-wide refusal notice matched /session/ in its own text ("Your session is FINE") and offered Sign in to a
    signed-in member refused access.
  * pages answered a refusal with "WorkHive did not answer" (seller profile, ai-quality, PH Intelligence, the seller's
    wallet, marketplace's verdict and grid) or "check your connection" (audit log): the wrong cause, a remedy that
    cannot work.
  * a failed read drew the empty state as well: "No approved assets in this hive yet" (asset-hub), "No readiness
    snapshot yet. Sign in and add your first asset" (hive), "No plan exists for this shift yet - Generate now"
    (shift-brain: a duplicate plan one tap away).
  * a refused live refresh went silent (alert-hub, shift-brain).
  * a check the server failed or refused answered "not an admin": the founder console and Marketplace Admin showed
    their no-access gate to the founder; Platform Actions said "you're offline" to a connected one.

WHAT THIS HOLDS (static):
  1. SHARED - whReadError / whWriteError / the page-wide notice each have a signed-out branch; the notice decides
     Sign in by its identity, and a refused member gets no Sign in; whPlatformAdminAnswer answers 'unreachable' on any
     error; whAdminCheckOfflineText is true online as well as offline.
  2. PAGES - each fixed site keeps its fix (an anchor per site, below).
  3. RATCHET - hard-coded "did not answer" sentences per page never rise above the count measured when this was
     written: a new failure path uses whReadError, which reads the error, instead of a sentence with one cause in it.

    python tools/validate_refusal_sentences.py
    python tools/validate_refusal_sentences.py --self-test
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

# measured 2026-10-19 after the A1 fixes (string literals only, comments stripped); lower it when a page sheds one
NO_ANSWER_BASELINE = {
    "ai-quality.html": 1, "community.html": 3, "hive.html": 1, "index.html": 1, "integrations.html": 2,
    "marketplace-seller-profile.html": 2, "marketplace-seller.html": 2, "marketplace.html": 5, "ph-intelligence.html": 1,
    "plant-connections.html": 1, "platform-actions.html": 1, "report-sender.html": 2, "resume.html": 2, "status.html": 1,
}

# (page, regex that must match the code, what breaks without it)
ANCHORS = [
    ("marketplace-seller-profile.html", r"whReadError\(_mspErr,",
     "the seller profile answers every failure 'WorkHive did not answer' again - a refusal included"),
    ("ai-quality.html", r"whReadError\(err, 'your AI quality data'\)",
     "ai-quality answers a refused read 'WorkHive did not answer. Try again'"),
    ("ph-intelligence.html", r"whReadError\(error, 'the PH Intelligence report'\)",
     "PH Intelligence answers a refused read 'WorkHive did not answer'"),
    ("audit-log.html", r"whReadError\(error, 'the audit log'\)",
     "the audit log answers every failure 'Check your connection'"),
    ("marketplace-seller.html", r"_nn\.textContent = _failCopy\(_e,",
     "the seller's wallet blames the service for a refused read"),
    ("marketplace.html", r": _accessDenied\s*\?\s*_mkDeniedSaid\('the marketplace listings'\) \+ ' The figures above",
     "the marketplace verdict answers a refusal 'WorkHive did not answer'"),
    ("marketplace.html", r": _accessDenied\s*\?\s*escHtml\(_mkDeniedSaid\('the marketplace listings'\)\)",
     "the marketplace listings grid answers a refusal 'WorkHive did not answer'"),
    ("asset-hub.html", r"if \(_ahReadFailed\) \{\s*empty\.style\.display = 'none';",
     "a failed asset read draws 'No approved assets in this hive yet' under 'Could not load your asset fleet'"),
    ("hive.html", r"const _rdFailed = !row && window\._readinessErr === true;",
     "a failed readiness read says 'No readiness snapshot yet. Sign in and add your first asset'"),
    ("shift-brain.html", r"empty\.style\.display = _sbReadFailed \? 'none' : 'block';",
     "a failed plan read offers 'No plan exists for this shift yet - Generate now' (a duplicate plan)"),
    ("alert-hub.html", r"The live refresh did not run",
     "a refused live Action Brief refresh goes silent on alert-hub"),
    ("shift-brain.html", r"The live refresh did not run",
     "a refused live briefing refresh goes silent on shift-brain"),
    ("platform-actions.html", r"could not check your access just now, so its queues stay closed",
     "Platform Actions tells a connected founder 'you're offline' when the check fails"),
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
    for j in range(i, min(len(text), i + 30000)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return text[i:i + 30000]


def shared_problems(utils: str) -> list[str]:
    u = _code(utils)
    bad = []
    if not re.search(r"function _whSignedOut\(\)", u):
        bad.append("utils.js: _whSignedOut() is gone - every refusal sentence speaks to a member, visitors included")
    # SL L4 (2026-10-21): the two makers became wrappers that log what they say (whTold); the sentences live in
    # _whReadErrorText / _whWriteErrorText, so the maker is read WITH the function that composes its sentence
    rd = _fn(u, "whReadError") + _fn(u, "_whReadErrorText")
    wr = _fn(u, "whWriteError") + _fn(u, "_whWriteErrorText")
    if "_whSignedOut()" not in rd:
        bad.append("utils.js: whReadError's refusal tells a signed-out visitor about 'this account' and 'a supervisor'")
    if "_whSignedOut()" not in wr:
        bad.append("utils.js: whWriteError's refusal tells a signed-out visitor about 'this account'")
    if not re.search(r"_whSignedOut\(\)[^;]*\n?\s*\?\s*'Some of this page is shown only to signed-in members", u):
        bad.append("utils.js: the page-wide refusal notice speaks to a visitor as a member")
    sn = _fn(u, "_whShowNotice")
    if not re.search(r"var _isAccess = \(id === 'wh-access-denied-notice'\);", sn) or "/session|" in sn:
        bad.append("utils.js: the notice decides Sign in from its own text again - 'your session is fine' earns a Sign in button")
    # SL AV3 (2026-10-20) added a second reason for no Reload (the live-off notice: a reload cannot open a firewall);
    # the refused member's condition must still lead the guard
    if not re.search(r"if \(!\(_isAccess && !_isSession\)(?: && id !== 'wh-live-notice')?\) el\.appendChild\(_rb\);", sn):
        bad.append("utils.js: a refused member's notice offers a Reload that cannot turn a no into a yes")
    pa = _fn(u, "whPlatformAdminAnswer")
    if not re.search(r"if \(r1\.error\) return 'unreachable';", pa) or not re.search(r"if \(r2\.error\) return 'unreachable';", pa):
        bad.append("utils.js: whPlatformAdminAnswer answers 'no' for a check the server failed or refused - an admin is told the page is not for them")
    if re.search(r"return 'no';\s*\}\s*\}\s*$", pa.strip()[-80:]):
        bad.append("utils.js: whPlatformAdminAnswer's catch answers 'no' when it could not ask")
    ot = _fn(u, "whAdminCheckOfflineText")
    if "onLine === false" not in ot or "could not check your access just now" not in ot:
        bad.append("utils.js: whAdminCheckOfflineText says 'you're offline' to a connected admin whose check failed")
    return bad


def page_problems(pages: dict[str, str]) -> list[str]:
    bad = []
    for page, rx, why in ANCHORS:
        if not re.search(rx, _code(pages.get(page, ""))):
            bad.append(f"{page}: {why}")
    return bad


def no_answer_counts(pages: dict[str, str]) -> dict[str, int]:
    out = {}
    for p, t in pages.items():
        n = len(re.findall(r"[\"'`][^\"'`\n]{0,200}did not answer[^\"'`\n]{0,200}[\"'`]", _code(t)))
        if n:
            out[p] = n
    return out


def ratchet_problems(counts: dict[str, int]) -> list[str]:
    bad = []
    for p, n in sorted(counts.items()):
        cap = NO_ANSWER_BASELINE.get(p, 0)
        if n > cap:
            bad.append(f"{p}: {n} hard-coded 'did not answer' sentence(s), baseline {cap} - a new failure path must ask "
                       "whReadError, which reads the error, rather than name one cause for all of them")
    return bad


def load_pages() -> dict[str, str]:
    return {Path(p).name: Path(p).read_text(encoding="utf-8") for p in glob.glob(str(ROOT / "*.html"))
            if not re.search(r"backup|\.bak", Path(p).name)}


def run() -> int:
    utils = (ROOT / "utils.js").read_text(encoding="utf-8")
    pages = load_pages()
    counts = no_answer_counts(pages)
    bad = shared_problems(utils) + page_problems(pages) + ratchet_problems(counts)
    lower = [f"{p} {n}<{NO_ANSWER_BASELINE[p]}" for p, n in counts.items() if n < NO_ANSWER_BASELINE.get(p, 0)]
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL refusal-has-a-sentence - {len(bad)} problem(s)")
        return 1
    print(f"PASS refusal-has-a-sentence - shared sentences speak to a visitor as a visitor and to a member as a member, the "
          f"notice signs in only a visitor, an unanswered admin check is 'could not check'; {len(ANCHORS)} page fixes hold; "
          f"{sum(counts.values())} hard-coded no-answer sentence(s), none above baseline"
          + (f" (lower the baseline: {', '.join(lower)})" if lower else ""))
    return 0


def self_test() -> int:
    ok = True
    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    u = (ROOT / "utils.js").read_text(encoding="utf-8")
    pages = load_pages()
    expect("the real tree passes", not shared_problems(u) and not page_problems(pages) and not ratchet_problems(no_answer_counts(pages)))
    expect("a member-only read refusal fails", bool(shared_problems(u.replace(
        "    if (_whSignedOut()) return T('WorkHive does not show ' + thing", "    if (false) return T('WorkHive does not show ' + thing"))))
    expect("the notice keying Sign in on /session/ fails", bool(shared_problems(u.replace(
        "var _isAccess = (id === 'wh-access-denied-notice');", "var _isAccess = /session|/.test(String(msg||''));"))))
    expect("an admin check answering 'no' on error fails", bool(shared_problems(u.replace(
        "    if (r1.error) return 'unreachable';", "    if (r1.error) return 'no';"))))
    # SL L4 reshaped the function to build its sentence, log it, then return it - the mutant follows the online branch
    expect("an offline-only admin sentence fails", bool(shared_problems(u.replace(
        "    : w + ' could not check your access just now, so it stays closed. Reload the page to try again.';",
        "    : \"You're offline.\";"))))
    mut = dict(pages); mut["hive.html"] = mut["hive.html"].replace("const _rdFailed = !row && window._readinessErr === true;", "const _rdFailed = false;")
    expect("hive's readiness fix reverted fails", any("hive.html" in b for b in page_problems(mut)))
    mut = dict(pages); mut["shift-brain.html"] = mut["shift-brain.html"].replace("empty.style.display = _sbReadFailed ? 'none' : 'block';", "empty.style.display = 'block';")
    expect("shift-brain's Generate-now-on-failure fails", any("shift-brain.html" in b for b in page_problems(mut)))
    mut = dict(pages); mut["audit-log.html"] = mut["audit-log.html"] + "<script>const x = 'WorkHive did not answer';</script>"
    expect("a new hard-coded no-answer sentence fails the ratchet", bool(ratchet_problems(no_answer_counts(mut))))
    mut = dict(pages); mut["index.html"] = mut["index.html"] + "<script>/* WorkHive did not answer */</script>"
    expect("the phrase in a comment does not count", not ratchet_problems(no_answer_counts(mut)))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
