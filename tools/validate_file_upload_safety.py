#!/usr/bin/env python3
"""validate_file_upload_safety.py — P12 upload-safety scanner (CWE-434-residual, 2026-07-17).

CONTEXT (verified 2026-07-17, bug-hunt denominator arc): the platform has NO server-side file
storage (grep: zero `storage.from().upload(`). Files are read CLIENT-SIDE (resume -> AI-extract,
logbook photo -> data-URI) and discarded, so classic unrestricted-upload / path-traversal are
low/N/A. The REAL residual risk on every `<input type="file">` surface is:
  (1) a missing `accept=` type allowlist  -> wrong file types reach the reader/extractor
  (2) a missing `file.size` guard         -> a huge file OOMs FileReader/canvas/the AI extractor (DoS)

This gate asserts BOTH per file-input surface. It is ADVISORY (never blocks a commit) so it surfaces
the gap while the per-page size-cap fixes land, then ratchets: once a surface is guarded it must
stay guarded. Mirrors the `night-crawler-freshness` non-blocking pattern.

Exit code: always 0 (advisory). Prints the per-surface report; a page-level allowlist records the
current unguarded surfaces so a NEWLY-added unguarded file input is visible in the diff.

USAGE
  python tools/validate_file_upload_safety.py            # report
  python tools/validate_file_upload_safety.py --selftest # deterministic self-test (no fs scan)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# pages/scripts that are throwaway / vendored / not shipped surfaces
EXCLUDE = ("node_modules", "remotion_scenes", "video_marketing_app", "tools",
           ".backup.", "logbook.backup")

FILE_INPUT_RE = re.compile(r"<input\b[^>]*\btype\s*=\s*[\"']?file[\"']?[^>]*>", re.I)
ACCEPT_RE = re.compile(r"\baccept\s*=\s*[\"'][^\"']+[\"']", re.I)
# a FILE size guard: `.size` in a byte-magnitude context (1024/MB/1e6/big literal) or an explicit
# file.size / files[i].size / a MAX*SIZE / maxBytes const. The byte-magnitude requirement avoids
# false-"guarded" from Map/Set `.size` comparisons (e.g. realtime channel caps `reg.size >= max`).
SIZE_GUARD_RE = re.compile(
    r"file\.size|files\s*\[\s*\d+\s*\]\.size"
    r"|\.size\b[^;\n]{0,48}(1024|1e6|000000|\bMB\b)"
    r"|\bMAX_?[A-Z_]*(SIZE|BYTES)\b|\bmaxBytes\b", re.I)


def scan_text(html: str) -> dict:
    """Return {surfaces, unguarded:[reasons]} for one file's text."""
    inputs = FILE_INPUT_RE.findall(html)
    if not inputs:
        return {"surfaces": 0, "unguarded": []}
    has_size = bool(SIZE_GUARD_RE.search(html))
    unguarded = []
    for tag in inputs:
        problems = []
        if not ACCEPT_RE.search(tag):
            problems.append("no accept= allowlist")
        if not has_size:
            problems.append("no file.size guard (DoS)")
        if problems:
            unguarded.append("; ".join(problems))
    return {"surfaces": len(inputs), "unguarded": unguarded}


def main() -> int:
    pages = []
    for p in sorted(REPO.glob("*.html")):
        if any(x in p.name for x in EXCLUDE):
            continue
        pages.append(p)
    total_surfaces = 0
    guarded = 0
    gaps = []
    for p in pages:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        r = scan_text(txt)
        if r["surfaces"] == 0:
            continue
        total_surfaces += r["surfaces"]
        if not r["unguarded"]:
            guarded += r["surfaces"]
        else:
            gaps.append((p.name, r["surfaces"], r["unguarded"]))
    print("File-upload safety (P12 · CWE-434-residual · client-side size/type guards)")
    print(f"  file-input surfaces: {total_surfaces}  ·  fully guarded: {guarded}  ·  "
          f"pages with a gap: {len(gaps)}")
    for name, n, probs in gaps:
        print(f"  ⚠ {name} ({n} input(s)): {', '.join(sorted(set(probs)))}")
    if gaps:
        print("  FIX: add a file.size cap (e.g. 10MB) + confirm accept= on each surface; "
              "then this ratchets guarded-only. ADVISORY — never blocks a commit.")
    else:
        print("  ✓ every file-upload surface has an accept= allowlist + a size guard.")
    return 0  # advisory


def selftest() -> int:
    fails = []
    guarded = ('<input type="file" accept="image/*,application/pdf">'
               '<script>if (f.size > 10*1024*1024) return alert("too big");</script>')
    if scan_text(guarded)["unguarded"]:
        fails.append("a surface with accept= + size guard should be clean")
    no_size = '<input type="file" accept="image/*"><script>read(files[0]);</script>'
    r = scan_text(no_size)
    if not r["unguarded"] or "size" not in r["unguarded"][0]:
        fails.append("a surface with no size guard should flag the DoS gap")
    no_accept = '<input type="file"><script>if (file.size > 5*1024*1024) {}</script>'
    r = scan_text(no_accept)
    if not r["unguarded"] or "accept" not in r["unguarded"][0]:
        fails.append("a surface with no accept= should flag the type gap")
    if scan_text("<p>no file input here</p>")["surfaces"] != 0:
        fails.append("a page with no file input should report 0 surfaces")
    # a Map.size comparison must NOT count as a file-size guard (the false-guarded case)
    mapsize = '<input type="file" accept="image/*"><script>if (reg.size >= max) poll();</script>'
    r = scan_text(mapsize)
    if not r["unguarded"]:
        fails.append("a Map.size comparison must NOT be mistaken for a file.size guard")
    if fails:
        print("✗ validate_file_upload_safety selftest FAILED:")
        for f in fails:
            print("   - " + f)
        return 1
    print("✓ validate_file_upload_safety selftest passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
