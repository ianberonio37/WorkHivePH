"""validate_in_list_chunked.py - SL LB3 (2026-10-21): a lookup by many keys reaches the database in pieces the gateway
accepts.

`.in(column, keys)` carries every key in the URL. Past ~8 KB the gateway answers 414 URI Too Long - measured on the
local gateway: 200 worker names made a 4.4 KB URL (200), 400 an 8.7 KB one (414); a UUID costs ~39 bytes, so ~200 ids
reach it. The pages build those key lists from what they listed - the posts on screen, a hive's assets, its members,
its projects - so a list that grows to a few hundred rows sends a lookup the gateway refuses, and a page that swallows
the error shows the lookup as empty. Found walking LB3 with a thousand rows:
  - pm-scheduler put every asset id in its scope and completion reads: a plant of a few hundred assets read NO PM work;
  - project-manager's rollups: every project card read 0% with 0 items;
  - loadWorkerTiers (utils.js) and hive's roster: every avatar showed the lowest tier;
  - community's reply counts and reactions over a thousand posts on screen.

Every `.in(<column>, <list>)` in a served page or shared script must be one of:
  1. a LITERAL list (`['open', 'done']`) or a CONSTANT one (`SVC_OPEN`, `A.concat(B)` of constants);
  2. asked through utils.js whInChunks - the list is the piece its builder receives:
       whInChunks(ids, (part) => db.from('t').select('a').in('id', part))
  3. chunked by hand - the list is sliced (`keys.slice(j, j + 100)`);
  4. marked bounded where it stands - `in-list-bounded: <why>` on its line or the two above it (one person's own
     memberships, one asset's links, a page capped at 60).
The helper itself is held too: tools/test_wh_in_chunks.mjs (18 cases) runs against utils.js.

SELF-TEST (--self-test): the helper broken three ways (no chunking, no de-duplication, an error swallowed) and three
pages put back the way they were (pm-scheduler's asset ids, project-manager's rollup, an annotation removed) must each
FAIL; the clean run is green.
    python tools/validate_in_list_chunked.py [--self-test]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_CALL = re.compile(r"\.in\(\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1\s*,")
LITERAL_LIST = re.compile(r"""^\[\s*(?:(?:'[^']*'|"[^"]*"|-?\d+(?:\.\d+)?|true|false)\s*,?\s*)*\]$""")
CONSTANT_LIST = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.concat\(\s*[A-Z][A-Z0-9_]*\s*\))*$")
BOUNDED = re.compile(r"in-list-bounded:\s*\S.{6,}")
HELPER_PARAM = re.compile(r"whInChunks\(")
# no ^: Pattern.match(src, pos) anchors at pos, and ^ would only ever match the start of the file
ARROW_PARAM = re.compile(r"\s*(?:async\s*)?(?:\(\s*([A-Za-z_$][\w$]*)\s*\)|([A-Za-z_$][\w$]*))\s*=>")


def files() -> dict[str, str]:
    out = {}
    for p in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        if p.name.endswith(".min.js"):
            continue
        out[p.name] = p.read_text(encoding="utf-8", errors="replace")
    return out


def _arg_end(src: str, i: int) -> int:
    """From index i (just inside a call's parentheses, at an argument's start), the index of the comma or closing paren
    that ends this argument - nested brackets and strings skipped."""
    depth, q = 0, None
    while i < len(src):
        c = src[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif c == "," and depth == 0:
            return i
        i += 1
    return i


def _inside_helper(src: str, at: int, arg: str) -> bool:
    """Is the .in() at `at` inside a whInChunks(keys, (part) => ...) call whose builder receives `arg`?"""
    lo = max(0, at - 2500)
    for m in reversed(list(HELPER_PARAM.finditer(src, lo, at))):
        k_end = _arg_end(src, m.end())          # the keys argument
        if k_end >= at or src[k_end] != ",":
            continue
        b = ARROW_PARAM.match(src, k_end + 1)
        if not b:
            continue
        param = b.group(1) or b.group(2)
        # the builder must still be open at the .in(): its argument has not ended before it
        if _arg_end(src, b.end()) < at:
            continue
        return param == arg
    return False


def check_file(name: str, src: str) -> list[str]:
    issues = []
    for m in IN_CALL.finditer(src):
        a0 = m.end()
        a1 = _arg_end(src, a0)
        arg = src[a0:a1].strip()
        if LITERAL_LIST.match(arg) or CONSTANT_LIST.match(arg):
            continue
        if ".slice(" in arg:
            continue
        line_no = src.count("\n", 0, m.start()) + 1
        lines = src.split("\n")
        near = "\n".join(lines[max(0, line_no - 3):line_no])
        if BOUNDED.search(near):
            continue
        if _inside_helper(src, m.start(), arg):
            continue
        issues.append(f"{name}:{line_no}: .in('{m.group(2)}', {arg[:60]}) carries a list a caller can grow in one URL - "
                      "ask it through whInChunks, or mark it 'in-list-bounded: <why>'")
    return issues


def check_helper(utils_src: str) -> list[str]:
    tmp = ROOT / ".tmp" / "in_chunks_utils_under_test.js"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(utils_src, encoding="utf-8")
    try:
        r = subprocess.run(["node", str(ROOT / "tools" / "test_wh_in_chunks.mjs"), str(tmp)], capture_output=True,
                           text=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        return [f"H1 could not run tools/test_wh_in_chunks.mjs: {e}"]
    if r.returncode != 0 or "PASS" not in r.stdout:
        return ["H1 whInChunks: " + " | ".join((r.stdout or r.stderr).strip().splitlines()[:4])]
    return []


def check(overrides: dict[str, str] | None = None) -> list[str]:
    fs = files()
    if overrides:
        fs.update(overrides)
    issues = check_helper(fs.get("utils.js", ""))
    for name, src in fs.items():
        issues += ["P1 " + i for i in check_file(name, src)]
    return issues


def self_test() -> list[str]:
    fails = []
    base = check()
    if base:
        fails.append(f"the clean run is not green: {base[:2]}")
    utils = (ROOT / "utils.js").read_text(encoding="utf-8")
    pm = (ROOT / "pm-scheduler.html").read_text(encoding="utf-8")
    pj = (ROOT / "project-manager.html").read_text(encoding="utf-8")
    ix = (ROOT / "index.html").read_text(encoding="utf-8")
    mutants = [
        ("the helper sends every key in one request",
         {"utils.js": utils.replace("var size = Math.max(1, opts.size || 100);", "var size = 1e9;", 1)}, "H1"),
        ("the helper asks a repeated key twice",
         {"utils.js": utils.replace("var list = Array.from(new Set((keys || []).filter(",
                                    "var list = Array.from(((keys || []).filter(", 1)}, "H1"),
        ("the helper swallows a piece's error",
         {"utils.js": utils.replace("if (r && r.error && !error) error = r.error;", "", 1)}, "H1"),
        ("pm-scheduler asks every asset id in one URL again",
         {"pm-scheduler.html": pm.replace("whInChunks(assetIds, (part) => _homes(db.from('pm_completions').select('*').in('asset_id', part)",
                                          "whInChunks(assetIds, (part) => _homes(db.from('pm_completions').select('*').in('asset_id', assetIds)", 1)}, "P1"),
        ("project-manager's rollup outside the helper",
         {"project-manager.html": pj.replace("const { data: nat } = await whInChunks(ids, (part) => db.from('v_project_truth')\n      .select('project_id, maintenance_nature').in('project_id', part).limit(500));",
                                             "const { data: nat } = await db.from('v_project_truth')\n      .select('project_id, maintenance_nature').in('project_id', ids).limit(500);", 1)}, "P1"),
        ("a bounded lookup with its reason removed",
         {"index.html": ix.replace("   // in-list-bounded: one person's own hive memberships, each hive once (a person belongs to a few hives)", "", 1)}, "P1"),
    ]
    for name, over, want in mutants:
        if all(over[k] == (ROOT / k).read_text(encoding="utf-8") for k in over):
            fails.append(f"mutant '{name}' did not apply - its anchor text is gone")
            continue
        got = check(over)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (6 mutants caught; the clean run is green)" if not fails
              else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues = check()
    print("In-list lookups chunked (SL LB3): no lookup carries a list a caller can grow in one URL")
    for i in issues[:60]:
        print("  [FAIL] " + i)
    n = sum(len(IN_CALL.findall(s)) for s in files().values())
    print(f"  PASS - {n} .in() lookups: each a fixed list, asked through whInChunks, sliced, or bounded with its reason; "
          "whInChunks holds its 18 cases" if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
