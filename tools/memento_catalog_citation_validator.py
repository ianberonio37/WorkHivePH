#!/usr/bin/env python3
"""
memento_catalog_citation_validator.py — guard `reference_pattern_catalog.md`
against citation rot. P16 of the Memento build (2026-06-06).

Why this exists
---------------
P13 shipped a pattern catalog ("do it like marketplace.html", "shared/envelope.ts
for return shape") that points to canonical files. The catalog is doctrine — but
files get renamed, deleted, and moved without anyone updating the catalog. Stale
citations silently become wrong answers.

What it checks
--------------
Parses ALL file-reference shapes in `reference_pattern_catalog.md`:
  1. Markdown links     — `[text](path)` where path ends with an indexable extension
  2. Backticked refs    — `` `marketplace.html` ``, `` `_shared/envelope.ts` ``,
                          `` `tools/foo.py` ``, `` `tests/x.spec.ts` ``
  3. Backticked dotted paths — `supabase/migrations/<ts>_<name>.sql` form

Resolves each reference against:
  - The project repo (path relative to the catalog's repo root)
  - The Memento memory dir (path relative to where the catalog lives)
  - Fallback: bare filename anywhere in the indexed corpus (via DB)

Exit codes
----------
  0 — every citation resolves
  1 — one or more citations are stale (printed to stdout with the line they're on)
  2 — the catalog file itself is missing

This is a STANDALONE tool. It does not touch the DB schema. It does query the
DB read-only to do the "bare filename anywhere in the corpus" fallback so that
a catalog ref to `envelope.ts` resolves whether it's at
`supabase/functions/_shared/envelope.ts` or moved one folder over.

Wire into platform G0 via `tools/run_platform_checks.py`'s validator registry
to make rot a failing gate. Until then it's a manual run:
  python tools/memento_catalog_citation_validator.py
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# Extensions that look like real source citations (filters out e.g. `RAISE`,
# table names, log messages that happen to appear in backticks).
CITATION_EXTS = {
    ".html", ".ts", ".tsx", ".js", ".jsx", ".py", ".sql", ".md", ".json",
}

# Markdown link form: [display text](filesystem path)
MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")

# Backticked code spans. We match generously; the extension filter rejects
# non-files. Forbids whitespace inside (file paths shouldn't have it).
BACKTICK_RE = re.compile(r"`([^`\n]+)`")

# Things we should NEVER count as citations even if they pass the extension
# filter (placeholders, URLs, type annotations).
SKIP_PATHS = frozenset({
    "path", "filename", "name", "file.ts", "file.js", "file.html",
    "your-fn-name", "<fn-name>", "<name>", "X.html", "x.ts",
})


def _looks_like_file_ref(s: str) -> bool:
    """True if `s` plausibly names a file we can find on disk."""
    s = s.strip().rstrip(",;:)")
    if not s or s in SKIP_PATHS:
        return False
    if s.startswith(("http://", "https://", "mailto:", "#")):
        return False
    # Must have a file extension we care about
    for ext in CITATION_EXTS:
        if s.lower().endswith(ext):
            return True
    return False


def extract_citations(catalog_path: Path) -> list[tuple[int, str, str]]:
    """Parse all file-like references. Returns
    [(line_number, raw_ref, shape), ...]
    where shape ∈ {'md-link', 'backtick'}."""
    if not catalog_path.exists():
        return []
    lines = catalog_path.read_text(encoding="utf-8", errors="replace").splitlines()
    found: list[tuple[int, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for lineno, line in enumerate(lines, start=1):
        # Markdown links first — they're more specific than backticks
        for m in MD_LINK_RE.finditer(line):
            path = m.group(2).strip()
            if _looks_like_file_ref(path):
                key = ("md-link", path)
                if key not in seen:
                    seen.add(key)
                    found.append((lineno, path, "md-link"))
        # Then backticks — but skip anything that was already inside a markdown
        # link target on the same line, to avoid double-counting.
        link_targets = {m.group(2) for m in MD_LINK_RE.finditer(line)}
        for m in BACKTICK_RE.finditer(line):
            tok = m.group(1).strip()
            if tok in link_targets:
                continue
            if _looks_like_file_ref(tok):
                key = ("backtick", tok)
                if key not in seen:
                    seen.add(key)
                    found.append((lineno, tok, "backtick"))
    return found


# Memento's indexer prefixes source_name by type (e.g. `migration_<file>.sql`,
# `shared_<file>.ts`, `page_<file>.html`). Catalogs occasionally cite that form
# instead of the on-disk path — those citations are still useful because they
# match exactly what retrieval surfaces. Treat them as valid when the
# un-prefixed name resolves under the known type-to-subdir mapping.
_SOURCE_NAME_PREFIXES = {
    "migration_": "supabase/migrations",
    "shared_":    "supabase/functions/_shared",
    "edge_fn_":   "supabase/functions",   # actual path is <name>/index.ts
    "page_":      ".",
    "js_":        ".",
    "spec_":      "tests",
    "pytool_":    "tools",
    "doctrine_":  ".",
    "skill_":     None,  # lives outside the repo (~/.claude/skills)
}


def _try_paths(rel: str, anchors: list[Path]) -> Path | None:
    """Try `rel` relative to each anchor; return the first that exists.
    Also tries Memento source_name prefix translations (e.g.
    `migration_X.sql` → `supabase/migrations/X.sql`)."""
    rel_path = Path(rel)
    candidates: list[str] = [rel]
    # Source-name-prefix translation
    bare = Path(rel).name
    for prefix, subdir in _SOURCE_NAME_PREFIXES.items():
        if bare.startswith(prefix) and subdir is not None:
            unprefixed = bare[len(prefix):]
            candidates.append(f"{subdir}/{unprefixed}")
            # edge_fn_<name>.ts → supabase/functions/<name>/index.ts
            if prefix == "edge_fn_" and unprefixed.endswith(".ts"):
                fn_name = unprefixed[:-3]
                candidates.append(f"{subdir}/{fn_name}/index.ts")
    for c in candidates:
        c_path = Path(c)
        for a in anchors:
            candidate = (a / c_path).resolve()
            try:
                if candidate.exists():
                    return candidate
            except OSError:
                continue
    return None


def _db_has_basename(db_path: Path, basename: str) -> bool:
    """Last-resort fallback: does ANY indexed chunk have a source_path whose
    file name matches `basename`? Catches files that moved but still exist."""
    if not db_path.exists():
        return False
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM chunks WHERE source_path LIKE ? LIMIT 1",
                (f"%{basename}",),
            )
            return cur.fetchone() is not None
    except sqlite3.Error:
        return False


def resolve(rel: str, catalog_dir: Path, repo_root: Path,
            db_path: Path) -> tuple[bool, str]:
    """Returns (resolved, location_or_reason).
    Location is either an absolute path str or 'db:<basename>' for the
    DB-fallback hit. Reason on miss is a short label."""
    anchors = [repo_root, catalog_dir]
    hit = _try_paths(rel, anchors)
    if hit is not None:
        return True, str(hit)
    # DB fallback — match by bare basename
    basename = Path(rel).name
    if _db_has_basename(db_path, basename):
        return True, f"db:{basename}"
    return False, "not found on disk or in index"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Validate citations in reference_pattern_catalog.md"
    )
    p.add_argument(
        "--catalog",
        help="path to reference_pattern_catalog.md "
             "(default: autodetect from Memento memory dir)",
    )
    p.add_argument(
        "--repo-root",
        default=str(Path.cwd().resolve()),
        help="anchor for repo-relative paths like 'tests/_fixtures.ts' "
             "(default: cwd)",
    )
    p.add_argument(
        "--db",
        default=str((Path.home() / ".claude-memento" / "memory.db").resolve()),
        help="Memento DB path for the basename-fallback (default: "
             "~/.claude-memento/memory.db)",
    )
    p.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of human-readable text",
    )
    args = p.parse_args()

    # Find the catalog
    if args.catalog:
        catalog_path = Path(args.catalog).resolve()
    else:
        # Walk memory dir candidates under ~/.claude/projects/
        catalog_path = None
        for proj in (Path.home() / ".claude" / "projects").glob("*/memory"):
            cand = proj / "reference_pattern_catalog.md"
            if cand.exists():
                catalog_path = cand
                break
        if catalog_path is None:
            print("FAIL  reference_pattern_catalog.md not found "
                  "(pass --catalog explicitly)", file=sys.stderr)
            return 2

    if not catalog_path.exists():
        print(f"FAIL  catalog not found: {catalog_path}", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    catalog_dir = catalog_path.parent.resolve()
    db_path = Path(args.db).resolve()

    cites = extract_citations(catalog_path)
    if not cites:
        print("OK  no file-like citations found in catalog (nothing to verify)")
        return 0

    results: list[dict] = []
    for lineno, ref, shape in cites:
        ok, loc = resolve(ref, catalog_dir, repo_root, db_path)
        results.append({
            "line": lineno, "ref": ref, "shape": shape,
            "ok": ok, "location": loc,
        })

    rot = [r for r in results if not r["ok"]]
    db_hits = [r for r in results if r["ok"] and r["location"].startswith("db:")]
    direct = [r for r in results if r["ok"] and not r["location"].startswith("db:")]

    if args.json:
        import json
        print(json.dumps({
            "catalog": str(catalog_path),
            "total": len(results),
            "direct": len(direct),
            "db_fallback": len(db_hits),
            "rot": len(rot),
            "results": results,
        }, indent=2))
        return 1 if rot else 0

    print(f"Catalog: {catalog_path}")
    print(f"  Total file-like citations : {len(results)}")
    print(f"  Resolved on disk          : {len(direct)}")
    print(f"  Resolved via DB fallback  : {len(db_hits)}  "
          f"(file moved — catalog still works via index)")
    print(f"  ROT (citations don't resolve): {len(rot)}")
    if db_hits:
        print()
        print("  DB-fallback hits (consider updating catalog to the new path):")
        for r in db_hits[:20]:
            print(f"    line {r['line']:>4}  {r['shape']:<10}  {r['ref']}")
    if rot:
        print()
        print("  ROT — these citations point at files that no longer exist:")
        for r in rot:
            print(f"    line {r['line']:>4}  {r['shape']:<10}  {r['ref']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
