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
  4. WALK     a script that WALKS a directory it names (iterdir / rglob / os.walk / os.listdir / scandir / glob) is
              reached by every file under that directory. The directory is a quoted path with no extension
              ("supabase/functions") or a Path chain (ROOT / "supabase" / "functions"), and only counts when some
              tracked file lives under it. A pattern given to rglob() matches at ANY depth, so rglob("*.sql") is read
              as **/*.sql (rglob("*") with no named directory is left out - it walks whatever its receiver is).
              Added 2026-11-05 (M7 release): tools/stamp_functions.py reads every function through
              ROOT / "supabase" / "functions" + iterdir/rglob, named no file, and so was never re-run after two
              edge-function edits - the release deployed both with the stamps of their previous code.

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
WALK_RE = re.compile(r"\.rglob\(|\.iterdir\(|os\.walk\(|os\.listdir\(|os\.scandir\(|\.glob\(|glob\.glob\(|glob\.iglob\(")
DIR_LIT_RE = re.compile(r"""["']([A-Za-z0-9_@\-][A-Za-z0-9_@./\-]*)/?["']""")
CHAIN_RE = re.compile(r"""[A-Za-z_][\w.]*\s*/\s*["']([A-Za-z0-9_@.\-]+)["']((?:\s*/\s*["'][A-Za-z0-9_@.\-]+["'])*)""")
SEG_RE = re.compile(r"""["']([A-Za-z0-9_@.\-]+)["']""")
RGLOB_RE = re.compile(r"""\.rglob\(\s*["']([^"']+)["']""")
PATH_CALL_RE = re.compile(r"""Path\(\s*["']([A-Za-z0-9_@\-][A-Za-z0-9_@./\-]*)["']\s*\)""")
JOIN_RE = re.compile(r"""os\.path\.join\(\s*(?:[\w.]+\s*,\s*)?((?:["'][A-Za-z0-9_@.\-]+["']\s*,?\s*)+)\)""")
WALK_AFTER_RE = re.compile(r"""\s*\)?\s*\.(rglob|glob|iterdir)\(\s*(?:["']([^"']*)["'])?""")
WALK_BEFORE_RE = re.compile(r"""os\.(walk|listdir|scandir)\(\s*(?:str\(\s*)?$""")
ASSIGN_RE = re.compile(r"""^\s*([A-Za-z_]\w*)\s*(?::\s*[\w\[\], ]+)?=\s*$""")
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


def _dir_exprs(src: str):
    """(start, end, dir) for every expression that names a directory: a Path chain (ROOT / "a" / "b"), Path("a/b"),
    os.path.join(ROOT, "a", "b"), or a bare quoted "a/b" with no extension."""
    for m in CHAIN_RE.finditer(src):
        yield m.start(), m.end(), "/".join([m.group(1)] + SEG_RE.findall(m.group(2)))
    for m in PATH_CALL_RE.finditer(src):
        yield m.start(), m.end(), norm(m.group(1)).rstrip("/")
    for m in JOIN_RE.finditer(src):
        yield m.start(), m.end(), "/".join(SEG_RE.findall(m.group(1)))
    for m in DIR_LIT_RE.finditer(src):
        d = norm(m.group(1)).rstrip("/")
        if "/" in d and "." not in os.path.basename(d):
            yield m.start(), m.end(), d


def _walk_pattern(d: str, verb: str, pat: str | None) -> str:
    """The files one walk of directory d can read, as a glob: glob(p) -> d/p, rglob(p) -> d/**/p, a listing -> d/*,
    os.walk or a pattern the script computes -> d/** (everything under it)."""
    if verb == "glob" and pat:
        return d + "/" + pat.lstrip("/")
    if verb == "rglob" and pat:
        return d + "/**/" + pat.lstrip("/")
    if verb in ("iterdir", "listdir", "scandir"):
        return d + "/**"   # a listing is followed by reading what is inside (stamp_functions: iterdir -> rglob)
    return d + "/**"


def walked_patterns(src: str, tracked_dirs: set[str]) -> set[str]:
    """What a script reaches by WALKING a directory (rule 4), as globs. Naming a directory is not walking it -
    `sys.path.insert(0, str(ROOT / "tools"))` names tools/ in 37 gates that never list it - so the named directory must
    itself be the thing walked: called directly (Path("a").glob("*.sql"), (ROOT / "a").rglob(, os.walk("a")), or
    assigned to a name that is then walked (FN = ROOT / "supabase" / "functions" ... FN.iterdir()). A walk with a
    literal pattern reaches only that pattern ((ROOT / "tools").glob("validate_*.py") never reaches a .mjs). It counts
    only when a tracked file lives under the directory."""
    if not WALK_RE.search(src):
        return set()
    out = set()
    for s, e, d in _dir_exprs(src):
        if d not in tracked_dirs:
            continue
        m = WALK_AFTER_RE.match(src, e)
        if m:
            out.add(_walk_pattern(d, m.group(1), m.group(2)))
            continue
        b = WALK_BEFORE_RE.search(src[max(0, s - 40):s])
        if b:
            out.add(_walk_pattern(d, b.group(1), None))
            continue
        line_start = src.rfind("\n", 0, s) + 1
        assigned = ASSIGN_RE.search(src[line_start:s])
        if assigned:
            name = re.escape(assigned.group(1))
            for u in re.finditer(r"""\b%s\s*\.(rglob|glob|iterdir)\(\s*(?:["']([^"']*)["'])?""" % name, src):
                out.add(_walk_pattern(d, u.group(1), u.group(2)))
            for u in re.finditer(r"os\.(walk|listdir|scandir)\(\s*%s\b" % name, src):
                out.add(_walk_pattern(d, u.group(1), None))
    return out


def rglob_patterns(src: str) -> list[str]:
    """rglob(pattern) matches at any depth - read as **/pattern; rglob("*") names no files, so it is left out."""
    return ["**/" + p.lstrip("/") for p in RGLOB_RE.findall(src) if p.strip("*/") ]


def tracked_dirs_of(tracked: Iterable[str]) -> set[str]:
    out = set()
    for t in tracked:
        parts = norm(t).split("/")[:-1]
        for i in range(1, len(parts) + 1):
            out.add("/".join(parts[:i]))
    return out


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
    tdirs = tracked_dirs_of(tracked)
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
        literals = path_literals(src) + rglob_patterns(src)
        if any(literal_reaches(c, lit, ambiguous) for c in files for lit in literals):
            affected.append(v["id"])
        elif served and ROSTER_RE.search(src):
            affected.append(v["id"])
        else:
            walked = [glob_to_re(p) for p in walked_patterns(src, tdirs)]
            if walked and any(w.match(c) for c in files for w in walked):
                affected.append(v["id"])
    return list(dict.fromkeys(affected))
