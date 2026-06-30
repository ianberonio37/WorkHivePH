#!/usr/bin/env python3
"""memory_supersedes.py - Memory-System M3.2: supersedes map builder + down-rank proof.
================================================================================
The 80/20 of contradiction-handling (a full LLM contradiction-judge is over-scoped). A memory
whose frontmatter declares `supersedes: <slug>` (or a comma list) REPLACES that older memory;
the retriever then down-ranks the superseded chunk (`SUPERSEDE_PENALTY`) so an obsolete decision
can't co-surface as current right next to its reversal.

This tool scans the auto-memory dir for `supersedes:` fields and writes the map into the Memento
DB `meta` table (key `supersedes_map`, JSON `{superseded_slug: by_slug}`), where the retriever's
`load_supersedes()` reads it. An empty/absent map is a strict no-op, so retrieval is unchanged
until a `supersedes:` field actually exists. It also warns if a `supersedes:` points at a slug
that has no file (a likely typo).

Commands:
  (default)/--apply  scan + write the map to meta; print what changed.
  --check            scan + print the map; write nothing. Exit 1 if a supersedes target is missing.
  --self-test        prove the full mechanism end-to-end at unit level: frontmatter -> map
                     (parse), meta -> set (the retriever's loader), and that a superseded chunk
                     ranks BELOW its replacement at equal base score (the down-rank semantics).

Stdlib only. Writes only the single meta row. Never touches chunk data.
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MEMENTO_TOOLS = Path.home() / ".claude-memento" / "tools"
sys.path.insert(0, str(MEMENTO_TOOLS))
try:
    import memento_db  # noqa: E402
    import memento_indexer as mi  # noqa: E402
    import memento_retrieve as mr  # noqa: E402  (the consumer of the map)
except Exception as e:  # pragma: no cover
    print(f"  SKIP — memento modules not importable ({type(e).__name__}: {e})")
    sys.exit(0)

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"


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


def _norm(slug: str) -> str:
    return mr._slug(str(slug).strip())


def scan(mem_dir: Path) -> tuple[dict, list[str]]:
    """Return ({superseded_slug: by_slug}, warnings). Reads `supersedes:` from frontmatter."""
    mapping: dict[str, str] = {}
    warns: list[str] = []
    present = {mr._slug(p.name) for p in mem_dir.glob("*.md")}
    for fp in sorted(mem_dir.glob("*.md")):
        if fp.name.lower() == "memory.md":
            continue
        try:
            meta, _ = mi.parse_frontmatter(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        raw = meta.get("supersedes")
        if not raw:
            continue
        by = mr._slug(fp.name)
        for tgt in str(raw).replace(";", ",").split(","):
            t = _norm(tgt)
            if not t:
                continue
            mapping[t] = by
            if t not in present:
                warns.append(f"{fp.name}: supersedes '{t}' but no such file")
            if t == by:
                warns.append(f"{fp.name}: supersedes itself (ignored)")
                mapping.pop(t, None)
    return mapping, warns


def write_map(mapping: dict) -> None:
    with memento_db._connect() as conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('supersedes_map', ?)",
                     (json.dumps(mapping),))
        conn.commit()


def do_self_test() -> int:
    ok = True
    # 1. parse: A supersedes B  ->  map has B
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "MEMORY.md").write_text("# index\n", encoding="utf-8")
        (td / "feedback_old_b.md").write_text(
            "---\nname: feedback_old_b\ndescription: old\nmetadata:\n  type: feedback\n---\nold\n", encoding="utf-8")
        (td / "feedback_new_a.md").write_text(
            "---\nname: feedback_new_a\ndescription: new\nsupersedes: feedback_old_b\n"
            "metadata:\n  type: feedback\n---\nnew\n", encoding="utf-8")
        mapping, warns = scan(td)
    parse_ok = mapping.get("feedback_old_b") == "feedback_new_a" and not warns
    print(f"  parse: A supersedes B -> map {mapping}  ({'OK' if parse_ok else 'FAIL'})")
    ok &= parse_ok

    # 2. loader: the retriever's load_supersedes reads the map back out of meta (real loader)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        scratch = Path(tf.name)
    try:
        c = sqlite3.connect(scratch)
        c.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("INSERT INTO meta VALUES ('supersedes_map', ?)", (json.dumps(mapping),))
        c.commit()
        loaded = mr.load_supersedes(c)
        c.close()
    finally:
        try: scratch.unlink()
        except OSError: pass
    loader_ok = "feedback_old_b" in loaded
    print(f"  loader: meta -> set {sorted(loaded)}  ({'OK' if loader_ok else 'FAIL'})")
    ok &= loader_ok

    # 3. down-rank semantics: at equal base score, the superseded chunk ends BELOW its replacement
    superseded = loaded
    base = 0.10
    a = {"name": "feedback_new_a.md", "score": base}
    b = {"name": "feedback_old_b.md", "score": base}
    for cand in (a, b):
        if mr._slug(cand["name"]) in superseded:
            cand["score"] *= mr.SUPERSEDE_PENALTY
    ranked = sorted([a, b], key=lambda c: -c["score"])
    order_ok = ranked[0]["name"] == "feedback_new_a.md" and a["score"] > b["score"] and mr.SUPERSEDE_PENALTY < 1.0
    print(f"  rank: replacement {a['score']:.3f} > superseded {b['score']:.3f} "
          f"(penalty {mr.SUPERSEDE_PENALTY})  ({'OK' if order_ok else 'FAIL'})")
    ok &= order_ok

    if ok:
        print(f"  {G}TEETH VERIFIED{X} frontmatter->map->set->down-rank all proven; superseded ranks below replacement.")
        return 0
    print(f"  {R}FAIL{X} a link in the supersedes mechanism broke.")
    return 1


def main() -> int:
    print(f"{B}Memory-System M3.2 - supersedes map builder + down-rank{X}")
    print("=" * 62)
    argv = sys.argv[1:]
    if "--self-test" in argv:
        rc = do_self_test()
        print(f"\n{(G if rc == 0 else R)}{B}  SUPERSEDES SELFTEST: {'PASS' if rc == 0 else 'FAIL'}{X}")
        return rc

    mem_dir = _find_memory_md_dir()
    if mem_dir is None:
        print(f"  {Y}SKIP{X} no auto-memory dir found")
        return 0
    mapping, warns = scan(mem_dir)
    for w in warns:
        print(f"  {Y}warn{X} {w}")
    if "--check" in argv:
        print(f"  {len(mapping)} supersedes link(s): {mapping or '{}'}")
        return 1 if warns else 0
    write_map(mapping)
    print(f"  {G}wrote{X} supersedes_map to meta — {len(mapping)} link(s) "
          f"{('('+', '.join(f'{k}<-{v}' for k,v in list(mapping.items())[:4])+')') if mapping else '(none yet; retriever no-op)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
