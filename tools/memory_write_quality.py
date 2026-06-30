#!/usr/bin/env python3
"""memory_write_quality.py - Memory-System M3.1: write-quality gate for memory topic files.
================================================================================
The Memento indexer derives a chunk's TYPE (which sets its importance + recency half-life,
i.e. how it ranks) from frontmatter `metadata.type` first, then a filename-prefix fallback.
A curated topic file that has NEITHER a valid type NOR a known prefix silently falls to
`type='unknown'` -> importance 1, 14-day decay -> it ranks near the bottom forever and the
lesson is effectively lost. Empty `name`/`description` similarly starve the FTS/title signal.
None of this errors at write time; it just quietly degrades recall.

This is the WRITE-SIDE (WAT-deterministic) gate that prevents bad memories at the source. It
**imports the real indexer** (`memento_indexer.parse_frontmatter` + `detect_type`) so the lint
can never drift from how files are actually indexed — it asserts on the genuine outcome.

Scope: curated topic files = `*.md` in the auto-memory dir, EXCLUDING the auto-generated/agent
files (MEMORY.md index, handoff_*, *.bak*). Transcripts are `.jsonl` (already excluded).

Checks (ERR = gate-failing, WARN = reported):
  ERR  type_unknown        detect_type() == 'unknown' (the silent-degradation case)
  ERR  missing_name        no non-empty `name:`
  ERR  missing_description no non-empty `description:`
  ERR  index_line_too_long a MEMORY.md index line exceeds the 200-char loader line cap
  WARN missing_explicit_type  indexed only via filename prefix (no `metadata.type`) - brittle
  WARN name_stem_mismatch  `name:` != filename stem (the slug convention)
  WARN prefix_type_mismatch  filename prefix disagrees with the declared/detected type
  WARN index_dup_link      MEMORY.md links the same topic file more than once

  --self-test  prove teeth: a malformed (typeless) temp file FAILS, a well-formed one PASSES.

Exit 0 = all curated files index with a valid type + required fields; 1 = an ERR (or toothless
self-test). Stdlib only; reads the memory dir; writes nothing.
"""
from __future__ import annotations

import io
import re
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MEMENTO_TOOLS = Path.home() / ".claude-memento" / "tools"
sys.path.insert(0, str(MEMENTO_TOOLS))
try:
    import memento_indexer as mi  # noqa: E402  (the REAL frontmatter + type logic)
except Exception as e:  # pragma: no cover
    print(f"  SKIP — memento indexer not importable ({type(e).__name__}: {e})")
    sys.exit(0)

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# Valid types for a hand-written curated topic file (the 4 the memory schema allows).
CURATED_TYPES = ("user", "feedback", "project", "reference")
PREFIXES = ("user_", "feedback_", "project_", "reference_")
LINE_CAP = 200  # MEMORY.md loader line-truncation point (matches compact_memory_index.py)


def _find_memory_md_dir() -> Path | None:
    root = Path.home() / ".claude" / "projects"
    if not root.exists():
        return None
    best = None
    for idx in root.glob("*/memory/MEMORY.md"):
        try:
            mt = idx.stat().st_mtime
        except OSError:
            continue
        if best is None or mt > best[0]:
            best = (mt, idx.parent)
    return best[1] if best else None


def _is_curated(fp: Path) -> bool:
    n = fp.name.lower()
    if n == "memory.md" or n.startswith("handoff_") or n.startswith("handoff-"):
        return False
    if ".bak" in n or n.startswith("transcript_") or n.startswith("session_"):
        return False
    return fp.suffix.lower() == ".md"


def lint_file(fp: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one curated topic file."""
    errs: list[str] = []
    warns: list[str] = []
    try:
        raw = fp.read_text(encoding="utf-8")
    except Exception as e:
        return [f"unreadable ({type(e).__name__})"], []

    meta, _ = mi.parse_frontmatter(raw)
    detected = mi.detect_type(meta, fp.name)

    # ERR: the silent-degradation case — would index as 'unknown'
    if detected == "unknown":
        errs.append("type_unknown")

    # required fields
    name = str(meta.get("name") or "").strip()
    desc = str(meta.get("description") or "").strip()
    if not name:
        errs.append("missing_name")
    if not desc:
        errs.append("missing_description")

    # explicit type present in frontmatter?
    md = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    explicit_type = str(md.get("type") or meta.get("type") or "").strip().lower()
    if not explicit_type:
        warns.append("missing_explicit_type")
    elif explicit_type not in CURATED_TYPES and detected in CURATED_TYPES:
        warns.append(f"noncurated_type:{explicit_type}")

    # name should equal the filename stem (the slug convention)
    if name and name != fp.stem:
        warns.append("name_stem_mismatch")

    # filename prefix must agree with the type. `reference_url_`/`url_` is a special
    # cached_web prefix (matches detect_type), so exempt it from the reference check.
    nl = fp.name.lower()
    eff_type = explicit_type or detected
    if not (nl.startswith("reference_url_") or nl.startswith("url_")):
        fpref = next((p.rstrip("_") for p in PREFIXES if nl.startswith(p)), "")
        if fpref and eff_type and fpref != eff_type:
            warns.append(f"prefix_type_mismatch:{fpref}!={eff_type}")

    return errs, warns


def lint_index(mem_dir: Path) -> tuple[list[str], list[str]]:
    """Check the MEMORY.md index: line length cap + duplicate links."""
    errs: list[str] = []
    warns: list[str] = []
    idx = mem_dir / "MEMORY.md"
    if not idx.exists():
        return errs, warns
    link_re = re.compile(r"^- \[.*?\]\(([^)]+)\)")
    seen: dict[str, int] = {}
    for ln in idx.read_text(encoding="utf-8").splitlines():
        if len(ln) > LINE_CAP:
            errs.append(f"index_line_too_long:{len(ln)}>{LINE_CAP}: {ln[:48]}...")
        m = link_re.match(ln)
        if m:
            tgt = m.group(1)
            seen[tgt] = seen.get(tgt, 0) + 1
    for tgt, c in seen.items():
        if c > 1:
            warns.append(f"index_dup_link:{tgt}(x{c})")
    return errs, warns


def run(mem_dir: Path, verbose: bool = True) -> tuple[int, int, int]:
    """Returns (n_files, n_err_files, n_warn). Prints per-file ERR/WARN."""
    files = sorted(p for p in mem_dir.glob("*.md") if _is_curated(p))
    n_err_files = 0
    n_warn = 0
    for fp in files:
        errs, warns = lint_file(fp)
        n_warn += len(warns)
        if errs:
            n_err_files += 1
            print(f"  {R}ERR{X}  {fp.name}: {', '.join(errs)}")
        elif warns and verbose:
            print(f"  {Y}warn{X} {fp.name}: {', '.join(warns)}")
    ie, iw = lint_index(mem_dir)
    for e in ie:
        n_err_files += 1
        print(f"  {R}ERR{X}  MEMORY.md: {e}")
    for w in iw:
        n_warn += 1
        if verbose:
            print(f"  {Y}warn{X} MEMORY.md: {w}")
    return len(files), n_err_files, n_warn


def do_self_test() -> int:
    """Teeth: a typeless/nameless temp file must FAIL; a well-formed one must PASS."""
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        bad = td / "notes-on-stuff.md"   # no known prefix, no type -> would index 'unknown'
        bad.write_text("---\ndescription: a note\n---\nsome content\n", encoding="utf-8")
        good = td / "feedback_well_formed_example.md"
        good.write_text("---\nname: feedback_well_formed_example\n"
                        "description: a properly typed lesson\nmetadata:\n  type: feedback\n---\nbody\n",
                        encoding="utf-8")
        be, _ = lint_file(bad)
        ge, gw = lint_file(good)
        bad_caught = "type_unknown" in be and "missing_name" in be
        good_clean = not ge
        print(f"  malformed file -> errors {be}  ({'CAUGHT' if bad_caught else 'MISSED'})")
        print(f"  well-formed file -> errors {ge or 'none'}  ({'CLEAN' if good_clean else 'FALSE-POSITIVE'})")
        if bad_caught and good_clean:
            print(f"  {G}TEETH VERIFIED{X} typeless file FAILs, well-formed file PASSes.")
            return 0
        print(f"  {R}TOOTHLESS{X}")
        return 1


def main() -> int:
    print(f"{B}Memory-System M3.1 - topic-file write-quality lint{X}")
    print("=" * 62)
    argv = sys.argv[1:]
    if "--self-test" in argv:
        rc = do_self_test()
        print(f"\n{(G if rc == 0 else R)}{B}  WRITE-QUALITY SELFTEST: {'PASS' if rc == 0 else 'FAIL'}{X}")
        return rc

    mem_dir = _find_memory_md_dir()
    if mem_dir is None:
        print(f"  {Y}SKIP{X} no auto-memory dir found")
        return 0
    verbose = "--quiet" not in argv
    n, n_err, n_warn = run(mem_dir, verbose=verbose)
    print(f"\n  {n} curated topic files · {n_err} with ERR · {n_warn} warnings  (dir: {mem_dir.name})")
    if n_err:
        print(f"\n{R}{B}  WRITE-QUALITY: FAIL{X} - {n_err} file(s) would index malformed (type_unknown / "
              f"missing field / over-long index line).")
        return 1
    print(f"\n{G}{B}  WRITE-QUALITY: PASS{X} - every curated topic file indexes with a valid type + "
          f"required fields.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
