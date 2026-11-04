"""rerun_selector - which gates does a changed source file reach? (the --rerun-failed selection, 2026-11-04)

`run_platform_checks --rerun-failed` re-runs what failed on the last full board plus every gate the fix TOUCHED. A gate
is tied to a changed file when its script names that file. The first rule matched the file's BASENAME inside quotes.
Measured on a family edit (learn/<slug>/index.html, 2026-11-04) it reached 119 of the 152 gates that read the
families and MISSED 33 (the ones that reach pages through the page roster or a glob, e.g. page-roster, plain-language,
page-craft), while over-selecting every gate that quotes the landing page, because every family page is also called
index.html. Three rules now, each a measured path:

  1. LITERAL  a quoted path that resolves to the changed file: the exact path, a directory-qualified suffix
              ("functions/login/index.ts"), or a bare basename that is UNIQUE among tracked files. index.html,
              index.html.md and index.ts are shared by hundreds of files, so a bare mention of one of them names
              the ROOT file of that name only.
  2. GLOB     a quoted pattern (learn/*/index.html, */index.html, *.html, learn/**/*.html) that matches the changed
              path with pathlib.glob semantics: `*` never crosses a directory, `**` does.
  3. ROSTER   a script that reads the page roster (served_page_set / page_roster.json / sitemap.xml) is reached by
              every served page.

The runner and the release gate are every gate's host, not something a gate reads: an edit to them selects nothing by
itself. tools/prove_rerun_selector.py pins every rule with synthetic scripts.
"""
from __future__ import annotations

import collections
import os
import re
import subprocess
from typing import Callable, Iterable

HOSTS = ("run_platform_checks.py", "release_gate.py")
SOURCE_EXT = ("html", "htm", "js", "mjs", "cjs", "css", "py", "json", "md", "ts", "tsx", "sql", "toml", "yml", "yaml",
              "txt", "xml", "svg", "png", "webp", "ico")
PATH_RE = re.compile(r"""["']([A-Za-z0-9_@./*{}\[\]\-]+\.(?:%s))["']""" % "|".join(SOURCE_EXT))
ROSTER_RE = re.compile(r"served_page_set|served_pages\s*\(|page_roster|PAGE_ROSTER|sitemap\.xml")
GLOB_CHARS = ("*", "?", "[")
NOT_SERVED = (".tmp/", "node_modules/", "tests/", "test-data-seeder/", "seo_assets/", "remotion_scenes/", ".claude/",
              "substrate/", "supabase/")
NOT_SERVED_NAME = ("-test.html", "backup", "offline-fallback", "symbol-gallery")


def norm(p: str) -> str:
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def glob_to_re(pat: str) -> re.Pattern:
    """pathlib.Path.glob semantics on a posix relative path: * stays inside one directory, ** crosses them."""
    out, i = [], 0
    while i < len(pat):
        ch = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3
        elif pat.startswith("**", i):
            out.append(".*"); i += 2
        elif ch == "*":
            out.append("[^/]*"); i += 1
        elif ch == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(ch)); i += 1
    return re.compile("^" + "".join(out) + "$")


def path_literals(src: str) -> list[str]:
    return sorted({norm(m) for m in PATH_RE.findall(src)})


def ambiguous_basenames(tracked: Iterable[str]) -> set[str]:
    counts = collections.Counter(os.path.basename(norm(t)) for t in tracked)
    return {name for name, n in counts.items() if n > 1}


def is_served_page(path: str) -> bool:
    p = norm(path)
    if not p.endswith(".html"):
        return False
    if any(p.startswith(d) for d in NOT_SERVED):
        return False
    return not any(s in p for s in NOT_SERVED_NAME)


def literal_reaches(changed: str, literal: str, ambiguous: set[str]) -> bool:
    c, p = norm(changed), norm(literal)
    if any(ch in p for ch in GLOB_CHARS):
        return bool(glob_to_re(p).match(c))
    if "/" in p:
        return c == p or c.endswith("/" + p)
    # a bare basename: the file itself at the root, or a name no other tracked file shares
    if c == p:
        return True
    return os.path.basename(c) == p and p not in ambiguous


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout
    except OSError:
        return []
    return [t for t in out.split("\0") if t]


def _read(script: str) -> str | None:
    try:
        with open(script, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def gates_for_changes(validators: list[dict], changed: Iterable[str], tracked: Iterable[str] = (),
                      read_script: Callable[[str], str | None] = _read) -> list[str]:
    """Ids of the gates reached by the changed files, in registry order, each once."""
    files = [norm(c) for c in changed if os.path.basename(norm(c)) not in HOSTS]
    if not files:
        return []
    ambiguous = ambiguous_basenames(tracked)
    served = [c for c in files if is_served_page(c)]
    affected: list[str] = []
    for v in validators:
        script = norm(v.get("script") or "")
        if not script:
            continue
        if script in files:
            affected.append(v["id"])
            continue
        src = read_script(script)
        if src is None:
            continue
        literals = path_literals(src)
        if any(literal_reaches(c, lit, ambiguous) for c in files for lit in literals):
            affected.append(v["id"])
        elif served and ROSTER_RE.search(src):
            affected.append(v["id"])
    return list(dict.fromkeys(affected))
