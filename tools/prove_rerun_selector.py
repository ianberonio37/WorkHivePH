#!/usr/bin/env python3
"""prove_rerun_selector - the --rerun-failed gate selection, pinned (2026-11-04).

Synthetic gate scripts, in memory, one per way a gate names a page; a set of changed files; the ids the selector must
return and must not. The cases are the measured failures of the basename rule (tools/rerun_selector.py): a family page
edit must reach glob and roster readers and must NOT reach every gate that quotes the landing page; an edge function's
index.ts must not reach every gate that quotes some other index.ts.

  python tools/prove_rerun_selector.py        # exit 1 on the first wrong selection
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.rerun_selector import gates_for_changes, glob_to_re, literal_reaches  # noqa: E402

SCRIPTS = {
    "tools/g_bare.py":    'for p in ("index.html", "nav-hub.js"): read(p)',
    "tools/g_glob.py":    'for p in ROOT.glob("learn/*/index.html"): read(p)',
    "tools/g_star.py":    'for p in ROOT.glob("*/index.html"): read(p)',
    "tools/g_dstar.py":   'PATTERNS = ("learn/**/*.html", "about/**/*.html")',
    "tools/g_roster.py":  'from served_page_set import served_pages\nfor p in served_pages(): read(p)',
    "tools/g_ts_bare.py": 'src = open("index.ts").read()',
    "tools/g_ts_full.py": 'src = open("supabase/functions/login/index.ts").read()',
    "tools/g_ts_sfx.py":  'src = open("functions/login/index.ts").read()',
    "tools/g_css.py":     'css = open("components.css").read()',
    "tools/g_self.py":    'pass',
}
VALIDATORS = [{"id": name[6:-3], "script": name} for name in SCRIPTS]
TRACKED = ["index.html", "learn/x/index.html", "learn/y/index.html", "tools/x/index.html", "about/index.html",
           "supabase/functions/login/index.ts", "supabase/functions/ai-gateway/index.ts", "nav-hub.js",
           "components.css", "tools/g_self.py"]
read = SCRIPTS.get

CASES = [
    # changed files                          must reach                                         must not reach
    (["learn/x/index.html"],                 {"g_glob", "g_dstar", "g_roster"},                  {"g_bare", "g_star", "g_ts_bare", "g_css"}),
    (["tools/x/index.html"],                 {"g_roster"},                                       {"g_bare", "g_glob", "g_dstar"}),
    (["about/index.html"],                   {"g_star", "g_dstar", "g_roster"},                  {"g_bare", "g_glob"}),
    (["index.html"],                         {"g_bare", "g_roster"},                             {"g_glob", "g_star", "g_dstar"}),
    (["nav-hub.js"],                         {"g_bare"},                                         {"g_roster", "g_glob"}),
    (["supabase/functions/login/index.ts"],  {"g_ts_full", "g_ts_sfx"},                          {"g_ts_bare", "g_roster", "g_bare"}),
    (["components.css"],                     {"g_css"},                                          {"g_roster", "g_bare"}),
    (["tools/g_self.py"],                    {"g_self"},                                         {"g_bare"}),
    (["run_platform_checks.py"],             set(),                                              set(SCRIPTS and [n[6:-3] for n in SCRIPTS])),
]


def main() -> int:
    bad = 0
    # the glob translation itself
    for pat, yes, no in [("learn/*/index.html", "learn/x/index.html", "learn/x/y/index.html"),
                         ("*/index.html", "about/index.html", "learn/x/index.html"),
                         ("*.html", "index.html", "learn/x/index.html"),
                         ("learn/**/*.html", "learn/x/index.html", "tools/x/index.html")]:
        r = glob_to_re(pat)
        if not r.match(yes) or r.match(no):
            print(f"FAIL glob {pat!r}: should match {yes!r} and not {no!r}"); bad += 1
    if literal_reaches("learn/x/index.html", "index.html", {"index.html"}):
        print("FAIL a bare 'index.html' must not reach a family page"); bad += 1
    if not literal_reaches("index.html", "index.html", {"index.html"}):
        print("FAIL a bare 'index.html' must reach the root page"); bad += 1
    for changed, must, must_not in CASES:
        got = set(gates_for_changes(VALIDATORS, changed, tracked=TRACKED, read_script=read))
        missing, extra = must - got, must_not & got
        if missing or extra:
            print(f"FAIL {changed}: missing={sorted(missing)} over-selected={sorted(extra)} got={sorted(got)}"); bad += 1
        else:
            print(f"  ok  {changed} -> {sorted(got)}")
    print(("PASS" if not bad else "FAIL") + f" rerun-selector - {len(CASES)} change sets, {bad} wrong")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
