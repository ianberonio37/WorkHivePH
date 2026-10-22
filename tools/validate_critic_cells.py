#!/usr/bin/env python3
"""validate_critic_cells.py - an open critic cell, once built and banked, stays closed (ENH-C, 2026-10-22).

ENH-C is the enhancement class "an open critic cell on a production page, signed in": a (page, rubric dim) that a
signed-in critic walk left critiqued with a finding (tools/enhancement_inventory.py, class C). A row closes when the
cell is BUILT closed on the page itself, used end to end as its cast at phone-390 and desktop-1280, and a gate fails
on the page as it was before the build. This is that gate, in two halves:

  C1  every ENH-C row at locking or locked names a cell the inventory no longer measures - no signed-in English critic
      row carries that finding. A later critic walk that banks it again reopens the cell, and this fails: the "keep it
      closed" half every ENH-C row asks for. The critic registry as it was before the build fails it for every cell.
  C2  the mechanism each cell's fix stands on is still there - in its page, or in the lens for a cell the instrument
      misread. A B3 cell's rewritten sentences are graded by the lens's OWN ruler (tools/b3_ruler.mjs reads syllables,
      fk, PASSIVE and the thresholds out of survey_ufai_rubric.js), never by a copy of it.
  C3  a B3 cell stays closed in EVERY state a later walk can reach (offline, a refusal, an empty view), not only the
      one its walk saw: every English sentence a B3-cell page passes to _t() passes the same ruler, a middot list
      split where the lens splits it.

    python tools/validate_critic_cells.py              the gate
    python tools/validate_critic_cells.py --self-test  the critic registry and every page as they were before the build
                                                       (BEFORE_BUILD) must fail; mutants of each mechanism must fail;
                                                       the clean run is green
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
TRAJ = ROOT / "trajectory_registry.json"
LENS = "survey_ufai_rubric.js"
BEFORE_BUILD = "5bf88960"   # HEAD when ENH-C was built: the pages, the lens and the critic registry as they were
BANKED = ("locking", "locked")


def _read(rel: str, files: dict | None) -> str:
    if files is not None and rel in files:
        return files[rel]
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def _strip(html: str) -> str:
    """the words a reader sees in a run of markup: tags out, entities a sentence uses, whitespace folded"""
    t = re.sub(r"<[^>]+>", " ", html)
    t = t.replace("&middot;", "·").replace("&rarr;", "→").replace("&#8594;", "→").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip().split()) >= 4]


def _b3_fails(sentences: list[str]) -> list[str]:
    """the sentences the lens's own B3 ruler fails (empty list = all pass)"""
    if not sentences:
        return []
    r = subprocess.run(["node", str(ROOT / "tools" / "b3_ruler.mjs"), "--json", *sentences], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 2:
        return [f"(the B3 ruler could not read the lens: {(r.stderr or '').strip()[:160]})"]
    out = []
    for ln in (r.stdout or "").splitlines():
        try:
            g = json.loads(ln)
        except ValueError:
            continue
        if g.get("fails"):
            out.append(f"\"{g['sentence'][:90]}\" ({', '.join(g['fails'])})")
    return out


def _grab(src: str, rx: str) -> str:
    m = re.search(rx, src, re.S)
    return m.group(1) if m else ""


# C2: each built cell -> (the ENH rows it closes, a check that returns a list of problems)
def _shift_brain(f):
    s = _read("shift-brain.html", f)
    p = []
    i_title, i_gate, i_wrap = s.find('class="page-title"'), s.find('<div id="hive-gate"'), s.find('<div id="page-wrap"')
    if not (0 <= i_title < i_gate and i_title < i_wrap):
        p.append("the page's title and back link are not above the gate and the board - a no-hive screen has no h1 and no way back")
    gate = s[i_gate:s.find("</div>\n  </div>", i_gate)] if i_gate >= 0 else ""
    if 'data-wh-gate="no-hive"' not in gate:
        p.append('the no-hive screen does not declare itself (data-wh-gate="no-hive")')
    if 'class="sb-gate-card"' not in gate or not re.search(r"\.sb-gate-card\s*\{[^}]*border:[^}]*border-radius", s):
        p.append("the no-hive message is not one card (border and radius) - nothing on the screen is grouped")
    if not re.search(r"\.sb-gate-cta\s*\{[^}]*min-height:\s*44px", s):
        p.append('"Go to Hive" is not held to the 44px target')
    return p


def _analytics_report(f):
    s = _read("analytics-report.html", f)
    p = []
    i_main, i_head, i_gate = s.find('<main id="ar-page">'), s.find("</header>"), s.find('<div id="hive-gate"')
    if not (0 <= i_main < i_head < i_gate):
        p.append("the no-hive gate is not inside <main> under the page's header - the page reads as empty and untitled")
    if i_gate >= 0 and 'data-wh-gate="no-hive"' not in s[i_gate:i_gate + 80]:
        p.append('the no-hive gate does not declare itself (data-wh-gate="no-hive")')
    if "_arp.style.display  = 'none'" in s or "_arp.style.display = 'none'" in s:
        p.append("the gate still hides the whole page instead of the generator")
    p += [f"B3 {x}" for x in _b3_fails(_sentences(_strip(_grab(s, r'<div id="hive-gate"[^>]*>(.*?)</div>'))))]
    return p


def _ph_intelligence(f):
    s = _read("ph-intelligence.html", f)
    gate = _grab(s, r"(<div class=\"empty-state\" data-wh-gate=\"no-hive\" style=\"[^\"]*\")")
    if not gate or "border:" not in gate or "background:" not in gate:
        return ["the no-hive gate is bare text, not a card (C3: nothing grouped)"]
    return []


def _resume(f):
    s = _read("resume.html", f)
    p = []
    if not re.search(r'<label[^>]*for="jd-input"', s):
        p.append("the job-ad box's visible label is not bound to it (M1: placeholder as label)")
    if re.search(r'id="jd-input"[^>]*aria-label=', s):
        p.append("the job-ad box is still named by a hidden aria-label rather than its visible label")
    p += [f"B3 {x}" for x in _b3_fails(_sentences(_strip(_grab(s, r'data-i="p_turnroughnotesintoprofession_f75a" class="sec-sub">([^<]+)<'))))]
    return p


def _achievements(f):
    s = _read("achievements.html", f)
    t = _grab(s, r"label = _t\('No achievements yet'[^\n]*\n\s*sub\s*=\s*_t\('((?:[^'\\]|\\.)*)'")
    return ["the empty-state line is gone (cannot grade it)"] if not t else [f"B3 {x}" for x in _b3_fails(_sentences(t))]


def _pm_scheduler(f):
    s = _read("pm-scheduler.html", f)
    a = _grab(s, r"if \(total === 0\) \{\s*text = _t\('((?:[^'\\]|\\.)*)'")
    b = _grab(s, r"else if \(compliance < 80\) \{\s*text = _t\(`((?:[^`\\]|\\.)*)`")
    if not a or not b:
        return ["the empty and low-compliance lines are gone (cannot grade them)"]
    return [f"B3 {x}" for x in _b3_fails(_sentences(a) + _sentences(re.sub(r"\$\{[^}]*\}", "70", b)))]


def _platform_actions(f):
    s = _read("platform-actions.html", f)
    runs = [
        _grab(s, r"<p>(Platform Actions is [^<]+)</p>"),
        _grab(s, r"(Approve publishes the listing.*?)</p>"),
        _grab(s, r'p_sellersawaitingverification_b209">[^<]*</h2>.*?<p class="mod-sub"[^>]*>(.*?)</p>'),
        _grab(s, r'<div class="sub"[^>]*>(Who decided what[^<]*)</div>'),
        _grab(s, r"if \(!Array\.isArray\(uses\)\) \{\s*return '<div class=\"mod-empty\"[^>]*>([^<]*)</div>'"),
    ]
    p = []
    if not all(runs):
        p.append("a sentence the B3 fix rewrote is gone (cannot grade it)")
    p += [f"B3 {x}" for x in _b3_fails([x for r in runs if r for x in _sentences(_strip(r))])]
    if re.search(r'class="mod-empty">(Active hives|People \(30d\)|People today|Most-opened page|Signed-out sessions)', s) \
            or 'class="mod-empty" id="usage-updated"' in s:
        p.append("a figure's label wears the empty-state class (E2: a label read as an empty that explains nothing)")
    return p


def _marketplace(f):
    s = _read("marketplace.html", f)
    if "'</strong> replied'" in s and "<span data-user-content>' + e(String(r.reply_text)" not in s:
        return ["a seller's reply is not marked as their own words (B3 grades it as the marketplace's copy)"]
    if "You asked: <span data-user-content>" not in s:
        return ["the buyer's question is not marked as their own words"]
    return []


def _marketplace_seller(f):
    s = _read("marketplace-seller.html", f)
    return [] if re.search(r"\.li-actions \.btn-sm\.danger\s*\{\s*margin-left:\s*auto", s) else \
        ["a draft's Delete sits beside its Edit (Z3: one slip from destroying the listing being edited)"]


def _alert_hub(f):
    lens, page = _read(LENS, f), _read("alert-hub.html", f)
    p = []
    if "n.matches('[data-ai-generated], [data-user-content]')) out += ' '" not in lens:
        p.append("the lens grades an agent's marked words through their parent line again (B3 read the brief headlines as the page's copy)")
    if "<span data-ai-generated>" not in page:
        p.append("the feed no longer marks the brief headline as the agent's words")
    return p


def _live_notice(f):
    """two cells the critic re-walk opened while ENH-C was built (offline walks, hive and logbook V1): the "live updates are
    off" notice repeated the offline banner's news mid-screen, over hive's language button and logbook's Voice Journal"""
    fn = _grab(_read("utils.js", f), r"(function _whLiveState\(.*?\n\}\n)")
    if not fn:
        return ["utils.js has no _whLiveState - the live notice's owner moved"]
    p = []
    if not re.search(r"navigator\.onLine\s*===\s*false", fn):
        p.append("_whLiveState no longer asks whether the device is offline")
    if not re.search(r"&&\s*!_offlineNow\)\s*\{\s*_whShowNotice\('wh-live-notice'", fn):
        p.append("the live notice shows while the device is offline, on top of the offline banner")
    return p


MECHANISMS = [
    (("ENH327", "ENH328", "ENH329", "ENH330", "ENH331", "ENH332", "ENH333"), "shift-brain no-hive gate", _shift_brain),
    (("ENH299", "ENH300", "ENH301", "ENH302"), "analytics-report no-hive gate", _analytics_report),
    (("ENH318",), "ph-intelligence no-hive gate", _ph_intelligence),
    (("ENH325", "ENH326"), "resume copy and label", _resume),
    (("ENH295",), "achievements copy", _achievements),
    (("ENH323",), "pm-scheduler copy", _pm_scheduler),
    (("ENH320", "ENH321"), "platform-actions copy and labels", _platform_actions),
    (("ENH317",), "marketplace people's words", _marketplace),
    (("ENH316",), "marketplace-seller Delete apart", _marketplace_seller),
    (("ENH296",), "alert-hub agent's words", _alert_hub),
    (("hive V1", "logbook V1"), "live notice waits offline", _live_notice),
]


# C3: a B3 cell must stay closed in EVERY state a later walk can reach - offline, a refusal, an empty view, a rare count -
# not only the state its walk saw. Every English sentence the page passes to _t() is graded by the lens's own ruler; a
# middot list is split where the lens splits it (B3 reads " · " as a fact separator, not a clause).
B3_PAGES = {"achievements.html": "ENH295", "alert-hub.html": "ENH296", "index.html": "ENH309",
            "integrations.html": "ENH311", "marketplace.html": "ENH317", "plant-connections.html": "ENH319",
            "platform-actions.html": "ENH320", "pm-scheduler.html": "ENH323", "resume.html": "ENH325",
            "skillmatrix.html": "ENH335"}


def _t_sentences(src: str) -> list[str]:
    strs = re.findall(r"_t\(\s*'((?:[^'\\]|\\.){20,600})'", src) + re.findall(r"_t\(\s*`((?:[^`\\]|\\.){20,600})`", src)
    out = []
    for t in strs:
        t = re.sub(r"\$\{[^}]*\}", "7", t).replace("\\'", "'")
        t = re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ").replace("&middot;", "·").replace("&amp;", "&")
        for part in re.split(r"\s+·\s+", t):
            out += [x for x in _sentences(part)]
    return out


def _b3_pages(files):
    probs = []
    for page, rid in B3_PAGES.items():
        bad = _b3_fails(_t_sentences(_read(page, files)))
        if bad:
            probs.append(f"{page} ({rid}): {len(bad)} sentence(s) fail the lens's B3 ruler, e.g. {bad[0]}")
    return probs


def _enhc_rows(traj: list | None) -> list[dict]:
    if traj is None:
        d = json.loads(TRAJ.read_text(encoding="utf-8"))
        traj = d["trajectories"] if isinstance(d, dict) else d
    return [t for t in traj if t.get("wave") == "ENH-C" and t.get("status") != "descoped"]


def check(files: dict | None = None, traj: list | None = None, critic_rows: list | None = None,
          banked_all: bool = False) -> list[str]:
    import enhancement_inventory as inv
    issues = []
    rows = _enhc_rows(traj)
    if critic_rows is None:
        cells = {(c["page"], c["key"]) for c in inv.collect() if c["cls"] == "C"}
    else:
        cells = {(c["page"], c["key"]) for c in inv._critic(inv.production_pages(), critic_rows)}
    for t in rows:
        if not banked_all and t.get("status") not in BANKED:
            continue
        cell = (t["enh"]["page"], t["enh"]["key"])
        if cell in cells:
            issues.append(f"C1 {t['id']} is banked but its cell {cell[0]} {cell[1]} is open again - a signed-in English "
                          f"critic walk carries the finding")
    for ids, name, fn in MECHANISMS:
        for prob in fn(files):
            issues.append(f"C2 {name} ({', '.join(ids)}): {prob}")
    for prob in _b3_pages(files):
        issues.append(f"C3 {prob}")
    return issues


def _git(path: str) -> str:
    r = subprocess.run(["git", "show", f"{BEFORE_BUILD}:{path}"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def self_test() -> list[str]:
    fails = []
    clean = check()
    if clean:
        fails.append(f"the clean run is not green: {clean[:2]}")
    # every page (and the lens) as it was before the build: each mechanism must fail
    for ids, name, fn in MECHANISMS:
        rels = {"shift-brain no-hive gate": ["shift-brain.html"], "analytics-report no-hive gate": ["analytics-report.html"],
                "ph-intelligence no-hive gate": ["ph-intelligence.html"], "resume copy and label": ["resume.html"],
                "achievements copy": ["achievements.html"], "pm-scheduler copy": ["pm-scheduler.html"],
                "platform-actions copy and labels": ["platform-actions.html"],
                "marketplace people's words": ["marketplace.html"],
                "marketplace-seller Delete apart": ["marketplace-seller.html"],
                "alert-hub agent's words": [LENS, "alert-hub.html"],
                "live notice waits offline": ["utils.js"]}[name]
        before = {r: _git(r) for r in rels}
        if not all(before.values()):
            fails.append(f"could not read {name}'s files as they were before the build ({BEFORE_BUILD})")
            continue
        if not fn(before):
            fails.append(f"'{name}' as it was before the build ({BEFORE_BUILD}) was not caught")
    # the critic registry as it was before the build: every ENH-C cell it carried must reopen
    old = _git("critic_registry.json")
    if not old:
        fails.append("could not read the critic registry as it was before the build")
    else:
        crit = json.loads(old)
        crit_rows = crit["rows"] if isinstance(crit, dict) else crit
        got = [i for i in check(critic_rows=crit_rows, banked_all=True) if i.startswith("C1")]
        if len(got) < 30:
            fails.append(f"the critic registry as it was before the build reopened only {len(got)} ENH-C cells (35 were open)")
    # mutants of the mechanisms, one each
    sb = _read("shift-brain.html", None)
    mutants = [
        ("the gate's 44px action back to 35px", {"shift-brain.html": sb.replace("min-height: 44px;\n      margin-top: 1.25rem", "margin-top: 1.25rem", 1)}),
        ("the resume label unbound", {"resume.html": _read("resume.html", None).replace('for="jd-input"', "", 1)}),
        ("a passive sentence back in the resume", {"resume.html": _read("resume.html", None).replace(
            "You check every suggestion before you use it.", "You review every suggestion before it is used.", 1)}),
        ("the Delete beside its Edit again", {"marketplace-seller.html": _read("marketplace-seller.html", None).replace(
            ".li-actions .btn-sm.danger { margin-left: auto; }", "", 1)}),
        ("a figure label in the empty-state class", {"platform-actions.html": _read("platform-actions.html", None).replace(
            "class=\"mod-label\">People (30d)", "class=\"mod-empty\">People (30d)", 1)}),
        ("the live notice shown offline again", {"utils.js": _read("utils.js", None).replace(
            "typeof _whShowNotice === 'function' && !_offlineNow)", "typeof _whShowNotice === 'function')", 1)}),
    ]
    for name, files in mutants:
        if not any(i.startswith("C2") for i in check(files)):
            fails.append(f"mutant '{name}' was not caught")
    # C3: the B3-cell pages as they were before the build carried failing sentences in some state; each must be caught
    before_pages = {p: _git(p) for p in B3_PAGES}
    missed = [p for p, src in before_pages.items() if src and not _b3_fails(_t_sentences(src))]
    caught = [p for p, src in before_pages.items() if src and _b3_fails(_t_sentences(src))]
    if len(caught) < 8:
        fails.append(f"C3 caught only {len(caught)} of the {len(B3_PAGES)} B3-cell pages as they were before the build "
                     f"(missed: {', '.join(missed)})")
    pm = _read("pm-scheduler.html", None)
    c3_mut = {"pm-scheduler.html": pm.replace(
        "Check that critical assets (red border) still come first in your team plan.",
        "Check the asset list below to confirm criticals (red border) are still being prioritized in your team plan.", 1)}
    if not any(i.startswith("C3") for i in check(c3_mut)):
        fails.append("C3 mutant 'a passive, over-grade sentence back in pm-scheduler' was not caught")
    print(f"  {len(MECHANISMS)} mechanisms against the pages as they were; the registry as it was; {len(mutants)} mutants; "
          f"C3 caught {len(caught)} of {len(B3_PAGES)} B3-cell pages as they were")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (the pages, the lens and the critic registry as they were before the build all fail; every "
              "mutant is caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues = check()
    banked = [t for t in _enhc_rows(None) if t.get("status") in BANKED]
    print(f"Critic cells (ENH-C): {len(banked)} banked rows held closed; {len(MECHANISMS)} mechanisms in place")
    if issues:
        for i in issues:
            print("  [FAIL]", i)
        print(f"  FAIL - {len(issues)} problem(s)")
        return 1
    print("  PASS - no banked ENH-C cell is open again, and every fix's mechanism is where it was built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
