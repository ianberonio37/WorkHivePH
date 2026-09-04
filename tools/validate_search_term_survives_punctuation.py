#!/usr/bin/env python3
"""search-term-survives-punctuation - T99: a comma in a search box must not 400 the read.

MEASURED against the live REST endpoint (2026-08-26): `or=(machine.ilike.*bearing, spherical*,...)`
returns HTTP 400, "failed to parse logic tree". PostgREST's or=(a,b) grammar splits on top-level
commas, so an unquoted comma inside a value ends the condition early and the whole filter is
rejected. Parentheses do the same.

★THE TERM THAT BREAKS IT IS THE ORDINARY ONE. "Bearing, spherical roller, 22320 E1 XL C3, SKF" is
how a real part is named - it is this platform's OWN example in the longest-truncates gate - and
typing it into the logbook, community or global search produced a 400 that the page renders as a
FAILED READ. A legitimate search looked like an outage, which is worse than no results: the worker
concludes the system is down and stops looking.

★TWO DIFFERENT JOBS, AND ONLY ONE WAS BEING DONE. Escaping % and _ stops a wildcard changing WHICH
rows match; removing , ( ) and the backslash stops the filter failing to parse AT ALL. Four sites did the first and
not the second. marketplace.html was the exception - it strips the delimiters - which is why the
same phrase worked there and nowhere else, and why nobody had noticed.

★DELIMITERS ARE REMOVED, NOT ESCAPED, because PostgREST offers no escape for them inside an unquoted
value; a space preserves word boundaries so "Bearing, spherical" still matches "Bearing spherical".
Verified after the fix: the same read returns 200 with an empty array - an honest no-match instead
of an error.

*THE BUG IS SPECIFIC TO THE .or() STRING FORM, measured both ways so nobody over-applies the rule:
a direct .ilike("machine", "%bearing, spherical%") passes the value as its own argument and returns
HTTP 200 with a comma in it, because there is no condition list to split. Only or=(a,b) concatenates
conditions into ONE string, and only there does a comma end a condition early. asset-hub and the
search overlay both use the direct form for some reads - those are fine and must not be "fixed".

Re-drive: python tools/validate_search_term_survives_punctuation.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("node_modules", "_fixtures", ".tmp", "test-data-seeder", "tools", ".git")


def main() -> int:
    failures = []

    # 1. the central helper does BOTH jobs
    utils = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    m = re.search(r"function whSafeSearchTerm\([^)]*\)\s*\{(.*?)\n\}", utils, re.S)
    if not m:
        print("FAIL search-term-survives-punctuation - whSafeSearchTerm is gone from utils.js; every "
              "search box that feeds a PostgREST .or() depends on it")
        return 1
    body = m.group(1)
    if not re.search(r"\[,\(\)\\\]|,\(\)", body):
        failures.append("whSafeSearchTerm no longer removes the PostgREST delimiters , ( ) and the "
                        "backslash - a "
                        "comma in the phrase ends the or() condition early and the read 400s")
    if not (re.search(r"%", body) and re.search(r"_", body)):
        failures.append("whSafeSearchTerm no longer escapes the LIKE wildcards % and _ - a typed % "
                        "silently changes which rows match")

    # 2. no page interpolates a raw term into an .or() ilike
    pat = re.compile(r"\.or\(\s*[`'\"][^`'\"]*ilike[^`'\"]*[`'\"]", re.S)
    for p in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        if set(p.relative_to(ROOT).parts[:-1]) & set(SKIP):
            continue
        src = io.open(p, encoding="utf-8", errors="replace").read()
        for hit in pat.finditer(src):
            frag = hit.group(0)
            names = set(re.findall(r"\$\{\s*(\w+)", frag)) | set(re.findall(r"['\"]\s*\+\s*(\w+)", frag))
            for n in names:
                # the variable must be produced by the helper, or by a local strip of the delimiters
                decl = re.search(rf"(?:const|let|var)\s+{re.escape(n)}\s*=(.{{0,300}})", src, re.S)
                d = decl.group(1) if decl else ""
                # for-of terms (`for (const _term of safeSV.split(...))`, the T15 term-AND loop)
                # have no `=` declaration — resolve ONE level to the iterated source and judge
                # ITS declaration instead. Found 2026-09-03: the loop's terms come from a
                # whSafeSearchTerm-produced variable and were flagged as raw.
                if not d:
                    fo = re.search(rf"for\s*\(\s*(?:const|let|var)\s+{re.escape(n)}\s+of\s+(\w+)", src)
                    if fo:
                        srcdecl = re.search(rf"(?:const|let|var)\s+{re.escape(fo.group(1))}\s*=(.{{0,300}})", src, re.S)
                        d = srcdecl.group(1) if srcdecl else ""
                if "whSafeSearchTerm" in d or re.search(r"\[,\(\)", d) or re.search(r",\(\)", d):
                    continue
                line = src[:hit.start()].count("\n") + 1
                failures.append(f"{p.name}:{line}: interpolates `{n}` into an .or() ilike without "
                                f"removing the PostgREST delimiters - a comma in the phrase returns "
                                f"HTTP 400 and the page shows a failed read for a legitimate search")

    # 3. the EDGE functions, where the same bug is worse because it is SILENT. supabase-js
    #    RETURNS {data:null,error} rather than throwing, so a rejected filter destructured as
    #    `const { data } = await q` never reaches a catch - it becomes an ordinary empty result.
    #    agentic-rag-loop's lane B takes a natural-language QUESTION, where commas are the common
    #    case, and a 400 there just means the AI answers with less grounding and nobody is told.
    fns = ROOT / "supabase" / "functions"
    if fns.exists():
        for f in sorted(fns.rglob("index.ts")):
            body = io.open(f, encoding="utf-8", errors="replace").read()
            rel = f"supabase/functions/{f.parent.name}"
            for hit in re.finditer(r"\.or\(\s*`[^`]*ilike[^`]*`", body):
                frag = hit.group(0)
                for n in set(re.findall(r"\$\{\s*(\w+)", frag)):
                    decl = re.search(rf"const\s+{re.escape(n)}\s*=(.{{0,400}})", body, re.S)
                    d = decl.group(1) if decl else ""
                    if re.search(r"\[,\(\)", d):
                        continue
                    failures.append(f"{rel}: interpolates `{n}` into an .or() ilike without removing "
                                    f"the PostgREST delimiters - a comma returns 400, and because the "
                                    f"error is usually destructured away it degrades to an empty "
                                    f"result nobody sees")
            if re.search(r"\.or\(\s*`[^`]*ilike", body) and re.search(
                    r"const\s*\{\s*data:\s*\w+\s*\}\s*=\s*await\s+q\s*;", body):
                failures.append(f"{rel}: reads an .or() result as `const {{ data }} = await q` - "
                                f"supabase-js returns {{data:null,error}} instead of throwing, so a "
                                f"rejected filter becomes a silent empty result and the catch never "
                                f"fires")

    if failures:
        print("FAIL search-term-survives-punctuation:")
        for f in sorted(set(failures)):
            print("    - " + f)
        return 1

    print("  whSafeSearchTerm strips , ( ) and the backslash, escapes % and _ · no raw term reaches an .or() ilike")
    print("PASS search-term-survives-punctuation - a part named \"Bearing, spherical roller\" can be "
          "searched for without breaking the read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
